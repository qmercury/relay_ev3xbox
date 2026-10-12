# Xbox Service 자동 시작

학생 프로그램과 Xbox 입력 서비스를 분리하기 위해 EV3에서는
`xbox_service.py`가 학생 `main.py`와 별개의 systemd 서비스로 실행됩니다.

## 목적

```text
EV3 부팅
   ↓
ev3-xbox-service.service 자동 시작
   ↓
UDP 5005에서 Relay 대기
   ↓
Robot ID 자동 검색 응답
   ↓
127.0.0.1:5006으로 학생 XboxController 상태 전달
```

따라서 SSH 터미널을 닫아도 Xbox 서비스가 종료되지 않습니다.

## Robot ID

각 EV3에는 한 번만 고유한 Robot ID를 지정합니다.

권장 예:

```text
EV3-01
EV3-02
EV3-03
```

Robot ID는 DHCP로 바뀔 수 있는 IP 주소 대신 EV3를 식별하는 값입니다.

Relay 프로그램은 로컬 네트워크에 검색 요청을 보내고 각 EV3의 `xbox_service.py`가 자신의 Robot ID와 현재 IP로 응답합니다.

같은 Robot ID를 두 EV3에 사용하면 안 됩니다.

## 설치/업데이트

먼저 해당 EV3에 대한 `.vscode/ev3-target.json`과 SSH 연결을 설정합니다.

예:

```json
{
  "host": "192.168.77.2",
  "user": "robot",
  "port": 22,
  "robot_id": "EV3-01"
}
```

그다음 PC에서:

```bash
python3 tools/ev3_service.py install
```

Windows에서는:

```powershell
python tools/ev3_service.py install
```

설치 과정에서 systemd 등록을 위해 EV3의 sudo 암호를 물어볼 수 있습니다.

`robot_id`가 설정되어 있으면 설치 과정에서 다음 파일에도 저장합니다.

```text
/home/robot/ev3-xbox/robot_id
```

서비스 파일은:

```text
ev3/xbox_service.py
       ↓
/home/robot/ev3-xbox/xbox_service.py

ev3/systemd/ev3-xbox-service.service
       ↓
/etc/systemd/system/ev3-xbox-service.service
```

로 설치됩니다.

그리고:

```text
systemctl daemon-reload
systemctl enable
systemctl restart
```

를 수행합니다.

## Robot ID만 변경

서비스가 이미 설치되어 있으면 전체 재설치 없이 ID만 변경할 수 있습니다.

macOS / Linux:

```bash
python3 tools/ev3_service.py set-id EV3-01
```

Windows:

```powershell
python tools/ev3_service.py set-id EV3-01
```

명령이 끝나면 Xbox 서비스가 재시작되고 새 Robot ID로 검색됩니다.

## 상태 확인

```bash
python3 tools/ev3_service.py status
```

정상이면 Robot ID와 systemd 상태가 함께 표시됩니다.

```text
=== robot id ===
EV3-01

=== systemd ===
enabled
active
```

## 학생 코드와 분리

학생이 VSCode에서 **EV3: 업로드 및 실행** 또는 **EV3: 정지**를 사용해도
이 systemd 서비스는 종료하지 않습니다.

```text
ev3-xbox-service.service  ← 항상 유지
student/main.py           ← 학생이 자유롭게 재실행
```

학생 프로그램이 오류로 종료되어도 Xbox 서비스는 계속 살아 있습니다.

## 자동 IP 검색

서비스가 실행 중이면 Relay와 배포 도구가 UDP 5005로 로컬 검색 요청을 보낼 수 있습니다.

EV3는 다음 정보를 응답합니다.

```text
Robot ID
현재 EV3 IP
서비스 포트
```

따라서 Relay에서는 EV3 IP를 저장하거나 직접 입력할 필요가 없습니다.

VSCode 배포 도구도 `robot_id`가 설정되어 있으면 먼저 Robot ID로 현재 IP를 찾습니다. 검색에 실패한 경우에만 `ev3-target.json`의 `host`를 예비 주소로 사용합니다.

## 안전정지

Relay에서 제어 패킷이 약 250 ms 이상 끊기면 `xbox_service.py`가
EV3의 모든 tacho motor에 best-effort brake/stop을 보냅니다.

systemd가 서비스를 종료할 때는 `SIGINT`를 사용하도록 설정하여
`xbox_service.py`의 종료 정리 코드도 실행되도록 했습니다.
