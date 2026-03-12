"""
알림 처리 모듈 - 게임 내 각종 알림(캡차, 룬, 감지기 등)을 감지하고 처리한다.
자동 풀이가 가능한 알림은 즉시 처리하고, 수동 알림은 사용자에게 통보한다.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from input.engine import InputEngine
    from screen.monitor import ScreenMonitor
    from solver.text_captcha import TextCaptchaSolver
    from solver.rune_solver import RuneSolver

# 사운드 알림 (Windows winsound 사용)
try:
    import winsound
    _WINSOUND_AVAILABLE = True
except ImportError:
    _WINSOUND_AVAILABLE = False


class AlertHandler:
    """
    게임 내 알림 감지 및 처리 엔진.
    - 텍스트 캡차: OCR 인식 후 자동 입력
    - 클릭 감지기: 화면 변화 감지 후 클릭
    - 룬: 화살표 감지 후 방향키 입력
    - 수동 알림: 사운드로 사용자에게 통보
    """

    def __init__(
        self,
        screen_monitor: ScreenMonitor,
        input_engine: InputEngine,
        text_solver: TextCaptchaSolver,
        rune_solver: RuneSolver,
    ) -> None:
        """의존 모듈들을 주입받는다."""
        self._screen = screen_monitor
        self._input = input_engine
        self._text_solver = text_solver
        self._rune_solver = rune_solver

    def handle_text_captcha(self) -> bool:
        """
        텍스트 캡차를 처리한다.
        1. 캡차 영역을 캡처한다.
        2. OCR로 텍스트를 인식한다.
        3. 인식된 텍스트를 입력하고 엔터를 누른다.
        반환: 처리 성공 여부
        """
        # 화면 캡처
        frame = self._screen.capture()
        if frame is None:
            return False

        try:
            import numpy as np
        except ImportError:
            return False

        # 캡차 영역 추출 (화면 중앙 부근 - 일반적인 캡차 위치)
        h, w = frame.shape[:2]
        # 캡차 대화상자는 보통 화면 중앙에 표시된다
        region_x = w // 4
        region_y = h // 3
        region_w = w // 2
        region_h = h // 6
        captcha_region = frame[
            region_y:region_y + region_h,
            region_x:region_x + region_w,
        ]

        # OCR 인식
        text = self._text_solver.recognize_text(captcha_region)
        if not text:
            return False

        # 인식된 텍스트 입력 전 짧은 대기
        time.sleep(random.uniform(0.3, 0.8))

        # 텍스트 입력
        self._input.type_string(text)
        time.sleep(random.uniform(0.1, 0.3))

        # 엔터 키 입력
        self._input.press_enter()

        return True

    def handle_click_detector(self, click_count: int = 5) -> bool:
        """
        클릭 감지기를 처리한다.
        화면 변화를 감지하여 변화가 발생한 위치를 클릭한다.
        click_count: 클릭 횟수 (기본 5회)
        반환: 처리 성공 여부
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return False

        # 기준 프레임 캡처
        base_frame = self._screen.capture_gray()
        if base_frame is None:
            return False

        # 잠시 대기 후 새 프레임 캡처하여 차이 분석
        time.sleep(0.5)
        new_frame = self._screen.capture_gray()
        if new_frame is None:
            return False

        # 프레임 차이 계산
        diff = cv2.absdiff(base_frame, new_frame)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

        # 변화 영역의 중심 좌표 찾기
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return False

        # 가장 큰 변화 영역의 중심을 클릭 대상으로 설정
        largest = max(contours, key=cv2.contourArea)
        moments = cv2.moments(largest)
        if moments["m00"] == 0:
            return False

        target_x = int(moments["m10"] / moments["m00"])
        target_y = int(moments["m01"] / moments["m00"])

        # 지정 횟수만큼 클릭 (랜덤 딜레이 포함)
        for i in range(click_count):
            # 클릭 위치에 약간의 변동 추가 (같은 픽셀만 반복 클릭 방지)
            offset_x = target_x + random.randint(-5, 5)
            offset_y = target_y + random.randint(-5, 5)
            self._input.click_at(offset_x, offset_y)
            time.sleep(random.uniform(0.15, 0.4))

        return True

    def handle_rune(self) -> bool:
        """
        룬을 처리한다.
        화면에서 화살표 방향을 감지하고 순서대로 입력한다.
        반환: 처리 성공 여부
        """
        # 화살표 방향 감지
        arrows = self._screen.detect_rune_arrows()
        if not arrows:
            return False

        # 룬 풀이 시작 전 짧은 대기 (자연스러운 반응 시간)
        time.sleep(random.uniform(0.5, 1.0))

        # 화살표 키 입력
        return self._rune_solver.solve(arrows, self._input)

    def notify_user(self, message: str) -> None:
        """
        사용자에게 알림을 보낸다.
        현재는 Windows 비프음을 사용하며, 디스코드 웹훅은 향후 지원 예정이다.
        """
        # Windows 비프음 알림 (3회 반복)
        if _WINSOUND_AVAILABLE:
            for _ in range(3):
                try:
                    winsound.Beep(1000, 300)  # 1000Hz, 300ms
                    time.sleep(0.2)
                except Exception:
                    break

        # TODO: 디스코드 웹훅 알림 구현
        # webhook_url = Config().get('alerts.discord_webhook')
        # if webhook_url:
        #     requests.post(webhook_url, json={'content': message})
