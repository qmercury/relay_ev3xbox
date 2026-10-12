import json
import socket
import time

import pygame

EV3_IP = "192.168.77.2"
EV3_PORT = 5005
SEND_HZ = 30
SEND_INTERVAL = 1.0 / SEND_HZ
DEADZONE = 0.12


def deadzone(value):
    if abs(value) < DEADZONE:
        return 0.0
    return value


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Xbox 컨트롤러를 찾지 못했습니다.")
    raise SystemExit

pad = pygame.joystick.Joystick(0)
pad.init()

print("Controller:", pad.get_name())
print("EV3:", EV3_IP)
print("Send rate:", SEND_HZ, "Hz")
print("Ctrl+C to stop")
print()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
seq = 0

try:
    while True:
        pygame.event.pump()

        lx = deadzone(pad.get_axis(0))
        ly = deadzone(pad.get_axis(1))
        rx = deadzone(pad.get_axis(2))
        ry = deadzone(pad.get_axis(3))

        # Confirmed on Xbox Series X Controller / macOS SDL mapping.
        lt = pad.get_button(9)
        rt = pad.get_button(10)
        dpad_up = pad.get_button(11)
        dpad_down = pad.get_button(12)
        dpad_left = pad.get_button(13)
        dpad_right = pad.get_button(14)

        seq += 1
        packet = {
            "seq": seq,
            "lx": round(lx, 3),
            "ly": round(ly, 3),
            "rx": round(rx, 3),
            "ry": round(ry, 3),
            "lt": lt,
            "rt": rt,
            "du": dpad_up,
            "dd": dpad_down,
            "dl": dpad_left,
            "dr": dpad_right,
        }

        data = json.dumps(packet).encode("utf-8")
        sock.sendto(data, (EV3_IP, EV3_PORT))

        print(
            "\r"
            f"LX {lx:+.2f}  "
            f"LY {ly:+.2f}  "
            f"RX {rx:+.2f}  "
            f"RY {ry:+.2f}",
            end="",
            flush=True,
        )

        time.sleep(SEND_INTERVAL)
except KeyboardInterrupt:
    print("\nRelay stopped.")
finally:
    sock.close()
    pygame.quit()
