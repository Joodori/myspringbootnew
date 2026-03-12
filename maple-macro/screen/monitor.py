"""
화면 모니터 모듈 - 게임 화면 캡처, 템플릿 매칭, 변화 감지, 룬 화살표 인식을 담당한다.
mss 라이브러리로 고속 화면 캡처를 수행하고, OpenCV로 이미지 처리를 한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    import cv2
    import numpy as np
    from numpy.typing import NDArray
except ImportError:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

try:
    import mss
except ImportError:
    mss = None  # type: ignore[assignment]


@dataclass
class TemplateInfo:
    """등록된 템플릿 이미지 정보"""
    name: str                           # 템플릿 이름
    image: Optional[NDArray] = None     # 템플릿 이미지 (numpy 배열)
    precision: float = 0.85             # 매칭 임계값 (0~1)


@dataclass
class MatchResult:
    """템플릿 매칭 결과"""
    found: bool = False       # 매칭 성공 여부
    x: int = 0                # 매칭 위치 X 좌표 (중심)
    y: int = 0                # 매칭 위치 Y 좌표 (중심)
    confidence: float = 0.0   # 매칭 신뢰도
    scale: float = 1.0        # 매칭된 스케일 (멀티스케일 사용 시)


class ScreenMonitor:
    """
    게임 화면 캡처 및 분석 엔진.
    - mss로 고속 화면 캡처
    - 템플릿 매칭으로 특정 UI 요소 탐지
    - 프레임 차이 분석으로 팝업/변화 감지
    - HSV 분석으로 룬 화살표 방향 인식
    """

    def __init__(self, game_region: Optional[dict] = None) -> None:
        """
        화면 모니터를 초기화한다.
        game_region: {"left": x, "top": y, "width": w, "height": h} 형식의 캡처 영역
                     None이면 전체 화면을 캡처한다.
        """
        self._sct = mss.mss() if mss is not None else None
        self._game_region = game_region
        self._templates: dict[str, TemplateInfo] = {}
        self._prev_frame: Optional[NDArray] = None

    def capture(self) -> Optional[NDArray]:
        """
        게임 화면을 캡처하여 numpy 배열(BGR)로 반환한다.
        캡처 실패 시 None을 반환한다.
        """
        if self._sct is None or np is None:
            return None

        try:
            if self._game_region:
                monitor = self._game_region
            else:
                # 전체 주 모니터 캡처
                monitor = self._sct.monitors[1]

            screenshot = self._sct.grab(monitor)
            # BGRA → BGR 변환 (OpenCV 표준 형식)
            frame = np.array(screenshot)[:, :, :3]
            return frame
        except Exception:
            return None

    def capture_gray(self) -> Optional[NDArray]:
        """화면을 캡처하여 그레이스케일로 반환한다."""
        frame = self.capture()
        if frame is None or cv2 is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def register_template(
        self, name: str, image_path: str, precision: float = 0.85
    ) -> bool:
        """
        템플릿 이미지를 등록한다.
        name: 템플릿 식별 이름
        image_path: 템플릿 이미지 파일 경로
        precision: 매칭 임계값 (높을수록 정확한 매칭 요구)
        """
        if cv2 is None:
            return False
        if not os.path.exists(image_path):
            return False

        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False

        self._templates[name] = TemplateInfo(
            name=name, image=img, precision=precision
        )
        return True

    def find_template(
        self, name: str, screen: Optional[NDArray] = None
    ) -> MatchResult:
        """
        등록된 템플릿을 화면에서 찾는다.
        먼저 원본 크기로 매칭을 시도하고, 실패하면 멀티스케일 매칭으로 폴백한다.
        반환: MatchResult (found, x, y, confidence, scale)
        """
        if cv2 is None or np is None:
            return MatchResult()

        template_info = self._templates.get(name)
        if template_info is None or template_info.image is None:
            return MatchResult()

        # 화면 캡처 (제공되지 않은 경우)
        if screen is None:
            screen = self.capture_gray()
        elif len(screen.shape) == 3:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        if screen is None:
            return MatchResult()

        template = template_info.image
        precision = template_info.precision

        # 1차: 원본 크기 매칭 시도
        result = self._match_at_scale(screen, template, 1.0)
        if result.confidence >= precision:
            result.found = True
            return result

        # 2차: 멀티스케일 매칭 (0.7~1.3 범위, 0.1 간격)
        best_result = result
        for scale in [0.7, 0.8, 0.9, 1.1, 1.2, 1.3]:
            scaled_result = self._match_at_scale(screen, template, scale)
            if scaled_result.confidence > best_result.confidence:
                best_result = scaled_result

        if best_result.confidence >= precision:
            best_result.found = True
        return best_result

    def _match_at_scale(
        self, screen: NDArray, template: NDArray, scale: float
    ) -> MatchResult:
        """지정 스케일로 템플릿 매칭을 수행한다."""
        if cv2 is None or np is None:
            return MatchResult()

        # 스케일 적용
        if scale != 1.0:
            h, w = template.shape[:2]
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resized = cv2.resize(template, (new_w, new_h))
        else:
            resized = template

        # 템플릿이 화면보다 큰 경우 스킵
        if (resized.shape[0] > screen.shape[0] or
                resized.shape[1] > screen.shape[1]):
            return MatchResult()

        # 정규화 상관관계 매칭
        match = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match)

        # 매칭 위치의 중심 좌표 계산
        h, w = resized.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2

        return MatchResult(
            found=False,
            x=center_x,
            y=center_y,
            confidence=float(max_val),
            scale=scale,
        )

    def detect_screen_change(
        self, threshold: int = 20, min_area: int = 1000
    ) -> bool:
        """
        이전 프레임과 비교하여 화면 변화(팝업 등)를 감지한다.
        threshold: 픽셀 변화 감지 임계값
        min_area: 변화 영역의 최소 면적 (노이즈 필터링)
        반환: 유의미한 화면 변화가 감지되면 True
        """
        if cv2 is None or np is None:
            return False

        current = self.capture_gray()
        if current is None:
            return False

        if self._prev_frame is None:
            self._prev_frame = current
            return False

        # 이전 프레임과 크기가 다르면 비교 불가
        if self._prev_frame.shape != current.shape:
            self._prev_frame = current
            return False

        # 프레임 차이 계산
        diff = cv2.absdiff(self._prev_frame, current)
        # 임계값 적용하여 이진화
        _, thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)

        # 변화 영역의 총 면적 계산
        changed_area = cv2.countNonZero(thresh)

        # 이전 프레임 갱신
        self._prev_frame = current

        # 최소 면적 이상의 변화가 있으면 True
        return changed_area >= min_area

    def detect_rune_arrows(
        self, region: Optional[dict] = None
    ) -> list[str]:
        """
        룬 화살표 방향을 감지한다.
        HSV 색공간에서 빨간→초록 그라데이션을 분석하여 화살표 방향을 인식한다.
        반환: 화살표 방향 리스트 (예: ['up', 'left', 'down', 'right'])
        """
        if cv2 is None or np is None:
            return []

        frame = self.capture()
        if frame is None:
            return []

        # 관심 영역(ROI) 추출 - 룬 UI가 표시되는 영역
        if region:
            x, y = region.get("left", 0), region.get("top", 0)
            w, h = region.get("width", 200), region.get("height", 80)
            roi = frame[y:y+h, x:x+w]
        else:
            # 기본: 화면 중앙 상단 영역 (룬 UI 일반 위치)
            h_frame, w_frame = frame.shape[:2]
            cx = w_frame // 2
            roi_w, roi_h = 300, 100
            roi = frame[
                max(0, h_frame // 3 - roi_h):h_frame // 3,
                max(0, cx - roi_w // 2):cx + roi_w // 2,
            ]

        if roi.size == 0:
            return []

        # HSV 변환
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # 빨간색~초록색 범위의 밝은 영역 마스크 (채도 100+, 명도 100+)
        # 룬 화살표는 보통 밝고 채도가 높은 색상이다
        mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([80, 255, 255]))

        # 윤곽선 검출
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 윤곽선을 x 좌표 기준으로 정렬 (왼쪽→오른쪽)
        arrow_regions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100:  # 너무 작은 영역 무시
                continue
            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            arrow_regions.append((x_c, y_c, w_c, h_c))

        arrow_regions.sort(key=lambda r: r[0])

        # 각 화살표 영역의 방향 판별 (종횡비 및 무게중심 기반)
        directions: list[str] = []
        for x_r, y_r, w_r, h_r in arrow_regions:
            aspect = w_r / max(h_r, 1)
            # 가로로 긴 형태 → 좌/우
            if aspect > 1.3:
                # 무게중심이 왼쪽에 치우치면 왼쪽, 오른쪽이면 오른쪽
                sub_roi = mask[y_r:y_r+h_r, x_r:x_r+w_r]
                moments = cv2.moments(sub_roi)
                if moments["m00"] > 0:
                    cx_m = moments["m10"] / moments["m00"]
                    if cx_m < w_r / 2:
                        directions.append("left")
                    else:
                        directions.append("right")
                else:
                    directions.append("right")
            # 세로로 긴 형태 → 상/하
            elif aspect < 0.7:
                sub_roi = mask[y_r:y_r+h_r, x_r:x_r+w_r]
                moments = cv2.moments(sub_roi)
                if moments["m00"] > 0:
                    cy_m = moments["m01"] / moments["m00"]
                    if cy_m < h_r / 2:
                        directions.append("up")
                    else:
                        directions.append("down")
                else:
                    directions.append("up")
            else:
                # 정사각형에 가까우면 그래디언트로 판별 시도
                directions.append("up")

        return directions
