# Windows 배포 서명

실행 파일의 회사명/제작자 속성은 마스입니다. 이 값은 Authenticode에서 검증한 게시자 이름과 별개이며, 현재 제공한 EXE는 서명되지 않았습니다.

SmartScreen의 알 수 없는 게시자를 없애려면 공개 신뢰 인증기관에서 발급받은 코드 서명 인증서로 EXE를 서명해야 합니다. 인증서의 확인된 이름이 Windows 게시자로 표시됩니다. 새 파일은 유효한 인증서로 서명해도 평판이 쌓이기 전까지 경고가 나올 수 있습니다. 임의의 이름을 속성에 적거나 자체 인증서를 만들었다고 해결되지 않습니다.

인증서와 개인 키를 Windows 사용자 인증서 저장소에 설치한 뒤 `SignRelease.ps1`에 인증서 지문과 압축 해제한 앱 폴더를 전달하면 서명·검증합니다. 서명한 EXE를 수정하지 말고 폴더를 다시 ZIP으로 묶어 배포합니다. 이 도구는 보안 설정이나 신뢰할 수 있는 루트 인증서를 변경하지 않습니다. 인증서 개인 키는 앱이나 ZIP에 포함하지 않습니다.

Microsoft Store의 MSIX 배포를 선택하면 Store의 심사 및 서명 경로를 이용할 수 있습니다. 계정 등록과 게시 심사가 따로 필요합니다.

공식 안내: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
