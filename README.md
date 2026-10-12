# EV3 Xbox · 교사용 Relay

Xbox 컨트롤러 여러 개를 노트북에 Bluetooth로 연결하고, 각 컨트롤러의 입력을 Wi-Fi/UDP를 통해 **서로 다른 EV3**로 전달하는 교사용 프로그램입니다.

## 실행

- 노트북에 Python 3과 `pygame==2.6.1`을 설치합니다.
- `python -m pip install -r requirements.txt`
- `python desktop/relay_gui.py`

화면의 중계 카드를 통해 선수 이름, EV3 Robot ID, Xbox를 배정한 뒤 중계를 시작합니다. EV3 IP는 저장하지 않으며 Robot ID로 자동 검색합니다. 연결이 끊기면 해당 로봇 중계만 정지하고 복구 후 **수동으로 중계를 시작**해야 합니다.

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
