# 메이플 매크로 헬퍼 v1.0

MapleStory 사냥 보조 프로그램 - Key Record-Replay 방식의 PyQt5 GUI 애플리케이션

## 주요 기능

### 핵심 시스템
- **Key Record-Replay**: 실제 게임플레이를 녹화하고 랜덤 변형하여 재생
- **Interception 드라이버**: 커널 레벨 입력으로 안티치트 우회 (ctypes SendInput 폴백)
- **상태 머신 기반 제어**: IDLE → HUNTING → BUFFING → ALERT_SOLVING 등 명확한 상태 전이
- **60초 사이클 + 랜덤 지터**: 9~16초 간격, 2~6ms 미세 딜레이

### 자동 감지 & 해결
- **거짓말 탐지기 (텍스트)**: EasyOCR로 한글 자동 인식 및 입력
- **클릭형 거탐**: 자동 클릭 해결
- **룬**: HSV 기반 화살표 감지 + 자동 입력
- **비올레타/투명도형**: 알림만 (수동 해결 필요)

### GUI (Weing-3.0V 스타일)
- 카테고리별 패턴 녹화 (메소/버프/루틴/스킬A/스킬B)
- 패턴 파일 리스트 + 삭제 + 테스트 재생
- 실시간 상태 LED + 세션 타이머
- 로그 출력 패널
- 기능별 토글 체크박스
- F6/F7/F8/F9 핫키

## 프로젝트 구조

```
maple-macro/
├── main.py                    # 진입점
├── config.json                # 설정 파일
├── requirements.txt           # 의존성
├── build.spec                 # PyInstaller 빌드 설정
├── core/
│   ├── config.py              # 설정 관리자
│   ├── timing.py              # 타이밍 엔진 (지터/딜레이)
│   ├── state.py               # 상태 머신
│   └── controller.py          # 핵심 컨트롤러
├── input/
│   ├── engine.py              # Interception + SendInput 입력 엔진
│   └── human_mouse.py         # 베지어 곡선 마우스 이동
├── pattern/
│   ├── event.py               # 이벤트 데이터 클래스
│   └── engine.py              # Record-Replay 엔진
├── screen/
│   └── monitor.py             # 화면 캡처 + 템플릿 매칭 + 프레임 diff
├── solver/
│   ├── text_captcha.py        # OCR 텍스트 거탐 해결
│   ├── rune_solver.py         # 룬 화살표 해결
│   └── alert_handler.py       # 거탐 통합 핸들러
├── gui/
│   └── main_window.py         # PyQt5 풀 기능 GUI
├── notify/
│   └── notifier.py            # 사운드/토스트 알림
├── patterns/                  # 녹화된 패턴 저장
│   ├── routine/
│   ├── buff/
│   ├── meso/
│   ├── skillA/
│   └── skillB/
└── templates/                 # 이미지 감지 템플릿
```

## 설치 & 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. Interception 드라이버 설치 (관리자 권한 필요)
# https://github.com/oblitum/Interception 에서 다운로드

# 3. 실행
python main.py
```

## 빌드 (exe)

```bash
pyinstaller build.spec
# 결과: dist/MapleMacroHelper.exe
```

## 사용법

1. **패턴 녹화**: 카테고리 선택 → 녹화 버튼 → 마우스 좌클릭으로 녹화 시작/종료
2. **매크로 시작**: F6 또는 시작 버튼
3. **일시정지**: F7 또는 일시정지 버튼
4. **정지**: F8 또는 정지 버튼

## 안티 감지 전략

- 속도 변동: 0.85~1.15 (Weing의 0.93~1.0보다 넓은 범위)
- 9~16초 간격 랜덤 지터 삽입
- 커널 레벨 입력 (Interception)
- 세션 시간 제한 (기본 120분, HackRank 점수 누적 방지)
- 프레임 diff 기반 감지 (템플릿 매칭 한계 극복)

## 기술 스택

- Python 3.10+
- PyQt5 (GUI)
- OpenCV + MSS (화면 캡처/처리)
- EasyOCR (한글 OCR)
- Interception (커널 입력)
- scipy (베지어 곡선)

## 라이선스

개인 사용 목적. 상업적 사용 및 배포 금지.
