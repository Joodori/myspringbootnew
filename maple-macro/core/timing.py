"""
타이밍 엔진 모듈 - 매크로의 실행 간격과 지터(jitter)를 관리한다.
사람처럼 불규칙한 입력 타이밍을 시뮬레이션하기 위해 랜덤 딜레이를 삽입한다.
"""

from __future__ import annotations

import random
import time
from typing import Optional

from core.config import Config


class TimingEngine:
    """
    매크로 타이밍 관리 엔진.
    - 주기적 지터 삽입으로 패턴 탐지를 회피한다.
    - sleep 시 ±15% 변동을 추가하여 자연스러운 타이밍을 만든다.
    """

    def __init__(self) -> None:
        """설정에서 타이밍 파라미터를 로드한다."""
        cfg = Config()
        self.cycle_duration_ms: int = cfg.get("cycle_duration_ms", 60000)

        # 지터 설정 로드 - 일정 간격마다 짧은 랜덤 딜레이를 넣는다
        jitter = cfg.get("jitter", {})
        self.interval_min_ms: int = jitter.get("interval_min_ms", 9000)
        self.interval_max_ms: int = jitter.get("interval_max_ms", 16000)
        self.duration_min_ms: int = jitter.get("duration_min_ms", 2)
        self.duration_max_ms: int = jitter.get("duration_max_ms", 6)

        # 마지막 지터 삽입 시각 기록
        self._last_jitter_time: float = time.monotonic()
        # 다음 지터까지의 간격 (랜덤 결정)
        self._next_jitter_interval_ms: int = self._random_interval()

    def _random_interval(self) -> int:
        """다음 지터 삽입까지의 랜덤 간격(ms)을 생성한다."""
        return random.randint(self.interval_min_ms, self.interval_max_ms)

    def sleep_with_jitter(self, base_delay_ms: float) -> None:
        """
        기본 딜레이에 ±15% 변동을 추가하여 sleep한다.
        사람의 반응 속도 편차를 모방하는 핵심 함수이다.
        """
        # ±15% 범위의 랜덤 변동 적용
        variation = base_delay_ms * random.uniform(-0.15, 0.15)
        actual_delay_ms = max(0, base_delay_ms + variation)
        actual_delay_sec = actual_delay_ms / 1000.0
        time.sleep(actual_delay_sec)

    def should_insert_jitter(self, elapsed_since_last_jitter_ms: Optional[float] = None) -> bool:
        """
        지터를 삽입할 시점인지 판단한다.
        elapsed_since_last_jitter_ms가 주어지면 그 값을 사용하고,
        아니면 내부 타이머로 자동 계산한다.
        """
        if elapsed_since_last_jitter_ms is not None:
            return elapsed_since_last_jitter_ms >= self._next_jitter_interval_ms

        # 내부 타이머 기반 판단
        now = time.monotonic()
        elapsed_ms = (now - self._last_jitter_time) * 1000.0
        return elapsed_ms >= self._next_jitter_interval_ms

    def get_jitter_delay(self) -> float:
        """
        삽입할 지터 딜레이(초)를 반환하고 내부 타이머를 리셋한다.
        반환값은 2~6ms 범위의 랜덤 값이다.
        """
        delay_ms = random.randint(self.duration_min_ms, self.duration_max_ms)
        # 내부 타이머 리셋 - 다음 지터 간격도 새로 결정
        self._last_jitter_time = time.monotonic()
        self._next_jitter_interval_ms = self._random_interval()
        return delay_ms / 1000.0

    def insert_jitter_if_needed(self) -> None:
        """지터 삽입 시점이면 짧은 딜레이를 넣는다. 매 반복에서 호출하면 된다."""
        if self.should_insert_jitter():
            delay = self.get_jitter_delay()
            time.sleep(delay)

    def get_cycle_duration_sec(self) -> float:
        """사이클 주기를 초 단위로 반환한다."""
        return self.cycle_duration_ms / 1000.0
