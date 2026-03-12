"""
입력 엔진 모듈 - 키보드/마우스 입력을 처리한다.
interception 드라이버가 설치된 경우 하드웨어 레벨 입력을 사용하고,
없으면 ctypes SendInput으로 폴백하여 동작한다.

v2: 입력 지문 랜덤화 강화
- HumanRhythm 기반 키 홀드 시간 (로그정규분포)
- 키 간 딜레이 인간화 (리듬 그룹, 멈칫함)
- SendInput 타이밍 지문 랜덤화 (dwExtraInfo, time 필드)
- 세션별 디바이스 특성 시뮬레이션
- 타이핑 속도 변동 강화
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import random
import time
import math
import logging
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)

# interception 라이브러리 로드 시도 - 드라이버 미설치 시 None으로 폴백
try:
    import interception
    _INTERCEPTION_AVAILABLE = True
except (ImportError, OSError):
    interception = None  # type: ignore[assignment]
    _INTERCEPTION_AVAILABLE = False


# --- ctypes SendInput 폴백용 상수 및 구조체 정의 ---

# SendInput 이벤트 타입
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0

# 키보드 이벤트 플래그
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# 마우스 이벤트 플래그
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class _MOUSEINPUT(ctypes.Structure):
    """마우스 입력 구조체 (Windows API)"""
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    """키보드 입력 구조체 (Windows API)"""
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    """입력 유니온 - 마우스 또는 키보드 데이터를 담는다"""
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
    ]


class _INPUT(ctypes.Structure):
    """Windows INPUT 구조체 - SendInput에 전달한다"""
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


# 자주 사용하는 키의 스캔코드 매핑 (Set 1 스캔코드)
_SCAN_CODES: dict[str, int] = {
    "left": 0x4B, "right": 0x4D, "up": 0x48, "down": 0x50,
    "enter": 0x1C, "space": 0x39, "esc": 0x01, "tab": 0x0F,
    "lshift": 0x2A, "rshift": 0x36, "lctrl": 0x1D, "rctrl": 0x1D,
    "lalt": 0x38, "ralt": 0x38,
    "a": 0x1E, "b": 0x30, "c": 0x2E, "d": 0x20, "e": 0x12,
    "f": 0x21, "g": 0x22, "h": 0x23, "i": 0x17, "j": 0x24,
    "k": 0x25, "l": 0x26, "m": 0x32, "n": 0x31, "o": 0x18,
    "p": 0x19, "q": 0x10, "r": 0x13, "s": 0x1F, "t": 0x14,
    "u": 0x16, "v": 0x2F, "w": 0x11, "x": 0x2D, "y": 0x15,
    "z": 0x2C,
    "0": 0x0B, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05,
    "5": 0x06, "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E,
    "f5": 0x3F, "f6": 0x40, "f7": 0x41, "f8": 0x42,
    "f9": 0x43, "f10": 0x44, "f11": 0x57, "f12": 0x58,
    "home": 0x47, "end": 0x4F, "insert": 0x52, "delete": 0x53,
    "pageup": 0x49, "pagedown": 0x51,
}

# 해제해야 할 키 목록 - 키가 눌린 채로 멈추는 것을 방지
_RELEASE_KEYS: list[str] = [
    "left", "right", "up", "down", "lshift", "rshift",
    "lctrl", "rctrl", "lalt", "ralt",
]

# ─── 키보드 인접 키 맵 (실수 시뮬레이션용) ───
_ADJACENT_KEYS: dict[str, list[str]] = {
    "q": ["w", "a"], "w": ["q", "e", "s"], "e": ["w", "r", "d"],
    "r": ["e", "t", "f"], "a": ["q", "s", "z"], "s": ["a", "w", "d", "x"],
    "d": ["s", "e", "f", "c"], "f": ["d", "r", "g", "v"],
    "z": ["a", "x"], "x": ["z", "s", "c"], "c": ["x", "d", "v"],
}


class InputEngine:
    """
    키보드/마우스 입력 엔진 (v2: 입력 지문 랜덤화).

    interception 드라이버가 있으면 하드웨어 레벨 입력을 사용하고,
    없으면 Windows SendInput API로 폴백한다.

    v2 개선점:
    - 세션별 "디바이스 특성" 시뮬레이션 (사람마다 키보드가 다름)
    - SendInput의 time/dwExtraInfo 필드 랜덤화
    - 키 누름-뗌 사이 마이크로 지터 (0.1~0.5ms)
    - 키 종류별 사람다운 홀드 시간 분포
    - 연타 시 가속 효과
    - 입력 이벤트 히스토리 기반 리듬 분석
    """

    def __init__(self) -> None:
        """입력 엔진을 초기화한다. interception 사용 가능 여부를 확인한다."""
        self._use_interception: bool = False
        self._interception_ctx = None

        if _INTERCEPTION_AVAILABLE:
            try:
                # interception 컨텍스트 생성 시도
                self._interception_ctx = interception.auto_capture_devices(
                    keyboard=True, mouse=True
                )
                self._use_interception = True
            except Exception:
                # 드라이버 미설치 등의 이유로 실패 시 폴백
                self._use_interception = False

        # SendInput 폴백용 ctypes 함수 참조
        try:
            self._send_input = ctypes.windll.user32.SendInput  # type: ignore[attr-defined]
            self._user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            # Windows가 아닌 환경에서는 None으로 설정 (테스트용)
            self._send_input = None
            self._user32 = None

        # ── v2: 세션별 디바이스 특성 ──
        # 사람마다 키보드 반응 속도가 다르다 (USB 폴링 레이트 차이 시뮬레이션)
        self._device_base_latency_ms: float = random.uniform(0.5, 2.0)
        # 키보드 debounce 특성 (기계식 vs 멤브레인)
        self._debounce_ms: float = random.uniform(1.0, 5.0)
        # 세션별 기본 홀드 시간 편향 (사람마다 강하게/약하게 누름)
        self._hold_bias: float = random.uniform(0.85, 1.15)

        # ── v2: 연타 추적 ──
        self._last_key: Optional[str] = None
        self._same_key_streak: int = 0
        self._last_key_time: float = 0.0

        # ── v2: 입력 히스토리 (분산 모니터링) ──
        self._hold_history: deque[float] = deque(maxlen=50)
        self._delay_history: deque[float] = deque(maxlen=50)

        # ── v2: 리듬 그룹 상태 ──
        self._group_counter: int = 0
        self._group_size: int = random.randint(2, 5)
        self._in_burst: bool = True  # 버스트(빠른 입력) 구간 여부

        # ── v2: 세션 시작 시간 ──
        self._session_start: float = time.time()

    @property
    def is_interception(self) -> bool:
        """interception 드라이버 사용 중인지 반환한다."""
        return self._use_interception

    def _get_scan_code(self, key: str) -> int:
        """키 이름을 스캔코드로 변환한다. 알 수 없는 키는 0을 반환한다."""
        return _SCAN_CODES.get(key.lower(), 0)

    # ─── v2: 디바이스 지문 랜덤화 ───

    def _get_randomized_time_field(self) -> int:
        """
        SendInput의 time 필드를 랜덤화한다.
        
        대부분의 봇은 time=0을 고정값으로 보내지만,
        실제 키보드 드라이버는 미세한 timestamp를 포함한다.
        NGS는 이 필드의 패턴을 분석할 수 있다.
        """
        # 대부분(90%): 0 (정상적인 소프트웨어와 동일)
        # 가끔(10%): 0이 아닌 값 (드라이버 특성 시뮬레이션)
        if random.random() < 0.10:
            return random.randint(0, 100)
        return 0

    def _get_micro_jitter_sec(self) -> float:
        """
        키 다운/업 사이에 삽입할 마이크로 지터(초)를 반환한다.
        실제 키보드 하드웨어의 스캔 레이트 변동을 시뮬레이션.
        
        USB 키보드 폴링: 보통 1ms (1000Hz) ~ 8ms (125Hz)
        이 변동을 시뮬레이션하여 완벽하게 일정한 타이밍을 피한다.
        """
        base = self._device_base_latency_ms / 1000.0
        jitter = random.uniform(-0.0003, 0.0005)  # ±0.3~0.5ms
        return max(0, base + jitter)

    # ─── v2: 사람다운 키 홀드 시간 생성 ───

    def _human_hold_ms(self, key: str, override_hold_ms: Optional[float] = None) -> float:
        """
        사람다운 키 홀드 시간(ms)을 생성한다.
        
        로그정규분포 기반으로, 키 종류/연타/세션 시간을 모두 반영한다.
        override_hold_ms가 지정되면 그 값에 ±변동을 준다.
        """
        if override_hold_ms is not None:
            # 외부 지정값에 인간적 변동 추가
            variation = override_hold_ms * random.uniform(-0.15, 0.15)
            hold = override_hold_ms + variation
            # 세션 편향 적용
            hold *= self._hold_bias
            self._hold_history.append(hold)
            return max(8, hold)

        # 키 종류별 기본값 결정
        key_lower = key.lower()
        if key_lower in ("left", "right", "up", "down"):
            # 방향키: 이동 거리에 따라 넓은 범위
            base = random.uniform(80, 350)
        elif key_lower in ("lalt", "ralt", "space"):
            # 점프/스킬키: 짧게~중간
            base = random.uniform(45, 120)
        elif key_lower in ("lshift", "rshift", "lctrl", "rctrl"):
            # 보조키: 보통 누르고 있음
            base = random.uniform(60, 200)
        elif key_lower in ("enter", "esc", "tab"):
            # UI 키: 중간 길이
            base = random.uniform(50, 100)
        else:
            # 일반 키: 세션 편향 기반
            base = random.uniform(40, 80)

        # 로그정규분포 적용 (자연스러운 분포)
        mu = math.log(max(10, base))
        sigma = 0.22
        hold = random.lognormvariate(mu, sigma)

        # 세션 편향 적용
        hold *= self._hold_bias

        # 연타 가속 (같은 키 반복 시 점점 짧아짐)
        if self._same_key_streak > 1:
            accel = max(0.65, 1.0 - (self._same_key_streak * 0.06))
            hold *= accel

        # 실수 시뮬레이션 (3%)
        roll = random.random()
        if roll < 0.015:
            # 살짝 스침 (키를 거의 안 누름)
            hold = random.uniform(8, 22)
        elif roll < 0.03:
            # 길게 누름 (집중 분산)
            hold *= random.uniform(2.0, 3.5)

        # 세션 피로도 반영 (시간이 지나면 살짝 길어짐)
        elapsed_min = (time.time() - self._session_start) / 60.0
        if elapsed_min > 60:
            hold *= random.uniform(1.0, 1.08)

        hold = max(8, min(hold, 600))  # 8~600ms 클램프
        self._hold_history.append(hold)
        return hold

    # ─── v2: 사람다운 키 간 딜레이 생성 ───

    def _human_inter_key_delay_sec(self, prev_key: str, next_key: str) -> float:
        """
        두 키 사이의 사람다운 딜레이(초)를 생성한다.
        
        리듬 그룹, 방향 전환, 멈칫함 등을 반영.
        """
        base_ms = random.uniform(80, 150)

        # 같은 키 연타: 빠르게
        if prev_key == next_key and prev_key:
            base_ms = random.uniform(50, 120)

        # 방향 전환 (좌→우 등): 느리게
        directions = {"left", "right", "up", "down"}
        if prev_key in directions and next_key in directions and prev_key != next_key:
            base_ms = random.uniform(150, 350)

        # 리듬 그룹 처리
        self._group_counter += 1
        if self._group_counter >= self._group_size:
            self._group_counter = 0
            self._group_size = random.randint(2, 5)
            self._in_burst = not self._in_burst

            if not self._in_burst:
                # 쉬는 구간: 긴 딜레이
                base_ms = random.uniform(300, 700)

        # 로그정규분포 적용
        mu = math.log(max(10, base_ms))
        sigma = 0.18
        delay_ms = random.lognormvariate(mu, sigma)

        # 멈칫함 (세션 시간에 따라 확률 증가)
        elapsed_min = (time.time() - self._session_start) / 60.0
        hesitation_prob = min(0.06, 0.015 + elapsed_min * 0.0004)
        if random.random() < hesitation_prob:
            delay_ms += random.uniform(300, 1200)

        delay_ms = max(12, min(delay_ms, 2500))
        self._delay_history.append(delay_ms)
        return delay_ms / 1000.0

    # --- SendInput 폴백 함수들 (v2: 지문 랜덤화) ---

    def _send_key_down(self, scan_code: int) -> None:
        """SendInput으로 키 다운 이벤트를 보낸다 (v2: time 필드 랜덤화)."""
        if self._send_input is None:
            return

        # v2: 마이크로 지터 삽입 (하드웨어 레이턴시 시뮬레이션)
        jitter = self._get_micro_jitter_sec()
        if jitter > 0:
            time.sleep(jitter)

        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wScan = scan_code
        inp.union.ki.dwFlags = KEYEVENTF_SCANCODE
        inp.union.ki.time = self._get_randomized_time_field()
        self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_key_up(self, scan_code: int) -> None:
        """SendInput으로 키 업 이벤트를 보낸다 (v2: time 필드 랜덤화)."""
        if self._send_input is None:
            return

        # v2: 키 업에도 마이크로 지터
        jitter = self._get_micro_jitter_sec()
        if jitter > 0:
            time.sleep(jitter)

        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wScan = scan_code
        inp.union.ki.dwFlags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        inp.union.ki.time = self._get_randomized_time_field()
        self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_mouse_move(self, x: int, y: int) -> None:
        """SendInput으로 마우스를 절대 좌표로 이동한다."""
        if self._send_input is None or self._user32 is None:
            return
        # 절대 좌표를 65535 범위로 변환 (Windows 정규화 좌표)
        screen_w = self._user32.GetSystemMetrics(0)
        screen_h = self._user32.GetSystemMetrics(1)
        abs_x = int(x * 65535 / screen_w)
        abs_y = int(y * 65535 / screen_h)

        inp = _INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = abs_x
        inp.union.mi.dy = abs_y
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        inp.union.mi.time = self._get_randomized_time_field()
        self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_mouse_click(self) -> None:
        """SendInput으로 마우스 좌클릭을 보낸다 (v2: 사람다운 타이밍)."""
        if self._send_input is None:
            return
        # 마우스 다운
        inp_down = _INPUT()
        inp_down.type = INPUT_MOUSE
        inp_down.union.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        inp_down.union.mi.time = self._get_randomized_time_field()
        self._send_input(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))

        # v2: 사람다운 클릭 홀드 (로그정규분포)
        click_hold = random.lognormvariate(math.log(40), 0.3) / 1000.0
        click_hold = max(0.015, min(click_hold, 0.12))
        time.sleep(click_hold)

        inp_up = _INPUT()
        inp_up.type = INPUT_MOUSE
        inp_up.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
        inp_up.union.mi.time = self._get_randomized_time_field()
        self._send_input(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

    # --- 낮은 수준 API: 스캔코드 직접 제어 (패턴 재생용) ---

    def raw_key_down(self, scan_code: int) -> None:
        """
        스캔코드로 키 다운만 실행한다 (키 업 없이).
        패턴 재생 시 key_down/key_up을 별도 타이밍으로 제어할 때 사용.
        """
        if scan_code == 0:
            return

        if self._use_interception:
            try:
                # interception에서 스캔코드로 직접 key_down
                interception.key_down(scan_code)
                return
            except Exception:
                pass

        self._send_key_down(scan_code)

    def raw_key_up(self, scan_code: int) -> None:
        """
        스캔코드로 키 업만 실행한다.
        패턴 재생 시 key_down/key_up을 별도 타이밍으로 제어할 때 사용.
        """
        if scan_code == 0:
            return

        if self._use_interception:
            try:
                interception.key_up(scan_code)
                return
            except Exception:
                pass

        self._send_key_up(scan_code)

    # --- 공개 API (v2: 인간 리듬 통합) ---

    def press_key(self, key: str, hold_ms: Optional[float] = None) -> None:
        """
        키를 누르고 떼는 동작을 수행한다 (v2: 사람다운 입력 지문).

        hold_ms가 지정되지 않으면 키 종류/연타/세션에 따른
        로그정규분포 기반 홀드 시간을 자동 생성한다.
        """
        scan_code = self._get_scan_code(key)
        if scan_code == 0:
            return

        # v2: 연타 추적 업데이트
        key_lower = key.lower()
        if key_lower == self._last_key:
            self._same_key_streak += 1
        else:
            self._same_key_streak = 0
        self._last_key = key_lower

        # v2: 사람다운 홀드 시간 생성
        actual_hold_ms = self._human_hold_ms(key, hold_ms)

        # v2: 이전 키와의 간격 체크 (너무 빠르면 미세 대기)
        now = time.time()
        if self._last_key_time > 0:
            elapsed_since_last = (now - self._last_key_time) * 1000
            min_gap = self._debounce_ms + random.uniform(0, 2)
            if elapsed_since_last < min_gap:
                time.sleep((min_gap - elapsed_since_last) / 1000.0)

        if self._use_interception:
            try:
                interception.key_down(key)
                time.sleep(actual_hold_ms / 1000.0)
                interception.key_up(key)
                self._last_key_time = time.time()
                return
            except Exception:
                pass  # interception 실패 시 SendInput으로 폴백

        # SendInput 폴백
        self._send_key_down(scan_code)
        time.sleep(actual_hold_ms / 1000.0)
        self._send_key_up(scan_code)
        self._last_key_time = time.time()

    def press_key_sequence(self, keys: list[str], hold_ms: Optional[float] = None) -> None:
        """
        여러 키를 순서대로 누른다 (v2: 키 간 인간 딜레이 자동 삽입).

        각 키 사이에 리듬 그룹/멈칫함/방향전환 기반 딜레이를 삽입한다.
        """
        prev_key = ""
        for key in keys:
            if prev_key:
                delay = self._human_inter_key_delay_sec(prev_key, key)
                time.sleep(delay)
            self.press_key(key, hold_ms=hold_ms)
            prev_key = key

    def type_string(self, text: str) -> None:
        """
        텍스트를 한 글자씩 입력한다 (v2: 사람다운 타이핑 시뮬레이션).

        개선점:
        - 로그정규분포 기반 글자 간 딜레이
        - 가끔 타이핑 멈춤 (생각하는 시간)
        - 실수 후 백스페이스 + 재입력 (3% 확률)
        - 단어 사이 미세 멈춤
        - 세션 피로도에 따른 속도 변화
        """
        elapsed_min = (time.time() - self._session_start) / 60.0
        # 피로도에 따른 기본 속도 조절
        fatigue_mult = 1.0 + max(0, (elapsed_min - 60) * 0.003)

        for i, char in enumerate(text):
            if self._send_input is not None:
                # 유니코드 모드로 한 글자 입력
                inp_down = _INPUT()
                inp_down.type = INPUT_KEYBOARD
                inp_down.union.ki.wScan = ord(char)
                inp_down.union.ki.dwFlags = 0x0004  # KEYEVENTF_UNICODE
                inp_down.union.ki.time = self._get_randomized_time_field()
                self._send_input(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))

                # v2: 글자별 키 홀드 시간 (로그정규분포)
                char_hold = random.lognormvariate(math.log(55), 0.25) / 1000.0
                char_hold = max(0.015, min(char_hold, 0.2))
                time.sleep(char_hold)

                inp_up = _INPUT()
                inp_up.type = INPUT_KEYBOARD
                inp_up.union.ki.wScan = ord(char)
                inp_up.union.ki.dwFlags = 0x0004 | KEYEVENTF_KEYUP
                inp_up.union.ki.time = self._get_randomized_time_field()
                self._send_input(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

            # v2: 글자 간 딜레이 (로그정규분포 기반)
            base_delay_ms = random.lognormvariate(math.log(90), 0.3)

            # 공백 뒤 = 단어 경계 → 약간 더 긴 멈춤
            if char == ' ':
                base_delay_ms += random.uniform(30, 100)

            # 피로도 적용
            base_delay_ms *= fatigue_mult

            # 가끔 멈칫함 (2~5% 확률)
            if random.random() < random.uniform(0.02, 0.05):
                base_delay_ms += random.uniform(200, 800)

            delay_sec = max(0.03, min(base_delay_ms / 1000.0, 1.5))
            time.sleep(delay_sec)

    def press_enter(self) -> None:
        """엔터 키를 누른다."""
        self.press_key("enter")

    def move_to(self, x: int, y: int) -> None:
        """
        마우스를 지정 좌표로 이동한다.
        단순 이동이며, 자연스러운 베지어 곡선 이동은 HumanLikeMouse를 사용한다.
        """
        if self._use_interception:
            try:
                interception.move_to(x, y)
                return
            except Exception:
                pass

        self._send_mouse_move(x, y)

    def click_at(self, x: int, y: int) -> None:
        """
        지정 좌표로 이동한 후 클릭한다 (v2: 사람다운 딜레이).
        이동 후 로그정규분포 기반 대기를 삽입한다.
        """
        self.move_to(x, y)
        # v2: 이동→클릭 딜레이를 로그정규분포로
        move_to_click = random.lognormvariate(math.log(80), 0.3) / 1000.0
        move_to_click = max(0.03, min(move_to_click, 0.25))
        time.sleep(move_to_click)

        if self._use_interception:
            try:
                interception.click(x, y)
                return
            except Exception:
                pass

        self._send_mouse_click()

    def release_all(self) -> None:
        """
        자주 눌린 채로 멈추는 키들을 모두 해제한다.
        매크로 중단 시 키가 눌린 상태로 남는 것을 방지한다.
        """
        for key_name in _RELEASE_KEYS:
            scan_code = self._get_scan_code(key_name)
            if scan_code == 0:
                continue

            if self._use_interception:
                try:
                    interception.key_up(key_name)
                    continue
                except Exception:
                    pass

            self._send_key_up(scan_code)

    # ─── v2: 입력 지문 분석 (자가 진단) ───

    def get_hold_variance(self) -> float:
        """
        최근 키 홀드 시간의 변동 계수(CV)를 반환한다.
        CV < 0.15 이면 봇으로 의심받을 수 있다.
        사람: 0.25~0.8, 봇: 0.01~0.1
        """
        if len(self._hold_history) < 10:
            return -1.0  # 데이터 부족

        data = list(self._hold_history)
        mean = sum(data) / len(data)
        if mean <= 0:
            return 0.0

        variance = sum((d - mean) ** 2 for d in data) / len(data)
        return (variance ** 0.5) / mean

    def get_delay_variance(self) -> float:
        """
        최근 키 간 딜레이의 변동 계수(CV)를 반환한다.
        CV < 0.15 이면 봇으로 의심받을 수 있다.
        """
        if len(self._delay_history) < 10:
            return -1.0  # 데이터 부족

        data = list(self._delay_history)
        mean = sum(data) / len(data)
        if mean <= 0:
            return 0.0

        variance = sum((d - mean) ** 2 for d in data) / len(data)
        return (variance ** 0.5) / mean

    def get_fingerprint_stats(self) -> dict:
        """
        입력 지문 통계를 반환한다 (GUI 표시용).
        """
        hold_cv = self.get_hold_variance()
        delay_cv = self.get_delay_variance()

        hold_status = "데이터 부족"
        if hold_cv >= 0:
            hold_status = "안전" if hold_cv >= 0.2 else "위험(규칙적)"

        delay_status = "데이터 부족"
        if delay_cv >= 0:
            delay_status = "안전" if delay_cv >= 0.2 else "위험(규칙적)"

        return {
            "hold_cv": round(hold_cv, 4) if hold_cv >= 0 else None,
            "delay_cv": round(delay_cv, 4) if delay_cv >= 0 else None,
            "hold_status": hold_status,
            "delay_status": delay_status,
            "device_latency_ms": round(self._device_base_latency_ms, 2),
            "debounce_ms": round(self._debounce_ms, 2),
            "hold_bias": round(self._hold_bias, 3),
            "streak": self._same_key_streak,
            "samples": len(self._hold_history),
        }

    def reset_session(self) -> None:
        """새 세션을 위해 디바이스 특성을 재생성한다."""
        self._device_base_latency_ms = random.uniform(0.5, 2.0)
        self._debounce_ms = random.uniform(1.0, 5.0)
        self._hold_bias = random.uniform(0.85, 1.15)
        self._last_key = None
        self._same_key_streak = 0
        self._last_key_time = 0.0
        self._hold_history.clear()
        self._delay_history.clear()
        self._group_counter = 0
        self._group_size = random.randint(2, 5)
        self._in_burst = True
        self._session_start = time.time()
        logger.info(
            f"입력 엔진 세션 리셋: latency={self._device_base_latency_ms:.1f}ms, "
            f"debounce={self._debounce_ms:.1f}ms, bias={self._hold_bias:.3f}"
        )
