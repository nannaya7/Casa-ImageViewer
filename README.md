# Image & CAD Integrated Viewer

일반 이미지 편집과 2D/3D CAD 파일 뷰잉을 통합한 Python 데스크톱 애플리케이션입니다.

---

## 주요 기능

| 분류 | 기능 |
|---|---|
| 이미지 뷰어/편집 | 확대·축소, 회전, 드래그 Crop, Resize, Undo, 다른 이름 저장 |
| 2D CAD 뷰어 | DXF 파싱, DWG 변환 로딩, 벡터 렌더링, Zoom/Pan |
| 3D 모델 뷰어 | STL/STEP 로딩, OpenGL 렌더링, 트랙볼 회전 |
| 파일 탐색기 | 내 컴퓨터·드라이브 트리, 지원 포맷 자동 필터링, 실시간 검색 |
| 파일 패널 | 미리보기·아이콘·간단히·자세히 4가지 뷰, 썸네일 비동기 로딩, 크기 슬라이더 |

---

## 지원 포맷

### 이미지 (편집 가능)

`.png` `.jpg` `.jpeg` `.bmp` `.gif` `.ico` `.tif` `.tiff` `.webp`
`.ppm` `.pgm` `.pbm` `.pnm` `.tga` `.dds` `.dib`

### 이미지 (뷰어 전용 / 일부 포맷은 첫 페이지 또는 기본 프레임)

`.heic` `.heif` `.avif` `.svg` `.raw` `.psd` `.pdf`

### 2D CAD (뷰어 전용)

`.dxf` `.dwg`

> DWG는 파일 구조상 직접 파싱하지 않고 ODA File Converter로 임시 DXF 변환 후 로딩합니다. DWG를 열려면 ODA File Converter 설치가 필요할 수 있습니다.

### 3D 모델 (뷰어 전용)

`.stl` `.step` `.stp`

---

## 기술 스택

| 분류 | 라이브러리 |
|---|---|
| GUI | PyQt6 |
| 이미지 처리 | Pillow |
| 확장 이미지 포맷 | pillow-heif, rawpy, pypdfium2, PyQt6 QtSvg |
| 2D CAD 파싱 | ezdxf, ezdxf.addons.odafc |
| 3D Mesh | trimesh |
| 3D 렌더링 | PyOpenGL |
| STEP 파싱 | cadquery-ocp |

---

## 설치 및 실행

### 요구 사항

- Python 3.10 이상

### 패키지 설치

```bash
pip install -r requirements.txt
```

### 실행

```bash
python main.py
# 또는 탐색기에서 이미지 파일과 연결하여 더블클릭으로 바로 열기
python main.py path/to/file.png
```

### DWG 열기

DWG 파일은 ODA File Converter가 설치되어 있으면 자동으로 변환해서 엽니다. 자동 탐색이 되지 않으면 환경 변수에 실행 파일 경로를 지정할 수 있습니다.

```powershell
setx ODA_FILE_CONVERTER "C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"
```

### 실행 파일 빌드

```bat
build_exe.bat        :: windowed onefile 빌드
build_exe_fast.bat   :: 빠른 실행용 onedir 빌드
build_exe_debug.bat  :: 콘솔 표시 디버그 빌드
```

빌드 결과와 로그는 `exe/` 폴더 아래에 생성됩니다. `exe/`는 Git 추적에서 제외됩니다.

---

## 프로젝트 구조

```
PyImageViewer/
├── main.py                      # 앱 진입점 + 전체 QSS 테마
├── build_exe.bat                # PyInstaller onefile 빌드
├── build_exe_fast.bat           # PyInstaller onedir 빠른 실행 빌드
├── build_exe_debug.bat          # 콘솔 표시 디버그 빌드
├── requirements.txt
├── image/
│   ├── icon/
│   │   ├── Casa-ImageViewer-ICON.png
│   │   └── Casa-ImageViewer-ICON.ico
│   └── folder_icon/
│       └── folder_default/link/user/favorite/share/open/selected.png
├── ui/
│   ├── main_window.py           # 메인 윈도우, 커스텀 헤더 바, 보기 메뉴
│   ├── file_browser.py          # 내 컴퓨터 + 드라이브 폴더 트리 (지연 로딩)
│   ├── file_panel.py            # 파일 목록 4종 뷰 + 썸네일 + 크기 슬라이더
│   ├── folder_icons.py          # 커스텀 폴더 아이콘 공용 모듈
│   ├── viewer_stack.py          # QStackedWidget 뷰어 전환
│   ├── image_viewer.py          # 이미지 뷰어/편집, 드래그 기반 자르기
│   ├── cad_viewer.py            # 2D CAD 뷰어
│   ├── model3d_viewer.py        # 3D 모델 뷰어 (OpenGL)
│   └── resize_dialog.py         # 크기 조정 다이얼로그
├── loaders/
│   ├── image_loader.py          # Pillow/확장 포맷 이미지 로더
│   ├── dxf_loader.py            # ezdxf + ODA 기반 DXF/DWG 로더
│   ├── stl_loader.py            # trimesh 로더
│   └── step_loader.py           # cadquery-ocp 로더
├── services/
│   ├── file_type_detector.py    # 확장자 → ViewerMode 매핑
│   └── loader_thread.py         # QThread 비동기 로더
└── models/
    └── viewer_mode.py            # ViewerMode Enum
```

---

## 개발 마일스톤

| 단계 | 목표 | 상태 |
|---|---|---|
| 1단계 | 프로젝트 인프라 (MainWindow, 파일 탐색기, 뷰어 전환) | 완료 |
| 2단계 | 이미지 뷰어 (로딩, Zoom, Rotate, Save As) | 완료 |
| 3단계 | 이미지 편집 (Crop, Resize, Undo) | 완료 |
| 4단계 | DXF Viewer | 완료 |
| 5단계 | STL Viewer | 완료 |
| 6단계 | STEP 지원 | 완료 |
| 7단계 | 안정화 (비동기 로딩, QSettings, 최근 파일) | 완료 |
| 8단계 | GUI 리디자인 (크림 테마, 커스텀 헤더, 검색 필터) | 완료 |
| 9단계 | UI 개선 (폴더 아이콘, 뷰 스타일, 썸네일, 내 컴퓨터, 슬라이더) | 완료 |
| 10단계 | PyInstaller 패키징 (onefile/fast/debug 빌드) | 완료 |
| 11단계 | 실행 속도 최적화, 확장 포맷, DWG 변환, Crop UX 개선 | 완료 |
