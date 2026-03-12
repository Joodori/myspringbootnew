"""
인간 리듬 시뮬레이터 - 사람의 실제 키 입력 리듬을 재현한다.

사람이 게임을 할 때의 실제 행동 특성:
1. 키 홀드 시간: 로그정규분포 (짧은 탭이 많고, 가끔 길게 누름)
2. 키 간 딜레이: 이전 키에 따라 달라짐 (같은 손 vs 다른 손)
3. 연타 시 가속: 같은 키 반복 시 점점 빨라짐
4. 멈칫함(hesitation): 가끔 0.3~1초 멈춤 (뭘 할지 생각)
5. 리듬 그룹: 2~4개 키를 묶어서 빠르게 → 쉬고 → 다시 빠르게
6. 실수: 가끔 잘못 누르고 바로 수정
7. 일관성 없음: 같은 동작도 매번 미세하게 다름

넥슨 서버 단 감지:
- 키보드 이벤트 간 시간 간격의 분산(variance)이 너무 낮으면 봇 판정
- 키 홀드 시간이 모두 동일하면 봇 판정
- 패턴 재생 속도가 선형적(일정한 배속)이면 봇 판정
"""

from __future__ import annotations

import math
import random
import time
import logging
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class HumanRhythm:
    """
    사람의 키 입력 리듬을 재현하는 엔진.
    
    모든 시간 값은 밀리초(ms) 단위이다.
    """

    def __init__(self) -> None:
        """리듬 엔진을 초기화한다."""
        # ── 개인별 특성 (세션마다 살짝 달라지는 "손 특성") ──
        # 사람마다 키 홀드 시간 기본값이 다름
        self._base_hold_ms: float = random.uniform(45, 75)
        # 사람마다 키 간 기본 딜레이가 다름
        self._base_inter_key_ms: float = random.uniform(80, 150)
        # 반응 속도 기본값 (ms)
        self._base_reaction_ms: float = random.uniform(180, 350)

        # ── 리듬 그룹 상태 ──
        self._group_counter: int = 0
        self._group_size: int = self._new_group_size()
        self._in_burst: bool = True  # 현재 버스트(빠른 입력) 구간인가

        # ── 연타 추적 ──
        self._last_key: Optional[str] = None
        self._same_key_streak: int = 0

        # ── 최근 딜레이 히스토리 (분산 계산용) ──
        self._delay_history: deque[float] = deque(maxlen=30)

        # ── 피로도 ──
        self._actions_count: int = 0
        self._session_start: float = time.time()

    def _new_group_size(self) -> int:
        """다음 리듬 그룹의 크기를 결정한다 (2~5개 키)."""
        return random.randint(2, 5)

    # ─── 핵심: 키 홀드 시간 생성 ───

    def get_key_hold_ms(self, key: str = "") -> float:
        """
        주어진 키에 대한 사람다운 홀드 시간(ms)을 생성한다.
        
        실제 사람의 키 홀드 시간 특성:
        - 일반 키: 40~100ms (로그정규분포)
        - 방향키: 80~500ms (이동 거리에 따라)
        - 스킬키: 50~120ms
        - 가끔 아주 짧게 스침: 15~30ms (실수)
        - 가끔 길게 누름: 150~300ms (의도적 or 실수)
        """
        # 키 종류별 기본값
        if key in ("left", "right", "up", "down"):
            base = random.uniform(80, 350)
        elif key in ("lalt", "lshift", "lctrl", "space"):
            base = random.uniform(50, 120)
        else:
            base = self._base_hold_ms

        # 로그정규분포 변형 (자연스러운 분포)
        mu = math.log(base)
        sigma = 0.25  # 분산 정도
        hold = random.lognormvariate(mu, sigma)

        # 실수 시뮬레이션
        roll = random.random()
        if roll < 0.02:
            # 2%: 살짝 스침 (키를 거의 안 누름)
            hold = random.uniform(10, 25)
        elif roll < 0.04:
            # 2%: 길게 누름 (주의 분산)
            hold = hold * random.uniform(2.0, 4.0)

        # 연타 시 점점 짧아짐 (손가락이 익숙해짐)
        if self._same_key_streak > 1:
            hold *= max(0.7, 1.0 - (self._same_key_streak * 0.05))

        return max(10, min(hold, 600))  # 10~600ms 클램프

    # ─── 핵심: 키 간 딜레이 생성 ───

    def get_inter_key_delay_ms(self, prev_key: str = "", next_key: str = "") -> float:
        """
        두 키 사이의 사람다운 딜레이(ms)를 생성한다.
        
        실제 사람의 키 간 딜레이 특성:
        - 같은 키 연타: 60~120ms (빠름)
        - 다른 키 전환: 100~200ms
        - 방향 전환 (←→): 150~350ms (손가락 이동)
        - 스킬 콤보: 80~180ms
        - 리듬 그룹 사이: 300~800ms (생각하는 시간)
        - 멈칫함: 500~2000ms (가끔)
        """
        base = self._base_inter_key_ms

        # 같은 키 연타
        if prev_key == next_key and prev_key:
            base = random.uniform(60, 130)
            self._same_key_streak += 1
        else:
            self._same_key_streak = 0

        # 방향 전환 페널티 (좌→우 등)
        direction_keys = {"left", "right", "up", "down"}
        if prev_key in direction_keys and next_key in direction_keys and prev_key != next_key:
            base = random.uniform(150, 350)

        # 리듬 그룹 처리
        self._group_counter += 1
        if self._group_counter >= self._group_size:
            # 그룹 사이 쉬기
            self._group_counter = 0
            self._group_size = self._new_group_size()
            self._in_burst = not self._in_burst

            if not self._in_burst:
                # 쉬는 구간: 긴 딜레이
                base = random.uniform(300, 800)

        # 로그정규분포 변형
        mu = math.log(max(10, base))
        sigma = 0.2
        delay = random.lognormvariate(mu, sigma)

        # 멈칫함 (hesitation) - 세션 시간에 따라 확률 증가
        elapsed_min = (time.time() - self._session_start) / 60.0
        hesitation_prob = min(0.08, 0.02 + elapsed_min * 0.0005)
        if random.random() < hesitation_prob:
            delay += random.uniform(400, 1500)

        # 딜레이를 히스토리에 기록
        self._delay_history.append(delay)

        self._last_key = next_key
        self._actions_count += 1

        return max(15, min(delay, 3000))  # 15~3000ms 클램프

    # ─── 패턴 재생 속도 변형 ───

    def get_replay_speed_factor(self) -> float:
        """
        패턴 재생 시 적용할 속도 팩터를 생성한다.
        
        Weing의 0.93~1.0 → 우리는 더 넓고 비선형적으로.
        
        사람이 같은 동작을 반복할 때:
        - 처음 몇 번: 약간 느림 (0.90~0.98)
        - 익숙해진 후: 약간 빠름 (0.95~1.05)
        - 지칠 때: 느려짐 (1.0~1.15)
        - 가끔 급발진: 매우 빠름 (0.80~0.90)
        """
        elapsed_min = (time.time() - self._session_start) / 60.0

        # 시간대별 기본 범위
        if elapsed_min < 15:
            base_min, base_max = 0.88, 1.0
        elif elapsed_min < 45:
            base_min, base_max = 0.90, 1.08
        elif elapsed_min < 75:
            base_min, base_max = 0.92, 1.12
        else:
            base_min, base_max = 0.95, 1.20

        speed = random.uniform(base_min, base_max)

        # 5% 확률로 급발진 (집중 모드 돌입)
        if random.random() < 0.05:
            speed = random.uniform(0.78, 0.88)

        # 3% 확률로 급감속 (화장실/폰 확인 등)
        if random.random() < 0.03:
            speed = random.uniform(1.25, 1.60)

        return speed

    # ─── 사냥 사이클 딜레이 ───

    def get_cycle_delay_sec(self) -> float:
        """
        사냥 사이클 간 딜레이(초)를 생성한다.
        Weing: 0.38~0.49초 → 우리: 더 넓고 가변적.
        
        사람의 사이클 간 행동:
        - 대부분: 0.2~0.6초 (바로 다음 동작)
        - 가끔: 0.8~2.0초 (화면 확인)
        - 드물게: 2.0~5.0초 (멍때리기/폰 확인)
        """
        roll = random.random()

        if roll < 0.70:
            # 70%: 일반 속도
            return random.uniform(0.25, 0.55)
        elif roll < 0.88:
            # 18%: 약간 느림 (화면 확인)
            return random.uniform(0.55, 1.2)
        elif roll < 0.96:
            # 8%: 느림 (뭔가 확인)
            return random.uniform(1.2, 2.5)
        else:
            # 4%: 멍때리기
            return random.uniform(2.5, 5.0)

    # ─── 실수 시뮬레이션 ───

    def should_make_mistake(self) -> bool:
        """
        실수를 할 확률을 반환한다.
        사람은 가끔 잘못된 키를 누르거나 이상한 행동을 한다.
        확률: 세션 시간에 따라 1~4%
        """
        elapsed_min = (time.time() - self._session_start) / 60.0
        # 초반 1%, 후반 4%까지 증가
        prob = min(0.04, 0.01 + elapsed_min * 0.0003)
        return random.random() < prob

    def get_mistake_action(self) -> dict:
        """
        실수 행동을 생성한다.
        
        Returns:
            {"type": "wrong_key", "key": "q", "hold_ms": 30}
            {"type": "double_tap", "key": "last_key", "count": 2}
            {"type": "early_release", "factor": 0.3}
            {"type": "stuck_key", "key": "up", "extra_ms": 200}
        """
        mistake_type = random.choices(
            ["wrong_key", "double_tap", "early_release", "stuck_key"],
            weights=[0.3, 0.25, 0.25, 0.2],
            k=1,
        )[0]

        if mistake_type == "wrong_key":
            # 근처 키를 잘못 누름
            nearby_keys = ["q", "w", "e", "a", "s", "d", "z", "x", "c"]
            return {
                "type": "wrong_key",
                "key": random.choice(nearby_keys),
                "hold_ms": random.uniform(15, 35),  # 바로 뗌
            }
        elif mistake_type == "double_tap":
            return {
                "type": "double_tap",
                "count": random.randint(2, 3),
            }
        elif mistake_type == "early_release":
            return {
                "type": "early_release",
                "factor": random.uniform(0.2, 0.5),
            }
        else:  # stuck_key
            return {
                "type": "stuck_key",
                "extra_ms": random.uniform(100, 400),
            }

    # ─── 분산 체크 (봇 감지 자가 진단) ───

    def get_delay_variance(self) -> float:
        """
        최근 딜레이의 분산을 계산한다.
        분산이 너무 낮으면 봇으로 감지될 수 있다.
        
        사람의 딜레이 변동 계수(CV): 보통 0.3~0.8
        봇의 딜레이 변동 계수(CV): 보통 0.01~0.1
        """
        if len(self._delay_history) < 5:
            return -1.0  # 데이터 부족

        delays = list(self._delay_history)
        mean = sum(delays) / len(delays)
        if mean <= 0:
            return 0.0

        variance = sum((d - mean) ** 2 for d in delays) / len(delays)
        std_dev = variance ** 0.5
        cv = std_dev / mean  # 변동 계수

        return cv

    def is_rhythm_natural(self) -> bool:
        """
        현재 리듬이 자연스러운지 자가 진단한다.
        변동 계수가 0.2 미만이면 위험.
        """
        cv = self.get_delay_variance()
        if cv < 0:
            return True  # 데이터 부족, 판단 불가
        return cv >= 0.2

    # ─── 세션 리셋 ───

    def reset_session(self) -> None:
        """새 세션을 위해 상태를 리셋한다. 개인 특성은 새로 랜덤 생성."""
        self._base_hold_ms = random.uniform(45, 75)
        self._base_inter_key_ms = random.uniform(80, 150)
        self._base_reaction_ms = random.uniform(180, 350)
        self._group_counter = 0
        self._group_size = self._new_group_size()
        self._in_burst = True
        self._last_key = None
        self._same_key_streak = 0
        self._delay_history.clear()
        self._actions_count = 0
        self._session_start = time.time()
