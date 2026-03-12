"""
핵심 컨트롤러 모듈 - 전체 매크로 로직을 통합 관리하는 상태 머신 기반 컨트롤러.
사냥 루프, 알림 감시, 패턴 재생, 거탐 처리를 조율한다.

v2: 안티 감지 강화
- BehaviorDiversityEngine: 잡행동/채널변경/LCP대응
- HumanRhythm: 사람다운 키 입력 리듬
- ProcessGuard: NGS 프로세스 은닉
- 피로도 시뮬레이션: 시간에 따라 속도/실수율 변화
"""

from __future__ import annotations

import random
import threading
import time
import logging
from typing import Optional, Callable

from core.state import State, StateMachine
from core.config import Config
from core.timing import TimingEngine
from core.anti_detect import BehaviorDiversityEngine
from core.human_rhythm import HumanRhythm
from core.process_guard import ProcessGuard
from pattern.engine import PatternEngine
from screen.monitor import ScreenMonitor
from input.engine import InputEngine
from input.human_mouse import HumanLikeMouse
from solver.alert_handler import AlertHandler
from solver.text_captcha import TextCaptchaSolver
from solver.rune_solver import RuneSolver
from notify.notifier import Notifier

logger = logging.getLogger(__name__)


class CoreController:
    """
    매크로 핵심 컨트롤러.
    
    상태 머신 기반으로 동작하며, 두 개의 스레드를 운영한다:
    - 메인 사냥 루프: 패턴 재생 + 버프/메소 체크
    - 감시 스레드: 거탐/룬 등 긴급 이벤트 감지
    
    v2 개선 (안티 감지):
    - 사냥 사이클 중 잡행동(noise) 랜덤 삽입
    - 패턴 선택 시 LCP 유사도 감소를 위한 가중치 조정
    - 피로도에 따른 속도/실수 변화
    - 사이클 간 딜레이를 인간 리듬으로 생성
    - 채널 변경으로 단일 위치 장기 체류 방지
    """

    def __init__(self) -> None:
        """컨트롤러 초기화. 모든 하위 모듈을 생성한다."""
        self.config = Config()
        self.state_machine = StateMachine()
        self.timing = TimingEngine()
        
        # ── 안티 감지 모듈 (v2) ──
        self.behavior = BehaviorDiversityEngine()
        self.rhythm = HumanRhythm()
        self.process_guard = ProcessGuard()
        
        # 입력 엔진
        self.input_engine = InputEngine()
        self.human_mouse = HumanLikeMouse(self.input_engine)
        
        # 패턴 엔진
        pattern_path = self.config.get("pattern_path", "patterns")
        self.pattern_engine = PatternEngine(base_path=pattern_path)
        
        # 화면 감시
        game_region = self.config.get("game_region")
        self.screen_monitor = ScreenMonitor(game_region=game_region)
        
        # 거탐/룬 해결기
        self.text_solver = TextCaptchaSolver()
        self.rune_solver = RuneSolver()
        self.alert_handler = AlertHandler(
            screen_monitor=self.screen_monitor,
            input_engine=self.input_engine,
            text_solver=self.text_solver,
            rune_solver=self.rune_solver,
        )
        
        # 알림
        self.notifier = Notifier()
        
        # 스레드 관리
        self._running = False
        self._recording_active = False
        self._hunt_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 세션 관리
        self._session_start: float = 0.0
        self._session_limit_min: int = self.config.get("session_limit_min", 120)
        self._cycle_count: int = 0
        
        # 콜백 (GUI 연동용)
        self._on_state_change: Optional[Callable[[State], None]] = None
        self._on_log: Optional[Callable[[str], None]] = None
        self._on_pattern_count_change: Optional[Callable[[], None]] = None

    # ─── 콜백 등록 (GUI 연동) ───

    def set_on_state_change(self, callback: Callable[[State], None]) -> None:
        """상태 변경 시 호출할 콜백 등록."""
        self._on_state_change = callback

    def set_on_log(self, callback: Callable[[str], None]) -> None:
        """로그 메시지 발생 시 호출할 콜백 등록."""
        self._on_log = callback
        # 하위 모듈에도 로그 콜백 전달
        self.behavior.set_on_log(callback)

    def set_on_pattern_count_change(self, callback: Callable[[], None]) -> None:
        """패턴 수 변경 시 호출할 콜백 등록."""
        self._on_pattern_count_change = callback

    def _log(self, message: str) -> None:
        """내부 로그 메시지 발행."""
        logger.info(message)
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass

    def _change_state(self, new_state: State) -> None:
        """상태 전이 + 콜백 호출."""
        old_state = self.state_machine.current
        self.state_machine.transition(new_state)
        self._log(f"상태 변경: {old_state.value} → {new_state.value}")
        if self._on_state_change:
            try:
                self._on_state_change(new_state)
            except Exception:
                pass

    # ─── 시작/정지/일시정지 ───

    def start(self) -> None:
        """매크로 시작. 사냥 루프와 감시 스레드를 생성한다."""
        if self._running:
            self._log("이미 실행 중입니다.")
            return
        
        # 환경 검사 (v2)
        warnings = self.process_guard.check_environment()
        for w in warnings:
            self._log(f"[경고] {w}")
        
        self._running = True
        self._session_start = time.time()
        self._cycle_count = 0
        
        # 안티 감지 모듈 세션 리셋 (v2)
        self.behavior.reset_session()
        self.rhythm.reset_session()
        self.input_engine.reset_session()  # v2: 입력 지문 리셋
        
        self._change_state(State.HUNTING)
        
        # 사냥 스레드
        self._hunt_thread = threading.Thread(
            target=self._hunt_loop, daemon=True, name="HuntLoop"
        )
        self._hunt_thread.start()
        
        # 감시 스레드
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="MonitorLoop"
        )
        self._monitor_thread.start()
        
        self._log("매크로 시작됨 (안티감지 v2 활성)")

    def stop(self) -> None:
        """매크로 정지."""
        self._running = False
        self._change_state(State.IDLE)
        self.input_engine.release_all()
        
        # 통계 출력 (v2)
        stats = self.behavior.get_stats()
        self._log(
            f"세션 종료 | 사이클: {self._cycle_count} | "
            f"잡행동: {stats['noise_count']}회 | "
            f"채널변경: {stats['channel_changes']}회"
        )
        
        # 리듬 자연스러움 자가진단 (v2)
        cv = self.rhythm.get_delay_variance()
        if cv >= 0:
            natural = "정상" if cv >= 0.2 else "위험(너무 규칙적)"
            self._log(f"리듬 변동계수: {cv:.3f} ({natural})")
        
        # v2: 입력 지문 통계
        fp = self.input_engine.get_fingerprint_stats()
        self._log(
            f"입력 지문 | hold_cv: {fp['hold_cv']} ({fp['hold_status']}) | "
            f"delay_cv: {fp['delay_cv']} ({fp['delay_status']}) | "
            f"samples: {fp['samples']}"
        )
        
        self._log("매크로 정지됨")

    def toggle_pause(self) -> None:
        """일시정지 토글."""
        current = self.state_machine.current
        if current == State.PAUSED:
            self._change_state(State.HUNTING)
            self._log("재개됨")
        elif current == State.HUNTING:
            self._change_state(State.PAUSED)
            self._log("일시정지됨")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_state(self) -> State:
        return self.state_machine.current

    # ─── 패턴 녹화 (GUI에서 호출) ───

    def start_recording(self, category: str) -> None:
        """지정 카테고리로 패턴 녹화를 시작한다."""
        self._recording_active = True
        self._log(f"패턴 녹화 시작: {category} (F9로 중지)")
        threading.Thread(
            target=self._record_pattern,
            args=(category,),
            daemon=True,
            name="PatternRecord"
        ).start()

    def stop_recording(self) -> None:
        """패턴 녹화를 중지한다."""
        self._recording_active = False

    def _record_pattern(self, category: str) -> None:
        """실제 녹화 실행 (별도 스레드)."""
        try:
            events = self.pattern_engine.record(
                category=category,
                on_stop_check=lambda: not self._recording_active,
            )
            if events:
                self._log(f"패턴 저장 완료: {category} ({len(events)}개 이벤트)")
                if self._on_pattern_count_change:
                    self._on_pattern_count_change()
            else:
                self._log("녹화 취소됨 (이벤트 없음)")
        except Exception as e:
            self._log(f"녹화 오류: {e}")

    # ─── 사냥 루프 (v2: 안티 감지 통합) ───

    def _hunt_loop(self) -> None:
        """
        메인 사냥 루프 (v2).
        
        개선점:
        - 잡행동(noise) 랜덤 삽입으로 행동 다양성 확보
        - LCP 대응 가중치로 패턴 시퀀스 비반복화
        - 인간 리듬 기반 사이클 딜레이
        - 피로도에 따른 속도 변화
        - 패턴 사이 미세 이동 삽입
        - 채널 변경으로 위치 다양성
        """
        self._log("사냥 루프 시작 (안티감지 v2)")
        
        while self._running:
            try:
                # ── 세션 시간 초과 체크 ──
                elapsed_min = (time.time() - self._session_start) / 60
                if elapsed_min >= self._session_limit_min:
                    self._log(f"세션 시간 초과 ({self._session_limit_min}분). 자동 정지.")
                    self.notifier.notify("세션 시간 초과! 매크로를 정지합니다.")
                    self.stop()
                    break
                
                # ── 상태별 분기 ──
                state = self.state_machine.current
                
                if state == State.PAUSED:
                    time.sleep(0.5)
                    continue
                
                if state == State.MANUAL_MODE:
                    time.sleep(0.5)
                    continue
                
                if state in (State.ALERT_SOLVING, State.RUNE_SOLVING):
                    time.sleep(0.3)
                    continue
                
                if state != State.HUNTING:
                    time.sleep(0.2)
                    continue
                
                # ── 피로도 업데이트 (v2) ──
                self.behavior.update_fatigue()
                
                # ══════════════════════════════════
                # ▼ 잡행동 삽입 체크 (v2) ▼
                # ══════════════════════════════════
                if self.behavior.should_insert_noise():
                    self._log("[안티감지] 잡행동 삽입")
                    self.behavior.execute_noise(self.input_engine)
                    continue  # 잡행동 후 다음 사이클로
                
                # ══════════════════════════════════
                # ▼ 채널 변경 체크 (v2) ▼
                # ══════════════════════════════════
                if self.behavior.should_change_channel():
                    self._log("[안티감지] 채널 변경 시간")
                    self.behavior.execute_channel_change(self.input_engine)
                    continue
                
                # ── 사냥 실행 ──
                
                # 1. 버프 체크
                buff_result = self.screen_monitor.find_template("buff_expired")
                if buff_result and buff_result.found:
                    self._change_state(State.BUFFING)
                    self._log("버프 만료 감지 → 버프 패턴 실행")
                    self.pattern_engine.play_random(
                        "buff", stop_check=self._should_stop_pattern
                    )
                    self._change_state(State.HUNTING)
                    continue
                
                # 2. 메소 줍기 체크
                meso_result = self.screen_monitor.find_template("meso_drop")
                if meso_result and meso_result.found:
                    self.pattern_engine.play_random(
                        "meso", stop_check=self._should_stop_pattern
                    )
                    continue
                
                # 3. 포션 체크
                potion_result = self.screen_monitor.find_template("potion_needed")
                if potion_result and potion_result.found:
                    self.pattern_engine.play_random(
                        "potion", stop_check=self._should_stop_pattern
                    )
                    continue
                
                # ══════════════════════════════════
                # ▼ 4. 사냥 루틴 (v2: LCP 대응) ▼
                # ══════════════════════════════════
                weights_cfg = self.config.get("hunt_weights", {
                    "routine": 0.5, "skillA": 0.25, "skillB": 0.25
                })
                
                # v2: LCP 대응 가중치 조정
                adjusted_weights = self.behavior.get_anti_lcp_weights(weights_cfg)
                
                categories = list(adjusted_weights.keys())
                weights = list(adjusted_weights.values())
                
                # 패턴이 있는 카테고리만 필터링
                available = []
                available_weights = []
                for cat, w in zip(categories, weights):
                    if self.pattern_engine.get_pattern_count(cat) > 0:
                        available.append(cat)
                        available_weights.append(w)
                
                if available:
                    selected = random.choices(available, weights=available_weights, k=1)[0]
                    
                    # v2: 패턴 사용 기록 (LCP 히스토리)
                    self.behavior.record_pattern_used(selected)
                    
                    # v2: 패턴 사이 미세 이동 삽입 (15~25% 확률)
                    if self.behavior.should_insert_movement_noise():
                        direction, hold_ms = self.behavior.get_movement_noise()
                        self.input_engine.press_key(direction, hold_ms=hold_ms)
                        time.sleep(random.uniform(0.05, 0.15))
                    
                    # v2: 인간 리듬 기반 속도 팩터
                    speed = self.rhythm.get_replay_speed_factor()
                    
                    # v2: 피로도 반영
                    fatigue = self.behavior.get_fatigue_speed_factor()
                    final_speed = speed * fatigue
                    
                    self.pattern_engine.play_random(
                        selected, stop_check=self._should_stop_pattern
                    )
                    
                    self._cycle_count += 1
                    
                    # v2: 실수 시뮬레이션 (확률적)
                    if self.rhythm.should_make_mistake():
                        mistake = self.rhythm.get_mistake_action()
                        self._execute_mistake(mistake)
                    
                else:
                    self._log("사용 가능한 패턴 없음. 대기 중...")
                    time.sleep(2.0)
                
                # ══════════════════════════════════
                # ▼ 사이클 간 딜레이 (v2: 인간 리듬) ▼
                # ══════════════════════════════════
                cycle_delay = self.rhythm.get_cycle_delay_sec()
                session_mod = self.behavior.get_session_delay_modifier()
                actual_delay = cycle_delay * session_mod
                time.sleep(actual_delay)
                
                # 지터 삽입
                self.timing.insert_jitter_if_needed()
                
            except Exception as e:
                self._log(f"사냥 루프 오류: {e}")
                time.sleep(1.0)
        
        self._log("사냥 루프 종료")

    # ─── 실수 실행 (v2) ───

    def _execute_mistake(self, mistake: dict) -> None:
        """실수 행동을 실행한다."""
        try:
            mtype = mistake.get("type", "")
            
            if mtype == "wrong_key":
                # 잘못된 키를 살짝 누르고 바로 뗌
                key = mistake.get("key", "q")
                hold = mistake.get("hold_ms", 25)
                self.input_engine.press_key(key, hold_ms=hold)
                self._log(f"[리듬] 실수: 잘못된 키 '{key}' 터치")
                
            elif mtype == "double_tap":
                # 같은 키 연타 실수
                count = mistake.get("count", 2)
                if self.behavior._pattern_history:
                    # 아무 일반 키 연타
                    for _ in range(count):
                        self.input_engine.press_key("lalt", hold_ms=random.uniform(20, 40))
                        time.sleep(random.uniform(0.03, 0.08))
                self._log(f"[리듬] 실수: 연타 {count}회")
                
            elif mtype == "stuck_key":
                # 키가 살짝 더 눌림
                extra = mistake.get("extra_ms", 200)
                time.sleep(extra / 1000.0)
                self._log(f"[리듬] 실수: 키 홀드 +{extra:.0f}ms")
                
        except Exception:
            pass  # 실수 실행 실패는 무시

    # ─── 감시 루프 ───

    def _monitor_loop(self) -> None:
        """
        화면 감시 루프 (별도 스레드).
        프레임 diff로 거탐 팝업 감지, 우선순위: 거탐 > 룬 > 일반.
        """
        self._log("감시 루프 시작")
        
        while self._running:
            try:
                state = self.state_machine.current
                
                if state in (State.PAUSED, State.MANUAL_MODE, State.IDLE):
                    time.sleep(0.5)
                    continue
                
                # 거탐 감지 (프레임 diff)
                changes = self.screen_monitor.detect_screen_change(
                    threshold=20, min_area=2000
                )
                
                if changes:
                    alert_type = self._classify_alert(changes)
                    if alert_type:
                        self._handle_alert(alert_type)
                
                # 룬 감지
                rune_result = self.screen_monitor.find_template("rune_indicator")
                if rune_result and rune_result.found:
                    self._handle_rune()
                
                # v2: 감시 주기도 인간 리듬으로 랜덤화
                time.sleep(random.uniform(0.4, 1.2))
                
            except Exception as e:
                self._log(f"감시 루프 오류: {e}")
                time.sleep(1.0)
        
        self._log("감시 루프 종료")

    # ─── 거탐 처리 ───

    def _classify_alert(self, changes: list) -> Optional[str]:
        """화면 변화를 기반으로 거짓말 탐지기 유형을 분류한다."""
        if not changes:
            return None
        
        largest = max(changes, key=lambda c: c.get("area", 0))
        area = largest.get("area", 0)
        
        if area > 50000:
            return "violetta"
        elif area > 10000:
            return "text_captcha"
        elif area > 3000:
            return "click_5"
        
        return None

    def _handle_alert(self, alert_type: str) -> None:
        """거탐 유형에 따라 처리한다."""
        auto_solve_list = self.config.get("alerts", {}).get("auto_solve", [])
        manual_list = self.config.get("alerts", {}).get("manual_only", [])
        
        self._log(f"거짓말 탐지기 감지: {alert_type}")
        
        if alert_type in manual_list:
            self._change_state(State.MANUAL_MODE)
            self.notifier.notify(f"⚠️ {alert_type} 감지! 수동 해결이 필요합니다!")
            self._log(f"{alert_type}: 수동 해결 필요 → 알림 전송")
            return
        
        if alert_type in auto_solve_list:
            prev_state = self.state_machine.current
            self._change_state(State.ALERT_SOLVING)
            
            # v2: 거탐 반응 전 사람다운 딜레이
            reaction_delay = random.uniform(0.5, 2.0)
            time.sleep(reaction_delay)
            
            success = False
            try:
                if alert_type == "text_captcha":
                    success = self.alert_handler.handle_text_captcha()
                elif alert_type in ("click_5", "click_2"):
                    success = self.alert_handler.handle_click_detector()
                elif alert_type == "rune":
                    success = self.alert_handler.handle_rune()
            except Exception as e:
                self._log(f"거탐 해결 오류: {e}")
            
            if success:
                self._log(f"{alert_type} 자동 해결 성공")
                # v2: 해결 후 사람다운 잠깐 멈춤 (안도감)
                time.sleep(random.uniform(0.5, 1.5))
                self._change_state(prev_state)
            else:
                self._log(f"{alert_type} 자동 해결 실패 → 수동 모드 전환")
                self.notifier.notify(f"거탐 자동 해결 실패: {alert_type}")
                self._change_state(State.MANUAL_MODE)
        else:
            self.notifier.notify(f"알 수 없는 거탐 유형: {alert_type}")

    def _handle_rune(self) -> None:
        """룬을 감지하고 자동 해결을 시도한다."""
        prev_state = self.state_machine.current
        self._change_state(State.RUNE_SOLVING)
        self._log("룬 감지 → 해결 시도")
        
        try:
            # v2: 룬 감지 후 사람다운 반응 딜레이
            time.sleep(random.uniform(0.8, 2.5))
            
            if self.pattern_engine.get_pattern_count("move") > 0:
                self.pattern_engine.play_random(
                    "move", stop_check=self._should_stop_pattern
                )
            
            time.sleep(random.uniform(0.3, 0.8))
            
            # 룬 활성화
            self.input_engine.press_key("space")
            time.sleep(random.uniform(0.8, 1.5))
            
            # 화살표 감지 + 입력
            arrows = self.screen_monitor.detect_rune_arrows()
            if arrows:
                # v2: 화살표 사이에 인간 딜레이
                self.rune_solver.solve(arrows, self.input_engine)
                self._log(f"룬 해결 시도: {arrows}")
            else:
                self._log("룬 화살표 감지 실패")
                self.notifier.notify("룬 화살표 감지 실패! 수동 해결 필요")
            
        except Exception as e:
            self._log(f"룬 해결 오류: {e}")
        
        self._change_state(prev_state)

    # ─── 유틸리티 ───

    def _should_stop_pattern(self) -> bool:
        """패턴 재생 중단 조건을 반환한다."""
        if not self._running:
            return True
        state = self.state_machine.current
        return state in (State.ALERT_SOLVING, State.MANUAL_MODE, State.IDLE)

    def get_session_elapsed_min(self) -> float:
        """현재 세션 경과 시간 (분)을 반환한다."""
        if self._session_start <= 0:
            return 0.0
        return (time.time() - self._session_start) / 60

    def get_cycle_count(self) -> int:
        """현재 세션의 사이클 수를 반환한다."""
        return self._cycle_count
