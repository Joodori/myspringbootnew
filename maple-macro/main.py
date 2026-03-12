"""
메이플 매크로 헬퍼 - 메인 진입점.
PyQt5 GUI 애플리케이션을 실행하고 CoreController를 연결한다.
"""

import sys
import os
import logging

# 실행 디렉토리를 스크립트 위치로 설정 (PyInstaller 호환)
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow
from core.controller import CoreController


def setup_logging() -> None:
    """로깅을 설정한다."""
    log_format = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("macro.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    """애플리케이션을 초기화하고 메인 윈도우를 표시한다."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("메이플 매크로 헬퍼 시작")

    # 패턴 디렉토리 생성
    for cat in ("routine", "buff", "meso", "skillA", "skillB", "move", "potion"):
        os.makedirs(os.path.join("patterns", cat), exist_ok=True)
    os.makedirs("templates", exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("메이플 매크로 헬퍼")

    # 컨트롤러 생성
    controller = CoreController()

    # 메인 윈도우 생성 및 컨트롤러 연결
    window = MainWindow()
    window.set_controller(controller)
    window.show()

    logger.info("GUI 표시 완료, 이벤트 루프 시작")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
