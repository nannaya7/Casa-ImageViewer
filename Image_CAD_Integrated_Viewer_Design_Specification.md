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
| Image Core | Pillow | 이미지 처리 |
| 2D CAD Parser | ezdxf | DXF 파싱 |
| 3D Mesh | trimesh | STL 로드 |
| STEP Parser | pythonOCC / CadQuery | STEP 처리 |
| 3D Rendering | PyOpenGL / VTK | 3D 렌더링 |

---

## 5. 시스템 아키텍처

```text
ViewerApp
 ├─ MainWindow
 │   ├─ FileBrowserPanel
 │   ├─ ToolbarManager
 │   ├─ ViewerStack
 │   │   ├─ ImageViewerWidget
 │   │   ├─ Cad2DViewerWidget
 │   │   └─ Model3DViewerWidget
 │   └─ StatusBar
 │
 ├─ loaders
 │   ├─ image_loader.py
 │   ├─ dxf_loader.py
 │   ├─ stl_loader.py
 │   ├─ step_loader.py
 │   └─ dwg_converter.py
 │
 ├─ services
 │   ├─ file_type_detector.py
 │   ├─ thumbnail_service.py
 │   ├─ async_loader.py
 │   └─ settings_service.py
 │
 └─ models
     ├─ loaded_file.py
     ├─ viewer_mode.py
     └─ format_capability.py
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
- QRubberBand 사용
- ROI 좌표 계산
- image.crop() 수행

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
- 직접 파싱 미지원
- ODA File Converter 기반
- DWG → DXF 변환 후 로딩

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
QRubberBand를 사용해서 ROI를 선택하고 crop 수행하게 해줘.
```

---

## 12. 단계별 개발 마일스톤

### 1단계 — 프로젝트 인프라
목표:
- MainWindow 생성
- 파일 탐색기
- QStackedWidget
- 확장자 인식

### 2단계 — 이미지 뷰어
목표:
- 이미지 로딩
- Zoom
- Rotate
- Save As

### 3단계 — 이미지 편집
목표:
- Crop
- Resize
- Undo
- 원본 보호

### 4단계 — DXF Viewer
목표:
- DXF 파싱
- 벡터 렌더링
- Zoom/Pan

### 5단계 — STL Viewer
목표:
- STL 로딩
- OpenGL 렌더링
- Trackball 회전

### 6단계 — STEP 지원
목표:
- STEP 로딩
- 테셀레이션
- Mesh 렌더링

### 7단계 — 안정화
목표:
- 비동기 로딩
- 예외 처리
- 설정 저장
- 최근 파일

### 8단계 — 배포
목표:
- PyInstaller 패키징
- Windows 실행 파일
- 외부 의존성 정리

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

MVP 단계에서는:
- 이미지 Viewer/Editor
- DXF Viewer
- STL Viewer

까지 우선 구현하고, 이후:
- STEP
- DWG
- HEIC/AVIF
- SVG/PDF

등의 고급 포맷을 확장하는 방식으로 진행한다.

포맷별 Loader 구조와 비동기 로딩 아키텍처를 기반으로 확장성과 유지보수성을 확보한다.
