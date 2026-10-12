# EV3 Xbox · 교사용 Relay

**문서 목록:** [docs/README.md](docs/README.md) · **전체 개발 현황:** [원본 로드맵](https://github.com/qmercury/ev3XboxConnect/blob/main/docs/NEXT_STEPS.md)

Xbox 컨트롤러 여러 개를 노트북에 Bluetooth로 연결하고, 각 컨트롤러의 입력을 Wi-Fi/UDP를 통해 **서로 다른 EV3**로 전달하는 교사용 프로그램입니다.

## 처음 다운로드: 터미널에서 GitHub 저장소 복제하기

`git clone`은 교사용 Relay 프로젝트 파일을 노트북으로 복사하는 명령입니다. **처음 한 번만** 실행합니다. [Git](https://git-scm.com/downloads)과 **Python 3.9~3.13(권장 3.12)**을 미리 설치하고, 첫 설치 시에는 인터넷에 연결하세요. [Python 설치](https://www.python.org/downloads/). `pygame`과 가상환경은 실행기가 자동으로 준비합니다.

### Windows PowerShell — 아래 블록 전체 복사·붙여넣기

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\Documents\EV3_Projects" | Out-Null
Set-Location "$HOME\Documents\EV3_Projects"
git clone https://github.com/qmercury/relay_ev3xbox.git
Set-Location .\relay_ev3xbox
.\Start-Relay.cmd
```

- `New-Item`: 문서 폴더에 프로젝트 저장 장소를 만듭니다.
- `Set-Location`: 작업할 폴더로 이동합니다.
- `git clone`: Relay 저장소를 다운로드합니다.
- `.\Start-Relay.cmd`: 가상환경과 pygame을 자동 설치(첫 실행)하고 Relay 창을 엽니다.

### Mac 터미널(zsh) — 아래 블록 전체 복사·붙여넣기

```bash
mkdir -p ~/Documents/EV3_Projects
cd ~/Documents/EV3_Projects
git clone https://github.com/qmercury/relay_ev3xbox.git
cd relay_ev3xbox
./Start-Relay.command
```

- `mkdir -p`: 문서 폴더 안에 프로젝트 저장 장소를 만듭니다.
- `cd`: 작업할 폴더로 이동합니다.
- `git clone`: Relay 저장소를 다운로드합니다.
- `./Start-Relay.command`: 가상환경·pygame 자동 설치 후 Relay 창을 엽니다.

Mac에서 실행 권한 오류가 나는 환경이라면 `bash ./Start-Relay.command`로 실행할 수 있습니다. 현재 저장소의 파일은 실행 가능 권한으로 관리합니다.

### 이미 복제했다면: 최신 코드 업데이트

기존 `relay_ev3xbox` 폴더에서 아래 명령을 사용하세요. **`git clone`을 다시 실행하지 않습니다.** 실행 중인 Relay 창을 먼저 닫고 업데이트하는 것이 안전합니다.

```bash
git pull --ff-only
```

업데이트 후 Windows는 `.\Start-Relay.cmd`, Mac은 `./Start-Relay.command`를 실행합니다. **첫 설치 이후** pygame 설치가 준비되어 있으면 인터넷 없이도 Relay를 시작할 수 있습니다.

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

## 문서와 대회 준비 상태 (2026-10-12)

- **[얼라이언스 Relay 운영](docs/relay/alliance-relay.md):** 팀 3대 중계, 인터넷 없는 Wi-Fi, 공용 AP vs 팀별 AP 비교, 남은 검증 항목
- **[테스트 기록](docs/TEST_LOG.md):** macOS/EV3 실기 시험 내역. 기존 시험 결과는 역사적 기록으로 보존
- **[전체 프로젝트 진행 상황](https://github.com/qmercury/ev3XboxConnect/blob/main/docs/NEXT_STEPS.md):** 원본 실험 저장소와 학생·교사 운영 저장소의 역할 및 다음 테스트

**현재 공유기 모델은 확정되지 않았습니다.** ipTIME A3000UA USB 무선랜 카드의 SoftAP, 별도 휴대용 AP, 공용 공유기 등을 검토 중입니다. GitHub Actions에서 Windows·Mac 설치 자동화가 성공했더라도, **Windows 실물 노트북에서 Xbox 3개·EV3 3대 중계**가 검증됐다는 의미는 아닙니다.

## 운영 조건

- 인터넷 없이 로컬 2.4GHz Wi-Fi로 노트북과 EV3 간 통신
- 코치의 배터리 전원 공유기/AP 사용 가능 (동시 연결 대수 및 지연은 실기 검증 필요)
- 출전 EV3 총 18대, 경기 중 EV3 최대 9대 + Relay 노트북 최대 3대 운영 계획
- Xbox 버튼/축 매핑은 macOS에서 검증되었고 Windows에서는 실기 확인 필요

상세 운영: [docs/relay/alliance-relay.md](docs/relay/alliance-relay.md).
학생용 소스: [qmercury/student_ev3xbox](https://github.com/qmercury/student_ev3xbox).
원본 개발 프로젝트: [qmercury/ev3XboxConnect](https://github.com/qmercury/ev3XboxConnect).
