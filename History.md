# History

## Release 0.5 — 2026-05-18

### 5단계: STL 3D 뷰어

- `loaders/stl_loader.py` — trimesh 기반 STL 파서
  - trimesh.load(force='mesh') 로 메시 로딩
  - 페이스 노멀 기반 플랫 셰이딩용 flat_vertices / flat_normals 배열 사전 생성 (face × 3 확장)
  - 바운딩 스피어 중심(center) + 반지름(radius) 추출
- `ui/model3d_viewer.py` — QOpenGLWidget 기반 3D 뷰어
  - CompatibilityProfile + 24bit 깊이 버퍼
  - GL_FLAT 셰이딩, GL_LIGHT0 방향광, 소재 ambient/diffuse/specular 설정
  - glVertexPointer / glNormalPointer + glDrawArrays(GL_TRIANGLES) 로 메시 렌더링
  - 아크볼(Arcball) 트랙볼 회전: 스크린 좌표 → 단위 구면 투영 → QQuaternion 누적
  - 좌클릭 드래그 = 회전, Ctrl+좌클릭 / 중간버튼 드래그 = 팬, 스크롤 = 줌
  - 화면 맞춤(fit): 쿼터니언·팬 리셋, zoom = radius × 3
  - 좌하단 XYZ 축 오버레이 (2D 오르토 패스, 빨강/초록/파랑)
- `ui/viewer_stack.py` — MODEL_3D 슬롯(index 3)에 Model3DViewerWidget 연결 (Placeholder 제거)
- `ui/main_window.py` — 3D 모드 추가
  - `_set_3d_mode()`: 뒤로 + 공용 줌 버튼 표시 (CAD 모드와 동일 구조)
  - `_zoom_in/_zoom_out/_fit` — MODEL_3D 디스패치 추가
  - `_on_file_opened` — MODEL_3D 분기 추가

---

## Release 0.1 — 2026-05-18

### 1단계: 프로젝트 인프라

- 프로젝트 초기 구조 생성
- `models/viewer_mode.py` — ViewerMode Enum 정의 (NONE / IMAGE / CAD_2D / MODEL_3D)
- `services/file_type_detector.py` — 확장자 기반 ViewerMode 자동 감지, 지원 포맷 필터링
- `ui/file_browser.py` — 폴더 트리(QTreeView) 패널, 홈 폴더 자동 이동
- `ui/file_panel.py` — 멀티뷰 파일 패널 (큰 아이콘 / 작은 아이콘 / 간단히 / 자세히)
- `ui/viewer_stack.py` — QStackedWidget 기반 뷰어 전환 (파일 패널 / 이미지 / CAD / 3D)
- `ui/main_window.py` — 메인 윈도우, QSplitter 레이아웃, 메뉴바, 상태바, 뷰 모드 툴바
- `main.py` — 앱 진입점
- `requirements.txt` 작성 (PyQt6, Pillow, ezdxf, trimesh, PyOpenGL)

### 1단계 UI 변경 (2026-05-18)

- 파일 목록을 폴더 트리 아래에서 우측 메인 영역으로 이동 (Windows 탐색기 구조)
- 뷰 모드 4종 추가: 큰 아이콘, 작은 아이콘, 간단히, 자세히
- 툴바: 탐색 모드에서는 뷰 모드 버튼 표시, 뷰어 모드에서는 뒤로 버튼으로 전환
- 파일 더블클릭 시 뷰어로 전환, 뒤로(Alt+Left) 버튼으로 파일 패널 복귀
- 상태바: 폴더 선택 시 경로+파일 수, 파일 열람 시 파일명+크기+모드 표시

---

## Release 0.4 — 2026-05-18

### 4단계: DXF 뷰어

- `loaders/dxf_loader.py` — ezdxf 기반 DXF 파서
  - 지원 엔티티: LINE / CIRCLE / ARC / LWPOLYLINE (bulge 아크 포함) / POLYLINE / SPLINE / ELLIPSE / INSERT (블록 참조 재귀 전개)
  - DXF Y-up → Qt Y-down 좌표 변환 (Y 축 반전)
  - 모든 엔티티를 단일 QPainterPath로 수집
- `ui/cad_viewer.py` — QGraphicsView 기반 2D CAD 뷰어
  - 마우스 휠 줌, ScrollHandDrag 팬
  - 화면 맞춤(fit), Cosmetic Pen(0px, 항상 1px 선폭)
  - 검은 배경, 연회색(200,200,200) 엔티티
  - DXF 파싱 오류 시 경고 다이얼로그 표시
- `ui/viewer_stack.py` — CAD_2D 슬롯에 Cad2DViewerWidget 연결
- `ui/main_window.py` — 툴바 구조 리팩토링 및 CAD 모드 추가
  - `_image_only_acts` (이미지 전용): 실행 취소, 자르기, 크기 조정, 회전, 저장
  - `_viewer_acts` (이미지 + CAD 공용): 확대(Ctrl++) / 축소(Ctrl+-) / 화면 맞춤(Ctrl+0)
  - `_current_mode` 필드로 확대/축소/맞춤 동작을 현재 뷰어에 위임
  - `_set_cad_mode()` 추가: 뒤로 + 공용 줌 버튼만 표시

---

## Release 0.3 — 2026-05-18

### 3단계: 이미지 편집

- `ui/resize_dialog.py` — 크기 조정 다이얼로그 (너비/높이 스핀박스, 비율 유지 체크박스)
- `ui/image_viewer.py` — 이미지 편집 기능 추가
  - Undo 스택 (최대 20단계, Ctrl+Z)
  - 자르기(Crop): 자르기 버튼 → 십자 커서 → QRubberBand 드래그 → 자동 적용, ESC로 취소
  - 크기 조정(Resize): LANCZOS 필터, 비율 유지 옵션
  - 회전(CW/CCW) 시 Undo 히스토리에 저장 (기존에는 저장 안 됨)
  - 새 파일 로드 시 Undo 히스토리 초기화
  - 원본 파일 직접 수정 없음 — 메모리 PIL.Image 편집, 저장 시에만 파일 기록
- `ui/main_window.py` — 툴바 이미지 편집 영역 추가
  - 실행 취소 (Ctrl+Z): 히스토리 없을 때 자동 비활성화
  - 자르기: 토글 버튼, crop 완료/ESC/뒤로 시 자동 해제
  - 크기 조정: 크기 조정 다이얼로그 호출

---

## Release 0.2 — 2026-05-18

### 2단계: 이미지 뷰어

- `loaders/image_loader.py` — Pillow 기반 이미지 로딩, EXIF 회전 자동 보정, PIL→QPixmap 변환
- `ui/image_viewer.py` — QGraphicsView 기반 이미지 뷰어
  - 마우스 휠 줌 (Ctrl++ / Ctrl+-)
  - 화면 맞춤 (Ctrl+0)
  - 시계방향 / 반시계방향 90° 회전 (PIL Transpose, 무손실)
  - 다른 이름으로 저장 (PNG / JPEG / BMP / TIFF / WebP, Ctrl+Shift+S)
  - ScrollHandDrag 팬, AnchorUnderMouse 줌 앵커
- `ui/viewer_stack.py` — 이미지 뷰어 플레이스홀더를 ImageViewerWidget으로 교체
- `ui/main_window.py` — 모드별 툴바 분리
  - 탐색 모드: 뷰 스타일 버튼
  - 이미지 모드: 확대 / 축소 / 화면 맞춤 / 회전 / 다른 이름으로 저장
  - CAD·3D 모드: 뒤로 버튼만 표시 (4·5단계에서 확장)
