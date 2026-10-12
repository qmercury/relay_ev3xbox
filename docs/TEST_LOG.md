# Test Log

## 2026-10-10 — Xbox → M3 MacBook Air → EV3 relay

### Goal

Verify that an Xbox Wireless Controller Model 1914 can be read on macOS and its control state can be delivered to an EV3 running ev3dev without requiring direct Xbox BLE support on the EV3.

### Host

- M3 MacBook Air
- Python 3.13.3
- pygame 2.6.1
- SDL 2.28.4
- Controller detected by pygame as `Xbox Series X Controller`

### EV3

- ev3dev
- Kernel: `4.14.117-ev3dev-2.3.5-ev3`
- BlueZ: `5.43`
- USB interface: `usb0`

### Confirmed controller mapping

| Input | pygame mapping |
| --- | --- |
| Left stick X | Axis 0 |
| Left stick Y | Axis 1 |
| Right stick X | Axis 2 |
| Right stick Y | Axis 3 |
| LT | Button 9 |
| RT | Button 10 |
| D-pad Up | Button 11 |
| D-pad Down | Button 12 |
| D-pad Left | Button 13 |
| D-pad Right | Button 14 |

The deadzone was raised from `0.08` to `0.12` after the Mac mini test showed left-stick idle/settling values reaching about `-0.099`. This prevents unintended low-speed motor creep.

### USB network

The EV3 USB interface did not receive IPv4 automatically during the test, although SSH over IPv6/mDNS worked.

Temporary IPv4 addresses were assigned:

```text
Mac: 192.168.77.1/24
EV3: 192.168.77.2/24
```

EV3:

```bash
sudo ip addr add 192.168.77.2/24 dev usb0
```

Mac:

```bash
sudo ifconfig en5 inet 192.168.77.1 netmask 255.255.255.0 up
```

The Mac interface name `en5` is specific to the machine used in this test and must not be hard-coded for other Macs.

Measured ping:

```text
4 packets transmitted
4 packets received
0.0% packet loss
round-trip min/avg/max/stddev = 1.409/1.681/2.313/0.367 ms
```

### UDP relay result

`mac/relay_test.py` sent Xbox state to `192.168.77.2:5005` at 30 Hz.

`ev3/xbox_receiver.py` received the packets successfully and printed sequence numbers and stick/trigger values.

Result:

```text
Xbox 1914
   ↓ Bluetooth
M3 MacBook Air
   ↓ pygame
UDP 30 Hz
   ↓ USB network
EV3
   ↓ Python receiver

PASS
```

Motor control was deliberately not tested at this stage. It will be continued on a Mac mini.

---

## Direct CSR8510 BLE experiment — paused

A low-cost CSR8510-compatible USB Bluetooth adapter was tested directly on EV3.

### USB identification

```text
ID 0a12:0001 Cambridge Silicon Radio, Ltd Bluetooth Dongle (HCI mode)
Product: CSR8510A10
bcdDevice: 88.91
```

`hciconfig -a` showed:

```text
hci0: USB, DOWN
hci1: UART, UP RUNNING
```

`hci1` is the EV3 internal Bluetooth adapter. `hci0` is the USB CSR-compatible adapter.

Attempting:

```bash
sudo hciconfig hci0 up
```

returned:

```text
Can't init device hci0: Invalid request code (56)
```

Reloading `btusb` with reset/autosuspend options did not resolve the issue.

Kernel configuration also showed:

```text
CONFIG_BT_HIDP=m
# CONFIG_UHID is not set
```

Because the direct BLE path would require old-kernel driver/kernel work, it has been deferred in favor of the Mac relay architecture.


## 2026-10-11 — Mac mini controller verification

- Python: 3.9.6
- pygame: 2.6.1
- SDL: 2.28.4
- Controller detected: `Xbox Series X Controller`
- Axes: 6
- Buttons: 16
- Hats: 0
- D-pad Up confirmed again as Button 11
- Left stick Axis 1 events confirmed
- Observed small Axis 1 values down to approximately `-0.099`; project deadzone increased to `0.12`

Result: Xbox → Mac mini input stage PASS.


## 2026-10-11 — Mac mini GUI + EV3 USB heartbeat verification

- Xbox controller detected in the pygame GUI
- EV3 connected over USB network at `192.168.77.2`
- GUI heartbeat acknowledgement received from EV3
- Both Xbox and EV3 status indicators turned green
- Relay card state reached `준비됨`
- Observed heartbeat RTT in GUI: approximately `17.3 ms`

Result: Mac mini GUI connection-status path PASS.

Motor movement has not yet been enabled in this test. Next step is to identify the attached EV3 motor ports/types and then add motor control with an EV3-local failsafe.


## 2026-10-11 — Mac mini motor port detection

Detected EV3 drive motors:

- Left/right assignment not yet confirmed
- `outA`: `lego-ev3-l-motor`
- `outD`: `lego-ev3-l-motor`

The next motor-control test will use ports A and D, initially limited to 30% output with the wheels raised. Motor side/direction will be confirmed before floor testing.


## 2026-10-11 — A/D motor direction check

Low-power individual motor test completed with wheels raised.

- `outA`: positive power rotates in robot-forward direction
- `outD`: positive power rotates in robot-forward direction
- No per-motor direction inversion is required for straight driving
- Physical left/right assignment is not yet recorded; initial drive code keeps port assignment configurable at the top of the file


## 2026-10-11 — Relay start-state stability fix verified

The pygame GUI no longer reinitializes the joystick subsystem during periodic controller scans.

Result on Mac mini:
- Xbox connected
- EV3 connected
- Relay state changes from `준비됨` to `중계 중`
- `중계 중` now remains active instead of immediately returning to ready

Result: PASS.


## 2026-10-11 — Initial motor drive verification

With the robot wheels raised and relay active:

- Left stick pushed forward
- Both EV3 large motors on ports A and D rotated in the robot-forward direction
- Initial drive output limit remained at 30%

Result: forward drive command PASS.


## 2026-10-11 — Steering verification

With the robot wheels raised and relay active:

- Left stick forward: both A/D motors drive forward
- Left stick right: robot turns in the correct right-turn direction

Result: basic arcade steering PASS.


## 2026-10-11 — EV3 local failsafe verification

Failsafe test completed with wheels raised:

- Relay GUI was active and motors were running
- Mac relay GUI was closed while motion command was active
- EV3 stopped both motors automatically after control packets stopped
- EV3 printed: `FAILSAFE: control timeout -> motors stopped`
- Failsafe timeout configured at approximately 250 ms

Result: EV3-local control-loss failsafe PASS.


## 2026-10-11 — Pybricks-compatible EV3 Motor test

Physical EV3 motor port mapping test:

- Student API: `Motor(Port.A, Direction.CLOCKWISE)`
- Physical port: EV3 output A
- Command: `dc(30)` for 0.5 s
- Motor stopped with `brake()`
- Reported relative angle after test: 127°

Result: PASS. Physical port A mapping and basic `dc()`, `brake()`, and `angle()` behavior verified.


## 2026-10-11 — EV3 physical port D motor test

The physical EV3 D-port motor test script executed successfully after the A-port compatibility test.

Next step: validate the Pybricks-compatible `DriveBase` using physical ports A and D.


## 2026-10-11 — Pybricks-compatible DriveBase straight test

The EV3 DriveBase compatibility test executed successfully.

- Physical left drive motor: Port.A
- Physical right drive motor: Port.D
- Student API: `DriveBase(left_wheel, right_wheel, 88, 145)`
- Command: `robot.drive(200, 0)`
- Both wheels rotated in the correct forward direction and stopped normally.

Result: PASS.


## 2026-10-11 — Xbox + DriveBase student-style control test

The Pybricks-compatible student API successfully controlled the EV3 through the teacher relay.

Verified:
- `XboxController()` receives relay state
- `Button.UP` is detected through `controller.buttons.pressed()`
- `DriveBase.drive()` runs the physical A/D drive motors
- D-pad UP drives both wheels forward
- Older ev3dev Python compatibility fix for `run_task()` works

Result: PASS.


## 2026-10-11 — Xbox DriveBase steering verification

With D-pad UP held, the right-stick X axis correctly changes left/right wheel speeds through the Pybricks-compatible `DriveBase.drive()` API.

Verified:
- Right stick right -> correct right steering direction
- Right stick left -> correct left steering direction
- Student-facing API remains `controller.joystick_right()[0]` + `robot.drive(...)`

Result: PASS.


## 2026-10-11 — Xbox DriveBase reverse steering verification

With D-pad DOWN held, the right-stick X axis correctly changes left/right wheel speeds while reversing.

Verified:
- D-pad DOWN -> both drive wheels reverse
- Right stick right -> correct reverse right steering direction
- Right stick left -> correct reverse left steering direction

Result: PASS.


## 2026-10-11 — Fixed-rate D-pad turn tuning

The fixed D-pad turn rate was reduced from 300 deg/s to 120 deg/s for the current bench speed of 200 mm/s and axle track of 145 mm.

Verified for D-pad RIGHT:
- Left drive motor rotates forward faster
- Right drive motor rotates forward more slowly
- Inside wheel no longer reverses
- Robot therefore follows a forward right-turning arc

Result: PASS.


## 2026-10-11 — D-pad left turn verification

Fixed-rate D-pad LEFT turn at speed 200 mm/s and turn rate 120 deg/s was verified.

- Right drive motor rotates forward faster
- Left drive motor rotates forward more slowly
- Robot follows the expected forward left-turning arc

Result: PASS.

Next: verify shooter motor direction on physical EV3 ports B and C before adding RB/LB shooter logic.


## 2026-10-11 — Shooter motor B compatibility retest

Physical EV3 port B uses an EV3 Medium Motor.

- Direct ev3dev2 MediumMotor test on Port.B worked.
- Re-running the Pybricks-compatible `05_shooter_b_test.py` also drove the motor successfully.
- Therefore the compatibility-layer `Motor.dc()` path works with the EV3 Medium Motor on Port.B.

The earlier no-motion/angle=0 result was transient and occurred around relay/service recovery; no Motor API change is required from this retest alone.

Result: PASS.


## 2026-10-11 — Shooter motor C next verification step

Port.B Medium Motor compatibility has been verified.

Next step:
- Test the second shooter motor on physical EV3 Port.C
- Use the same Pybricks-compatible `Motor.dc()` path
- Confirm the direction required for a synchronized two-motor shot


## 2026-10-11 — Shooter motor C basic test

Physical EV3 Port.C Medium Motor test completed.

- Student API: `Motor(Port.C, Direction.CLOCKWISE)`
- Command: `dc(30)` for 0.3 s
- Motor stopped normally
- Reported relative angle: 54°

Result: motor operation PASS. Shooter direction (forward/fire vs reverse) still needs visual confirmation.


## 2026-10-11 — Shooter button-control test prepared

Added `ev3/examples/07_shooter_buttons.py` using the same classroom-facing control structure as the previous SPIKE Prime soccer program.

Bench-test behavior:
- Physical Port.B / Port.C shooter motors
- RB: automatic forward-to-angle and return
- LB: manual forward / return on successive presses
- Re-press while moving: emergency stop
- Two-motor angle-difference safety
- Motion timeout safety
- Initial bench power limited to 30%
- Motor direction remains a student/robot assembly setting via `Direction.CLOCKWISE` / `COUNTERCLOCKWISE`


## 2026-10-11 — Native ev3dev2 + Xbox Port A verification

The new student-facing native runtime path was verified over Wi-Fi.

Verified:
- Relay discovered `EV3-01` automatically on the local Wi-Fi network
- `XboxController.connected()` returned `True`
- Left-stick values reached the student Python process through `ev3xbox`
- Native `python-ev3dev2` `LargeMotor(OUTPUT_A)` responded to Xbox left-stick Y input
- Motor A rotated in both directions and stopped at stick center
- Bench output was limited to 30%

Result: PASS.

Next: verify native `python-ev3dev2` two-motor A/D drive control through Xbox input.


## 2026-10-11 — Native ev3dev2 A/D Xbox drive verification

The native student runtime path was verified with both EV3 drive motors.

Verified:
- `MoveTank(OUTPUT_A, OUTPUT_D)` controlled the two physical drive motors
- Xbox left-stick Y controlled forward/reverse
- Xbox right-stick X produced the expected left/right speed difference for steering
- Both directions and steering responded normally
- Bench output remained limited to 30%
- Relay and `ev3xbox` continued to deliver controller state over Wi-Fi

Result: PASS.

Next: verify the actual VSCode student workflow: edit `student/main.py` -> Ctrl+Shift+B -> automatic Robot ID discovery -> SSH upload -> EV3 execution -> log/status check.


## 2026-10-11 — VSCode EV3 status task verification

The student status task was re-tested after stale-PID cleanup handling was fixed.

Verified:
- Robot ID `EV3-01` was discovered automatically as `192.168.200.175`
- SSH connection succeeded without a password prompt
- EV3 Python reported `Python 3.5.3`
- `XBOX_SERVICE=RUNNING`
- Completed student program was reported cleanly as `STUDENT_PROGRAM=NOT_RUNNING`
- No stale `/proc/<pid>/cmdline` warning appeared

Result: PASS.

Next: verify `EV3: 정지` against a deliberately long-running student program and confirm that the Xbox service remains running.


## 2026-10-11 — VSCode student stop task verification

The student stop task was verified while a long-running `student/main.py`
process was active.

Verified:
- Robot ID `EV3-01` was discovered automatically
- `EV3: 정지` stopped only the student program
- The persistent `xbox_service.py` process was intentionally left untouched
- The deploy tool completed without an SSH password prompt

Result: PASS.

A prior status check intermittently missed the UDP Robot ID discovery response
while the configured Wi-Fi host was still reachable. The deploy discovery path
was therefore strengthened to send both broadcast discovery requests and a
direct probe to the previously known host, with a longer retry window.


## 2026-10-11 — Final student environment status verification

Final status check after Robot ID discovery hardening:

- `EV3-01` discovered automatically as `192.168.200.175`
- `SSH=OK`
- `PYTHON=Python 3.5.3`
- `XBOX_SERVICE=RUNNING`
- `STUDENT_PROGRAM=NOT_RUNNING`
- No SSH password prompt
- No stale PID warning
- No Robot ID discovery fallback was needed

Result: PASS.

The basic student VSCode workflow is now verified end to end:
edit -> deploy -> run -> logs -> status -> stop.

## 2026-10-11 — EV3 reboot and Relay restart recovery

User-reported verification after rebooting the physical EV3 and restarting the Mac mini Relay GUI:

- Robot ID `EV3-01` was discovered at `192.168.200.175`.
- Passwordless SSH status: `SSH=OK`.
- EV3 Python: `Python 3.5.3`.
- `XBOX_SERVICE=RUNNING`; systemd showed `enabled` and `active`.
- Student program remained independently stopped: `STUDENT_PROGRAM=NOT_RUNNING`.
- The `ev3_service.py status` command also rediscovered `EV3-01` successfully.
- After closing and reopening `desktop/relay_gui.py`, Xbox and EV3 reconnected and the relay card returned to `준비됨` (ready), **without automatically starting control relay**.

Result: EV3 post-reboot service/discovery recovery PASS; Relay restart-to-ready PASS.

Not tested in this round: manual control resume following restart, changed-DHCP-address discovery, three-EV3 multi-discovery, Windows controller mapping.

## 2026-10-11 — Relay manual start/stop after restart

User-reported bench verification after successfully reopening Relay GUI:

- Initial relay card status was `준비됨` (ready).
- Pressing `중계 시작` changed status to `중계 중` (relaying).
- Pressing `중계 정지` returned status to `준비됨` (ready).
- No motor-motion test was required for this state-transition verification.

Result: Relay manual start/stop state transition after restart PASS.

Next: verify Robot ID discovery when the configured fallback IP is stale (without changing the actual Wi-Fi/DHCP network), then separately test real DHCP address changes.

## 2026-10-11 — Stale configured IP fallback test

User performed a safe stale-host simulation without changing the EV3 DHCP lease.

- Created a temporary config at `/tmp/ev3-target-stale-ip.json`, changing only `host` to `192.0.2.1` while keeping Robot ID `EV3-01`.
- Executed `python3 tools/ev3_deploy.py --config /tmp/ev3-target-stale-ip.json check`.
- Robot ID discovery correctly returned `EV3-01 -> 192.168.200.175`, overriding the stale configured host.
- `SSH=OK`, `PYTHON=Python 3.5.3`, `XBOX_SERVICE=RUNNING`, `STUDENT_PROGRAM=NOT_RUNNING`.

Result: Stale configured host recovery PASS. Actual DHCP lease / IP change is not yet verified.

## 2026-10-11 — ConnMan network inspection (read-only)

Read-only inspection of EV3 Wi-Fi after successful stale-IP discovery testing:

- Interface: `wlx00ada702b7c5`
- Current IPv4: `192.168.200.175/24`
- Default gateway: `192.168.200.254`
- `connman`: `active`; `NetworkManager`: `inactive`
- IPv4 address lifetime was shown as `valid_lft forever`, but that alone does not prove a static assignment.

Next read-only step: `connmanctl services`, followed by reading the active service's `IPv4.Configuration` to establish DHCP versus manual setup. No live DHCP address switch or disruptive network configuration change has been performed.

## 2026-10-11 — ConnMan DHCP mode verified

User-supplied read-only command output from `connmanctl services --properties wifi_00ada702b7c5_742d62726f616441353335_managed_psk`:

- Service name: `t-broadA535` / interface `wlx00ada702b7c5`.
- `State=online`; `AutoConnect=True`; `Favorite=True`.
- `IPv4=[ Method=dhcp, Address=192.168.200.175, Netmask=255.255.255.0, Gateway=192.168.200.254 ]`.
- `IPv4.Configuration=[ Method=dhcp ]`: confirms DHCP rather than static manual addressing.
- `Strength=30` at the time of inspection. This is not a throughput/latency measurement.

Result: DHCP configuration verified PASS. Actual lease change to a *different address* remains UNTESTED. Stale configured IP recovery was previously verified separately. Avoid modifying ConnMan's persistent network settings merely to force an IP change; use controlled DHCP/router test when available.

## 2026-10-11 — Xbox power-cycle recovery without auto-resume

User-reported test with the current Mac mini Relay GUI and EV3-01, performed without motor movement:

- With the Relay active, the Xbox controller was powered off.
- The Relay card changed to `확인 필요` (attention needed); control relay did not remain active.
- After turning the Xbox controller back on, the Relay detected the controller again and reached the **green `준비됨` (ready)** state.
- The Relay did **not** automatically return to `중계 중`; manual re-enablement is required.

Result: Xbox disconnect / reconnect and manual-resume safety behavior PASS (GUI-level). Physical motor-stop timing after controller power loss was not measured in this specific test.

Next: Validate an offline local Wi-Fi network independently of venue Wi-Fi/Internet, then expand to multiple EV3/Xbox units. An offline AP/router is a fallback when a tested host computer cannot provide its own AP.

## 2026-10-11 — Offline Mac mini Internet Sharing AP attempt

Attempted to create a standalone Wi-Fi network using macOS 26.6.2 Internet Sharing on Mac mini without an upstream Ethernet cable or available router.

- Mac mini interfaces: Ethernet `en0` (link inactive), Wi-Fi `en1`.
- GUI configured `Ethernet → Wi-Fi`; network name `EV3-RELAY`; user reported no error when toggling Internet Sharing on.
- Phone did **not** see `EV3-RELAY` in available SSIDs.
- `networksetup -getairportpower en1`: On; `networksetup -getairportnetwork en1`: not associated with an AirPort network.
- `ifconfig en1`: active with previous `192.168.200.132` address; does not establish AP function.
- `ifconfig bridge100`: `interface bridge100 does not exist`.
- `pgrep -fl 'InternetSharing|bootpd'`: no matching output.

Result: Standalone macOS Internet Sharing Wi-Fi AP **NOT FUNCTIONAL in this tested setup**. The missing Ethernet link is a possible cause, not proven. No EV3 network reconfiguration was attempted. Offline multi-EV3 network remains UNTESTED.

Decision: stop repeatedly toggling macOS Internet Sharing in this configuration. Restore the original Wi-Fi network and continue Relay/software testing there. For venue-independent deployment, validate either a proven host AP implementation or a standalone local Wi-Fi AP/router with no Internet uplink; test Wi-Fi regulations before competition.


## 2026-10-12 — 교사용 Relay 원클릭 실행기 추가 및 확인

기능:
- `Start-Relay.cmd`(Windows), `Start-Relay.command`(macOS) 더블클릭 시 Python 3.9–3.13 선택, `.venv` 준비, `pygame==2.6.1` 설치, `desktop/relay_gui.py` 실행
- `.venv`와 pygame이 이미 준비되면 설치를 건너뛰므로 대회장 인터넷이 없어도 재실행 가능. 최초 설치는 Python 및 인터넷이 필요
- 기존 EV3 `xbox_service.py`, 학생 알고리즘, 중계 프로토콜은 변경하지 않음

검증:
- GitHub Actions macOS 및 Windows에서 첫 패키지 설치와 두 번째 `PIP_NO_INDEX=1` 재실행 테스트 PASS
- 사용자의 Mac mini에서 `./Start-Relay.command` 실행 후 Relay GUI 열림 확인 PASS

아직 검증하지 않은 사항:
- 실제 Windows 노트북에서 Relay 창과 Xbox 3개 인식/버튼 매핑, EV3 3대 동시 조종
- 인터넷이 없는 대회용 AP/USB SoftAP 방식에서 EV3 3대 연결 및 안정성
- 공유기 제품은 미결정 (공용 AP와 팀별 AP 모두 후보)

진행 상태: [교사용 운영 계획](relay/alliance-relay.md) 및 [세 저장소 개발 현황](https://github.com/qmercury/ev3XboxConnect/blob/main/docs/NEXT_STEPS.md).
