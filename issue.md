# Issue Tracker

## [OPEN] 미리보기 모드 썸네일 로딩 중 잔상(ghost image) 문제

**현상**  
미리보기(LARGE_ICONS) 모드에서 폴더를 이동할 때, 이전 폴더의 썸네일 또는 깨진 이미지가 잠시 새 폴더의 아이템 위에 나타난다.

**원인 분석 (미확정)**  
- `_populate_current_view`의 호출 순서 레이스 컨디션 가능성
  - `_populate_icon_list` (리스트 교체) → `_start_thumbnail_loading` (gen 증가) 순서일 때,
    이전 워커의 `ready` 시그널이 gen 증가 이전에 처리되면 새 아이템에 이전 썸네일이 덮어씌워질 수 있음
  - 수정 시도: 순서를 `_start_thumbnail_loading` → `_populate_icon_list`로 변경 → **여전히 재현됨**
- Qt 내부 아이콘 캐시 또는 뷰포트 렌더링 타이밍 문제 가능성
- `QPixmapCache` 레벨에서의 캐시 충돌 가능성

**시도한 수정**  
1. `_populate_icon_list` 호출 전에 `_start_thumbnail_loading`을 먼저 호출하도록 순서 변경 (`ui/file_panel.py` `_populate_current_view`) → 미해결

**추가 조사 필요 항목**  
- `self._large_list.viewport().update()` 호출 효과 확인
- `_retired_thumbnails`에 남은 스레드에서 시그널이 늦게 도착하는지 확인
- `QListWidget` 대신 `QAbstractItemModel` 기반으로 전환 시 문제 해소 여부
- `setUpdatesEnabled(False/True)` 로 렌더링 타이밍 제어 시도
