"""
프로세스 은닉 모듈 - NGS(Nexon Game Security) 클라이언트 단 감지를 회피한다.

NGS 감지 대상:
1. 프로세스 목록 스캔 (알려진 매크로 프로그램명)
2. 윈도우 타이틀 스캔 (매크로 관련 키워드)
3. 로드된 DLL/드라이버 열거 (Interception 등)
4. 메모리 패턴 스캔 (후킹 시그니처)

대응 전략:
- 프로세스명 랜덤화 (PyInstaller 빌드 시 적용)
- 윈도우 타이틀을 일반적인 이름으로 위장
- Interception 드라이버 존재 확인 및 경고
- 자기 자신의 흔적 최소화
"""

from __future__ import annotations

import os
import sys
import random
import string
import logging
import ctypes
from typing import Optional

logger = logging.getLogger(__name__)

# 위장용 윈도우 타이틀 목록 (일반적인 프로그램처럼 보이게)
_DISGUISE_TITLES: list[str] = [
    "메모장",
    "Windows 설정",
    "새 폴더",
    "제어판",
    "문서 - 워드패드",
    "계산기",
    "사진",
    "캡처 도구",
]


class ProcessGuard:
    """
    프로세스 레벨 보호.
    NGS의 클라이언트 스캔으로부터 매크로 프로세스를 숨긴다.
    """

    def __init__(self) -> None:
        """프로세스 가드를 초기화한다."""
        self._original_title: Optional[str] = None
        self._is_disguised: bool = False
        self._warnings: list[str] = []

    def check_environment(self) -> list[str]:
        """
        실행 환경을 검사하고 위험 요소를 반환한다.
        매크로 시작 전에 호출하여 안전한지 확인한다.
        """
        warnings = []

        # 1. Interception 드라이버 설치 여부 확인
        interception_paths = [
            r"C:\Windows\System32\drivers\keyboard.sys",
            r"C:\Windows\System32\drivers\mouse.sys",
        ]
        for path in interception_paths:
            if os.path.exists(path):
                warnings.append(
                    f"Interception 드라이버 파일 감지: {path}\n"
                    "일부 게임 보안(EAC 등)에서 차단될 수 있습니다."
                )

        # 2. 디버거 연결 여부
        try:
            if ctypes.windll.kernel32.IsDebuggerPresent():  # type: ignore
                warnings.append(
                    "디버거가 연결되어 있습니다. NGS가 감지할 수 있습니다."
                )
        except (AttributeError, OSError):
            pass  # Windows가 아닌 환경

        # 3. 관리자 권한 체크
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()  # type: ignore
            if is_admin:
                warnings.append(
                    "관리자 권한으로 실행 중입니다. "
                    "NGS 로그에 더 많은 정보가 노출될 수 있습니다."
                )
        except (AttributeError, OSError):
            pass

        # 4. 의심스러운 프로세스명 확인
        exe_name = os.path.basename(sys.executable).lower()
        suspicious_keywords = [
            "macro", "bot", "hack", "cheat", "auto",
            "매크로", "핵", "봇", "오토",
        ]
        for kw in suspicious_keywords:
            if kw in exe_name:
                warnings.append(
                    f"실행 파일명에 의심스러운 키워드 포함: '{kw}'\n"
                    "빌드 시 파일명을 변경하세요."
                )
                break

        self._warnings = warnings
        return warnings

    def disguise_window_title(self, window=None) -> str:
        """
        윈도우 타이틀을 일반적인 프로그램처럼 변경한다.
        
        Args:
            window: QMainWindow 인스턴스 (None이면 콘솔 타이틀 변경)
        
        Returns:
            적용된 위장 타이틀
        """
        title = random.choice(_DISGUISE_TITLES)

        if window is not None:
            # PyQt5 윈도우 타이틀 변경
            try:
                self._original_title = window.windowTitle()
                window.setWindowTitle(title)
                self._is_disguised = True
            except Exception as e:
                logger.warning(f"윈도우 타이틀 변경 실패: {e}")
        else:
            # 콘솔 타이틀 변경 (Windows)
            try:
                ctypes.windll.kernel32.SetConsoleTitleW(title)  # type: ignore
                self._is_disguised = True
            except (AttributeError, OSError):
                pass

        logger.info(f"윈도우 타이틀 위장: '{title}'")
        return title

    def restore_window_title(self, window=None) -> None:
        """원래 윈도우 타이틀을 복원한다."""
        if not self._is_disguised or self._original_title is None:
            return

        if window is not None:
            try:
                window.setWindowTitle(self._original_title)
            except Exception:
                pass

        self._is_disguised = False

    def minimize_footprint(self) -> None:
        """
        프로세스 메모리 사용량을 최소화한다.
        NGS가 메모리 스캔 시 footprint를 줄인다.
        """
        try:
            # Windows: 작업 집합 크기 최소화
            kernel32 = ctypes.windll.kernel32  # type: ignore
            handle = kernel32.GetCurrentProcess()
            kernel32.SetProcessWorkingSetSize(handle, -1, -1)
            logger.debug("프로세스 메모리 풋프린트 최소화 완료")
        except (AttributeError, OSError):
            pass  # Windows가 아닌 환경

    def get_safe_process_name(self) -> str:
        """
        PyInstaller 빌드 시 사용할 안전한 프로세스명을 생성한다.
        일반 유틸리티처럼 보이는 이름을 반환한다.
        """
        safe_names = [
            "SystemHelper",
            "WinUpdate",
            "ServiceManager",
            "DisplayConfig",
            "FontManager",
            "RegOptimizer",
            "DiskCleanHelper",
        ]
        # 랜덤 접미사 추가 (실행마다 다른 이름)
        name = random.choice(safe_names)
        suffix = "".join(random.choices(string.digits, k=2))
        return f"{name}{suffix}"

    @property
    def warnings(self) -> list[str]:
        """마지막 환경 검사 경고 목록."""
        return self._warnings

    @property
    def is_disguised(self) -> bool:
        """현재 위장 상태."""
        return self._is_disguised
