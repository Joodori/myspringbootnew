"""
룬 풀이 모듈 - 감지된 화살표 방향에 따라 키 입력을 수행한다.
각 화살표 입력 사이에 랜덤 딜레이를 넣어 사람의 입력을 시뮬레이션한다.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from input.engine import InputEngine


class RuneSolver:
    """
    룬 화살표 풀이 엔진.
    화살표 방향 리스트를 받아 순서대로 키를 입력한다.
    """

    # 방향 이름과 키 매핑
    _DIRECTION_KEYS: dict[str, str] = {
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
    }

    def solve(
        self, arrows: list[str], input_engine: InputEngine
    ) -> bool:
        """
        화살표 방향 리스트에 따라 키를 순서대로 입력한다.
        각 입력 사이에 200~500ms 랜덤 딜레이를 삽입한다.
        반환: 풀이 완료 여부 (빈 리스트이면 False)
        """
        if not arrows:
            return False

        for i, direction in enumerate(arrows):
            key = self._DIRECTION_KEYS.get(direction.lower())
            if key is None:
                # 인식 불가 방향은 건너뛴다
                continue

            # 키 입력 (50~100ms 홀드)
            input_engine.press_key(key, hold_ms=random.uniform(50, 100))

            # 마지막 화살표가 아니면 딜레이 삽입
            if i < len(arrows) - 1:
                delay = random.uniform(0.2, 0.5)
                time.sleep(delay)

        return True
