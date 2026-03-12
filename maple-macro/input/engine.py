"""
입력 엔진 모듈 - 키보드/마우스 입력을 처리한다.
interception 드라이버가 설치된 경우 하드웨어 레벨 입력을 사용하고,
없으면 ctypes SendInput으로 폴백하여 동작한다.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import random
import time
from typing import Optional

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


class InputEngine:
    """
    키보드/마우스 입력 엔진.
    interception 드라이버가 있으면 하드웨어 레벨 입력을 사용하고,
    없으면 Windows SendInput API로 폴백한다.
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

    @property
    def is_interception(self) -> bool:
        """interception 드라이버 사용 중인지 반환한다."""
        return self._use_interception

    def _get_scan_code(self, key: str) -> int:
        """키 이름을 스캔코드로 변환한다. 알 수 없는 키는 0을 반환한다."""
        return _SCAN_CODES.get(key.lower(), 0)

    # --- SendInput 폴백 함수들 ---

    def _send_key_down(self, scan_code: int) -> None:
        """SendInput으로 키 다운 이벤트를 보낸다."""
        if self._send_input is None:
            return
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wScan = scan_code
        inp.union.ki.dwFlags = KEYEVENTF_SCANCODE
        self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_key_up(self, scan_code: int) -> None:
        """SendInput으로 키 업 이벤트를 보낸다."""
        if self._send_input is None:
            return
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wScan = scan_code
        inp.union.ki.dwFlags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
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
        self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _send_mouse_click(self) -> None:
        """SendInput으로 마우스 좌클릭을 보낸다."""
        if self._send_input is None:
            return
        # 마우스 다운
        inp_down = _INPUT()
        inp_down.type = INPUT_MOUSE
        inp_down.union.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        self._send_input(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))

        # 짧은 랜덤 딜레이 후 마우스 업
        time.sleep(random.uniform(0.02, 0.06))

        inp_up = _INPUT()
        inp_up.type = INPUT_MOUSE
        inp_up.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
        self._send_input(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

    # --- 공개 API ---

    def press_key(self, key: str, hold_ms: Optional[float] = None) -> None:
        """
        키를 누르고 떼는 동작을 수행한다.
        hold_ms가 지정되지 않으면 30~80ms 사이의 랜덤 홀드 시간을 사용한다.
        사람의 키 누르기를 자연스럽게 시뮬레이션한다.
        """
        scan_code = self._get_scan_code(key)
        if scan_code == 0:
            return

        if hold_ms is None:
            hold_ms = random.uniform(30, 80)

        if self._use_interception:
            try:
                interception.key_down(key)
                time.sleep(hold_ms / 1000.0)
                interception.key_up(key)
                return
            except Exception:
                pass  # interception 실패 시 SendInput으로 폴백

        # SendInput 폴백
        self._send_key_down(scan_code)
        time.sleep(hold_ms / 1000.0)
        self._send_key_up(scan_code)

    def type_string(self, text: str) -> None:
        """
        텍스트를 한 글자씩 입력한다.
        각 글자 사이에 50~150ms의 랜덤 딜레이를 넣어 타이핑을 시뮬레이션한다.
        한글 입력은 SendInput의 유니코드 모드를 사용한다.
        """
        for char in text:
            if self._send_input is not None:
                # 유니코드 모드로 한 글자 입력
                inp_down = _INPUT()
                inp_down.type = INPUT_KEYBOARD
                inp_down.union.ki.wScan = ord(char)
                inp_down.union.ki.dwFlags = 0x0004  # KEYEVENTF_UNICODE
                self._send_input(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))

                inp_up = _INPUT()
                inp_up.type = INPUT_KEYBOARD
                inp_up.union.ki.wScan = ord(char)
                inp_up.union.ki.dwFlags = 0x0004 | KEYEVENTF_KEYUP
                self._send_input(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

            # 타이핑 속도 변동 - 사람처럼 불규칙하게
            time.sleep(random.uniform(0.05, 0.15))

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
        지정 좌표로 이동한 후 클릭한다.
        이동 후 50~150ms 대기하여 자연스러운 클릭을 시뮬레이션한다.
        """
        self.move_to(x, y)
        time.sleep(random.uniform(0.05, 0.15))

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
