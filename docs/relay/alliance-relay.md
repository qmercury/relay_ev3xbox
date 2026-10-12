# 얼라이언스 Relay 운영

EV3 Xbox Relay는 학생 코드와 별개의 프로그램입니다.

한 노트북에서 Xbox 여러 개를 각각 다른 EV3에 1:1로 연결할 수 있습니다.

```text
Xbox 1 ─┐
Xbox 2 ─┼─ Bluetooth → Relay 노트북
Xbox 3 ─┘                    │
                              │ 로컬 Wi-Fi
                   ┌──────────┼──────────┐
                   ↓          ↓          ↓
                 EV3 1      EV3 2      EV3 3
```

## 대회장 인터넷 없는 Wi-Fi 구성 — 선택 및 실기 검증 전 (2026-10-12)

인터넷 없이 **노트북(교사용 Relay)과 EV3가 같은 로컬 Wi-Fi 네트워크**에서 UDP를 주고받는 구조입니다. **공유기 구매 및 네트워크 방식은 아직 확정하지 않았습니다.** 경기 중 최대 EV3 9대와 Relay 노트북 3대를 운용하는 계획이며, 팀 1개당 Xbox 3개 + EV3 3대를 한 노트북에서 중계합니다. 총 출전 EV3는 약 18대이며, 경기하지 않는 로봇의 Wi-Fi 연결 여부에 따라 실제 접속 수는 달라집니다.

### 운영안 A — 공용 공유기/AP 1대

```text
보조배터리 → 공용 AP (인터넷 없음)
                   │
           ┌───────┼───────┐
           ↓       ↓       ↓
       Relay 1  Relay 2  Relay 3
           │       │       │
      EV3 × 3  EV3 × 3  EV3 × 3
```

- 경기 중 **EV3 9대 + 노트북 3대 = 동시 Wi-Fi 클라이언트 12대** 기준으로 검증합니다.
- 경기에 참가하지 않는 EV3도 켜서 Wi-Fi에 접속해 있다면 12대를 초과하므로 공유기의 DHCP 주소와 접속 한도를 여유 있게 설계해야 합니다.
- 장비가 간단한 대신 공용 AP 장애 시 모든 팀에 영향이 있습니다.

### 운영안 B — 팀별 독립 Wi-Fi / AP

```text
팀 A: Relay 노트북 1대 + 팀 A AP + EV3 3대
팀 B: Relay 노트북 1대 + 팀 B AP + EV3 3대
팀 C: Relay 노트북 1대 + 팀 C AP + EV3 3대
```

- 팀별 네트워크가 분리되어 한 AP의 문제가 다른 팀으로 번질 가능성을 낮춥니다.
- 팀마다 휴대용 공유기를 사용하거나, Windows 노트북의 **ipTIME A3000UA USB 무선랜 어댑터**를 SoftAP 모드로 운영하는 후보를 검토 중입니다.
- **A3000UA를 인터넷 없는 Windows 실기 환경에서 AP로 사용하는 기능, DHCP 및 EV3 3대 동시 접속은 아직 검증되지 않았습니다.** USB 무선랜 카드가 단순히 설치되어 있다는 것만으로 AP가 생기지는 않습니다.
- AP가 여러 대라면 채널 간섭(특히 2.4GHz)과 대회 규정상 개인 무선 AP 허용 여부를 반드시 확인해야 합니다.

### Wi-Fi 장비 선택 기준

- EV3 USB Wi-Fi 동글이 사용할 수 있는 2.4GHz 대역과 WPA2-PSK
- 인터넷 연결이 없어도 로컬 Wi-Fi SSID와 DHCP 서버 유지
- UDP 5005의 검색 브로드캐스트 및 유니캐스트 조종·응답 허용, 클라이언트 격리(AP isolation) 꺼짐
- 동시 클라이언트 수와 RTT 안정성, 실제 조종 중 제어 데이터 누락 시 약 250ms EV3 자체 안전정지 확인
- 보조배터리나 노트북 USB 전원 등 대회장에서 사용할 전원 공급 방법
- 동일 Robot ID를 다른 팀에서 중복 사용하지 않도록 팀·로봇 관리

**구매를 확정하기 전에** 인터넷을 끊은 상태에서 EV3 1대 → 3대 → 경기 규모(최대 9대)를 차례대로 시험합니다. 공용 AP 1개와 팀별 AP는 비교 대상이며, 특정 모델을 최종 추천·보장하지 않습니다.

### 다중 Relay 안전 설계 — 추가 검증 필요

- 각 EV3에 고유 `robot_id` 부여. Robot ID 중복 및 다른 팀의 Robot ID 오지정 시 검색/제어 충돌 검증
- EV3 수신 서비스는 여러 Relay 간 **제어 소유권 인증·잠금이 아직 구현되지 않음**. 공용 네트워크에서는 타 Relay의 제어 신호가 충돌할 수 있으므로 추가 설계 필요
- EV3 하나가 끊겨도 다른 EV3 제어가 유지되는지 Xbox 3개/로봇 3대 동시 시험
- Windows 노트북 실제 Xbox 3개 버튼·축 매핑, DHCP 갱신, 무선 간섭, 안전정지 검증

### 기존 AP 실험 기록

Mac mini의 macOS 인터넷 공유 기능으로 별도 SSID를 생성하려고 시도했지만 해당 테스트에서는 SSID가 나타나지 않았습니다. 이것만으로 Windows SoftAP나 휴대용 공유기의 성공·실패를 추정하지 않습니다.

## EV3는 IP가 아니라 Robot ID로 찾습니다

EV3의 Wi-Fi IP는 DHCP로 자동 배정되어 바뀔 수 있습니다.

따라서 Relay 프로필에는 EV3 IP를 저장하지 않습니다. 각 EV3에 한 번만 고유한 Robot ID를 지정하고, Relay가 현재 IP를 자동으로 찾습니다.

예:

```text
최서안
Robot ID: EV3-01
Xbox 이름: 최서안 Xbox
```

Relay 내부에서는 실행할 때마다 다음처럼 현재 주소를 자동으로 연결합니다.

```text
EV3-01 → 192.168.137.23
EV3-02 → 192.168.137.31
EV3-03 → 192.168.137.18
```

다음 연결에서 DHCP 주소가 바뀌어도 Robot ID가 같으면 다시 찾아냅니다.

## Robot ID 설정

각 EV3에는 처음 한 번만 고유 ID를 저장합니다.

권장 형식:

```text
EV3-01
EV3-02
EV3-03
```

영문, 숫자, 마침표, 밑줄, 하이픈을 사용할 수 있고 최대 32자입니다.

`.vscode/ev3-target.json`에 다음처럼 넣으면 Xbox 서비스를 설치할 때 함께 저장됩니다.

```json
{
  "host": "192.168.77.2",
  "user": "robot",
  "robot_id": "EV3-01"
}
```

이미 서비스가 설치된 EV3는 다음 명령으로 ID만 변경할 수 있습니다.

```bash
python3 tools/ev3_service.py set-id EV3-01
```

Windows에서는 Python 명령이 `python`인 환경도 있습니다.

```bash
python tools/ev3_service.py set-id EV3-01
```

설정 후 Xbox 서비스가 재시작되고 새 Robot ID로 검색됩니다.

## 자동 검색 방식

Relay 프로그램은 로컬 네트워크에 EV3 검색 요청을 주기적으로 보냅니다.

```text
Relay 노트북
   │
   ├─ "사용 가능한 EV3 있나요?"
   │
   ├──→ EV3 EV3-01
   ├──→ EV3 EV3-02
   └──→ EV3 EV3-03
```

각 EV3의 `xbox_service.py`가 자신의 Robot ID와 함께 응답합니다.

```text
EV3-01 → 현재 IP 192.168.137.23
EV3-02 → 현재 IP 192.168.137.31
EV3-03 → 현재 IP 192.168.137.18
```

사용자는 IP를 직접 입력하지 않습니다.

같은 Robot ID를 가진 EV3가 두 대 이상 발견되면 안전을 위해 그 Robot ID의 중계를 시작하지 않습니다. 먼저 EV3 ID를 서로 다르게 수정해야 합니다.

## 선수 / EV3 / Xbox 이름

각 Relay 카드에서 사용자가 관리하는 값은 세 가지입니다.

```text
선수 이름
EV3 ID
Xbox 이름
```

예:

```text
최서안 / EV3-01
Xbox: 최서안 Xbox
EV3: EV3-01 · 192.168.137.23
```

IP는 상태 확인을 위해 화면에 표시될 수 있지만 직접 입력하거나 저장하는 값은 아닙니다.

프로필은 Git 저장소에 저장하지 않고 Relay 컴퓨터의 사용자 설정 폴더에 저장합니다.

- Windows: `%APPDATA%/EV3XboxRelay/profile.json`
- macOS: `~/Library/Application Support/EV3XboxRelay/profile.json`
- Linux: `~/.config/EV3XboxRelay/profile.json`

## 대회 중 상태 확인

화면 상단에는 전체 상태가 표시됩니다.

```text
준비 3/3 · 중계 3/3
```

각 카드에는 Xbox와 EV3 상태가 따로 표시됩니다.

```text
최서안 / EV3-01                    중계 중

● Xbox: 최서안 Xbox
● EV3: EV3-01 · 192.168.137.23

EV3-01 중계 중입니다.
```

Xbox 또는 EV3가 끊기면 해당 카드만 중지되고 다른 두 로봇의 중계는 계속됩니다.

연결이 복구되어도 중계가 자동으로 다시 시작되지는 않습니다. 카드가 다시 준비 상태가 된 뒤 `중계 시작`을 눌러 재개합니다. 스틱이 기울어진 상태에서 갑자기 로봇이 움직이는 것을 막기 위한 안전 동작입니다.

## 전체 중계 시작 / 긴급 정지

`전체 중계 시작`은 Xbox와 EV3가 모두 준비된 카드만 시작합니다.

`전체 긴급 정지`는 모든 활성 중계를 동시에 정지합니다.

개별 장비 고장이나 연결 끊김은 다른 로봇의 중계를 정지시키지 않습니다.

## 사용 규모

같은 Relay 프로그램을 다음처럼 사용할 수 있습니다.

```text
중계 1개       개인 수업
중계 3개       대회 얼라이언스
중계 여러 개   교사 관리
```

카드가 화면보다 많아지면 마우스 휠로 카드 영역을 스크롤합니다.

## 현재 검증 상태 (2026-10-12)

**EV3 실기에서 검증된 사항**

- macOS Relay와 EV3 1대의 Wi-Fi UDP 중계, Xbox 제어·A/D 모터 구동, 약 250ms 로컬 failsafe
- EV3 1대의 Robot ID 자동 검색, EV3 상주 서비스 복구, Relay 재실행 후 수동으로 중계 시작하는 안전 동작
- 학생 VSCode 프로그램 업로드·정지와 EV3 LCD 상태 표시

**구현 및 자동화 검증 완료, 대회 실기 검증 전**

- 교사용 Windows `Start-Relay.cmd` / Mac `Start-Relay.command`: Python 가상환경·pygame 자동 설치 및 GUI 실행
- GitHub Actions에서 Windows/macOS 설치·재실행 성공, 사용자의 Mac mini에서 실제 Mac 자동 실행 성공
- 실제 **Windows Xbox 3개 동시 연결/조종**, EV3 3대 동시 Relay, 인터넷 없는 AP 1대/팀별 AP 구성은 미검증
- **USB 무선랜 A3000UA SoftAP 모드**와 휴대용 공유기 제품은 확정/구매 전
- 중복 Robot ID·여러 Relay 소유권 충돌·전파 간섭·실제 DHCP IP 변경·경기 중 안전정지 검증 필요

세 저장소를 안내하는 [원본 프로젝트 최신 현황 및 다음 테스트](https://github.com/qmercury/ev3XboxConnect/blob/main/docs/NEXT_STEPS.md)도 참고하세요.
