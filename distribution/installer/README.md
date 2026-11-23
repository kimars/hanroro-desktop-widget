# 설치형 배포

HanroroWidget_Setup_x64.exe 하나를 배포합니다. Windows 10/11 x64, 현재 사용자 계정용입니다. 관리자 권한을 요청하지 않고 기본적으로 LocalAppData/Programs/HanroroWidget에 설치합니다. 시작 메뉴와 바탕화면에 바로가기를 만들고 Windows 설치된 앱 목록에 제거 기능을 등록합니다.

설치·제거 전에 CloseHanroro.exe가 앱의 기존 로컬 파이프에 quit을 보내 정상 종료를 요청합니다. 해당 파이프 서버 프로세스만 기다리며 다른 Python 프로세스를 찾거나 강제 종료하지 않습니다. 응답이 없으면 작업을 중단합니다.

메모, 설정, 사용자 사진은 기존 Mars/HanroroDesktop 데이터 폴더에 유지합니다. 제거는 설치 때 포함한 파일만 목록에 따라 지웁니다. 설치 폴더 전체를 재귀 삭제하지 않습니다. 자동 실행을 이미 사용 중이면 설치된 실행 파일 경로로 갱신합니다.

## 다시 만들기

NSIS 3.11 이상과 실행용 폴더가 필요합니다. build_installer.py에 --payload 실행용폴더 --output HanroroWidget_Setup_x64.exe --work 빌드작업폴더를 전달합니다. makensis가 PATH에 없으면 --makensis로 경로를 지정합니다. Linux에서 옮겨 설치한 NSIS는 --nsis-dir로 데이터 디렉터리를 지정합니다.

CloseHanroro.exe의 소스는 close_widget.c입니다. MinGW-w64에서 -municode -mwindows -Os -s -static-libgcc 옵션과 shell32, ole32, bcrypt, uuid 라이브러리로 빌드합니다.

설치 파일은 현재 코드 서명되지 않았습니다. 제작자 속성과 설치된 앱 목록의 게시자는 마스이지만 Authenticode 검증된 게시자라는 뜻은 아닙니다. 공개 신뢰 코드 서명 인증서를 이용해 최종 설치 EXE에 서명한 후 배포할 수 있습니다.

검증: NSIS 컴파일, 설치 스크립트 범위 검사, PE 메타데이터 및 매니페스트, 설치 파일 전체 추출 후 원본 실행 파일들의 SHA-256 대조. 실제 Windows 설치/제거 실기 검증은 수행하지 못했습니다.
