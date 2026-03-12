"""
설정 관리 모듈 - config.json 로드/저장을 담당하는 싱글톤 클래스
모든 설정값에 대한 기본값을 제공하며, 변경 시 자동 저장한다.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional


# 기본 설정값 정의 - config.json이 없거나 키가 누락된 경우 사용
_DEFAULTS: dict[str, Any] = {
    "game_region": None,
    "cycle_duration_ms": 60000,
    "session_limit_min": 120,
    "jitter": {
        "interval_min_ms": 9000,
        "interval_max_ms": 16000,
        "duration_min_ms": 2,
        "duration_max_ms": 6,
    },
    "speed_factor": {
        "min": 0.85,
        "max": 1.15,
    },
    "hunt_weights": {
        "routine": 0.5,
        "skillA": 0.25,
        "skillB": 0.25,
    },
    "templates": {},
    "alerts": {
        "auto_solve": ["text_captcha", "click_5", "click_2", "rune"],
        "manual_only": ["violetta", "shape_tracking", "correct_sentence"],
        "notify_method": "sound",
    },
    "hotkeys": {
        "start": "F6",
        "pause": "F7",
        "stop": "F8",
        "record_toggle": "F9",
    },
}


class Config:
    """
    싱글톤 패턴의 설정 관리자.
    config.json 파일을 읽고 쓰며, 점 표기법(dot notation)으로 중첩 키에 접근할 수 있다.
    스레드 안전하게 동작한다.
    """

    _instance: Optional[Config] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, config_path: Optional[str] = None) -> Config:
        """싱글톤 인스턴스를 반환한다. 최초 호출 시에만 초기화한다."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, config_path: Optional[str] = None) -> None:
        """설정 파일 경로를 지정하고 로드한다. 이미 초기화된 경우 건너뛴다."""
        if self._initialized:
            return
        # 설정 파일 경로 결정 - 지정되지 않으면 프로젝트 루트의 config.json 사용
        if config_path is None:
            self._path = Path(__file__).resolve().parent.parent / "config.json"
        else:
            self._path = Path(config_path)
        self._data: dict[str, Any] = {}
        self._file_lock = threading.Lock()
        self._load()
        self._initialized = True

    def _load(self) -> None:
        """config.json 파일을 읽어서 메모리에 로드한다. 파일이 없으면 기본값으로 생성한다."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                # 파일이 손상된 경우 기본값으로 복원
                self._data = _DEFAULTS.copy()
                self._save()
        else:
            # 설정 파일이 없으면 기본값으로 새로 생성
            self._data = _DEFAULTS.copy()
            self._save()

    def _save(self) -> None:
        """현재 설정을 config.json 파일에 저장한다. 스레드 안전."""
        with self._file_lock:
            os.makedirs(self._path.parent, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """
        점 표기법으로 설정값을 가져온다.
        예: config.get('jitter.interval_min_ms') -> 9000
        키가 없으면 기본값(_DEFAULTS)에서 찾고, 그래도 없으면 default를 반환한다.
        """
        keys = key.split(".")
        # 먼저 저장된 설정에서 탐색
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # 저장된 설정에 없으면 기본값에서 탐색
                value = _DEFAULTS
                for k2 in keys:
                    if isinstance(value, dict) and k2 in value:
                        value = value[k2]
                    else:
                        return default
                return value
        return value

    def set(self, key: str, value: Any) -> None:
        """
        점 표기법으로 설정값을 변경하고 즉시 저장한다.
        예: config.set('jitter.interval_min_ms', 10000)
        중간 딕셔너리가 없으면 자동 생성한다.
        """
        keys = key.split(".")
        target = self._data
        # 마지막 키 이전까지 중첩 딕셔너리를 순회/생성
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self._save()

    def get_all(self) -> dict[str, Any]:
        """전체 설정 딕셔너리의 복사본을 반환한다."""
        return self._data.copy()

    def reset(self) -> None:
        """모든 설정을 기본값으로 초기화하고 저장한다."""
        self._data = _DEFAULTS.copy()
        self._save()

    @classmethod
    def reset_instance(cls) -> None:
        """싱글톤 인스턴스를 초기화한다. 테스트 시 유용하다."""
        with cls._lock:
            cls._instance = None
