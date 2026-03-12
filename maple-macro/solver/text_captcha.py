"""
텍스트 캡차 풀이 모듈 - 메이플스토리 내 텍스트 기반 캡차를 OCR로 인식하고 해결한다.
EasyOCR을 사용하며, 사전 기반 보정으로 인식률을 높인다.
"""

from __future__ import annotations

import difflib
from typing import Optional

try:
    import cv2
    import numpy as np
    from numpy.typing import NDArray
except ImportError:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

# EasyOCR은 무거우므로 필요할 때만 로드
_easyocr = None


def _get_easyocr():
    """EasyOCR 모듈을 지연 로드한다."""
    global _easyocr
    if _easyocr is None:
        try:
            import easyocr
            _easyocr = easyocr
        except ImportError:
            pass
    return _easyocr


# 메이플스토리 몬스터/NPC 이름 사전 (OCR 보정용)
# 자주 등장하는 이름들을 미리 등록하여 유사도 기반 보정에 사용한다
_MAPLE_DICTIONARY: list[str] = [
    # 일반 몬스터
    "주황버섯", "슬라임", "스텀프", "리본돼지", "파란버섯",
    "초록버섯", "좀비버섯", "뿔버섯", "스톤골렘", "다크스톤골렘",
    "와일드보어", "파이어보어", "아이언호그", "크로노스",
    "블러디퀸", "반레온", "매그너스", "힐라", "시그너스",
    "루시드", "윌", "더스크", "진힐라", "듄켈",
    "검은마법사", "스우", "데미안", "가디언엔젤슬라임",
    # NPC
    "카산드라", "리린", "마이", "앨리시아", "하인즈",
    "프랭클", "체키", "피에르", "반반", "블러디퀸",
    # 공통 단어
    "사냥터", "포탈", "마을", "도적", "전사", "마법사", "궁수", "해적",
    "퀘스트", "미션", "이벤트", "보스", "던전",
]


class TextCaptchaSolver:
    """
    텍스트 캡차 인식 및 풀이 엔진.
    - EasyOCR로 한글/영문 텍스트를 인식한다.
    - 여러 전처리 방법을 시도하여 최적 결과를 선택한다.
    - 메이플 사전과 비교하여 OCR 오인식을 보정한다.
    """

    def __init__(self) -> None:
        """OCR 리더는 첫 사용 시 지연 초기화한다."""
        self._reader = None

    def _ensure_reader(self) -> bool:
        """EasyOCR 리더가 초기화되었는지 확인하고, 없으면 생성한다."""
        if self._reader is not None:
            return True

        easyocr = _get_easyocr()
        if easyocr is None:
            return False

        try:
            # 한국어 + 영어 모델 로드 (GPU 사용 가능 시 자동 활용)
            self._reader = easyocr.Reader(["ko", "en"], gpu=True)
            return True
        except Exception:
            try:
                # GPU 실패 시 CPU로 폴백
                self._reader = easyocr.Reader(["ko", "en"], gpu=False)
                return True
            except Exception:
                return False

    def preprocess_captcha(self, image: NDArray) -> list[NDArray]:
        """
        캡차 이미지에 여러 전처리를 적용한다.
        다양한 전처리 결과를 반환하여 OCR 인식률을 극대화한다.
        반환: 전처리된 이미지 리스트
        """
        if cv2 is None or np is None:
            return []

        results: list[NDArray] = []

        # 그레이스케일 변환
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 방법 1: 가우시안 블러 + 적응형 임계값 (Adaptive Threshold)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        adaptive = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        results.append(adaptive)

        # 방법 2: OTSU 이진화 + 노이즈 제거
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 모폴로지 연산으로 노이즈 제거
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)
        results.append(cleaned)

        # 방법 3: 반전 + 팽창 (어두운 배경의 밝은 텍스트용)
        inverted = cv2.bitwise_not(gray)
        _, inv_thresh = cv2.threshold(inverted, 128, 255, cv2.THRESH_BINARY)
        dilated = cv2.dilate(inv_thresh, kernel, iterations=1)
        results.append(dilated)

        # 방법 4: CLAHE 히스토그램 평활화 + 이진화
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, clahe_thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(clahe_thresh)

        return results

    def recognize_text(self, region: NDArray) -> str:
        """
        이미지 영역에서 텍스트를 인식한다.
        여러 전처리 방법을 시도하여 가장 높은 신뢰도의 결과를 반환한다.
        """
        if not self._ensure_reader():
            return ""

        # 전처리된 이미지들 생성
        preprocessed = self.preprocess_captcha(region)
        if not preprocessed:
            # 전처리 실패 시 원본으로 시도
            preprocessed = [region]

        best_text = ""
        best_confidence = 0.0

        for img in preprocessed:
            try:
                # EasyOCR 인식 수행
                results = self._reader.readtext(img)
                for bbox, text, confidence in results:
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_text = text
            except Exception:
                continue

        # 사전 기반 보정 적용
        if best_text:
            best_text = self._correct_with_dictionary(best_text)

        return best_text.strip()

    def _correct_with_dictionary(self, text: str) -> str:
        """
        OCR 인식 결과를 메이플 사전과 비교하여 보정한다.
        유사도가 0.6 이상이면 사전의 단어로 교체한다.
        difflib.get_close_matches를 사용한다.
        """
        # 공백으로 분리된 각 단어를 개별 보정
        words = text.split()
        corrected: list[str] = []

        for word in words:
            # 사전에서 유사한 단어 검색 (유사도 60% 이상)
            matches = difflib.get_close_matches(
                word, _MAPLE_DICTIONARY, n=1, cutoff=0.6
            )
            if matches:
                corrected.append(matches[0])
            else:
                corrected.append(word)

        return " ".join(corrected)
