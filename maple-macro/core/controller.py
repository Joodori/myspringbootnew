"""
핵심 컨트롤러 모듈 - 전체 매크로 로직을 통합 관리하는 상태 머신 기반 컨트롤러.
사냥 루프, 알림 감시, 패턴 재생, 거탐 처리를 조율한다.
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
    
    Weing-3.0V의 roop()+checker()를 개선하여:
    - 명확한 상태 전이
    - 우선순위 기반 처리 (거탐 > 룬 > 버프 > 사냥)
    - 세션 시간 제한
    """

    def __init__(self) -> None:
        """컨트롤러 초기화. 모든 하위 모듈을 생성한다."""
        self.config = Config()
        self.state_machine = StateMachine()
        self.timing = TimingEngine()
        
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
        self._hunt_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 세션 관리
        self._session_start: float = 0.0
        self._session_limit_min: int = self.config.get("session_limit_min", 120)
        
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
        self.state_machine.transition_to(new_state)
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
        
        self._running = True
        self._session_start = time.time()
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
        
        self._log("매크로 시작됨")

    def stop(self) -> None:
        """매크로 정지."""
        self._running = False
        self._change_state(State.IDLE)
        self.input_engine.release_all()
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
        self._log(f"패턴 녹화 시작: {category}")
        # 녹화는 별도 스레드에서 실행
        threading.Thread(
            target=self._record_pattern,
            args=(category,),
            daemon=True,
            name="PatternRecord"
        ).start()

    def _record_pattern(self, category: str) -> None:
        """실제 녹화 실행 (별도 스레드)."""
        try:
            events = self.pattern_engine.record(
                category=category,
                on_stop_check=lambda: not self._running,
            )
            if events:
                num = self.pattern_engine.save_pattern(category, events)
                self._log(f"패턴 저장 완료: {category}{num} ({len(events)}개 이벤트)")
                if self._on_pattern_count_change:
                    self._on_pattern_count_change()
            else:
                self._log("녹화 취소됨 (이벤트 없음)")
        except Exception as e:
            self._log(f"녹화 오류: {e}")

    # ─── 사냥 루프 ───

    def _hunt_loop(self) -> None:
        """
        메인 사냥 루프.
        
        Weing-3.0V의 roop()를 개선:
        - 가중치 기반 패턴 카테고리 선택
        - 세션 시간 제한
        - 상태 머신 기반 분기
        """
        self._log("사냥 루프 시작")
        
        while self._running:
            try:
                # 세션 시간 초과 체크
                elapsed_min = (time.time() - self._session_start) / 60
                if elapsed_min >= self._session_limit_min:
                    self._log(f"세션 시간 초과 ({self._session_limit_min}분). 자동 정지.")
                    self.notifier.notify("세션 시간 초과! 매크로를 정지합니다.")
                    self.stop()
                    break
                
                # 상태별 분기
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
                
                # ─── 사냥 실행 ───
                
                # 1. 버프 체크 (Weing의 buff 우선순위 유지)
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
                
                # 3. 포션 체크 (HP/MP 부족 시)
                potion_result = self.screen_monitor.find_template("potion_needed")
                if potion_result and potion_result.found:
                    self.pattern_engine.play_random(
                        "potion", stop_check=self._should_stop_pattern
                    )
                    continue
                
                # 4. 사냥 루틴 (가중치 기반 랜덤 선택)
                weights_cfg = self.config.get("hunt_weights", {
                    "routine": 0.5, "skillA": 0.25, "skillB": 0.25
                })
                categories = list(weights_cfg.keys())
                weights = list(weights_cfg.values())
                
                # 패턴이 있는 카테고리만 필터링
                available = []
                available_weights = []
                for cat, w in zip(categories, weights):
                    if self.pattern_engine.get_pattern_count(cat) > 0:
                        available.append(cat)
                        available_weights.append(w)
                
                if available:
                    selected = random.choices(available, weights=available_weights, k=1)[0]
                    self.pattern_engine.play_random(
                        selected, stop_check=self._should_stop_pattern
                    )
                else:
                    self._log("사용 가능한 패턴 없음. 대기 중...")
                    time.sleep(2.0)
                
                # 사이클 간 딜레이 (Weing: 0.38~0.49초)
                time.sleep(random.uniform(0.38, 0.49))
                
            except Exception as e:
                self._log(f"사냥 루프 오류: {e}")
                time.sleep(1.0)
        
        self._log("사냥 루프 종료")

    # ─── 감시 루프 ───

    def _monitor_loop(self) -> None:
        """
        화면 감시 루프 (별도 스레드).
        
        Weing-3.0V의 checker()를 개선:
        - 프레임 diff로 거탐 팝업 감지
        - 우선순위: 거탐 > 룬 > 일반
        - 자동 해결 시도 + 실패 시 알림
        """
        self._log("감시 루프 시작")
        
        while self._running:
            try:
                state = self.state_machine.current
                
                if state in (State.PAUSED, State.MANUAL_MODE, State.IDLE):
                    time.sleep(0.5)
                    continue
                
                # ─── 거탐 감지 (프레임 diff) ───
                changes = self.screen_monitor.detect_screen_change(
                    threshold=20, min_area=2000
                )
                
                if changes:
                    alert_type = self._classify_alert(changes)
                    if alert_type:
                        self._handle_alert(alert_type)
                
                # ─── 룬 감지 ───
                rune_result = self.screen_monitor.find_template("rune_indicator")
                if rune_result and rune_result.found:
                    self._handle_rune()
                
                # 감시 주기 (랜덤화)
                time.sleep(random.uniform(0.5, 1.0))
                
            except Exception as e:
                self._log(f"감시 루프 오류: {e}")
                time.sleep(1.0)
        
        self._log("감시 루프 종료")

    # ─── 거탐 처리 ───

    def _classify_alert(self, changes: list) -> Optional[str]:
        """
        화면 변화 정보를 기반으로 거짓말 탐지기 유형을 분류한다.
        
        분류 기준:
        - 텍스트 거탐: 특정 크기의 입력 UI 패턴
        - 클릭 거탐: 작은 반투명 창
        - 비올레타: 대형 미니게임 UI
        """
        # 가장 큰 변화 영역 기준으로 판단
        if not changes:
            return None
        
        largest = max(changes, key=lambda c: c.get("area", 0))
        area = largest.get("area", 0)
        
        # 넓은 영역 변화 = 거탐 또는 비올레타
        if area > 50000:
            # 비올레타/투명도형 등 대형 UI → 수동 대응
            return "violetta"
        elif area > 10000:
            # 텍스트 거탐 또는 클릭 거탐
            return "text_captcha"
        elif area > 3000:
            # 클릭 거탐 (작은 반투명 창)
            return "click_5"
        
        return None

    def _handle_alert(self, alert_type: str) -> None:
        """거탐 유형에 따라 처리한다."""
        auto_solve_list = self.config.get("alerts", {}).get("auto_solve", [])
        manual_list = self.config.get("alerts", {}).get("manual_only", [])
        
        self._log(f"거짓말 탐지기 감지: {alert_type}")
        
        # 수동 대응 목록에 있으면 알림만
        if alert_type in manual_list:
            self._change_state(State.MANUAL_MODE)
            self.notifier.notify(f"⚠️ {alert_type} 감지! 수동 해결이 필요합니다!")
            self._log(f"{alert_type}: 수동 해결 필요 → 알림 전송")
            return
        
        # 자동 해결 시도
        if alert_type in auto_solve_list:
            prev_state = self.state_machine.current
            self._change_state(State.ALERT_SOLVING)
            
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
                self._change_state(prev_state)
            else:
                self._log(f"{alert_type} 자동 해결 실패 → 수동 모드 전환")
                self.notifier.notify(f"거탐 자동 해결 실패: {alert_type}")
                self._change_state(State.MANUAL_MODE)
        else:
            # 분류 불가 → 알림
            self.notifier.notify(f"알 수 없는 거탐 유형: {alert_type}")

    def _handle_rune(self) -> None:
        """룬을 감지하고 자동 해결을 시도한다."""
        prev_state = self.state_machine.current
        self._change_state(State.RUNE_SOLVING)
        self._log("룬 감지 → 해결 시도")
        
        try:
            # 룬 위치로 이동 패턴 실행
            if self.pattern_engine.get_pattern_count("move") > 0:
                self.pattern_engine.play_random(
                    "move", stop_check=self._should_stop_pattern
                )
            
            time.sleep(0.5)
            
            # 룬 활성화 (스페이스바)
            self.input_engine.press_key("space")
            time.sleep(1.0)
            
            # 화살표 감지 + 입력
            arrows = self.screen_monitor.detect_rune_arrows()
            if arrows:
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
