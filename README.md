# EV3 Xbox · 교사용 Relay

Xbox 컨트롤러 여러 개를 노트북에 Bluetooth로 연결하고, 각 컨트롤러의 입력을 Wi-Fi/UDP를 통해 **서로 다른 EV3**로 전달하는 교사용 프로그램입니다.

## 설치 및 실행 — 더블클릭으로 자동 준비

Relay를 내려받은 노트북에 **Python 3.9~3.13**만 설치되어 있으면 아래 실행 파일이 자동으로 가상환경과 패키지를 준비합니다. **Python 3.12 권장**입니다.

- **Windows 10/11:** 프로젝트 폴더의 `Start-Relay.cmd`를 더블클릭합니다.
- **macOS:** 프로젝트 폴더의 `Start-Relay.command`를 엽니다. macOS에서 실행 권한이 없다고 나오면 최초 한 번 터미널에서 `chmod +x Start-Relay.command`를 실행하거나 `bash Start-Relay.command`로 시작할 수 있습니다.

처음 실행할 때는 자동으로 `.venv/`를 만들고 `requirements.txt`의 `pygame==2.6.1`을 설치한 다음 Relay GUI를 엽니다. **최초 설치에는 인터넷 연결이 필요**하지만, 설치가 끝난 뒤에는 같은 노트북에서 **인터넷 없이도 Relay를 실행할 수 있습니다.** 두 번째 실행부터는 가상환경과 패키지가 이미 준비된 경우 다운로드 없이 바로 시작합니다.

Python 자체가 없다면 실행 파일이 설치 안내를 표시합니다. [Python 3.12 다운로드](https://www.python.org/downloads/). Windows에서 설치 시 `Add python.exe to PATH` 옵션을 선택하면 편리합니다. 현재 방식은 Python까지 포함한 독립 실행형 .exe 설치 파일이 아니며, 이를 원하면 Windows PyInstaller 빌드를 별도로 제작해야 합니다.

### 어떤 파일이 생성되나요?

```text
relay_ev3xbox/
  Start-Relay.cmd          Windows 더블클릭
  Start-Relay.command      Mac 실행
  requirements.txt         pygame 버전
  tools/start_relay.py     자동 설치 및 실행 담당
  .venv/                   첫 실행 때 생성 (Git 제외)
  desktop/relay_gui.py     기존 Relay GUI
```

게임패드와 EV3의 선수 배정은 Relay 창에서 기존과 동일하게 설정합니다. 프로필은 사용자 설정 폴더에 유지됩니다. 프로그램 실행 중 Wi-Fi와 Xbox 연결이 끊기면 수동으로 중계를 재개해야 합니다. **Windows에서 Xbox 3개 동시 버튼/축 매핑은 아직 실기 검증 전**입니다.

### 오프라인 사전 점검

대회장으로 출발하기 전, **인터넷 연결 상태에서 처음 한 번** 설치를 완료하세요. GUI를 열지 않고 설치만 점검할 수도 있습니다.

```text
Windows: Start-Relay.cmd --setup-only
macOS:   bash ./Start-Relay.command --setup-only
```

`[Relay] SETUP=OK`를 확인한 뒤 인터넷을 끄고 다시 실행하여 GUI가 정상적으로 열리는지 시험하세요. 첫 설치 전에 인터넷을 끄면 pygame 패키지를 다운로드할 수 없습니다.


## EV3 수신 서비스 (교사/관리자)

EV3에는 `ev3/xbox_service.py`를 `ev3/systemd/ev3-xbox-service.service`로 설치합니다. Xbox 입력은 로컬 UDP 5006을 통해 학생의 `ev3xbox.XboxController`에 전달합니다. 제어 패킷이 끊기면 EV3 자체에서 250ms 안전정지 기능이 작동합니다.

예시 설정을 `.vscode/ev3-target.example.json`에서 `.vscode/ev3-target.json`으로 복사하고 해당 EV3의 IP/Robot ID를 지정하세요. 학생이 사용하는 로봇별로 ID는 달라야 합니다. 이 개인 설정 파일은 Git에 올리지 않습니다.

```bash
python tools/ev3_service.py status
python tools/ev3_service.py install
python tools/ev3_service.py set-id EV3-01
```

`tools/ev3_service.py`는 공통 SSH/Robot ID 검색 코드를 `tools/ev3_deploy.py`에서 가져옵니다. 이 지원 모듈은 호환성 유지를 위해 포함했습니다. **학생의 알고리즘 코드는 이 저장소에 포함되지 않습니다.**

## 운영 조건

- 인터넷 없이 로컬 2.4GHz Wi-Fi로 노트북과 EV3 간 통신
- 코치의 배터리 전원 공유기/AP 사용 가능 (동시 연결 대수 및 지연은 실기 검증 필요)
- 출전 EV3 총 18대, 경기 중 EV3 최대 9대 + Relay 노트북 최대 3대 운영 계획
- Xbox 버튼/축 매핑은 macOS에서 검증되었고 Windows에서는 실기 확인 필요

상세 운영: [docs/relay/alliance-relay.md](docs/relay/alliance-relay.md).
학생용 소스: [qmercury/student_ev3xbox](https://github.com/qmercury/student_ev3xbox).
원본 개발 프로젝트: [qmercury/ev3XboxConnect](https://github.com/qmercury/ev3XboxConnect).
