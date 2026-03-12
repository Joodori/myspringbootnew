"""
사람과 유사한 마우스 이동 모듈 - 베지어 곡선을 이용한 자연스러운 마우스 궤적 생성.
직선이 아닌 곡선 경로와 불규칙한 이징으로 봇 탐지를 회피한다.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import math
import random
import time
from typing import Optional

from input.engine import InputEngine


class HumanLikeMouse:
    """
    베지어 곡선 기반 마우스 이동 엔진.
    - 랜덤 제어점으로 자연스러운 곡선 경로를 생성한다.
    - 가우시안 노이즈가 포함된 이징으로 속도 변화를 시뮬레이션한다.
    """

    def __init__(self, input_engine: InputEngine) -> None:
        """입력 엔진 의존성을 주입받는다."""
        self._engine = input_engine

    def _get_cursor_pos(self) -> tuple[int, int]:
        """현재 마우스 커서 위치를 반환한다. Windows API를 사용한다."""
        try:
            point = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))  # type: ignore[attr-defined]
            return point.x, point.y
        except (AttributeError, OSError):
            # Windows가 아닌 환경에서는 (0, 0) 반환
            return 0, 0

    def _generate_bezier_controls(
        self, x1: int, y1: int, x2: int, y2: int
    ) -> list[tuple[float, float]]:
        """
        시작점과 끝점 사이에 랜덤 제어점을 생성한다.
        제어점은 직선 경로에서 ±30% 범위 내에서 벗어나게 하여
        자연스러운 곡선을 만든다.
        """
        # 두 점 사이의 거리 계산
        dx = x2 - x1
        dy = y2 - y1
        distance = math.hypot(dx, dy)

        # 거리에 비례하여 벗어남 정도를 결정 (최소 20px, 최대 30%)
        offset_range = max(20, distance * 0.3)

        # 중간 지점 근처에 제어점 생성 (수직 방향으로 랜덤 오프셋)
        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0

        # 수직 방향 벡터 계산
        if distance > 0:
            perp_x = -dy / distance
            perp_y = dx / distance
        else:
            perp_x, perp_y = 0.0, 1.0

        # 랜덤 오프셋 적용
        offset = random.uniform(-offset_range, offset_range)
        ctrl_x = mid_x + perp_x * offset + random.uniform(-10, 10)
        ctrl_y = mid_y + perp_y * offset + random.uniform(-10, 10)

        return [(x1, y1), (ctrl_x, ctrl_y), (x2, y2)]

    def _bezier_point(
        self, t: float, points: list[tuple[float, float]]
    ) -> tuple[float, float]:
        """
        2차 베지어 곡선 위의 점을 계산한다.
        t: 0.0 ~ 1.0 사이의 보간 값
        points: [시작점, 제어점, 끝점]
        """
        p0, p1, p2 = points
        # B(t) = (1-t)²·P0 + 2(1-t)t·P1 + t²·P2
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        return x, y

    def _irregular_easing(self, t: float) -> float:
        """
        불규칙한 이즈-인-아웃 함수.
        기본 ease-in-out에 가우시안 노이즈를 추가하여
        사람의 불규칙한 마우스 속도를 시뮬레이션한다.
        """
        # 기본 ease-in-out (3차 보간)
        if t < 0.5:
            eased = 4 * t * t * t
        else:
            eased = 1 - (-2 * t + 2) ** 3 / 2

        # 가우시안 노이즈 추가 (표준편차 0.02)
        noise = random.gauss(0, 0.02)
        result = eased + noise

        # 0~1 범위로 클램프
        return max(0.0, min(1.0, result))

    def move_to(
        self,
        target_x: int,
        target_y: int,
        duration_ms: Optional[float] = None,
    ) -> None:
        """
        현재 위치에서 목표 좌표까지 베지어 곡선을 따라 이동한다.
        duration_ms가 지정되지 않으면 거리에 비례하여 자동 계산한다.
        이동 중 각 단계에서 불규칙 이징을 적용하여 자연스러운 속도 변화를 만든다.
        """
        # 현재 커서 위치 가져오기
        start_x, start_y = self._get_cursor_pos()

        # 이동 거리 계산
        distance = math.hypot(target_x - start_x, target_y - start_y)

        # 이동 거리가 매우 짧으면 직접 이동
        if distance < 5:
            self._engine.move_to(target_x, target_y)
            return

        # 이동 시간 자동 계산 (거리에 비례, 200~800ms 범위)
        if duration_ms is None:
            duration_ms = min(800, max(200, distance * 1.5))
            # ±20% 변동 추가
            duration_ms *= random.uniform(0.8, 1.2)

        # 베지어 곡선 제어점 생성
        control_points = self._generate_bezier_controls(
            start_x, start_y, target_x, target_y
        )

        # 이동 단계 수 결정 (거리에 비례, 최소 10단계)
        steps = max(10, int(distance / 5))
        step_delay = (duration_ms / 1000.0) / steps

        # 베지어 곡선을 따라 단계적으로 이동
        for i in range(1, steps + 1):
            # 정규화된 진행률 (0~1)
            t_raw = i / steps
            # 불규칙 이징 적용
            t_eased = self._irregular_easing(t_raw)

            # 베지어 곡선 위의 좌표 계산
            px, py = self._bezier_point(t_eased, control_points)

            # 실제 마우스 이동
            self._engine.move_to(int(px), int(py))

            # 단계 간 딜레이 (약간의 변동 포함)
            time.sleep(step_delay * random.uniform(0.7, 1.3))

        # 최종 위치 보정 (부동소수점 오차 방지)
        self._engine.move_to(target_x, target_y)
