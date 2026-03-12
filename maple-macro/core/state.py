"""
상태 머신 모듈 - 매크로의 실행 상태를 관리한다.
각 상태 전환 시 등록된 콜백을 호출하여 다른 모듈에 상태 변경을 알린다.
"""

from __future__ import annotations

import threading
from enum import Enum, auto
from typing import Callable, Optional


class State(Enum):
    """매크로 실행 상태 열거형"""
    IDLE = auto()            # 대기 상태 - 매크로 미실행
    HUNTING = auto()         # 사냥 중 - 패턴 재생 및 일반 루틴 실행
    BUFFING = auto()         # 버프 사용 중 - 버프 스킬 시전
    RUNE_SOLVING = auto()    # 룬 풀이 중 - 화살표 방향 입력
    ALERT_SOLVING = auto()   # 알림 처리 중 - 텍스트 캡차/감지기 등 해결
    MANUAL_MODE = auto()     # 수동 모드 - 사용자 직접 조작
    PAUSED = auto()          # 일시 정지 - 핫키로 재개 가능


# 상태 전환 규칙 정의 - 각 상태에서 전환 가능한 상태 목록
_VALID_TRANSITIONS: dict[State, set[State]] = {
    State.IDLE: {State.HUNTING, State.MANUAL_MODE},
    State.HUNTING: {
        State.BUFFING, State.RUNE_SOLVING, State.ALERT_SOLVING,
        State.PAUSED, State.IDLE, State.MANUAL_MODE,
    },
    State.BUFFING: {State.HUNTING, State.PAUSED, State.IDLE, State.ALERT_SOLVING},
    State.RUNE_SOLVING: {State.HUNTING, State.IDLE, State.PAUSED},
    State.ALERT_SOLVING: {State.HUNTING, State.IDLE, State.PAUSED},
    State.MANUAL_MODE: {State.IDLE, State.HUNTING, State.PAUSED},
    State.PAUSED: {State.HUNTING, State.IDLE, State.MANUAL_MODE},
}


# 콜백 타입: (이전 상태, 새 상태)를 인자로 받는 함수
StateCallback = Callable[[State, State], None]


class StateMachine:
    """
    스레드 안전한 상태 머신.
    유효한 전환만 허용하며, 상태 변경 시 등록된 콜백을 실행한다.
    """

    def __init__(self, initial_state: State = State.IDLE) -> None:
        """초기 상태를 설정하고 콜백 리스트를 초기화한다."""
        self._state: State = initial_state
        self._lock: threading.Lock = threading.Lock()
        self._callbacks: list[StateCallback] = []
        # 상태별 콜백 - 특정 상태 진입 시에만 호출
        self._state_callbacks: dict[State, list[StateCallback]] = {
            s: [] for s in State
        }

    @property
    def current(self) -> State:
        """현재 상태를 반환한다."""
        with self._lock:
            return self._state

    def transition(self, new_state: State) -> bool:
        """
        새 상태로 전환을 시도한다.
        유효한 전환이면 상태를 변경하고 콜백을 호출한 뒤 True를 반환한다.
        유효하지 않은 전환이면 False를 반환하고 아무 동작도 하지 않는다.
        """
        with self._lock:
            if new_state not in _VALID_TRANSITIONS.get(self._state, set()):
                return False
            old_state = self._state
            self._state = new_state

        # 락 해제 후 콜백 실행 (데드락 방지)
        self._fire_callbacks(old_state, new_state)
        return True

    def force_transition(self, new_state: State) -> None:
        """전환 규칙을 무시하고 강제로 상태를 변경한다. 긴급 상황용."""
        with self._lock:
            old_state = self._state
            self._state = new_state
        self._fire_callbacks(old_state, new_state)

    def on_change(self, callback: StateCallback) -> None:
        """모든 상태 전환에 대해 호출될 콜백을 등록한다."""
        self._callbacks.append(callback)

    def on_enter(self, state: State, callback: StateCallback) -> None:
        """특정 상태 진입 시 호출될 콜백을 등록한다."""
        self._state_callbacks[state].append(callback)

    def _fire_callbacks(self, old_state: State, new_state: State) -> None:
        """등록된 콜백들을 실행한다. 콜백 예외는 무시하여 상태 머신 안정성을 보장한다."""
        # 전역 콜백 실행
        for cb in self._callbacks:
            try:
                cb(old_state, new_state)
            except Exception:
                pass
        # 상태별 콜백 실행
        for cb in self._state_callbacks.get(new_state, []):
            try:
                cb(old_state, new_state)
            except Exception:
                pass

    def is_active(self) -> bool:
        """매크로가 활성 상태(사냥/버프/풀이 중)인지 반환한다."""
        return self.current in {
            State.HUNTING, State.BUFFING,
            State.RUNE_SOLVING, State.ALERT_SOLVING,
        }

    def is_paused(self) -> bool:
        """일시 정지 상태인지 반환한다."""
        return self.current == State.PAUSED
