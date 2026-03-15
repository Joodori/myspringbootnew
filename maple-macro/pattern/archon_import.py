"""
Archon AK47 매크로 XML 파일을 PatternEvent 리스트로 변환하는 모듈.

Archon XML 형식:
  <item desc="Alt" type="2" value="164" delay_time="112"/>
  - type="2": Key Down, type="3": Key Up
  - value: Windows Virtual Key Code (VK_*)
  - delay_time: 이전 이벤트로부터의 딜레이 (ms)

변환 과정:
  1. XML 파싱 → (event_type, vk_code, delay_ms) 리스트
  2. VK 코드 → Set 1 스캔코드 변환
  3. delay_time을 누적 timestamp로 변환
  4. (옵션) 패턴 시작 전 위치 보정 시퀀스 삽입
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from typing import Optional

from pattern.event import PatternEvent

logger = logging.getLogger(__name__)


# ── Windows Virtual Key Code → Set 1 스캔코드 매핑 ──
# Archon XML의 value 필드는 VK 코드를 사용한다.
# 우리 재생 엔진은 스캔코드를 사용하므로 변환이 필요하다.
_VK_TO_SCAN: dict[int, int] = {
    # 방향키
    0x25: 0x4B,  # VK_LEFT
    0x26: 0x48,  # VK_UP
    0x27: 0x4D,  # VK_RIGHT
    0x28: 0x50,  # VK_DOWN

    # 보조키
    0xA0: 0x2A,  # VK_LSHIFT
    0xA1: 0x36,  # VK_RSHIFT
    0x10: 0x2A,  # VK_SHIFT → LShift
    0xA2: 0x1D,  # VK_LCONTROL
    0xA3: 0x1D,  # VK_RCONTROL
    0x11: 0x1D,  # VK_CONTROL → LCtrl
    0xA4: 0x38,  # VK_LMENU (LAlt)
    0xA5: 0x38,  # VK_RMENU (RAlt)
    0x12: 0x38,  # VK_MENU → LAlt

    # 기능키
    0x0D: 0x1C,  # VK_RETURN (Enter)
    0x20: 0x39,  # VK_SPACE
    0x1B: 0x01,  # VK_ESCAPE
    0x09: 0x0F,  # VK_TAB
    0x08: 0x0E,  # VK_BACK (Backspace)
    0x14: 0x3A,  # VK_CAPITAL (CapsLock)

    # 특수키
    0x24: 0x47,  # VK_HOME
    0x23: 0x4F,  # VK_END
    0x2D: 0x52,  # VK_INSERT
    0x2E: 0x53,  # VK_DELETE
    0x21: 0x49,  # VK_PRIOR (PageUp)
    0x22: 0x51,  # VK_NEXT (PageDown)

    # 숫자키 (상단)
    0x30: 0x0B,  # 0
    0x31: 0x02,  # 1
    0x32: 0x03,  # 2
    0x33: 0x04,  # 3
    0x34: 0x05,  # 4
    0x35: 0x06,  # 5
    0x36: 0x07,  # 6
    0x37: 0x08,  # 7
    0x38: 0x09,  # 8
    0x39: 0x0A,  # 9

    # 알파벳 (A=0x41 ~ Z=0x5A)
    0x41: 0x1E,  # A
    0x42: 0x30,  # B
    0x43: 0x2E,  # C
    0x44: 0x20,  # D
    0x45: 0x12,  # E
    0x46: 0x21,  # F
    0x47: 0x22,  # G
    0x48: 0x23,  # H
    0x49: 0x17,  # I
    0x4A: 0x24,  # J
    0x4B: 0x25,  # K
    0x4C: 0x26,  # L
    0x4D: 0x32,  # M
    0x4E: 0x31,  # N
    0x4F: 0x18,  # O
    0x50: 0x19,  # P
    0x51: 0x10,  # Q
    0x52: 0x13,  # R
    0x53: 0x1F,  # S
    0x54: 0x14,  # T
    0x55: 0x16,  # U
    0x56: 0x2F,  # V
    0x57: 0x11,  # W
    0x58: 0x2D,  # X
    0x59: 0x15,  # Y
    0x5A: 0x2C,  # Z

    # F키
    0x70: 0x3B,  # VK_F1
    0x71: 0x3C,  # VK_F2
    0x72: 0x3D,  # VK_F3
    0x73: 0x3E,  # VK_F4
    0x74: 0x3F,  # VK_F5
    0x75: 0x40,  # VK_F6
    0x76: 0x41,  # VK_F7
    0x77: 0x42,  # VK_F8
    0x78: 0x43,  # VK_F9
    0x79: 0x44,  # VK_F10
    0x7A: 0x57,  # VK_F11
    0x7B: 0x58,  # VK_F12

    # 넘패드
    0x60: 0x52,  # VK_NUMPAD0
    0x61: 0x4F,  # VK_NUMPAD1
    0x62: 0x50,  # VK_NUMPAD2
    0x63: 0x51,  # VK_NUMPAD3
    0x64: 0x4B,  # VK_NUMPAD4
    0x65: 0x4C,  # VK_NUMPAD5
    0x66: 0x4D,  # VK_NUMPAD6
    0x67: 0x48,  # VK_NUMPAD7
    0x68: 0x49,  # VK_NUMPAD8
    0x69: 0x4A,  # VK_NUMPAD9
}


# ── 스캔코드 역방향 조회 (이름용) ──
_SCAN_TO_NAME: dict[int, str] = {
    0x4B: "left", 0x4D: "right", 0x48: "up", 0x50: "down",
    0x1C: "enter", 0x39: "space", 0x01: "esc", 0x0F: "tab",
    0x2A: "lshift", 0x36: "rshift", 0x1D: "lctrl", 0x38: "lalt",
    0x47: "home", 0x4F: "end", 0x52: "insert", 0x53: "delete",
    0x49: "pageup", 0x51: "pagedown",
}


def parse_archon_xml(file_path: str) -> Optional[list[PatternEvent]]:
    """
    Archon AK47 매크로 XML 파일을 파싱하여 PatternEvent 리스트로 변환한다.

    반환: PatternEvent 리스트. 실패 시 None.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError, OSError) as e:
        logger.error(f"Archon XML 파싱 실패: {e}")
        return None

    # macroinfo에서 이름 추출 (로깅용)
    info = root.find("macroinfo")
    macro_name = info.get("name", "unknown") if info is not None else "unknown"

    items = root.find("macroitems")
    if items is None:
        logger.error("macroitems 요소를 찾을 수 없음")
        return None

    events: list[PatternEvent] = []
    cumulative_ms = 0.0
    skipped = 0

    for item in items.findall("item"):
        desc = item.get("desc", "")
        item_type = item.get("type", "")
        vk_code_str = item.get("value", "0")
        delay_str = item.get("delay_time", "0")

        try:
            vk_code = int(vk_code_str)
            delay_ms = float(delay_str)
        except ValueError:
            skipped += 1
            continue

        # type 변환
        if item_type == "2":
            event_type = "key_down"
        elif item_type == "3":
            event_type = "key_up"
        else:
            skipped += 1
            continue  # 마우스 등 다른 타입은 무시

        # VK → 스캔코드 변환
        scan_code = _VK_TO_SCAN.get(vk_code, 0)
        if scan_code == 0:
            logger.warning(
                f"알 수 없는 VK 코드: 0x{vk_code:02X} ({desc}), 스킵"
            )
            skipped += 1
            continue

        # 누적 타임스탬프 계산
        cumulative_ms += delay_ms

        event = PatternEvent(
            event_type=event_type,
            key_code=vk_code,      # 원본 VK 코드 보존
            scan_code=scan_code,   # 변환된 스캔코드
            timestamp=cumulative_ms,
        )
        events.append(event)

    logger.info(
        f"Archon XML 변환: '{macro_name}' → "
        f"{len(events)}개 이벤트, {skipped}개 스킵, "
        f"총 {cumulative_ms:.0f}ms"
    )

    return events if events else None


def create_position_reset_events(
    direction: str = "left",
    walk_ms: int = 3000,
    base_timestamp: float = 0.0,
) -> list[PatternEvent]:
    """
    캐릭터 위치를 초기화하는 이벤트 시퀀스를 생성한다.

    메이플스토리에서 캐릭터가 매번 같은 위치에서 시작하도록
    맵 끝까지 한 방향으로 걸어간 후 되돌아오는 패턴을 만든다.

    방법: 지정 방향으로 walk_ms만큼 이동 → 맵 끝 벽에 닿음
    → 캐릭터가 벽에 붙어있으면 항상 같은 위치

    direction: "left" 또는 "right"
    walk_ms: 한 방향으로 걸어가는 시간 (ms). 맵 크기에 따라 조절.
    base_timestamp: 시작 타임스탬프 (ms)

    반환: 위치 리셋 PatternEvent 리스트
    """
    scan_codes = {"left": 0x4B, "right": 0x4D}
    sc = scan_codes.get(direction, 0x4B)

    events: list[PatternEvent] = []
    t = base_timestamp

    # 방향키 누르기
    events.append(PatternEvent(
        event_type="key_down",
        key_code=0,
        scan_code=sc,
        timestamp=t,
    ))

    # walk_ms 동안 유지
    t += walk_ms

    # 방향키 떼기
    events.append(PatternEvent(
        event_type="key_up",
        key_code=0,
        scan_code=sc,
        timestamp=t,
    ))

    # 짧은 대기 (벽에 붙은 후 안정화)
    t += 200

    return events


def import_archon_with_position_reset(
    xml_path: str,
    reset_direction: str = "left",
    reset_walk_ms: int = 3000,
) -> Optional[list[PatternEvent]]:
    """
    Archon XML을 임포트하면서 앞에 위치 보정 시퀀스를 삽입한다.

    흐름:
    1. 위치 보정: 맵 끝으로 이동하여 시작점 고정
    2. Archon 매크로 재생: 녹화된 사냥 루틴 실행

    반환: [위치 보정 이벤트들 + Archon 매크로 이벤트들]
    """
    # Archon 매크로 이벤트 파싱
    macro_events = parse_archon_xml(xml_path)
    if not macro_events:
        return None

    # 위치 보정 비활성화면 (walk_ms <= 0) 바로 반환
    if reset_walk_ms <= 0:
        return macro_events

    # 위치 보정 이벤트 생성
    reset_events = create_position_reset_events(
        direction=reset_direction,
        walk_ms=reset_walk_ms,
        base_timestamp=0.0,
    )

    if not reset_events:
        return macro_events

    # 위치 보정 마지막 타임스탬프 확인
    reset_end_ms = reset_events[-1].timestamp

    # Archon 이벤트의 타임스탬프를 위치 보정 이후로 시프트
    shifted_events: list[PatternEvent] = []
    for ev in macro_events:
        shifted = PatternEvent(
            event_type=ev.event_type,
            key_code=ev.key_code,
            scan_code=ev.scan_code,
            timestamp=ev.timestamp + reset_end_ms,
        )
        shifted_events.append(shifted)

    combined = reset_events + shifted_events

    logger.info(
        f"위치 보정 + Archon 매크로 병합: "
        f"보정 {len(reset_events)}개 + 매크로 {len(shifted_events)}개 = "
        f"총 {len(combined)}개 이벤트, "
        f"{combined[-1].timestamp:.0f}ms"
    )

    return combined
