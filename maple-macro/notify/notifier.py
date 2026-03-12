"""
알림 모듈 - 사운드 및 외부 알림을 관리한다.
이벤트 종류에 따라 다른 비프음을 재생하고, 향후 디스코드 웹훅 등을 지원한다.
"""

from __future__ import annotations

from typing import Optional

# Windows winsound 사용 시도 - 비프음 재생용
try:
    import winsound
    _WINSOUND_AVAILABLE = True
except ImportError:
    _WINSOUND_AVAILABLE = False


# 이벤트별 사운드 설정 (주파수 Hz, 지속시간 ms, 반복 횟수)
_SOUND_PROFILES: dict[str, tuple[int, int, int]] = {
    "alert": (1000, 300, 3),      # 일반 알림 - 중간 음, 3회
    "captcha": (1500, 200, 5),    # 캡차 감지 - 높은 음, 5회 (긴급)
    "rune": (800, 400, 2),        # 룬 감지 - 낮은 음, 2회
    "error": (500, 500, 4),       # 오류 발생 - 매우 낮은 음, 4회
    "session_end": (600, 1000, 1), # 세션 종료 - 긴 단일음
    "manual_alert": (2000, 150, 6), # 수동 처리 필요 - 급한 높은 음, 6회
}


class Notifier:
    """
    알림 관리 클래스.
    사운드 알림을 기본으로 하며, 디스코드 웹훅은 플레이스홀더로 제공한다.
    """

    def __init__(self, discord_webhook_url: Optional[str] = None) -> None:
        """
        알림기를 초기화한다.
        discord_webhook_url: 디스코드 웹훅 URL (향후 지원)
        """
        self._webhook_url = discord_webhook_url

    def play_sound(self, sound_type: str = "alert") -> None:
        """
        지정된 타입의 사운드를 재생한다.
        sound_type: 'alert', 'captcha', 'rune', 'error', 'session_end', 'manual_alert'
        """
        if not _WINSOUND_AVAILABLE:
            return

        profile = _SOUND_PROFILES.get(sound_type, _SOUND_PROFILES["alert"])
        freq, duration, repeat = profile

        for _ in range(repeat):
            try:
                winsound.Beep(freq, duration)
            except Exception:
                break

    def notify(self, message: str, method: str = "sound") -> None:
        """
        메시지를 지정된 방법으로 알린다.
        method: 'sound' (기본), 'discord' (향후 지원)
        """
        if method == "sound":
            self.play_sound("alert")
        elif method == "discord":
            self._send_discord(message)
        else:
            # 알 수 없는 방법이면 사운드로 폴백
            self.play_sound("alert")

    def _send_discord(self, message: str) -> None:
        """
        디스코드 웹훅으로 메시지를 전송한다.
        현재는 플레이스홀더이며, requests 설치 시 동작한다.
        """
        if not self._webhook_url:
            # 웹훅 URL 미설정 시 사운드로 폴백
            self.play_sound("alert")
            return

        try:
            import requests
            requests.post(
                self._webhook_url,
                json={"content": f"[메이플 매크로] {message}"},
                timeout=5,
            )
        except Exception:
            # 전송 실패 시 사운드로 폴백
            self.play_sound("error")
