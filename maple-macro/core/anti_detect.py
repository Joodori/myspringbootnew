"""
행동 다양성 엔진 - 서버 단 패턴 분석(LCP/LBD/HackRank)을 회피한다.

넥슨의 감지 체계:
1. LCP(Longest Common Prefix): 키 시퀀스 구조적 유사도 분석
2. LBD(Live Bot Detection): 행동 로그 클러스터링 → 작업장 탐지
3. HackRank: 640+ 모델로 로그 점수화 → 상위 랭킹 정밀 분석

대응 전략:
- 사냥 사이클 중간에 "사람다운 잡행동(noise action)" 삽입
- 패턴 시퀀스 순서를 셔플하여 LCP 유사도 감소
- 맵 내 랜덤 이동 / 비전투 행동 / 미니맵 클릭 등
- 세션 간 불규칙한 접속 패턴 시뮬레이션
- 채널 변경 / 맵 이동으로 단일 위치 장기 체류 방지
"""

from __future__ import annotations

import random
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─── 잡행동(Noise Action) 유형 ───

@dataclass
class NoiseAction:
    """사람다운 잡행동 정의."""
    name: str
    keys: list[str]            # 입력할 키 시퀀스
    hold_range_ms: tuple[int, int]  # 키 홀드 범위
    delay_range_ms: tuple[int, int] # 키 사이 딜레이
    weight: float = 1.0        # 선택 확률 가중치
    description: str = ""


# 사람이 실제로 하는 잡행동들
_NOISE_ACTIONS: list[NoiseAction] = [
    NoiseAction(
        name="inventory_peek",
        keys=["i"],  # 인벤토리 열기
        hold_range_ms=(40, 90),
        delay_range_ms=(800, 2500),  # 열었다가 닫기까지
        weight=2.0,
        description="인벤토리를 잠깐 열었다 닫기",
    ),
    NoiseAction(
        name="stats_check",
        keys=["s"],  # 능력치 창
        hold_range_ms=(40, 80),
        delay_range_ms=(600, 1800),
        weight=1.0,
        description="능력치 창 확인",
    ),
    NoiseAction(
        name="minimap_toggle",
        keys=["m"],  # 미니맵 확대
        hold_range_ms=(30, 70),
        delay_range_ms=(400, 1200),
        weight=1.5,
        description="미니맵 토글",
    ),
    NoiseAction(
        name="chat_peek",
        keys=["enter"],  # 채팅 열었다 닫기
        hold_range_ms=(30, 60),
        delay_range_ms=(300, 800),
        weight=1.0,
        description="채팅창 열었다 닫기",
    ),
    NoiseAction(
        name="random_jump",
        keys=["lalt"],  # 점프
        hold_range_ms=(30, 80),
        delay_range_ms=(100, 300),
        weight=3.0,
        description="랜덤 점프 (이동감 추가)",
    ),
    NoiseAction(
        name="direction_change",
        keys=[],  # 동적으로 좌/우 결정
        hold_range_ms=(100, 400),
        delay_range_ms=(50, 200),
        weight=2.0,
        description="짧은 방향 전환",
    ),
    NoiseAction(
        name="idle_pause",
        keys=[],  # 아무 것도 안 함
        hold_range_ms=(0, 0),
        delay_range_ms=(1500, 5000),  # 멍때리기
        weight=1.5,
        description="잠깐 멈춤 (AFK 흉내)",
    ),
    NoiseAction(
        name="skill_window",
        keys=["k"],  # 스킬창
        hold_range_ms=(30, 70),
        delay_range_ms=(500, 1500),
        weight=0.8,
        description="스킬창 확인",
    ),
    NoiseAction(
        name="quick_sit",
        keys=["insert"],  # 앉기
        hold_range_ms=(30, 60),
        delay_range_ms=(2000, 6000),  # 잠깐 앉았다 일어나기
        weight=0.5,
        description="잠깐 앉았다 일어나기",
    ),
]


class BehaviorDiversityEngine:
    """
    행동 다양성 엔진.
    
    사냥 루프에 랜덤한 사람다운 행동을 삽입하여
    서버 단 패턴 분석에서 봇으로 분류되지 않도록 한다.
    
    핵심 원리:
    1. 시간 기반 노이즈: 일정 간격마다 잡행동 삽입
    2. 시퀀스 셔플: 사냥 패턴의 실행 순서를 불규칙하게
    3. 세션 프로파일: 접속/접속해제 패턴을 사람처럼
    4. 맵 다양성: 채널 변경, 미니 이동으로 좌표 분산
    """

    def __init__(self) -> None:
        """행동 다양성 엔진을 초기화한다."""
        # ── 노이즈 삽입 간격 ──
        # 기본: 30~90초마다 잡행동 1회
        self._noise_interval_min_sec: float = 30.0
        self._noise_interval_max_sec: float = 90.0
        self._last_noise_time: float = time.time()
        self._next_noise_interval: float = self._random_noise_interval()

        # ── 채널 변경 간격 ──
        # 기본: 15~40분마다 채널 변경 고려
        self._channel_interval_min_sec: float = 15 * 60
        self._channel_interval_max_sec: float = 40 * 60
        self._last_channel_time: float = time.time()
        self._next_channel_interval: float = self._random_channel_interval()

        # ── 세션 피로도 ──
        # 사람은 시간이 지나면 실수가 늘고, 반응이 느려진다
        self._session_start: float = time.time()
        self._fatigue_factor: float = 1.0  # 1.0 = 정상, 점점 증가

        # ── 시퀀스 히스토리 (LCP 대응) ──
        self._pattern_history: list[str] = []
        self._max_history: int = 20

        # ── 통계 ──
        self._total_noise_count: int = 0
        self._total_channel_changes: int = 0

        # 콜백
        self._on_log: Optional[Callable[[str], None]] = None

    def set_on_log(self, callback: Callable[[str], None]) -> None:
        """로그 콜백을 설정한다."""
        self._on_log = callback

    def _log(self, message: str) -> None:
        """로그 메시지를 발행한다."""
        logger.debug(message)
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass

    # ─── 설정 ───

    def configure(
        self,
        noise_interval_min: float = 30.0,
        noise_interval_max: float = 90.0,
        channel_interval_min: float = 900.0,
        channel_interval_max: float = 2400.0,
    ) -> None:
        """간격 설정을 변경한다."""
        self._noise_interval_min_sec = noise_interval_min
        self._noise_interval_max_sec = noise_interval_max
        self._channel_interval_min_sec = channel_interval_min
        self._channel_interval_max_sec = channel_interval_max

    def reset_session(self) -> None:
        """새 세션 시작 시 호출. 내부 타이머를 리셋한다."""
        now = time.time()
        self._session_start = now
        self._last_noise_time = now
        self._last_channel_time = now
        self._next_noise_interval = self._random_noise_interval()
        self._next_channel_interval = self._random_channel_interval()
        self._fatigue_factor = 1.0
        self._pattern_history.clear()

    # ─── 랜덤 간격 생성 ───

    def _random_noise_interval(self) -> float:
        """다음 노이즈까지의 랜덤 간격(초)."""
        return random.uniform(
            self._noise_interval_min_sec,
            self._noise_interval_max_sec,
        )

    def _random_channel_interval(self) -> float:
        """다음 채널 변경까지의 랜덤 간격(초)."""
        return random.uniform(
            self._channel_interval_min_sec,
            self._channel_interval_max_sec,
        )

    # ─── 피로도 시뮬레이션 ───

    def update_fatigue(self) -> None:
        """
        세션 경과 시간에 따른 피로도를 업데이트한다.
        사람은 1시간 이후부터 점점 느려지고 실수가 늘어난다.
        """
        elapsed_min = (time.time() - self._session_start) / 60.0
        if elapsed_min < 30:
            # 초반 30분: 워밍업 → 약간 빠름
            self._fatigue_factor = random.uniform(0.92, 1.0)
        elif elapsed_min < 60:
            # 30~60분: 정상 상태
            self._fatigue_factor = random.uniform(0.95, 1.05)
        elif elapsed_min < 90:
            # 60~90분: 약간 피로
            self._fatigue_factor = random.uniform(1.0, 1.15)
        else:
            # 90분+: 피로 누적
            self._fatigue_factor = random.uniform(1.05, 1.25)

    def get_fatigue_speed_factor(self) -> float:
        """
        현재 피로도에 따른 속도 팩터를 반환한다.
        패턴 재생 속도에 곱해서 사용한다.
        값이 클수록 느리다 (피로).
        """
        return self._fatigue_factor

    # ─── 노이즈 (잡행동) 삽입 ───

    def should_insert_noise(self) -> bool:
        """노이즈를 삽입할 시점인지 판단한다."""
        elapsed = time.time() - self._last_noise_time
        return elapsed >= self._next_noise_interval

    def get_noise_action(self) -> NoiseAction:
        """
        가중치 기반으로 랜덤 잡행동을 선택하고 타이머를 리셋한다.
        """
        actions = _NOISE_ACTIONS
        weights = [a.weight for a in actions]
        selected = random.choices(actions, weights=weights, k=1)[0]

        # 타이머 리셋
        self._last_noise_time = time.time()
        self._next_noise_interval = self._random_noise_interval()
        self._total_noise_count += 1

        self._log(f"잡행동 삽입: {selected.name} ({selected.description})")
        return selected

    def execute_noise(self, input_engine, action: Optional[NoiseAction] = None) -> None:
        """
        잡행동을 실행한다.
        input_engine: InputEngine 인스턴스
        action: 실행할 NoiseAction (None이면 자동 선택)
        """
        if action is None:
            action = self.get_noise_action()

        if action.name == "idle_pause":
            # 그냥 멈추기
            pause_sec = random.uniform(
                action.delay_range_ms[0] / 1000,
                action.delay_range_ms[1] / 1000,
            )
            time.sleep(pause_sec)
            return

        if action.name == "direction_change":
            # 랜덤 방향으로 짧게 이동
            direction = random.choice(["left", "right"])
            hold_ms = random.uniform(*action.hold_range_ms)
            input_engine.press_key(direction, hold_ms=hold_ms)
            time.sleep(random.uniform(
                action.delay_range_ms[0] / 1000,
                action.delay_range_ms[1] / 1000,
            ))
            return

        # 일반 키 기반 잡행동: 키 누르기 → 대기 → 같은 키 다시 눌러서 닫기
        for key in action.keys:
            hold_ms = random.uniform(*action.hold_range_ms)
            input_engine.press_key(key, hold_ms=hold_ms)

        # 열린 상태로 잠깐 대기
        delay_sec = random.uniform(
            action.delay_range_ms[0] / 1000,
            action.delay_range_ms[1] / 1000,
        )
        time.sleep(delay_sec)

        # 닫기 (같은 키 or ESC)
        close_key = random.choice([action.keys[0], "esc"]) if action.keys else "esc"
        input_engine.press_key(close_key, hold_ms=random.uniform(30, 70))

    # ─── 채널 변경 ───

    def should_change_channel(self) -> bool:
        """채널 변경 시점인지 판단한다."""
        elapsed = time.time() - self._last_channel_time
        return elapsed >= self._next_channel_interval

    def execute_channel_change(self, input_engine) -> None:
        """
        채널 변경을 수행한다.
        메이플의 채널변경: ESC → 채널변경 메뉴
        실제로는 게임 UI에 의존하므로 키 시퀀스로 처리.
        """
        self._log("채널 변경 시도")

        # 현재 활동 정지 → ESC
        time.sleep(random.uniform(0.3, 0.8))
        input_engine.press_key("esc", hold_ms=random.uniform(40, 80))
        time.sleep(random.uniform(0.8, 1.5))

        # 채널변경 메뉴 클릭 (좌표는 게임 해상도에 따라 설정 필요)
        # 여기서는 키보드 단축키 기반으로 처리
        # 실제 좌표는 config에서 가져와야 함
        input_engine.press_key("enter", hold_ms=random.uniform(40, 70))
        time.sleep(random.uniform(3.0, 6.0))  # 채널 변경 로딩 대기

        # 타이머 리셋
        self._last_channel_time = time.time()
        self._next_channel_interval = self._random_channel_interval()
        self._total_channel_changes += 1

        self._log(f"채널 변경 완료 (누적: {self._total_channel_changes}회)")

    # ─── LCP 대응: 시퀀스 셔플 ───

    def record_pattern_used(self, category: str) -> None:
        """사용한 패턴 카테고리를 히스토리에 기록한다."""
        self._pattern_history.append(category)
        if len(self._pattern_history) > self._max_history:
            self._pattern_history.pop(0)

    def get_anti_lcp_weights(self, base_weights: dict[str, float]) -> dict[str, float]:
        """
        최근 패턴 히스토리를 기반으로 가중치를 조정한다.
        같은 카테고리가 연속되면 가중치를 낮춰 LCP 유사도를 감소시킨다.
        
        예: routine이 3번 연속이면 routine 가중치를 0.3배로 감소
        """
        if not self._pattern_history:
            return dict(base_weights)

        adjusted = dict(base_weights)

        # 최근 5개 히스토리에서 빈도 계산
        recent = self._pattern_history[-5:]
        for cat in adjusted:
            count = recent.count(cat)
            if count >= 3:
                # 3회 이상 연속 → 가중치 70% 감소
                adjusted[cat] *= 0.3
            elif count >= 2:
                # 2회 연속 → 가중치 40% 감소
                adjusted[cat] *= 0.6

        # 바로 직전과 같은 카테고리면 추가 페널티
        if self._pattern_history:
            last = self._pattern_history[-1]
            if last in adjusted:
                adjusted[last] *= 0.5

        return adjusted

    def should_insert_movement_noise(self) -> bool:
        """
        패턴 사이에 짧은 이동 노이즈를 삽입할지 결정한다.
        확률: 15~25% (사람도 사냥 중 위치 미세 조정함)
        """
        return random.random() < random.uniform(0.15, 0.25)

    def get_movement_noise(self) -> tuple[str, float]:
        """
        삽입할 이동 노이즈를 반환한다.
        Returns: (방향 키, 홀드 시간 ms)
        """
        direction = random.choice(["left", "right"])
        # 짧은 이동: 50~200ms 홀드
        hold_ms = random.uniform(50, 200)
        return direction, hold_ms

    # ─── 세션 패턴 다양성 ───

    def get_session_delay_modifier(self) -> float:
        """
        세션 시간에 따른 딜레이 수정자를 반환한다.
        사람은 시간이 지날수록 리듬이 변한다.
        """
        elapsed_min = (time.time() - self._session_start) / 60.0

        # 시간대별 다른 리듬
        if elapsed_min < 10:
            # 시작: 빠르고 집중적
            return random.uniform(0.85, 0.95)
        elif elapsed_min < 30:
            # 안정기
            return random.uniform(0.93, 1.05)
        elif elapsed_min < 60:
            # 중반: 가끔 멍 때림
            if random.random() < 0.08:
                return random.uniform(1.5, 3.0)  # 가끔 큰 딜레이
            return random.uniform(0.95, 1.1)
        elif elapsed_min < 90:
            # 후반: 지침
            if random.random() < 0.12:
                return random.uniform(1.5, 4.0)
            return random.uniform(1.0, 1.2)
        else:
            # 90분+: 매우 지침
            if random.random() < 0.15:
                return random.uniform(2.0, 5.0)
            return random.uniform(1.05, 1.3)

    # ─── 키 입력 지문 랜덤화 ───

    def randomize_key_hold(self, base_hold_ms: float) -> float:
        """
        키 홀드 시간을 인간적으로 변형한다.
        사람의 키 홀드 시간 분포: 로그정규 분포에 가까움
        """
        # 기본 변동: ±25%
        variation = base_hold_ms * random.uniform(-0.25, 0.25)
        hold = base_hold_ms + variation

        # 가끔 (3%) 아주 짧거나 길게 누름 (실수 시뮬레이션)
        if random.random() < 0.03:
            if random.random() < 0.5:
                hold *= random.uniform(0.3, 0.5)   # 살짝 스침
            else:
                hold *= random.uniform(1.5, 2.5)    # 길게 누름

        return max(10, hold)  # 최소 10ms 보장

    def randomize_inter_key_delay(self, base_delay_ms: float) -> float:
        """
        키 사이 딜레이를 인간적으로 변형한다.
        사람의 타이핑: 간혹 멈칫함 (hesitation)
        """
        variation = base_delay_ms * random.uniform(-0.2, 0.2)
        delay = base_delay_ms + variation

        # 5% 확률로 멈칫함 (hesitation)
        if random.random() < 0.05:
            delay += random.uniform(200, 800)

        # 2% 확률로 아주 빠른 연타 (더블탭 실수)
        if random.random() < 0.02:
            delay *= random.uniform(0.1, 0.3)

        return max(5, delay)

    # ─── 통계 ───

    def get_stats(self) -> dict:
        """현재 세션의 안티 감지 통계를 반환한다."""
        return {
            "noise_count": self._total_noise_count,
            "channel_changes": self._total_channel_changes,
            "fatigue_factor": round(self._fatigue_factor, 3),
            "pattern_history_len": len(self._pattern_history),
            "session_elapsed_min": round(
                (time.time() - self._session_start) / 60, 1
            ),
        }
