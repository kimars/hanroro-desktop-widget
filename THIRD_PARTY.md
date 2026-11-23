# 출처와 라이선스

- Python — PSF License: https://www.python.org/
- PySide6 / Qt — LGPLv3/GPLv3/commercial: https://doc.qt.io/qtforpython-6/
- NanumSquareRound Regular/Bold — SIL OFL, NAVER / Sandoll: https://campaign.naver.com/nanumsquare_neo/ (`assets/fonts/NanumSquareRound-OFL.txt`)
- Jua — SIL OFL: https://github.com/google/fonts/tree/main/ofl/jua (`assets/fonts/Jua-OFL.txt`)
- Lucide — ISC: https://github.com/lucide-icons/lucide (`assets/icons/LICENSE.txt`)
- Heroicons musical-note — MIT: https://github.com/tailwindlabs/heroicons (`assets/icons/HEROICONS-LICENSE.txt`)
- 사진·영상 — 사용자가 지정한 공유 폴더의 원본. 출처는 `assets/sources.json`에 기록했습니다.

이번 배경은 실제 사진을 사용합니다. 생성형 작업실 배경은 제거했습니다.
앱은 사진·음악·메모를 외부 서버로 전송하지 않습니다.

턴테이블 본체·레코드·톤암 벡터는 이 프로젝트에서 직접 작성했습니다 (`assets/ui`).


음악 앱 연결은 Microsoft Windows.Media.Control API와 PyWinRT 3.2.1 바인딩을 사용합니다. PyWinRT 프로젝트: https://github.com/pywinrt/pywinrt (MIT). EXE 빌드에서 관련 배포 패키지의 라이선스 파일을 licenses 폴더로 수집합니다.


- NumPy — BSD-3-Clause, bundled OpenBLAS and runtime licenses: https://numpy.org/
- psutil — BSD-3-Clause: https://github.com/giampaolo/psutil
- PyAudioWPatch / PortAudio — MIT: https://github.com/s0d3s/PyAudioWPatch
- nvidia-ml-py — BSD-3-Clause: https://pypi.org/project/nvidia-ml-py/
- 기본 알람음과 타이머 초기화 아이콘은 이 프로젝트에서 직접 제작했습니다.

비주얼라이저는 기본 출력 장치의 WASAPI 루프백 신호를 메모리에서만 분석합니다. 마이크를 사용하거나 녹음 파일을 저장하지 않습니다. 상용 음원은 포함하지 않습니다.

가구 SVG(책상·의자·책장·스탠드·화분)와 가구 관리 아이콘은 이 프로젝트에서 직접 작성했습니다.

추가 가구·소품 SVG와 부분 움직임 레이어는 tools/expand_furniture.py에서 직접 작성해 생성합니다. 외부 가구 이미지를 포함하지 않습니다.
