"""
메인 윈도우 모듈 - PyQt5 기반 매크로 제어 GUI.
Weing-3.0V 수준의 풀 기능 UI를 제공한다.

기능:
- 카테고리별 패턴 녹화 (meso/buff/routine/skillA/skillB)
- 패턴 파일 리스트 + 삭제
- 실시간 상태 표시 (LED 스타일)
- 로그 출력 패널
- 기능 토글 체크박스 (핫키/룬/비올레타/클릭감지)
- 매크로 제어 (시작/일시정지/정지)
- 세션 시간 표시
"""

from __future__ import annotations

import os
import time
from typing import Optional

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QLabel, QStatusBar, QGroupBox, QListWidget,
        QCheckBox, QTabWidget, QTextEdit, QFrame, QSplitter,
        QMessageBox, QListWidgetItem, QSizePolicy, QComboBox,
        QSpinBox, QProgressBar, QToolTip, QFileDialog,
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
    from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QTextCursor
    _PYQT_AVAILABLE = True
except ImportError:
    _PYQT_AVAILABLE = False


# ─── 색상 상수 ───
_COLORS = {
    "bg_dark": "#FFFFFF",
    "bg_panel": "#F8F8F8",
    "bg_input": "#F0F0F0",
    "accent": "#2196F3",
    "accent_hover": "#1976D2",
    "text": "#222222",
    "text_dim": "#888888",
    "green": "#2E7D32",
    "yellow": "#F57F17",
    "red": "#C62828",
    "border": "#DDDDDD",
}

_STYLE_SHEET = f"""
QMainWindow {{
    background-color: {_COLORS['bg_dark']};
}}
QWidget {{
    color: {_COLORS['text']};
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {_COLORS['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 18px;
    padding-bottom: 6px;
    font-weight: bold;
    font-size: 13px;
    background-color: {_COLORS['bg_panel']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    color: {_COLORS['text']};
}}
QPushButton {{
    background-color: {_COLORS['bg_input']};
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    padding: 8px 16px;
    min-height: 32px;
    font-weight: bold;
    font-size: 13px;
    color: {_COLORS['text']};
}}
QPushButton:hover {{
    background-color: #E0E0E0;
    border-color: #BBBBBB;
}}
QPushButton:pressed {{
    background-color: #D0D0D0;
}}
QPushButton:disabled {{
    background-color: #F5F5F5;
    color: #BBBBBB;
    border-color: #E8E8E8;
}}
QPushButton#startBtn {{
    background-color: #4CAF50;
    border-color: #388E3C;
    color: white;
    font-size: 14px;
    min-height: 42px;
}}
QPushButton#startBtn:hover {{
    background-color: #388E3C;
}}
QPushButton#startBtn:disabled {{
    background-color: #A5D6A7;
    color: #E8E8E8;
    border-color: #A5D6A7;
}}
QPushButton#stopBtn {{
    background-color: #F44336;
    border-color: #D32F2F;
    color: white;
    font-size: 14px;
    min-height: 42px;
}}
QPushButton#stopBtn:hover {{
    background-color: #D32F2F;
}}
QPushButton#stopBtn:disabled {{
    background-color: #EF9A9A;
    color: #E8E8E8;
    border-color: #EF9A9A;
}}
QPushButton#pauseBtn {{
    background-color: #FF9800;
    border-color: #F57C00;
    color: white;
    font-size: 14px;
    min-height: 42px;
}}
QPushButton#pauseBtn:hover {{
    background-color: #F57C00;
}}
QPushButton#pauseBtn:disabled {{
    background-color: #FFCC80;
    color: #E8E8E8;
    border-color: #FFCC80;
}}
QPushButton#recordBtn {{
    background-color: #9C27B0;
    border-color: #7B1FA2;
    color: white;
}}
QPushButton#recordBtn:hover {{
    background-color: #7B1FA2;
}}
QPushButton#deleteBtn {{
    background-color: #FFEBEE;
    border-color: #EF9A9A;
    color: #C62828;
}}
QPushButton#deleteBtn:hover {{
    background-color: #FFCDD2;
    border-color: #E57373;
}}
QListWidget {{
    background-color: #FFFFFF;
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    padding: 4px;
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    color: {_COLORS['text']};
}}
QListWidget::item {{
    padding: 4px 8px;
    border-radius: 3px;
}}
QListWidget::item:selected {{
    background-color: #E3F2FD;
    color: #1565C0;
}}
QListWidget::item:hover {{
    background-color: #F5F5F5;
}}
QTextEdit {{
    background-color: #FFFFFF;
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    padding: 8px;
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    color: {_COLORS['text']};
}}
QCheckBox {{
    spacing: 8px;
    font-size: 13px;
    padding: 2px 0px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {_COLORS['border']};
    border-radius: 3px;
    background-color: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background-color: {_COLORS['accent']};
    border-color: {_COLORS['accent']};
}}
QCheckBox::indicator:hover {{
    border-color: #AAAAAA;
}}
QComboBox {{
    background-color: #FFFFFF;
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    padding: 4px 10px;
    min-height: 28px;
    font-size: 13px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QSpinBox {{
    background-color: #FFFFFF;
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 26px;
    font-size: 13px;
}}
QProgressBar {{
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    text-align: center;
    background-color: #F5F5F5;
    height: 20px;
    font-size: 11px;
    color: {_COLORS['text']};
}}
QProgressBar::chunk {{
    background-color: {_COLORS['green']};
    border-radius: 4px;
}}
QStatusBar {{
    background-color: {_COLORS['bg_panel']};
    border-top: 1px solid {_COLORS['border']};
    font-size: 12px;
    color: {_COLORS['text_dim']};
    padding: 4px 8px;
}}
QTabWidget::pane {{
    border: 1px solid {_COLORS['border']};
    border-radius: 5px;
    background-color: {_COLORS['bg_dark']};
}}
QTabBar::tab {{
    background-color: {_COLORS['bg_panel']};
    border: 1px solid {_COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 8px 16px;
    font-size: 12px;
    min-width: 70px;
}}
QTabBar::tab:selected {{
    background-color: {_COLORS['accent']};
    color: white;
}}
QTabBar::tab:hover {{
    background-color: #E0E0E0;
}}
"""


# ─── 상태 표시 색상 매핑 ───
_STATE_COLORS = {
    "IDLE": (_COLORS["text_dim"], "대기 중"),
    "HUNTING": ("#2E7D32", "● 사냥 중"),
    "PAUSED": ("#F57F17", "⏸ 일시정지"),
    "BUFFING": ("#1565C0", "◆ 버프 사용 중"),
    "ALERT_SOLVING": ("#C62828", "⚠ 거탐 해결 중"),
    "RUNE_SOLVING": ("#7B1FA2", "◈ 룬 해결 중"),
    "MANUAL_MODE": ("#E65100", "✋ 수동 모드"),
    "RECORDING": ("#D84315", "⏺ 녹화 중"),
}

# 패턴 카테고리 정의
_CATEGORIES = [
    ("meso", "메소", "메소 줍기 패턴"),
    ("buff", "버프", "버프 스킬 패턴"),
    ("routine", "루틴", "기본 사냥 루틴"),
    ("skillA", "스킬A", "공격 스킬 A 패턴"),
    ("skillB", "스킬B", "공격 스킬 B 패턴"),
]


if _PYQT_AVAILABLE:
    class MainWindow(QMainWindow):
        """
        매크로 메인 윈도우.
        Weing-3.0V 수준의 풀 기능 GUI를 제공한다.

        구성:
        - 상단: 상태 표시 (LED) + 세션 타이머
        - 중단: 제어 버튼 (시작/일시정지/정지)
        - 좌측 탭: 패턴 카테고리별 녹화/관리
        - 우측: 패턴 파일 리스트 + 삭제
        - 하단: 기능 토글 + 로그 출력
        """

        # 시그널 정의 (스레드 안전한 GUI 업데이트)
        sig_state_changed = pyqtSignal(str)
        sig_log_message = pyqtSignal(str)
        sig_pattern_count_changed = pyqtSignal()
        sig_countdown = pyqtSignal(int)          # 녹화 카운트다운 (남은 초)
        sig_recording_finished = pyqtSignal()    # 자동 녹화 완료

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            """메인 윈도우를 초기화하고 UI를 구성한다."""
            super().__init__(parent)
            self.setWindowTitle("메이플 매크로 헬퍼 v1.0")
            self.setMinimumSize(480, 860)
            self.resize(480, 860)

            self._controller = None  # CoreController 참조
            self._current_category: str = "routine"
            self._is_recording: bool = False

            self.setStyleSheet(_STYLE_SHEET)
            self._init_ui()
            self._connect_signals()
            self._start_timers()

        # ─── UI 초기화 ───

        def _init_ui(self) -> None:
            """전체 UI 레이아웃을 구성한다."""
            central = QWidget()
            self.setCentralWidget(central)
            main_layout = QVBoxLayout(central)
            main_layout.setContentsMargins(14, 14, 14, 8)
            main_layout.setSpacing(10)

            # 1. 상태 표시 영역
            main_layout.addWidget(self._create_status_section())

            # 2. 제어 버튼 영역
            main_layout.addWidget(self._create_control_section())

            # 3. 패턴 관리 영역 (카테고리 탭 + 파일 리스트)
            main_layout.addWidget(self._create_pattern_section())

            # 4. 기능 토글 체크박스
            main_layout.addWidget(self._create_feature_section())

            # 5. 설정 영역
            main_layout.addWidget(self._create_settings_section())

            # 6. 로그 출력 영역
            main_layout.addWidget(self._create_log_section())

            # 상태바
            self._statusbar = QStatusBar()
            self.setStatusBar(self._statusbar)
            self._statusbar.showMessage("준비됨 | F6: 시작  F7: 일시정지  F8: 정지  F9: 자동녹화")

        def _create_status_section(self) -> QGroupBox:
            """상태 표시 영역을 생성한다."""
            group = QGroupBox("상태")
            layout = QHBoxLayout(group)
            layout.setContentsMargins(14, 10, 14, 10)

            # 상태 LED + 텍스트
            self._state_label = QLabel("대기 중")
            self._state_label.setFont(QFont("Malgun Gothic", 18, QFont.Bold))
            self._state_label.setAlignment(Qt.AlignCenter)
            self._state_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            layout.addWidget(self._state_label, stretch=3)

            # 우측: 세션 타이머 + 패턴 카운트
            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)

            self._session_label = QLabel("세션: 00:00:00")
            self._session_label.setFont(QFont("Consolas", 11))
            self._session_label.setAlignment(Qt.AlignRight)
            self._session_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            info_layout.addWidget(self._session_label)

            self._cycle_label = QLabel("사이클: 0")
            self._cycle_label.setFont(QFont("Consolas", 11))
            self._cycle_label.setAlignment(Qt.AlignRight)
            self._cycle_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            info_layout.addWidget(self._cycle_label)

            layout.addLayout(info_layout, stretch=2)
            return group

        def _create_control_section(self) -> QGroupBox:
            """제어 버튼 영역을 생성한다."""
            group = QGroupBox("제어")
            layout = QHBoxLayout(group)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(10)

            self._start_btn = QPushButton("▶ 시작 (F6)")
            self._start_btn.setObjectName("startBtn")
            self._start_btn.setToolTip("매크로 시작 - 녹화된 패턴을 사용하여 자동 사냥")

            self._pause_btn = QPushButton("⏸ 일시정지 (F7)")
            self._pause_btn.setObjectName("pauseBtn")
            self._pause_btn.setToolTip("매크로 일시정지/재개")
            self._pause_btn.setEnabled(False)

            self._stop_btn = QPushButton("⏹ 정지 (F8)")
            self._stop_btn.setObjectName("stopBtn")
            self._stop_btn.setToolTip("매크로 완전 정지")
            self._stop_btn.setEnabled(False)

            layout.addWidget(self._start_btn)
            layout.addWidget(self._pause_btn)
            layout.addWidget(self._stop_btn)
            return group

        def _create_pattern_section(self) -> QGroupBox:
            """패턴 관리 영역 (카테고리별 녹화 + 파일 리스트)을 생성한다."""
            group = QGroupBox("패턴 관리")
            layout = QVBoxLayout(group)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(8)

            # 카테고리 버튼 (가로 배열)
            cat_layout = QHBoxLayout()
            cat_layout.setSpacing(6)

            self._cat_buttons: dict[str, QPushButton] = {}
            self._cat_count_labels: dict[str, QLabel] = {}

            for cat_id, cat_name, cat_desc in _CATEGORIES:
                btn_layout = QVBoxLayout()
                btn_layout.setSpacing(1)

                btn = QPushButton(cat_name)
                btn.setObjectName("recordBtn")
                btn.setToolTip(f"{cat_desc} 녹화/관리")
                btn.setCheckable(True)
                btn.setMinimumWidth(74)
                btn.setFixedHeight(36)
                btn.clicked.connect(lambda checked, c=cat_id: self._on_category_click(c))
                self._cat_buttons[cat_id] = btn
                btn_layout.addWidget(btn)

                count_label = QLabel("0개")
                count_label.setAlignment(Qt.AlignCenter)
                count_label.setFont(QFont("Consolas", 10))
                count_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
                self._cat_count_labels[cat_id] = count_label
                btn_layout.addWidget(count_label)

                cat_layout.addLayout(btn_layout)

            layout.addLayout(cat_layout)

            # 파일 리스트 + 제어 버튼
            list_layout = QHBoxLayout()
            list_layout.setSpacing(8)

            self._file_list = QListWidget()
            self._file_list.setMinimumHeight(130)
            self._file_list.setMaximumHeight(160)
            list_layout.addWidget(self._file_list, stretch=3)

            # 우측 버튼 (녹화, 테스트, 삭제)
            btn_side = QVBoxLayout()
            btn_side.setSpacing(6)

            self._record_btn = QPushButton("⏺ 자동녹화\n(F9)")
            self._record_btn.setObjectName("recordBtn")
            self._record_btn.setFixedSize(84, 50)
            self._record_btn.setToolTip(
                "녹화 시작: 자동으로 게임창 전환 → 지정 시간 녹화 → 자동 종료\n"
                "게임에서 실제로 사냥하는 키만 녹화됩니다"
            )
            btn_side.addWidget(self._record_btn)

            self._test_btn = QPushButton("▶ 테스트")
            self._test_btn.setFixedSize(84, 36)
            self._test_btn.setToolTip("선택한 패턴 1회 재생 테스트")
            btn_side.addWidget(self._test_btn)

            self._delete_btn = QPushButton("✕ 삭제")
            self._delete_btn.setObjectName("deleteBtn")
            self._delete_btn.setFixedSize(84, 36)
            self._delete_btn.setToolTip("선택한 패턴 파일 삭제")
            btn_side.addWidget(self._delete_btn)

            btn_side.addStretch()
            list_layout.addLayout(btn_side)

            layout.addLayout(list_layout)

            # 녹화 설정 + 카운트다운 표시
            rec_settings = QHBoxLayout()
            rec_settings.setSpacing(8)

            rec_settings.addWidget(QLabel("녹화 시간:"))
            self._rec_duration_spin = QSpinBox()
            self._rec_duration_spin.setRange(10, 300)
            self._rec_duration_spin.setValue(60)
            self._rec_duration_spin.setSuffix("초")
            self._rec_duration_spin.setToolTip("자동 녹화 지속 시간 (10~300초)")
            self._rec_duration_spin.setFixedWidth(90)
            rec_settings.addWidget(self._rec_duration_spin)

            self._countdown_label = QLabel("")
            self._countdown_label.setFont(QFont("Consolas", 12, QFont.Bold))
            self._countdown_label.setAlignment(Qt.AlignCenter)
            self._countdown_label.setStyleSheet(f"color: {_COLORS['accent']};")
            rec_settings.addWidget(self._countdown_label, stretch=1)

            layout.addLayout(rec_settings)

            # ── Archon XML 가져오기 + 위치 보정 설정 ──
            import_layout = QHBoxLayout()
            import_layout.setSpacing(8)

            self._import_xml_btn = QPushButton("XML 가져오기")
            self._import_xml_btn.setToolTip(
                "Archon AK47 매크로 파일(.xml)을 가져와\n"
                "선택된 카테고리에 패턴으로 저장합니다"
            )
            self._import_xml_btn.setFixedHeight(34)
            self._import_xml_btn.setStyleSheet(
                "background-color: #E3F2FD; border-color: #90CAF9; color: #1565C0;"
            )
            import_layout.addWidget(self._import_xml_btn)

            import_layout.addWidget(QLabel("보정:"))
            self._reset_dir_combo = QComboBox()
            self._reset_dir_combo.addItem("← 왼쪽", "left")
            self._reset_dir_combo.addItem("→ 오른쪽", "right")
            self._reset_dir_combo.addItem("없음", "none")
            self._reset_dir_combo.setToolTip(
                "매크로 시작 전 캐릭터 위치를 고정하는 방향\n"
                "맵 끝까지 이동하여 항상 같은 위치에서 시작"
            )
            self._reset_dir_combo.setFixedWidth(90)
            import_layout.addWidget(self._reset_dir_combo)

            import_layout.addWidget(QLabel("이동:"))
            self._reset_walk_spin = QSpinBox()
            self._reset_walk_spin.setRange(0, 10000)
            self._reset_walk_spin.setValue(3000)
            self._reset_walk_spin.setSuffix("ms")
            self._reset_walk_spin.setSingleStep(500)
            self._reset_walk_spin.setToolTip(
                "맵 끝으로 이동하는 시간 (ms)\n"
                "맵이 클수록 더 길게 설정 (3000~5000추천)\n"
                "0이면 위치 보정 없이 바로 매크로 실행"
            )
            self._reset_walk_spin.setFixedWidth(100)
            import_layout.addWidget(self._reset_walk_spin)

            layout.addLayout(import_layout)

            # 기본 카테고리 선택
            self._select_category("routine")

            return group

        def _create_feature_section(self) -> QGroupBox:
            """기능 토글 체크박스 영역을 생성한다."""
            group = QGroupBox("기능 설정")
            layout = QGridLayout(group)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(8)

            self._chk_hotkey = QCheckBox("핫키 활성화")
            self._chk_hotkey.setChecked(True)
            self._chk_hotkey.setToolTip("F6/F7/F8/F9 단축키 사용")
            layout.addWidget(self._chk_hotkey, 0, 0)

            self._chk_record_hotkey = QCheckBox("녹화 핫키")
            self._chk_record_hotkey.setChecked(True)
            self._chk_record_hotkey.setToolTip("F9 키로 녹화 시작/중지")
            layout.addWidget(self._chk_record_hotkey, 0, 1)

            self._chk_rune = QCheckBox("룬 자동해결")
            self._chk_rune.setChecked(True)
            self._chk_rune.setToolTip("룬 감지 시 자동으로 화살표 입력")
            layout.addWidget(self._chk_rune, 1, 0)

            self._chk_violetta = QCheckBox("비올레타 알림")
            self._chk_violetta.setChecked(True)
            self._chk_violetta.setToolTip("비올레타/투명도형 감지 시 소리 알림")
            layout.addWidget(self._chk_violetta, 1, 1)

            self._chk_click = QCheckBox("클릭 거탐 자동")
            self._chk_click.setChecked(True)
            self._chk_click.setToolTip("클릭형 거짓말 탐지기 자동 해결")
            layout.addWidget(self._chk_click, 2, 0)

            self._chk_text_captcha = QCheckBox("텍스트 거탐 자동")
            self._chk_text_captcha.setChecked(True)
            self._chk_text_captcha.setToolTip("텍스트 입력 거짓말 탐지기 OCR 자동 해결")
            layout.addWidget(self._chk_text_captcha, 2, 1)

            self._chk_buff = QCheckBox("버프 자동감지")
            self._chk_buff.setChecked(True)
            self._chk_buff.setToolTip("버프 만료 시 자동 버프 패턴 실행")
            layout.addWidget(self._chk_buff, 3, 0)

            self._chk_meso = QCheckBox("메소 자동수집")
            self._chk_meso.setChecked(True)
            self._chk_meso.setToolTip("메소 드롭 감지 시 자동 수집 패턴 실행")
            layout.addWidget(self._chk_meso, 3, 1)

            return group

        def _create_settings_section(self) -> QGroupBox:
            """설정 영역을 생성한다."""
            group = QGroupBox("설정")
            layout = QGridLayout(group)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(8)

            # 세션 제한 시간
            layout.addWidget(QLabel("세션 제한(분):"), 0, 0)
            self._session_limit_spin = QSpinBox()
            self._session_limit_spin.setRange(10, 480)
            self._session_limit_spin.setValue(120)
            self._session_limit_spin.setToolTip("자동 정지까지 최대 실행 시간")
            layout.addWidget(self._session_limit_spin, 0, 1)

            # 속도 변동 범위
            layout.addWidget(QLabel("속도 범위:"), 0, 2)
            self._speed_label = QLabel("0.85 ~ 1.15")
            self._speed_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            layout.addWidget(self._speed_label, 0, 3)

            # 세션 진행률 바
            layout.addWidget(QLabel("세션:"), 1, 0)
            self._session_progress = QProgressBar()
            self._session_progress.setRange(0, 100)
            self._session_progress.setValue(0)
            self._session_progress.setFormat("%v%")
            layout.addWidget(self._session_progress, 1, 1, 1, 3)

            return group

        def _create_log_section(self) -> QGroupBox:
            """로그 출력 영역을 생성한다."""
            group = QGroupBox("로그")
            layout = QVBoxLayout(group)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(6)

            self._log_text = QTextEdit()
            self._log_text.setReadOnly(True)
            self._log_text.setMinimumHeight(140)
            self._log_text.setMaximumHeight(200)
            self._log_text.setPlaceholderText("매크로 실행 로그가 여기에 표시됩니다...")
            layout.addWidget(self._log_text)

            # 로그 제어 버튼
            log_btn_layout = QHBoxLayout()
            log_btn_layout.setSpacing(4)

            self._clear_log_btn = QPushButton("로그 지우기")
            self._clear_log_btn.setFixedHeight(30)
            self._clear_log_btn.clicked.connect(self._log_text.clear)
            log_btn_layout.addWidget(self._clear_log_btn)

            log_btn_layout.addStretch()
            layout.addLayout(log_btn_layout)

            return group

        # ─── 시그널 연결 ───

        def _connect_signals(self) -> None:
            """위젯 시그널을 슬롯에 연결한다."""
            # 제어 버튼
            self._start_btn.clicked.connect(self._on_start)
            self._pause_btn.clicked.connect(self._on_pause)
            self._stop_btn.clicked.connect(self._on_stop)

            # 패턴 관리
            self._record_btn.clicked.connect(self._on_record_toggle)
            self._test_btn.clicked.connect(self._on_test_pattern)
            self._delete_btn.clicked.connect(self._on_delete_pattern)
            self._import_xml_btn.clicked.connect(self._on_import_xml)

            # 스레드-안전 시그널
            self.sig_state_changed.connect(self._on_state_changed_ui)
            self.sig_log_message.connect(self._on_log_message_ui)
            self.sig_pattern_count_changed.connect(self._refresh_pattern_counts)
            self.sig_countdown.connect(self._on_countdown_ui)
            self.sig_recording_finished.connect(self._on_recording_finished_ui)

        def _start_timers(self) -> None:
            """주기적 업데이트 타이머를 시작한다."""
            self._session_timer = QTimer(self)
            self._session_timer.timeout.connect(self._update_session_display)
            self._session_timer.start(1000)  # 1초마다

        # ─── 컨트롤러 연결 ───

        def set_controller(self, controller) -> None:
            """CoreController 인스턴스를 연결한다."""
            self._controller = controller

            # 컨트롤러 콜백 등록
            controller.set_on_state_change(
                lambda state: self.sig_state_changed.emit(state.value)
            )
            controller.set_on_log(
                lambda msg: self.sig_log_message.emit(msg)
            )
            controller.set_on_pattern_count_change(
                lambda: self.sig_pattern_count_changed.emit()
            )

            # 초기 패턴 카운트 표시
            self._refresh_pattern_counts()
            self._log("컨트롤러 연결 완료")

        # ─── 카테고리 관리 ───

        def _on_category_click(self, category: str) -> None:
            """카테고리 버튼 클릭 시 해당 카테고리를 선택한다."""
            self._select_category(category)

        def _select_category(self, category: str) -> None:
            """카테고리를 선택하고 UI를 업데이트한다."""
            self._current_category = category

            # 버튼 체크 상태 업데이트
            for cat_id, btn in self._cat_buttons.items():
                btn.setChecked(cat_id == category)

            # 파일 리스트 업데이트
            self._refresh_file_list()

        def _refresh_file_list(self) -> None:
            """현재 선택된 카테고리의 패턴 파일 목록을 갱신한다."""
            self._file_list.clear()
            cat = self._current_category

            if self._controller:
                count = self._controller.pattern_engine.get_pattern_count(cat)
                for i in range(count):
                    item = QListWidgetItem(f"  {cat}{i}")
                    self._file_list.addItem(item)
            else:
                # 컨트롤러 없이도 파일 시스템에서 직접 확인
                pattern_dir = os.path.join("patterns", cat)
                if os.path.isdir(pattern_dir):
                    files = sorted(
                        f for f in os.listdir(pattern_dir)
                        if f.startswith(cat)
                    )
                    for f in files:
                        self._file_list.addItem(f"  {f}")

        def _refresh_pattern_counts(self) -> None:
            """모든 카테고리의 패턴 개수를 업데이트한다."""
            for cat_id, label in self._cat_count_labels.items():
                count = 0
                if self._controller:
                    count = self._controller.pattern_engine.get_pattern_count(cat_id)
                else:
                    pattern_dir = os.path.join("patterns", cat_id)
                    if os.path.isdir(pattern_dir):
                        count = len([
                            f for f in os.listdir(pattern_dir)
                            if f.startswith(cat_id)
                        ])
                label.setText(f"{count}개")

                # 패턴이 있으면 초록색, 없으면 회색
                if count > 0:
                    label.setStyleSheet(f"color: {_COLORS['green']};")
                else:
                    label.setStyleSheet(f"color: {_COLORS['text_dim']};")

            # 파일 리스트도 갱신
            self._refresh_file_list()

        # ─── 제어 이벤트 핸들러 ───

        def _on_start(self) -> None:
            """시작 버튼 클릭 핸들러."""
            if not self._controller:
                self._log("[오류] 컨트롤러가 연결되지 않았습니다.")
                return

            self._controller.start()
            self._start_btn.setEnabled(False)
            self._pause_btn.setEnabled(True)
            self._stop_btn.setEnabled(True)

        def _on_pause(self) -> None:
            """일시정지 버튼 클릭 핸들러."""
            if not self._controller:
                return
            self._controller.toggle_pause()

        def _on_stop(self) -> None:
            """정지 버튼 클릭 핸들러."""
            if not self._controller:
                return

            self._controller.stop()
            self._start_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._stop_btn.setEnabled(False)

        # ─── 녹화/테스트/삭제 핸들러 ───

        def _on_record_toggle(self) -> None:
            """녹화 버튼 클릭 핸들러. 자동 녹화 시작/중지를 토글한다."""
            if not self._controller:
                self._log("[오류] 컨트롤러가 연결되지 않았습니다.")
                return

            if self._is_recording:
                # 녹화 중지 (수동 중단)
                self._is_recording = False
                self._controller.stop_recording()
                self._record_btn.setText("⏺ 자동녹화\n(F9)")
                self._record_btn.setStyleSheet("")
                self._countdown_label.setText("")
                self._rec_duration_spin.setEnabled(True)
                self._log(f"녹화 수동 중지: {self._current_category}")
                self._refresh_file_list()
            else:
                # 자동 녹화 시작
                self._is_recording = True
                duration = self._rec_duration_spin.value()
                self._record_btn.setText("⏹ 중지\n(F9)")
                self._record_btn.setStyleSheet(
                    f"background-color: {_COLORS['red']}; "
                    f"border-color: {_COLORS['red']};"
                )
                self._rec_duration_spin.setEnabled(False)
                self._countdown_label.setText(f"게임 전환 중...")

                self._controller.start_auto_recording(
                    category=self._current_category,
                    duration_sec=duration,
                    on_countdown=lambda sec: self.sig_countdown.emit(sec),
                    on_finished=lambda: self.sig_recording_finished.emit(),
                )
                self._log(
                    f"자동 녹화: {self._current_category} ({duration}초) "
                    f"- 게임으로 전환 후 사냥하세요"
                )

        def _on_test_pattern(self) -> None:
            """선택한 패턴을 1회 테스트 재생한다."""
            if not self._controller:
                self._log("[오류] 컨트롤러가 연결되지 않았습니다.")
                return

            selected = self._file_list.currentItem()
            if not selected:
                self._log("[오류] 테스트할 패턴을 선택하세요.")
                return

            pattern_name = selected.text().strip()
            self._log(f"패턴 테스트 재생: {pattern_name}")
            # 컨트롤러를 통해 단일 패턴 재생
            cat = self._current_category
            self._controller.pattern_engine.play_random(
                cat, stop_check=lambda: False
            )

        def _on_delete_pattern(self) -> None:
            """선택한 패턴 파일을 삭제한다."""
            selected = self._file_list.currentItem()
            if not selected:
                self._log("[오류] 삭제할 패턴을 선택하세요.")
                return

            pattern_name = selected.text().strip()
            reply = QMessageBox.question(
                self,
                "패턴 삭제",
                f"'{pattern_name}' 패턴을 삭제하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                cat = self._current_category
                pattern_path = os.path.join("patterns", cat, pattern_name)
                try:
                    if os.path.exists(pattern_path):
                        os.remove(pattern_path)
                        self._log(f"패턴 삭제 완료: {pattern_name}")
                    else:
                        self._log(f"[경고] 파일 없음: {pattern_path}")
                except Exception as e:
                    self._log(f"[오류] 삭제 실패: {e}")

                self._refresh_pattern_counts()

        def _on_import_xml(self) -> None:
            """Archon AK47 XML 가져오기 핸들러."""
            if not self._controller:
                self._log("[오류] 컨트롤러가 연결되지 않았습니다.")
                return

            # 파일 선택 다이얼로그
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Archon AK47 매크로 파일 선택",
                "",
                "XML 파일 (*.xml);;All Files (*)",
            )
            if not file_path:
                return  # 취소

            cat = self._current_category

            # 위치 보정 설정 읽기
            dir_data = self._reset_dir_combo.currentData()
            walk_ms = self._reset_walk_spin.value()

            if dir_data == "none":
                walk_ms = 0

            self._log(
                f"[Archon] XML 가져오기: {os.path.basename(file_path)} "
                f"→ {cat}"
            )
            if walk_ms > 0:
                self._log(
                    f"[Archon] 위치 보정: {dir_data} {walk_ms}ms"
                )

            success = self._controller.import_archon_xml(
                xml_path=file_path,
                category=cat,
                reset_direction=dir_data if dir_data != "none" else "left",
                reset_walk_ms=walk_ms,
            )

            if success:
                self._refresh_pattern_counts()
                self._log(f"[Archon] 가져오기 완료!")
            else:
                self._log(f"[Archon] 가져오기 실패")

        # ─── 상태 업데이트 (스레드-안전) ───

        def _on_state_changed_ui(self, state_value: str) -> None:
            """상태 변경 시 UI를 업데이트한다 (메인 스레드에서 실행)."""
            color, text = _STATE_COLORS.get(
                state_value, (_COLORS["text_dim"], state_value)
            )
            self._state_label.setText(text)
            self._state_label.setStyleSheet(f"color: {color}; font-size: 18px;")

            # 상태에 따른 버튼 활성화
            is_running = state_value not in ("IDLE",)
            self._start_btn.setEnabled(not is_running)
            self._pause_btn.setEnabled(is_running)
            self._stop_btn.setEnabled(is_running)

            # 상태바 업데이트
            self._statusbar.showMessage(f"상태: {text}")

        def _on_log_message_ui(self, message: str) -> None:
            """로그 메시지를 로그 패널에 추가한다 (메인 스레드에서 실행)."""
            timestamp = time.strftime("%H:%M:%S")

            # 색상 코드 (메시지 유형에 따라)
            if "[오류]" in message or "오류" in message or "실패" in message:
                color = _COLORS["red"]
            elif "[경고]" in message or "경고" in message:
                color = _COLORS["yellow"]
            elif "성공" in message or "완료" in message:
                color = _COLORS["green"]
            else:
                color = _COLORS["text_dim"]

            html = f'<span style="color:{_COLORS["text_dim"]}">[{timestamp}]</span> '
            html += f'<span style="color:{color}">{message}</span>'
            self._log_text.append(html)

            # 자동 스크롤
            cursor = self._log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self._log_text.setTextCursor(cursor)

        def _log(self, message: str) -> None:
            """로그 메시지를 추가하는 내부 편의 메서드."""
            self._on_log_message_ui(message)

        # ─── 녹화 카운트다운 UI ───

        def _on_countdown_ui(self, remaining: int) -> None:
            """녹화 카운트다운 업데이트 (메인 스레드)."""
            if remaining > 0:
                mins = remaining // 60
                secs = remaining % 60
                self._countdown_label.setText(f"녹화 중 {mins:01d}:{secs:02d}")
                # 10초 이하면 빨간색
                if remaining <= 10:
                    self._countdown_label.setStyleSheet(f"color: {_COLORS['red']};")
                else:
                    self._countdown_label.setStyleSheet(f"color: {_COLORS['green']};")
            else:
                self._countdown_label.setText("완료!")
                self._countdown_label.setStyleSheet(f"color: {_COLORS['green']};")

        def _on_recording_finished_ui(self) -> None:
            """자동 녹화 완료 시 UI 복원 (메인 스레드)."""
            self._is_recording = False
            self._record_btn.setText("⏺ 자동녹화\n(F9)")
            self._record_btn.setStyleSheet("")
            self._rec_duration_spin.setEnabled(True)
            self._refresh_file_list()
            self._refresh_pattern_counts()
            # 1초 후 카운트다운 레이블 초기화
            QTimer.singleShot(1500, lambda: self._countdown_label.setText(""))

        # ─── 세션 타이머 업데이트 ───

        def _update_session_display(self) -> None:
            """1초마다 세션 시간을 업데이트한다."""
            if not self._controller or not self._controller.is_running:
                return

            elapsed_min = self._controller.get_session_elapsed_min()
            hours = int(elapsed_min // 60)
            mins = int(elapsed_min % 60)
            secs = int((elapsed_min * 60) % 60)
            self._session_label.setText(f"세션: {hours:02d}:{mins:02d}:{secs:02d}")

            # 진행률 바 업데이트
            limit = self._session_limit_spin.value()
            progress = min(100, int((elapsed_min / limit) * 100))
            self._session_progress.setValue(progress)

            # 80% 이상이면 경고 색상
            if progress >= 80:
                self._session_progress.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {_COLORS['red']}; border-radius: 3px; }}"
                )
            elif progress >= 50:
                self._session_progress.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {_COLORS['yellow']}; border-radius: 3px; }}"
                )
            else:
                self._session_progress.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {_COLORS['green']}; border-radius: 3px; }}"
                )

        # ─── 기능 상태 조회 (컨트롤러용) ───

        def is_feature_enabled(self, feature: str) -> bool:
            """체크박스 기반 기능 활성화 상태를 반환한다."""
            feature_map = {
                "hotkey": self._chk_hotkey,
                "record_hotkey": self._chk_record_hotkey,
                "rune": self._chk_rune,
                "violetta": self._chk_violetta,
                "click": self._chk_click,
                "text_captcha": self._chk_text_captcha,
                "buff": self._chk_buff,
                "meso": self._chk_meso,
            }
            chk = feature_map.get(feature)
            return chk.isChecked() if chk else False

        def get_session_limit(self) -> int:
            """설정된 세션 제한 시간(분)을 반환한다."""
            return self._session_limit_spin.value()

        # ─── 키보드 이벤트 (핫키) ───

        def keyPressEvent(self, event) -> None:
            """핫키 이벤트를 처리한다."""
            if not self._chk_hotkey.isChecked():
                super().keyPressEvent(event)
                return

            key = event.key()
            if key == Qt.Key_F6:
                self._on_start()
            elif key == Qt.Key_F7:
                self._on_pause()
            elif key == Qt.Key_F8:
                self._on_stop()
            elif key == Qt.Key_F9:
                if self._chk_record_hotkey.isChecked():
                    self._on_record_toggle()
            else:
                super().keyPressEvent(event)

        # ─── 종료 처리 ───

        def closeEvent(self, event) -> None:
            """윈도우 종료 시 매크로를 안전하게 정지한다."""
            if self._controller and self._controller.is_running:
                reply = QMessageBox.question(
                    self,
                    "종료 확인",
                    "매크로가 실행 중입니다. 정지하고 종료하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return
                self._controller.stop()

            event.accept()

else:
    # PyQt5가 없는 환경에서의 폴백 클래스
    class MainWindow:  # type: ignore[no-redef]
        """PyQt5 미설치 시 폴백 - GUI 없이 콘솔 모드로 동작한다."""

        def __init__(self, *args, **kwargs) -> None:
            print("[경고] PyQt5가 설치되지 않아 GUI를 표시할 수 없습니다.")

        def show(self) -> None:
            print("[정보] 콘솔 모드로 동작합니다. Ctrl+C로 종료하세요.")

        def set_controller(self, controller) -> None:
            pass

        def is_feature_enabled(self, feature: str) -> bool:
            return True

        def get_session_limit(self) -> int:
            return 120
