# 가구 확장·부분 애니메이션·오디오 위치·공연 제거

2026-11-22 · Linux / Python 3.12 / PySide6 6.12.0 / Qt offscreen.

- 자동 검사 101개.
- 가구/소품 25종과 사용자 사진 액자, 6개 분류 탭을 검증했습니다. 모든 SVG 및 움직이는 레이어를 실제 Qt SVG 렌더러로 읽었습니다.
- 가구 25개를 동시에 생성하고 조명 움직임 켜기/끄기, 책상 고정, 편집 중 정지, 편집 종료 후 재개를 검사했습니다.
- 움직이는 부분은 별도 SVG 레이어와 Qt Quick 변환 애니메이터로 처리합니다. 본체는 그대로 둡니다.
- 오디오 막대의 부모가 LP가 아닌 음악 카드이며 재생바 위에 위치하는지 검사했습니다.
- 공연 위젯, 설정, 데이터 키를 제거했습니다. 예전 테마의 공연 데이터는 읽어도 복원하지 않습니다. 개인 달력/일정은 유지합니다.
- 기존 메모 입력, 비동기 저장, 가구 드래그/고정/회전/테마 보관, 오디오/시스템 갱신 분리 검사를 포함합니다.
- Windows x64 GUI 실행 파일을 준비하고 패키지 의존성/ZIP CRC를 검사했습니다. 회사명 마스는 파일 속성이며, Authenticode 서명은 아닙니다.

Windows 실제 장치에서 재생 제어, 스피커 출력 캡처, GPU 및 체감 성능, SmartScreen/서명 동작은 실기 검증하지 못했습니다. 공개 신뢰 코드 서명 인증서가 제공되지 않았습니다.


## 설치형 배포 검증

- NSIS 3.11의 Windows x64 Unicode 설치 프로그램을 생성했습니다. 설치·제거 모두 현재 사용자 권한으로 실행합니다.
- 압축 무결성 검사 통과. 설치 파일을 추출해 2,704개 원본 파일의 SHA-256이 실행용 폴더와 모두 같은지 확인했습니다.
- 실행 파일 PE 아키텍처, 회사명 마스, 버전 1.2.0.0, asInvoker 매니페스트를 검사했습니다. Authenticode 서명은 없습니다.
- 설치·제거 동시 실행 방지, 알려진 로컬 파이프의 서버 프로세스에만 정상 종료 요청, 파일별 제거 목록, HKCU 등록 및 사용자 데이터 보존을 스크립트에서 확인했습니다.
- 실제 Windows에서 설치와 제거 UI를 실행하는 실기 검증은 하지 못했습니다.


## 1.3.0 업데이트 기능

- 기존 검사에 업데이트 검사 6개를 더해 107개 통과했습니다. 이후 변경한 다운로드 취소 정리와 설치 핸드오프 처리는 업데이트 검사로 다시 확인했습니다.
- 버전 비교, HTTPS와 GitHub 호스트 제한, 배포 저장소 일치, SHA-256 및 길이 검증, 잘린 파일 거부, 파일 원자 교체, 취소 및 별도 프로세스 통신을 검사했습니다.
- 설치 직전에도 별도 프로세스에서 해시를 검사하며 Windows의 일반 실행 경로와 다운로드 파일 보안 표시를 유지합니다. 보안 경고를 끄지 않습니다.
- 설정 → 업데이트, 시작 시 및 6시간 간격 확인, 명시적 버튼 클릭 후 설치하는 흐름을 추가했습니다.
- NSIS의 /AUTOUPDATE 스위치와 설치 성공 후 재실행 코드를 추가했습니다.
- 공개 배포 저장소 생성과 실제 새 버전 배포는 GitHub 브라우저 로그인이 필요합니다. 현재 전용 저장소 연결은 준비 단계이며, 실제 Windows 설치 전환과 실서비스 업데이트는 실기 검증하지 못했습니다.

## 1.4.0 배경 업데이트

- 전체 자동 검사 110개 통과. 사진별 시간, 순서, 삭제, 중지·재개, 영상 모드 전환, 누락 파일, 설정 보존 및 테마 내보내기·가져오기 확인.
- Windows 11의 Progman 하위 WorkerW 탐색과 동적 FFmpeg DLL 배치 수정. 실제 Windows 바탕화면 연결·영상 GPU 출력은 이 Linux 환경에서 실기 검증하지 못했습니다.
- 기본 사진 5장과 영상 1개의 공개 배포를 사용자가 승인했습니다. Windows CI에서 설치 파일을 빌드하고 실행 검사를 통과한 경우에만 게시합니다. 실제 Explorer 바탕화면 연결·GPU 영상 재생은 별도 실기 확인이 필요합니다.

## 공개 배포 확인

- GitHub Windows release #3에서 Windows x64 런타임·네이티브 실행 파일·설치 파일 빌드, 패키지 앱 실행 검사 및 v1.4.0 릴리스 게시가 통과했습니다.
- 공식 Windows NSIS에 amd64 부트스트랩이 없는 경우 x86 설치 부트스트랩으로 x64 앱을 설치합니다. 64비트 OS 확인과 64비트 레지스트리 보기를 유지합니다.
- Explorer 바탕화면 연결과 실제 GPU 영상 출력·설치 후 재실행은 Windows 실기 확인이 별도로 필요합니다.

## 1.5.0 업데이트 알림

- 전체 검사 116개 통과. 15초 대기, 입력·편집 중 보류, 같은 버전 중복 알림, 이번 실행 동안 미루기, 미리보기의 설치 방지, 작업 프로세스 종료 뒤 설치 시작을 검사했습니다.
- 실제 QML 장면에서 왼쪽 아래 알림이 위젯보다 높은 z 순서로 나타나고 버튼을 클릭할 수 있음을 확인했습니다.
- 사용자가 새 누끼 인물 이미지와 이를 포함한 설치 파일의 공개 배포를 승인했습니다. Windows CI에서 빌드 및 앱 실행 검사를 통과한 설치 파일을 게시합니다.

## 1.5.1 인물 표시 및 배포 자료 복구

- Windows 설치본에서 libpng의 IDAT 압축 오류를 재현했습니다. 업로드 출력 제한으로 인물 PNG와 일부 큰 기본 자료가 잘린 것이 원인이었습니다.
- 영향을 받은 8개 파일을 작은 구간으로 읽어 재전송하고 GitHub가 반환한 모든 blob SHA가 원본과 일치함을 확인했습니다.
- 13개 기본 바이너리 자료의 파일 크기와 SHA-256을 assets/integrity.json으로 고정하고 불일치 시 Windows 빌드를 중단합니다.
- 인물 그리기 영역과 말풍선 클릭 영역을 분리하고 이미지 준비·등장 애니메이션·크기 변경 후 표시 영역을 갱신합니다.
- Windows 빌드 실행 검사에서도 알림을 표시하고 인물 이미지의 준비 상태를 확인합니다.

- 최종 자동 검사 120개 통과.


## 1.6.0
- Full prior suite plus new weather/theme cases: 124 passed. Compact navigation/dark-mode UI test: 1 passed (125 total); native photo night/day pixel regression adds one case (126 total).
- Weather location→forecast requests tested using deterministic responses, including direct-city override, rounded/invalid coordinates and WMO rain/snow/storm mappings.
- Theme test verifies custom global/individual colors survive and default music card changes to dark.
- QML scene rendered without errors; weather screenshot is a deterministic preview, not a live weather observation.
- Closed all timers/services in settings fixture teardown: the old fixture left writer threads and Qt objects alive between tests.
- Public network service availability and accuracy at the user's IP were not tested from the restricted build environment. Failures are surfaced in the UI and direct city selection is available.

- Night dim is rendered into the Windows photo wallpaper and refreshes on weather/day transition; video uses its background layer. Regression checks dimmed pixels, distinct cache file, and day restoration.


## 1.6.1
- Fix six-hour background interval to 60 seconds, using public HEAD redirect probes and verified REST metadata only for a newer version.
- Added HEAD preservation through redirects, no REST lookup for current version, cross-repository redirect rejection, subprocess probe → desktop prompt integration without settings, and quiet retry/backoff tests.
- Existing install/download hash and trusted-host checks remain in place. Old clients retain their previous schedule until this version is installed.


## 1.6.2
Removed weather UI, location preferences, weather service and its QML card. Existing persisted weather settings are discarded by state validation. Night lighting uses only PC time (19:00–07:00). Regression tests cover legacy weather settings removal, custom colors, palette mouse input and native night/day wallpaper restoration.


## 1.7.0
- Full Linux/offscreen suite: 134 passed; follow-up shell/theme/atomic-image checks: 8 passed.
- New tests exercise ordered app search, bounded file fallback, quality/preferences validation, original byte preservation, 3840×2160 output, GUI timer responsiveness during import/render, search opening and selection, custom-color preservation and asynchronous night/day background changes.
- Native guardian CI smoke test checks stop-event and parent-death exits using a hidden STATIC window. It does not hide a taskbar or intercept keyboard input.
- Native Win-key capture/Win combinations, actual Explorer taskbar restoration, Store-app identity and Windows Search result availability require physical Windows checks; no claim that those inputs were simulated on Linux.
- Local QML scene and separate dock/search/settings rendered without QML errors.


## 1.7.1
Added regression coverage for spatial taskbar order, no app truncation, paging, non-topmost dock flags, restored original launcher, all-app start grid, four windows in one group, paused-audio suspension, shared automatic/manual feed reads, malicious feed rejection and API fallback. Actual host HEAD and REST probes both succeeded against v1.7.0: user-specific failure was not reproduced, so no claim that HEAD blocking was confirmed. Native Explorer UIA order and physical Win keys require Windows desktop verification; CI validates compilation, guardian lifetime and packaged image loading.

- Final source suite: 137 passed. Packaged live automatic probe (not a settings click) is now a required Windows build step, using the actual public metadata and checksum before installer publication.

- Follow-up shell/app integration tests cover desktop-space reservation and original launcher behavior. Overlay mask now updates when its size changes so reserving dock space does not leave stale click regions.
