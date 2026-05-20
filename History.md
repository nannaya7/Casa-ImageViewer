# History

## Release 0.10 — 2026-05-20

### 실행 속도, 패키징, 포맷 지원, 이미지 편집 UX 개선

#### 시작 속도 및 안정화

- `ui/viewer_stack.py`: 이미지/CAD/3D 뷰어를 앱 시작 시 모두 만들지 않고, 필요한 순간에 생성하는 lazy 초기화로 변경
- `ui/main_window.py`: 이미지/DXF/STL/STEP 로더 import를 파일 열기 시점으로 지연
- 시작 시 `runtime.log` 기록을 제거하고, 예외 발생 시에만 `*.runtime.log` 기록
- 초기 폴더 로딩을 "내 컴퓨터" 1회로 정리해 중복 로딩 제거
- `LoaderThread.finished` 커스텀 신호를 `loaded`로 변경해 `QThread.finished`와의 이름 충돌 제거
- 로더/썸네일 스레드 lifecycle 정리, stale 결과 무시, 닫기 시 wait 처리 보강
- 파일 크기 조회, `QSettings` 정수 변환, 권한 없는 폴더 접근, 빈 STL 메시 등 예외 처리 보강

#### 파일 탐색 및 파일 관리

- `ui/file_browser.py`: 드라이브 표시를 `C:\` 형식에서 `C 드라이브`, `D 드라이브` 형식으로 변경
- "내 컴퓨터"를 선택 가능한 항목으로 변경하고, 오른쪽 파일 목록에 특수 폴더와 드라이브를 표시
- 앱 시작 위치를 항상 "내 컴퓨터"로 변경
- `ui/file_panel.py`: 파일 목록 우클릭 메뉴 추가
  - 열기, 기본 앱으로 열기, 파일 위치 열기, 이름 바꾸기, 휴지통으로 이동, 경로 복사, 새로 고침, 현재 폴더 열기
- 미리보기 슬라이더 값을 `QSettings`에 저장/복원
- 현재 보이는 파일 목록 뷰만 populate하도록 최적화해 폴더 전환 속도 개선
- 썸네일 생성은 큰 아이콘 보기에서만 수행하도록 변경

#### 이미지 포맷 확장

- 이미지 지원 확장자 추가:
  - `.heic`, `.heif`, `.avif`, `.svg`, `.raw`, `.pdf`, `.psd`
- `loaders/image_loader.py`
  - HEIC/HEIF/AVIF: `pillow-heif` 등록 후 Pillow 로딩
  - SVG: `QSvgRenderer`로 래스터화 후 PIL 이미지 변환
  - RAW: `rawpy`로 현상 후 PIL 이미지 변환
  - PDF: `pypdfium2`로 첫 페이지 렌더링
  - PSD: Pillow 로딩 경로 사용
- `requirements.txt`에 `pillow-heif`, `rawpy`, `pypdfium2` 추가

#### DWG 지원 정책 구현

- `loaders/dxf_loader.py`: `.dwg` 파일은 `ezdxf.addons.odafc`를 통해 ODA File Converter로 임시 DXF 변환 후 로딩
- ODA File Converter 자동 탐색:
  - PATH의 `ODAFileConverter`
  - `C:\Program Files\ODA\...`
  - `ODA_FILE_CONVERTER` 또는 `ODAFC_PATH` 환경 변수
- 변환기가 없거나 변환 실패 시 원인을 안내하는 오류 메시지 표시

#### 이미지 편집 UX

- 자르기 버튼 제거
- 이미지 위에서 바로 왼쪽 드래그하면 자르기 선택 영역 생성
- 마우스를 떼도 즉시 적용하지 않고 선택 영역 유지
- 모서리/변 핸들 드래그로 영역 조절
- 선택 영역 안쪽 클릭 시 최종 자르기 적용
- `Esc`로 현재 선택 영역 취소
- 회전 버튼 텍스트(`↻`, `↺`)를 직접 그린 QIcon으로 교체해 폰트/인코딩 깨짐 방지
- 상단 툴바 버튼 글자 굵기를 `뒤로` 버튼과 동일하게 조정

#### PyInstaller 빌드

- `build_exe.bat`: windowed onefile 빌드, 결과물은 `exe/` 아래 생성
- `build_exe_fast.bat`: 빠른 실행을 위한 onedir 빌드
- `build_exe_debug.bat`: 콘솔 표시 디버그 빌드
- 빌드 로그를 `exe/build.log`, `exe/build_fast.log`, `exe/build_debug.log`에 저장
- 실행 파일 아이콘을 `image/icon/Casa-ImageViewer-ICON.ico`로 지정
- `.gitignore`: `exe/`, `EXE/`, `runtime.log`, `*.runtime.log` 제외
- PyInstaller Qt 충돌 방지를 위해 PyQt5/PySide 계열 제외, `ezdxf.addons.odafc` hidden import 추가

---

## Release 0.9+ — 2026-05-19

### UI 개선 (내 컴퓨터 · 미리보기 슬라이더 · 간단히 모드 · 폴더 아이콘 · 팔레트)

#### 내 컴퓨터 폴더 트리 (`ui/file_browser.py`)

- `QFileSystemModel` → `QStandardItemModel` 기반 커스텀 지연 로딩 트리로 전면 교체
- 최상위 노드 "내 컴퓨터" 추가 (시스템 컴퓨터 아이콘, 선택 불가)
  - 하위: 바탕 화면·문서·다운로드·음악·사진·동영상 (존재하는 폴더만 표시)
  - 하위: 연결된 드라이브 전체 (`QDir.drives()`)
- 지연 로딩: 모든 폴더 항목에 placeholder 자식 → 펼칠 때 실제 하위 폴더 로드
- `_path_index: dict[str, QStandardItem]` 로 경로 → 트리 항목 빠른 역조회
- `navigate_to(folder)`: 오른쪽 파일 패널에서 폴더 이동 시 트리 자동 따라가기
  - `_path_index` 조회 → 없으면 드라이브부터 단계별 확장·로드 후 선택

#### 미리보기 크기 슬라이더 (`ui/file_panel.py`)

- 미리보기(큰 아이콘) 뷰 하단 우측에 수평 슬라이더 (너비 120px) 추가
- 범위: 최소 64px(아이콘모드 크기) ~ 최대 154px(기존 대비 +20%)
- `valueChanged` → 아이콘·그리드 크기 실시간 갱신 (grid = `size × 200/128`, `size × 180/128`)
- `sliderReleased` → 썸네일 재로드 (드래그 중 불필요한 로딩 방지)
- `_start_thumbnail_loading`에 `max_size` 파라미터 추가
- `main.py` QSS: `#sliderBar` 배경·구분선 / `QSlider` groove·handle·sub-page 테마 추가

#### 간단히 모드 선택 블럭 개선 (`ui/file_panel.py`)

- `_CompactSelectDelegate(QStyledItemDelegate)` 추가
  - 선택 하이라이트를 아이콘+텍스트 실제 너비에만 그림 (기존 200px 그리드 전체 채움 방지)
  - 선택 시: (1) 둥근 하이라이트 rect → (2) 아이콘 → (3) `highlightedText` 색 텍스트 순으로 직접 그림
  - 비선택 시: `super().paint()` 위임
- `_list_view.setItemDelegate(_CompactSelectDelegate(...))` 적용
- `QListView.Flow.TopToBottom + Wrapping=True + gridSize(200, 24)` 유지 → 다중 컬럼 세로 레이아웃

#### 커스텀 폴더 아이콘 (`ui/folder_icons.py` 신규)

- 7종 PNG 지연 로딩 (`image/folder_icon/folder_*.png`)
- `_base_type(path)` 자동 감지: symlink→link / UNC→share / 홈→user / 즐겨찾기→favorite / 기본→default
- `make_folder_icon(path)` → Normal.Off=유형 아이콘, Normal.On/Active.Off=open, Selected.Off=selected
- `ui/file_panel.py` `_get_icon()`, `ui/file_browser.py` `_FolderIconModel.data()` 에서 공용 사용

#### 컬러 팔레트 및 기타 (`main.py`, `ui/main_window.py`)

- QSS 6색 시맨틱 팔레트 전면 적용 (Background `#F8F4EE` / Panel `#EEE8DF` / Border `#E5D7C8` / Primary `#D8A15B` / Hover `#F3E5D0` / Text `#4A382B`)
- 뷰 레이블 재정렬: 미리보기·아이콘·간단히·자세히
- 보기 메뉴 추가 (메뉴바)
- `_ArrowBranchStyle` 바로가기 화살표 오버레이 크기 축소

---

## Release 0.9 — 2026-05-19

### UI 개선 (파일 연결 · 폴더 트리 · 아이콘 뷰 · 썸네일)

#### 파일 연결 지원 (`main.py`)

- `sys.argv[1]` 경로를 받아 탐색기 더블클릭으로 바로 파일 열기
- `QTimer.singleShot(0, ...)` 으로 윈도우 표시 후 `window.open_file()` 호출

#### 폴더 트리 화살표 스타일 (`ui/file_browser.py`)

- `_ArrowBranchStyle(QProxyStyle)` 클래스 추가
  - `PE_IndicatorBranch` 오버라이드: 접힌 폴더 `>`, 열린 폴더 `v` 쉐브론 그리기
  - 리프 노드(파일 없는 항목)는 아무것도 그리지 않아 모든 연결선 제거
  - `QLineF` + 안티앨리어싱으로 부드러운 화살표 (`hw=1.76, hh=2.82`)
  - 색상: `#8A7060` (앱 테마 갈색 계열)
- `QTreeView::branch` QSS 규칙 완전 제거 — QSS 엔진이 개입하면 QProxyStyle이 무시되는 문제 방지
- `navigate_to(folder)` 공개 메서드 추가 (CLI 인수 등 외부에서 폴더 이동용)

#### 아이콘 크기 조정 (`ui/file_panel.py`)

- 큰 아이콘: 64×64 → **128×128** (grid 100×90 → 200×180, 2배)
- 작은 아이콘: 24×24 → **64×64** (grid 160×32 → 100×90, 이전 큰 아이콘 크기 적용)

#### 기본 뷰 모드 및 설정 복원 (`ui/main_window.py`)

- 최초 실행 기본값: 큰 아이콘 → **작은 아이콘**으로 변경
- 이후 실행: `QSettings`에 저장된 마지막 선택 모드 자동 복원 (기존 로직 활용)

#### 큰 아이콘 썸네일 미리보기 (`ui/file_panel.py`)

- `_ThumbnailWorker(QObject)` 클래스 추가
  - `QThread`에서 실행, `ready(int, QImage)` 시그널로 결과 전달
  - `QImageReader.setScaledSize()` 로 읽기 단계에서 축소 → 메모리·속도 효율
  - `.png .jpg .jpeg .bmp .gif .tif .tiff .webp .ppm .pgm .pbm .pnm` 포맷 지원
  - `cancel()` 플래그로 폴더 이동 시 즉시 중단
- `_start_thumbnail_loading()` / `_cancel_thumbnails()` / `_on_thumbnail_ready()` 추가
  - 세대(generation) 카운터 `_thumb_gen` 으로 이전 스레드의 오래된 결과 자동 무시
  - 폴더 진입 시 시스템 아이콘으로 즉시 표시 후, 썸네일 준비되는 순서대로 교체

---

## Release 0.8 — 2026-05-18

### 8단계: GUI 리디자인 (따뜻한 크림 테마 · 커스텀 헤더 바 · 검색 필터)

- `main.py` — 앱 전체 QSS 적용 (`app.setStyleSheet(_APP_QSS)`)
  - 따뜻한 크림/베이지 팔레트: 배경 `#F5EDE0`, 툴바·상태바 `#EDE0CC`
  - 메뉴바, 버튼(알약형), segmented control, 검색창, 트리뷰, 리스트, 스크롤바, 다이얼로그 전체 통일
- `ui/main_window.py` — `QToolBar` → 커스텀 `QWidget` 헤더 바로 전면 교체
  - **탐색 모드** (`_browse_bar`): 열기 버튼(좌) · 뷰 스타일 segmented control(중앙) · 검색창(우)
  - **뷰어 모드** (`_viewer_bar`): 뒤로 버튼 + 모드별 편집·줌·회전 그룹 위젯 (separator 포함)
  - `QAction` 키보드 단축키 → `QShortcut`으로 분리 (PyQt6.QtGui)
  - 폴더 이동 시 검색창 자동 초기화 (`blockSignals` 사용)
- `ui/file_browser.py` — 폴더 패널 헤더 다크 테마 → 크림 테마 (`objectName("folderHeader")`)
- `ui/file_panel.py` — 실시간 검색 필터 추가
  - `_filter_query: str` 인스턴스 변수 추가
  - `set_filter(query)` 공개 메서드: 파일 이름 포함 여부로 즉시 필터링
  - `load_folder()` 호출 시 `_filter_query` 자동 초기화
  - `_reload()` 헬퍼로 중복 코드 통합

---

## Release 0.7 — 2026-05-18

### 7단계: 안정화 (QThread 비동기 로딩 · QSettings · 최근 파일)

- `services/loader_thread.py` (신규) — QThread 기반 범용 비동기 로더
  - `LoaderThread(fn, file_path, parent)`: 블로킹 로더 함수를 백그라운드 스레드에서 실행
  - 성공 시 `finished(object)` 시그널, 실패 시 `error(str)` 시그널 발행
  - 세대(generation) 카운터 방식으로 탐색 이탈 후 도착한 결과 자동 무시
- 각 뷰어에 `display_X()` 메서드 추가 (비동기 결과 수신·표시 전용)
  - `image_viewer.display_image(pil_image, file_path="")` — PIL 이미지 즉시 반영
  - `cad_viewer.display_dxf(dxf_path)` — QPainterPath 즉시 반영
  - `model3d_viewer.display_mesh(mesh)` — MeshData 즉시 반영
- `ui/main_window.py` — 전면 리팩토링
  - **비동기 로딩**: `_on_file_opened()` → `LoaderThread` 시작, 툴바 비활성화 + 상태바 "로딩 중..." 표시
  - **세대 카운터**: `_load_gen` — 파일 전환 시 이전 스레드 결과 자동 무시
  - **로딩 취소**: `_cancel_loading()` — 뒤로/다른 파일 열기/창 닫기 시 스레드 정리
  - **QSettings**: `_restore_settings()` / `_save_settings()` / `closeEvent()`
    - 저장 항목: 창 크기·위치(`geometry`·`windowState`), 마지막 폴더(`lastFolder`), 뷰 스타일(`viewStyle`), 최근 파일(`recentFiles`)
    - 앱 재시작 시 마지막 폴더 자동 탐색, 뷰 스타일 복원
  - **최근 파일**: 파일 메뉴 → "최근 파일" 서브메뉴 (최대 10개, 목록 지우기 포함)
    - 파일 열 때마다 목록 맨 앞에 추가, 중복 제거
    - 앱 종료 후 재시작해도 유지

---

## Release 0.6 — 2026-05-18

### 6단계: STEP 3D 뷰어

- `loaders/step_loader.py` — cadquery-ocp(OCP) 기반 STEP 파서
  - `STEPControl_Reader`로 STEP 파일 읽기 및 전송 (`TransferRoots → OneShape`)
  - `BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)` 로 OCC 메시 생성 (선형 편차 0.1, 각도 편차 0.5 rad)
  - `StlAPI_Writer`로 임시 바이너리 STL 변환 후 기존 `load_stl()` 재활용 → `MeshData` 반환
  - cadquery 미설치 시 명확한 설치 안내 메시지 표시
  - OCP 모듈 경로: `OCP.STEPControl`, `OCP.BRepMesh`, `OCP.StlAPI` (cadquery-ocp 번들)
- `ui/model3d_viewer.py` — STEP 분기 추가
  - `load_file()`: 확장자 `.step`/`.stp` → `load_step()`, 나머지 → `load_stl()` 로 분기
  - 에러 타이틀을 "STL 오류" → "3D 모델 오류"로 일반화
- `requirements.txt` — `cadquery>=2.4.0` 추가 (OCP 번들 포함)

---

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
