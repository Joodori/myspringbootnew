"""
패턴 이벤트 데이터 모듈 - 기록된 키보드 이벤트를 저장하는 데이터 클래스.
패턴 녹화/재생의 기본 단위이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PatternEvent:
    """
    단일 키보드 이벤트를 나타내는 데이터 클래스.
    녹화 시 기록되며, 재생 시 타임스탬프 간격에 따라 순서대로 실행된다.
    """
    event_type: str    # 이벤트 타입: 'key_down' 또는 'key_up'
    key_code: int      # 가상 키 코드 (VK_*)
    scan_code: int     # 하드웨어 스캔 코드
    timestamp: float   # 이벤트 발생 시각 (ms 단위, 녹화 시작 기준 상대값)

    def __repr__(self) -> str:
        """디버깅용 문자열 표현."""
        return (
            f"PatternEvent({self.event_type}, "
            f"key=0x{self.key_code:02X}, "
            f"scan=0x{self.scan_code:02X}, "
            f"t={self.timestamp:.1f}ms)"
        )

    @property
    def is_key_down(self) -> bool:
        """키 다운 이벤트인지 반환한다."""
        return self.event_type == "key_down"

    @property
    def is_key_up(self) -> bool:
        """키 업 이벤트인지 반환한다."""
        return self.event_type == "key_up"

    @property
    def delay_from(self) -> float:
        """타임스탬프를 초 단위로 변환하여 반환한다."""
        return self.timestamp / 1000.0
