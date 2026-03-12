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
        QSpinBox, QProgressBar, QToolTip,
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
    from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QTextCursor
    _PYQT_AVAILABLE = True
except ImportError:
    _PYQT_AVAILABLE = False


# ─── 색상 상수 ───
_COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_panel": "#16213e",
    "bg_input": "#0f3460",
    "accent": "#e94560",
    "accent_hover": "#ff6b6b",
    "text": "#eaeaea",
    "text_dim": "#8892b0",
    "green": "#00e676",
    "yellow": "#ffd600",
    "red": "#ff1744",
    "border": "#233554",
}

_STYLE_SHEET = f"""
QMainWindow {{
    background-color: {_COLORS['bg_dark']};
}}
QWidget {{
    color: {_COLORS['text']};
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 12px;
}}
QGroupBox {{
    border: 1px solid {_COLORS['border']};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: bold;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {_COLORS['accent']};
}}
QPushButton {{
    background-color: {_COLORS['bg_input']};
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    padding: 6px 14px;
    min-height: 24px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {_COLORS['accent']};
    border-color: {_COLORS['accent']};
}}
QPushButton:pressed {{
    background-color: {_COLORS['accent_hover']};
}}
QPushButton:disabled {{
    background-color: #2a2a3e;
    color: #555;
}}
QPushButton#startBtn {{
    background-color: #1b5e20;
    border-color: #2e7d32;
    font-size: 14px;
    min-height: 36px;
}}
QPushButton#startBtn:hover {{
    background-color: #2e7d32;
}}
QPushButton#stopBtn {{
    background-color: #b71c1c;
    border-color: #c62828;
    font-size: 14px;
    min-height: 36px;
}}
QPushButton#stopBtn:hover {{
    background-color: #c62828;
}}
QPushButton#pauseBtn {{
    background-color: #e65100;
    border-color: #ef6c00;
    font-size: 14px;
    min-height: 36px;
}}
QPushButton#pauseBtn:hover {{
    background-color: #ef6c00;
}}
QPushButton#recordBtn {{
    background-color: #880e4f;
    border-color: #ad1457;
}}
QPushButton#recordBtn:hover {{
    background-color: #ad1457;
}}
QPushButton#deleteBtn {{
    background-color: #4a0000;
    border-color: #6a0000;
}}
QPushButton#deleteBtn:hover {{
    background-color: #b71c1c;
}}
QListWidget {{
    background-color: {_COLORS['bg_panel']};
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    padding: 4px;
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 11px;
}}
QListWidget::item {{
    padding: 3px 6px;
    border-radius: 2px;
}}
QListWidget::item:selected {{
    background-color: {_COLORS['accent']};
}}
QTextEdit {{
    background-color: {_COLORS['bg_panel']};
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    padding: 6px;
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 11px;
    color: {_COLORS['text_dim']};
}}
QCheckBox {{
    spacing: 6px;
    font-size: 11px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {_COLORS['border']};
    border-radius: 3px;
    background-color: {_COLORS['bg_panel']};
}}
QCheckBox::indicator:checked {{
    background-color: {_COLORS['accent']};
    border-color: {_COLORS['accent']};
}}
QComboBox {{
    background-color: {_COLORS['bg_input']};
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QSpinBox {{
    background-color: {_COLORS['bg_input']};
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    padding: 2px 6px;
}}
QProgressBar {{
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    text-align: center;
    background-color: {_COLORS['bg_panel']};
    height: 18px;
    font-size: 10px;
}}
QProgressBar::chunk {{
    background-color: {_COLORS['green']};
    border-radius: 3px;
}}
QStatusBar {{
    background-color: {_COLORS['bg_panel']};
    border-top: 1px solid {_COLORS['border']};
    font-size: 11px;
}}
QTabWidget::pane {{
    border: 1px solid {_COLORS['border']};
    border-radius: 4px;
    background-color: {_COLORS['bg_dark']};
}}
QTabBar::tab {{
    background-color: {_COLORS['bg_panel']};
    border: 1px solid {_COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    font-size: 11px;
    min-width: 60px;
}}
QTabBar::tab:selected {{
    background-color: {_COLORS['accent']};
    color: white;
}}
QTabBar::tab:hover {{
    background-color: {_COLORS['bg_input']};
}}
"""


# ─── 상태 표시 색상 매핑 ───
_STATE_COLORS = {
    "IDLE": (_COLORS["text_dim"], "대기 중"),
    "HUNTING": (_COLORS["green"], "● 사냥 중"),
    "PAUSED": (_COLORS["yellow"], "⏸ 일시정지"),
    "BUFFING": ("#64b5f6", "◆ 버프 사용 중"),
    "ALERT_SOLVING": (_COLORS["red"], "⚠ 거탐 해결 중"),
    "RUNE_SOLVING": ("#ce93d8", "◈ 룬 해결 중"),
    "MANUAL_MODE": (_COLORS["yellow"], "✋ 수동 모드"),
    "RECORDING": ("#ff6e40", "⏺ 녹화 중"),
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

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            """메인 윈도우를 초기화하고 UI를 구성한다."""
            super().__init__(parent)
            self.setWindowTitle("메이플 매크로 헬퍼 v1.0")
            self.setMinimumSize(380, 780)
            self.resize(380, 780)

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
            main_layout.setContentsMargins(8, 8, 8, 4)
            main_layout.setSpacing(6)

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
            self._statusbar.showMessage("준비됨 | F6: 시작  F7: 일시정지  F8: 정지  F9: 녹화")

        def _create_status_section(self) -> QGroupBox:
            """상태 표시 영역을 생성한다."""
            group = QGroupBox("상태")
            layout = QHBoxLayout(group)
            layout.setContentsMargins(10, 6, 10, 6)

            # 상태 LED + 텍스트
            self._state_label = QLabel("대기 중")
            self._state_label.setFont(QFont("Malgun Gothic", 16, QFont.Bold))
            self._state_label.setAlignment(Qt.AlignCenter)
            self._state_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            layout.addWidget(self._state_label, stretch=3)

            # 우측: 세션 타이머 + 패턴 카운트
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            self._session_label = QLabel("세션: 00:00:00")
            self._session_label.setFont(QFont("Consolas", 10))
            self._session_label.setAlignment(Qt.AlignRight)
            self._session_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            info_layout.addWidget(self._session_label)

            self._cycle_label = QLabel("사이클: 0")
            self._cycle_label.setFont(QFont("Consolas", 10))
            self._cycle_label.setAlignment(Qt.AlignRight)
            self._cycle_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
            info_layout.addWidget(self._cycle_label)

            layout.addLayout(info_layout, stretch=2)
            return group

        def _create_control_section(self) -> QGroupBox:
            """제어 버튼 영역을 생성한다."""
            group = QGroupBox("제어")
            layout = QHBoxLayout(group)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(6)

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
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(4)

            # 카테고리 버튼 (가로 배열)
            cat_layout = QHBoxLayout()
            cat_layout.setSpacing(3)

            self._cat_buttons: dict[str, QPushButton] = {}
            self._cat_count_labels: dict[str, QLabel] = {}

            for cat_id, cat_name, cat_desc in _CATEGORIES:
                btn_layout = QVBoxLayout()
                btn_layout.setSpacing(1)

                btn = QPushButton(cat_name)
                btn.setObjectName("recordBtn")
                btn.setToolTip(f"{cat_desc} 녹화/관리")
                btn.setCheckable(True)
                btn.setMinimumWidth(52)
                btn.setFixedHeight(32)
                btn.clicked.connect(lambda checked, c=cat_id: self._on_category_click(c))
                self._cat_buttons[cat_id] = btn
                btn_layout.addWidget(btn)

                count_label = QLabel("0개")
                count_label.setAlignment(Qt.AlignCenter)
                count_label.setFont(QFont("Consolas", 9))
                count_label.setStyleSheet(f"color: {_COLORS['text_dim']};")
                self._cat_count_labels[cat_id] = count_label
                btn_layout.addWidget(count_label)

                cat_layout.addLayout(btn_layout)

            layout.addLayout(cat_layout)

            # 파일 리스트 + 제어 버튼
            list_layout = QHBoxLayout()
            list_layout.setSpacing(4)

            self._file_list = QListWidget()
            self._file_list.setMinimumHeight(100)
            self._file_list.setMaximumHeight(140)
            list_layout.addWidget(self._file_list, stretch=3)

            # 우측 버튼 (녹화, 테스트, 삭제)
            btn_side = QVBoxLayout()
            btn_side.setSpacing(4)

            self._record_btn = QPushButton("⏺ 녹화\n(F9)")
            self._record_btn.setObjectName("recordBtn")
            self._record_btn.setFixedSize(64, 44)
            self._record_btn.setToolTip("선택한 카테고리로 패턴 녹화 시작/중지")
            btn_side.addWidget(self._record_btn)

            self._test_btn = QPushButton("▶ 테스트")
            self._test_btn.setFixedSize(64, 30)
            self._test_btn.setToolTip("선택한 패턴 1회 재생 테스트")
            btn_side.addWidget(self._test_btn)

            self._delete_btn = QPushButton("✕ 삭제")
            self._delete_btn.setObjectName("deleteBtn")
            self._delete_btn.setFixedSize(64, 30)
            self._delete_btn.setToolTip("선택한 패턴 파일 삭제")
            btn_side.addWidget(self._delete_btn)

            btn_side.addStretch()
            list_layout.addLayout(btn_side)

            layout.addLayout(list_layout)

            # 기본 카테고리 선택
            self._select_category("routine")

            return group

        def _create_feature_section(self) -> QGroupBox:
            """기능 토글 체크박스 영역을 생성한다."""
            group = QGroupBox("기능 설정")
            layout = QGridLayout(group)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(4)

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
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(4)

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
            layout.setContentsMargins(6, 4, 6, 4)
            layout.setSpacing(2)

            self._log_text = QTextEdit()
            self._log_text.setReadOnly(True)
            self._log_text.setMinimumHeight(120)
            self._log_text.setMaximumHeight(180)
            self._log_text.setPlaceholderText("매크로 실행 로그가 여기에 표시됩니다...")
            layout.addWidget(self._log_text)

            # 로그 제어 버튼
            log_btn_layout = QHBoxLayout()
            log_btn_layout.setSpacing(4)

            self._clear_log_btn = QPushButton("로그 지우기")
            self._clear_log_btn.setFixedHeight(24)
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

            # 스레드-안전 시그널
            self.sig_state_changed.connect(self._on_state_changed_ui)
            self.sig_log_message.connect(self._on_log_message_ui)
            self.sig_pattern_count_changed.connect(self._refresh_pattern_counts)

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
            """녹화 버튼 클릭 핸들러. 녹화 시작/중지를 토글한다."""
            if not self._controller:
                self._log("[오류] 컨트롤러가 연결되지 않았습니다.")
                return

            if self._is_recording:
                # 녹화 중지
                self._is_recording = False
                self._controller.stop_recording()
                self._record_btn.setText("⏺ 녹화\n(F9)")
                self._record_btn.setStyleSheet("")
                self._log(f"녹화 중지: {self._current_category}")
                self._refresh_file_list()
            else:
                # 녹화 시작
                self._is_recording = True
                self._record_btn.setText("⏹ 중지\n(F9)")
                self._record_btn.setStyleSheet(
                    f"background-color: {_COLORS['red']}; "
                    f"border-color: {_COLORS['red']};"
                )
                self._controller.start_recording(self._current_category)
                self._log(f"녹화 시작: {self._current_category} (마우스 왼쪽 클릭으로 녹화 시작/종료)")

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

        # ─── 상태 업데이트 (스레드-안전) ───

        def _on_state_changed_ui(self, state_value: str) -> None:
            """상태 변경 시 UI를 업데이트한다 (메인 스레드에서 실행)."""
            color, text = _STATE_COLORS.get(
                state_value, (_COLORS["text_dim"], state_value)
            )
            self._state_label.setText(text)
            self._state_label.setStyleSheet(f"color: {color}; font-size: 16px;")

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
