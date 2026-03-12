"""
패턴 엔진 모듈 - 키보드 패턴의 녹화, 저장, 로드, 재생을 관리한다.
카테고리별로 여러 패턴을 저장하고, 재생 시 랜덤 선택 + 타이밍 변동을 적용한다.
"""

from __future__ import annotations

import os
import pickle
import random
import time
import threading
from pathlib import Path
from typing import Callable, Optional

from pattern.event import PatternEvent
from core.config import Config
from core.timing import TimingEngine

# 입력 엔진은 지연 임포트 (순환 참조 방지)
_input_engine = None


def set_input_engine(engine) -> None:
    """외부에서 입력 엔진 인스턴스를 설정한다 (controller와 공유)."""
    global _input_engine
    _input_engine = engine


def _get_input_engine():
    """입력 엔진 인스턴스를 반환한다."""
    global _input_engine
    if _input_engine is None:
        try:
            from input.engine import InputEngine
            _input_engine = InputEngine()
        except Exception:
            _input_engine = None
    return _input_engine


class PatternEngine:
    """
    패턴 녹화/재생 엔진.
    - 카테고리별 패턴 관리 (routine, buff, meso, skillA, skillB, move, potion)
    - 녹화된 패턴을 pickle로 직렬화하여 저장
    - 재생 시 속도 팩터와 이벤트별 타이밍 변동을 적용
    """

    # 지원하는 패턴 카테고리 목록
    CATEGORIES: list[str] = [
        "routine", "buff", "meso", "skillA", "skillB", "move", "potion"
    ]

    def __init__(self, base_path: str = "patterns") -> None:
        """
        패턴 저장 디렉토리를 생성하고 기존 패턴을 로드한다.
        base_path: 패턴 파일이 저장될 기본 경로
        """
        self._base_path = Path(base_path)
        # 카테고리별 디렉토리 생성
        for category in self.CATEGORIES:
            (self._base_path / category).mkdir(parents=True, exist_ok=True)

        # 메모리에 로드된 패턴 딕셔너리: {카테고리: [패턴 리스트]}
        self._patterns: dict[str, list[list[PatternEvent]]] = {
            cat: [] for cat in self.CATEGORIES
        }

        self._timing = TimingEngine()
        self._recording = False
        self._record_lock = threading.Lock()

        # 기존 패턴 파일 로드
        self.load_all()

    def load_all(self) -> None:
        """모든 카테고리의 패턴 파일(.pkl)을 메모리에 로드한다."""
        for category in self.CATEGORIES:
            cat_dir = self._base_path / category
            self._patterns[category] = []

            if not cat_dir.exists():
                continue

            # 번호순으로 정렬하여 로드
            pkl_files = sorted(cat_dir.glob("*.pkl"))
            for pkl_file in pkl_files:
                try:
                    with open(pkl_file, "rb") as f:
                        events: list[PatternEvent] = pickle.load(f)
                    if events:
                        self._patterns[category].append(events)
                except (pickle.UnpicklingError, EOFError, OSError):
                    # 손상된 파일은 건너뛴다
                    continue

    def save_pattern(
        self, category: str, events: list[PatternEvent]
    ) -> Optional[str]:
        """
        패턴을 pickle 파일로 저장한다.
        기존 패턴 번호의 빈 자리를 채워 연속적인 번호를 유지한다.
        반환: 저장된 파일 경로, 실패 시 None
        """
        if category not in self.CATEGORIES:
            return None
        if not events:
            return None

        cat_dir = self._base_path / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        # 기존 파일 번호 확인하여 빈 번호 찾기 (gap-filling)
        existing_nums: set[int] = set()
        for f in cat_dir.glob("*.pkl"):
            try:
                num = int(f.stem)
                existing_nums.add(num)
            except ValueError:
                continue

        # 1번부터 시작하여 빈 번호를 찾는다
        new_num = 1
        while new_num in existing_nums:
            new_num += 1

        file_path = cat_dir / f"{new_num:03d}.pkl"
        try:
            with open(file_path, "wb") as f:
                pickle.dump(events, f)
            # 메모리에도 추가
            self._patterns[category].append(events)
            return str(file_path)
        except OSError:
            return None

    def record(
        self,
        category: str,
        on_stop_check: Callable[[], bool] = lambda: False,
    ) -> Optional[list[PatternEvent]]:
        """
        키보드 이벤트를 녹화한다.
        on_stop_check가 True를 반환하면 녹화를 중단한다.
        interception 우선 시도, 없으면 keyboard 라이브러리로 폴백.
        """
        if category not in self.CATEGORIES:
            return None

        with self._record_lock:
            if self._recording:
                return None
            self._recording = True

        events: list[PatternEvent] = []
        start_time = time.monotonic()

        try:
            # 방법 1: interception 키보드 후킹
            try:
                import interception as icp
                self._record_with_interception(icp, events, start_time, on_stop_check)
            except (ImportError, OSError):
                # 방법 2: keyboard 라이브러리 폴백
                self._record_with_keyboard(events, start_time, on_stop_check)

        finally:
            self._recording = False

        # 녹화된 이벤트가 있으면 자동 저장
        if events:
            self.save_pattern(category, events)

        return events

    def _record_with_interception(
        self, icp, events: list[PatternEvent],
        start_time: float, on_stop_check: Callable[[], bool],
    ) -> None:
        """인터셉션 드라이버로 키보드 이벤트를 녹화한다."""
        while not on_stop_check():
            try:
                device = icp.wait(100)
                if device is None:
                    continue
                stroke = icp.receive(device)
                if stroke is None:
                    continue
                elapsed_ms = (time.monotonic() - start_time) * 1000.0
                event_type = "key_down" if stroke.state == 0 else "key_up"
                event = PatternEvent(
                    event_type=event_type,
                    key_code=stroke.code,
                    scan_code=stroke.code,
                    timestamp=elapsed_ms,
                )
                events.append(event)
                icp.send(device, stroke)
            except Exception:
                continue

    def _record_with_keyboard(
        self, events: list[PatternEvent],
        start_time: float, on_stop_check: Callable[[], bool],
    ) -> None:
        """
        keyboard 라이브러리로 키보드 이벤트를 녹화한다 (인터셉션 없을 때 폴백).
        """
        try:
            import keyboard as kb
        except ImportError:
            return  # keyboard도 없으면 녹화 불가

        recorded: list[kb.KeyboardEvent] = []

        def _on_key(e: kb.KeyboardEvent) -> None:
            recorded.append(e)

        # 모든 키보드 이벤트 후킹
        kb.hook(_on_key)
        try:
            while not on_stop_check():
                time.sleep(0.05)  # 50ms 폴링
        finally:
            kb.unhook_all()

        # keyboard 이벤트를 PatternEvent로 변환
        # 스캔코드 매핑 (역방향)
        from input.engine import _SCAN_CODES
        name_to_scan = {name: code for name, code in _SCAN_CODES.items()}

        for e in recorded:
            elapsed_ms = (e.time - recorded[0].time) * 1000.0 if recorded else 0.0
            event_type = "key_down" if e.event_type == "down" else "key_up"
            # 키 이름으로 스캔코드 찾기
            key_name = e.name.lower() if e.name else ""
            scan = e.scan_code if e.scan_code else name_to_scan.get(key_name, 0)
            if scan == 0:
                continue  # 알 수 없는 키 무시
            event = PatternEvent(
                event_type=event_type,
                key_code=scan,
                scan_code=scan,
                timestamp=max(0, elapsed_ms),
            )
            events.append(event)

    def play_random(
        self,
        category: str,
        stop_check: Callable[[], bool] = lambda: False,
    ) -> bool:
        """
        지정 카테고리에서 랜덤 패턴을 선택하여 재생한다.
        - 전체 속도 팩터(0.85~1.15)를 적용한다.
        - 개별 이벤트마다 ±10% 타이밍 변동을 추가한다.
        - 재생 중 주기적으로 지터를 삽입한다.
        반환: 재생 성공 여부
        """
        if category not in self.CATEGORIES:
            return False
        patterns = self._patterns.get(category, [])
        if not patterns:
            return False

        engine = _get_input_engine()
        if engine is None:
            return False

        # 랜덤 패턴 선택
        pattern = random.choice(patterns)
        if not pattern:
            return False

        # 전체 속도 팩터 결정 (설정에서 로드)
        cfg = Config()
        speed_min = cfg.get("speed_factor.min", 0.85)
        speed_max = cfg.get("speed_factor.max", 1.15)
        speed_factor = random.uniform(speed_min, speed_max)

        # 이벤트 순서대로 재생 (스캔코드 직접 제어)
        prev_timestamp = 0.0
        pressed_keys: set[int] = set()  # 현재 눌려있는 키 추적

        for event in pattern:
            if stop_check():
                # 중단 요청 시 모든 키 해제 후 종료
                for sc in pressed_keys:
                    engine.raw_key_up(sc)
                self._release_all_keys()
                return False

            # 이전 이벤트와의 시간 간격 계산
            delay_ms = event.timestamp - prev_timestamp
            if delay_ms > 0:
                # 속도 팩터 적용
                adjusted_delay = delay_ms * speed_factor
                # 개별 이벤트 ±10% 타이밍 변동
                adjusted_delay *= random.uniform(0.9, 1.1)
                time.sleep(adjusted_delay / 1000.0)

            # 지터 삽입 확인
            self._timing.insert_jitter_if_needed()

            # 키 이벤트 재생: key_down/key_up을 녹화된 타이밍 그대로 재현
            sc = event.scan_code
            if event.is_key_down:
                engine.raw_key_down(sc)
                pressed_keys.add(sc)
            elif event.is_key_up:
                engine.raw_key_up(sc)
                pressed_keys.discard(sc)

            prev_timestamp = event.timestamp

        # 재생 완료 후 남은 키 해제
        for sc in pressed_keys:
            engine.raw_key_up(sc)

        return True

    def delete_pattern(self, category: str, num: int) -> bool:
        """
        특정 카테고리의 n번 패턴을 삭제한다.
        num은 1부터 시작하는 인덱스이다.
        """
        if category not in self.CATEGORIES:
            return False

        cat_dir = self._base_path / category
        # 해당 번호의 파일 찾기
        target_file = cat_dir / f"{num:03d}.pkl"
        if target_file.exists():
            try:
                target_file.unlink()
                # 메모리에서도 다시 로드
                self.load_all()
                return True
            except OSError:
                return False
        return False

    def get_pattern_count(self, category: str) -> int:
        """지정 카테고리의 패턴 개수를 반환한다."""
        if category not in self.CATEGORIES:
            return 0
        return len(self._patterns.get(category, []))

    def _release_all_keys(self) -> None:
        """재생 중단 시 모든 키를 해제한다."""
        engine = _get_input_engine()
        if engine is not None:
            engine.release_all()
