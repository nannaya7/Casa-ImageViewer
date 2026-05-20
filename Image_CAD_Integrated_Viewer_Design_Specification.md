# Image & CAD Integrated Viewer Project Specification (초판) Release 0.1

## 1. 프로젝트 개요

- 프로젝트명: Image & CAD Integrated Viewer
- 목적:
  - 일반 이미지 파일은 편집 가능
  - 2D/3D CAD 파일은 Readonly 전용
  - AI 협업 기반 단계별 개발 진행

---

## 2. 지원 포맷 정의

### 2.1 일반 이미지 포맷

#### 1차 필수 지원
- `.png`
- `.jpg`
- `.jpeg`
- `.bmp`
- `.gif`
- `.ico`
- `.tif`
- `.tiff`
- `.webp`

#### 2차 확장 지원
- `.ppm`
- `.pgm`
- `.pbm`
- `.pnm`
- `.tga`
- `.dds`
- `.dib`

#### 선택 지원
- `.heic`
- `.heif`
- `.avif`
- `.svg`
- `.raw`
- `.psd`
- `.pdf`

---

## 3. CAD 및 3D 포맷 지원

### 2D CAD
- `.dxf`
- `.dwg`

### 3D 모델
- `.stl`
- `.step`
- `.stp`

---

## 4. 기술 스택

| 분류 | 기술명 | 용도 |
|---|---|---|
| Language | Python 3.10+ | 기본 개발 언어 |
| GUI | PyQt6 / PySide6 | UI 구성 |
| Image Core | Pillow / pillow-heif / rawpy / pypdfium2 / QtSvg | 이미지 처리 및 확장 포맷 |
| 2D CAD Parser | ezdxf + ODA File Converter | DXF 파싱 및 DWG 변환 |
| 3D Mesh | trimesh | STL 로드 |
| STEP Parser | pythonOCC / CadQuery | STEP 처리 |
| 3D Rendering | PyOpenGL / VTK | 3D 렌더링 |

---

## 5. 시스템 아키텍처

```text
ViewerApp
 ├─ MainWindow (975줄)
 │   ├─ FileBrowserPanel       ← 내 컴퓨터 + 드라이브 트리 (QStandardItemModel, 지연 로딩)
 │   ├─ FilePanelWidget        ← 4가지 뷰 스타일 + 썸네일 + 크기 슬라이더 + 우클릭 메뉴
 │   ├─ CustomHeaderBar        ← 탐색/뷰어 모드 전환 (QWidget 기반)
 │   ├─ ViewerStack (Lazy)     ← 처음 열릴 때만 뷰어 인스턴스 생성
 │   │   ├─ ImageViewerWidget  ← 드래그 Crop + 핸들 조정 + 오른쪽 드래그 Pan
 │   │   ├─ Cad2DViewerWidget
 │   │   └─ Model3DViewerWidget
 │   ├─ StatusBar
 │   └─ About/License Dialog
 │
 ├─ ui (공용 모듈)
 │   └─ folder_icons.py        ← 커스텀 폴더 아이콘 지연 로딩 + 유형별 매핑
 │
 ├─ loaders
 │   ├─ image_loader.py        ← Pillow + HEIC/AVIF/SVG/RAW/PDF/PSD 확장
 │   ├─ dxf_loader.py          ← ezdxf + ODA 자동 탐색으로 DWG 지원
 │   ├─ stl_loader.py
 │   └─ step_loader.py
 │
 ├─ services
 │   ├─ file_type_detector.py
 │   └─ loader_thread.py       ← QThread 범용 비동기 로더
 │
 └─ models
     └─ viewer_mode.py
```

---

## 6. UI 레이아웃 구조

```text
+-----------------------------------------------------------------------------+
| MenuBar                                                                    |
+-----------------------------------------+-----------------------------------+
|                                         | Toolbar                          |
| Left File Explorer                      +-----------------------------------+
|                                         |                                   |
| Folder Tree                             | QStackedWidget                    |
| File List                               |                                   |
|                                         | Image Viewer                      |
|                                         | 2D CAD Viewer                     |
|                                         | 3D Model Viewer                   |
+-----------------------------------------+-----------------------------------+
| StatusBar                                                                  |
+-----------------------------------------------------------------------------+
```

---

## 7. 이미지 모듈 설계

### 핵심 기능
- 확대/축소
- 확대 상태 화면 이동
- 회전
- 잘라내기(Crop)
- 크기 조정(Resize)
- 다른 이름 저장
- Undo 지원

### 구현 원칙
- 원본 파일 직접 수정 금지
- 메모리상에서 PIL.Image 객체 편집
- 저장 시에만 파일 기록

### Crop 설계
- 별도 자르기 버튼 없이 이미지 위 왼쪽 드래그로 ROI 선택
- QRubberBand와 8개 핸들로 선택 영역 표시
- 마우스 릴리즈 후 즉시 적용하지 않고, 모서리/변 드래그로 영역 조절
- 선택 영역 내부 클릭 시 ROI 좌표 계산 후 `image.crop()` 수행
- `Esc`로 현재 선택 영역 취소

### 이미지 Pan 설계
- 확대되어 스크롤 가능한 상태에서 오른쪽 버튼 드래그로 화면 이동
- 왼쪽 버튼은 자르기 생성/조절/확정에 사용
- 화면 이동은 `QGraphicsView` 스크롤바 값을 직접 갱신해 처리

### Resize 설계
- 비율 유지 옵션
- LANCZOS 필터 적용

---

## 8. 2D CAD Viewer 설계

### 지원 객체
- LINE
- CIRCLE
- ARC
- LWPOLYLINE

### 기능
- Zoom
- Pan
- Fit To Window

### DWG 처리 정책
- DWG 직접 파싱은 미지원
- `ezdxf.addons.odafc` + ODA File Converter 기반
- DWG → 임시 DXF 변환 후 기존 DXF 렌더링 파이프라인으로 로딩
- 변환기 자동 탐색: PATH, `Program Files`, `ODA_FILE_CONVERTER`, `ODAFC_PATH`
- 변환기가 없거나 변환 실패 시 사용자에게 원인 안내

---

## 9. 3D Viewer 설계

### STL
- trimesh.load()
- Vertex / Face 추출
- OpenGL 렌더링

### STEP
- CadQuery 또는 pythonOCC 사용
- 테셀레이션 후 Mesh 변환

### 인터랙션
- Rotate
- Pan
- Zoom
- Axis 표시
- Fit View

---

## 10. 비동기 처리 및 최적화

### 적용 기능
- QThread 기반 비동기 로딩
- 대용량 이미지 다운샘플링
- 로딩 진행률 표시
- 로딩 취소 기능

### 메모리 정책
- 썸네일 캐시 분리
- 최근 파일 캐시 제한

---

## 11. AI 협업 개발 전략

### AI 활용 원칙
- 단계별 구현 요청
- 한 번에 하나의 기능만 요청
- UI와 로직 분리 요청
- 항상 테스트 가능한 코드 생성 요구

### 권장 AI 요청 방식

```text
PyQt6 기반으로 파일 탐색기와 QStackedWidget 구조를 구현해줘.
확장자에 따라 Viewer 모드가 자동 전환되게 해줘.
```

```text
Pillow 기반 이미지 Crop 기능을 구현해줘.
QRubberBand와 조절 핸들을 사용해서 ROI를 선택하고, 내부 클릭으로 crop을 확정하게 해줘.
```

---

## 12. 단계별 개발 마일스톤

| 단계 | 내용 | 상태 |
|---|---|---|
| 1단계 | 프로젝트 인프라 (MainWindow, 파일 탐색기, 뷰어 전환) | 완료 |
| 2단계 | 이미지 뷰어 (Pillow, QGraphicsView, 줌/회전/저장) | 완료 |
| 3단계 | 이미지 편집 (Undo, Crop, Resize) | 완료 |
| 4단계 | DXF 뷰어 (ezdxf, QPainterPath, Zoom/Pan) | 완료 |
| 5단계 | STL 3D 뷰어 (trimesh, QOpenGLWidget, 아크볼 회전) | 완료 |
| 6단계 | STEP 3D 뷰어 (cadquery-ocp, STL 변환 경유) | 완료 |
| 7단계 | 안정화 (QThread 비동기, QSettings, 최근 파일) | 완료 |
| 8단계 | GUI 리디자인 (크림 테마, 커스텀 헤더 바, 검색 필터) | 완료 |
| 9단계 | UI 개선 (폴더 아이콘, 뷰 스타일, 썸네일, 내 컴퓨터, 슬라이더) | 완료 |
| 10단계 | PyInstaller 패키징 (onefile/fast/debug 빌드) | 완료 |
| 11단계 | 실행 속도 최적화, 확장 포맷, DWG 변환, Crop UX 개선 | 완료 |

### 9단계 주요 구현 사항

#### FileBrowserPanel — 내 컴퓨터 트리

- `QStandardItemModel` + placeholder 기반 지연 로딩
- 최상위: 내 컴퓨터 → 특수 폴더(바탕화면·문서·다운로드·음악·사진·동영상) + 드라이브
- `navigate_to()`: 파일 패널 폴더 이동 시 트리 자동 동기화

#### FilePanelWidget — 파일 패널 개선

- 미리보기 뷰 하단 크기 슬라이더 (64px ~ 154px, 드래그 중 실시간 갱신)
- 간단히 모드: TopToBottom+Wrapping 다중 컬럼 + `_CompactSelectDelegate` 선택 블럭 최적화

#### folder_icons.py — 커스텀 폴더 아이콘

- 7종 PNG 지연 로딩, 경로 유형별 자동 매핑
- QIcon 상태별 다중 pixmap (Normal/Active/Selected)

### 10~11단계 주요 구현 사항

#### PyInstaller 패키징

- `build_exe.bat`: 터미널 창 없는 onefile 빌드
- `build_exe_fast.bat`: 빠른 실행을 위한 onedir 빌드
- `build_exe_debug.bat`: 콘솔 표시 디버그 빌드
- 결과물과 빌드 로그는 `exe/` 아래 생성
- 앱/실행 파일 아이콘은 `Casa-ImageViewer-ICON`으로 통일

#### 실행 속도 최적화

- 이미지/CAD/3D 뷰어 lazy 생성
- 로더 import 지연
- 시작 시 중복 폴더 로딩 제거
- 썸네일 생성은 큰 아이콘 보기에서만 수행
- 현재 활성 파일 목록 뷰만 갱신
- 이미지 확대 상태에서 오른쪽 버튼 드래그 기반 화면 이동 지원

#### 확장 포맷

- HEIC/HEIF/AVIF: `pillow-heif`
- SVG: `QSvgRenderer`
- RAW: `rawpy`
- PDF: `pypdfium2` 첫 페이지 렌더링
- PSD: Pillow 로딩

---

## 13. 권장 MVP 범위

### MVP 포함
- 이미지 뷰어/편집
- DXF Viewer
- STL Viewer

### MVP 제외
- STEP 고급 기능
- RAW/PSD 편집
- 고급 CAD 편집 기능

---

## 14. 결론

본 프로젝트는 이미지 편집 기능과 CAD/3D 순수 뷰어 기능을 통합한 데스크톱 애플리케이션 구축을 목표로 한다.

현재 구현 범위는 다음을 포함한다:

- 이미지 Viewer/Editor
- DXF Viewer
- DWG 변환 로딩
- STL/STEP 3D Viewer
- HEIC/HEIF/AVIF, SVG, RAW, PSD, PDF 확장 이미지 포맷
- PyInstaller 기반 실행 파일 빌드

포맷별 Loader 구조, lazy 뷰어 초기화, 비동기 로딩 아키텍처를 기반으로 확장성과 유지보수성을 확보한다.
