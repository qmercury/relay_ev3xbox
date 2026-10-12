import json
import os
from pathlib import Path
import platform
import re
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

# Keep Xbox events available while this window is focused/backgrounded.
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

import pygame


DEFAULT_EV3_PORT = 5005
DISCOVERY_QUERY_INTERVAL = 1.0
DISCOVERY_ACTIVE_SECONDS = 3.0

CONTROL_HZ = 30
HEARTBEAT_INTERVAL = 0.5
EV3_TIMEOUT = 1.5
DEADZONE = 0.12

ROBOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,32}$")

# Xbox Series controller mapping verified on macOS.
# Windows mapping must be verified on the actual competition laptops.
XBOX_BUTTONS = {
    "a": 0,
    "b": 1,
    "x": 2,
    "y": 3,
    "lb": 9,
    "rb": 10,
    "dpad_up": 11,
    "dpad_down": 12,
    "dpad_left": 13,
    "dpad_right": 14,
}
LT_AXIS = 4
RT_AXIS = 5

WINDOW_W = 900
WINDOW_H = 720
HEADER_H = 108
FOOTER_H = 62
CARD_H = 166
CARD_GAP = 10

BG = (245, 247, 250)
CARD = (255, 255, 255)
BORDER = (214, 219, 226)
TEXT = (30, 35, 45)
MUTED = (105, 115, 130)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
AMBER = (217, 119, 6)
BUTTON = (235, 238, 243)
BUTTON_HOVER = (222, 226, 233)
DANGER = (254, 226, 226)
OVERLAY = (15, 23, 42, 165)


def apply_deadzone(value):
    if abs(value) < DEADZONE:
        return 0.0
    return float(value)


def trigger_value(raw_value):
    value = (float(raw_value) + 1.0) / 2.0
    if value < 0.02:
        return 0.0
    if value > 0.98:
        return 1.0
    return max(0.0, min(1.0, value))


def button_down(joystick, button_index):
    try:
        return bool(joystick.get_button(button_index))
    except (pygame.error, IndexError):
        return False


def profile_file_path():
    system = platform.system()

    if system == "Windows":
        root = os.environ.get("APPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Roaming"
        base = base / "EV3XboxRelay"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "EV3XboxRelay"
    else:
        root = os.environ.get("XDG_CONFIG_HOME")
        base = Path(root) if root else Path.home() / ".config"
        base = base / "EV3XboxRelay"

    base.mkdir(parents=True, exist_ok=True)
    return base / "profile.json"


def load_font(size, bold=False):
    system = platform.system()

    if system == "Darwin":
        names = ["Apple SD Gothic Neo", "AppleGothic", "Arial Unicode MS"]
    elif system == "Windows":
        names = ["Malgun Gothic", "맑은 고딕", "Arial"]
    else:
        names = ["Noto Sans CJK KR", "NanumGothic", "DejaVu Sans"]

    for name in names:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)

    return pygame.font.Font(None, size)


@dataclass
class RelayState:
    relay_id: str
    slot_number: int
    player_name: str
    robot_id: str
    controller_label: str
    ev3_ip: Optional[str] = None
    controller_instance_id: Optional[int] = None
    controller_name: str = ""
    relay_enabled: bool = False
    seq: int = 0
    ping_id: int = 0
    pending_pings: Dict[int, float] = field(default_factory=dict)
    last_ev3_seen: float = 0.0
    last_rtt_ms: Optional[float] = None
    message: str = "EV3를 자동으로 찾는 중입니다."


class RelayApp:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()

        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("EV3 Xbox Relay")

        self.font_title = load_font(28, bold=True)
        self.font_header = load_font(19, bold=True)
        self.font_normal = load_font(16)
        self.font_small = load_font(13)
        self.font_button = load_font(14, bold=True)

        self.clock = pygame.time.Clock()
        self.running = True
        self.session_id = uuid.uuid4().hex

        # Control/heartbeat socket. This uses an ephemeral local port.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("0.0.0.0", 0))
        self.sock.setblocking(False)

        self.controllers = {}
        self.relays = []
        self.next_slot_number = 1

        # robot_id -> {ip_address: last_announce_monotonic}
        self.discovery_by_id = {}

        self.last_controller_scan = 0.0
        self.last_discovery_query = 0.0
        self.last_heartbeat = 0.0
        self.last_control = 0.0

        self.button_rects = {}
        self.scroll_offset = 0

        self.edit_relay_id = None
        self.edit_field_index = 0
        self.edit_values = {}
        self.edit_error = ""
        self.edit_field_rects = {}
        self.edit_save_rect = None
        self.edit_cancel_rect = None

        self.load_profile()
        self.scan_controllers(force=True)

    # ------------------------------------------------------------------
    # Profile / identities
    # ------------------------------------------------------------------

    def load_profile(self):
        path = profile_file_path()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}

        items = data.get("relays")

        if not isinstance(items, list) or not items:
            self.add_relay(persist=False)
            return

        max_slot = 0

        for raw in items:
            if not isinstance(raw, dict):
                continue

            try:
                slot = int(raw.get("slot_number", max_slot + 1))
            except (TypeError, ValueError):
                slot = max_slot + 1

            slot = max(1, slot)
            max_slot = max(max_slot, slot)

            # v1 profiles used robot_name + manually stored ev3_ip.
            # Migrate robot_name into robot_id, but intentionally do not keep
            # the old IP. The current address must be discovered each run.
            robot_id = str(
                raw.get("robot_id")
                or raw.get("robot_name")
                or "EV3-{}".format(slot)
            ).strip()

            relay = RelayState(
                relay_id="relay-{}".format(slot),
                slot_number=slot,
                player_name=str(
                    raw.get("player_name") or "선수 {}".format(slot)
                ),
                robot_id=robot_id,
                controller_label=str(
                    raw.get("controller_label") or "Xbox {}".format(slot)
                ),
            )
            self.relays.append(relay)

        if not self.relays:
            self.add_relay(persist=False)
            return

        self.next_slot_number = max_slot + 1

    def save_profile(self):
        data = {
            "version": 2,
            "relays": [
                {
                    "slot_number": relay.slot_number,
                    "player_name": relay.player_name,
                    "robot_id": relay.robot_id,
                    "controller_label": relay.controller_label,
                }
                for relay in self.relays
            ],
        }

        path = profile_file_path()
        temporary = path.with_suffix(".tmp")

        try:
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError:
            pass

    def add_relay(self, persist=True):
        slot = self.next_slot_number
        self.next_slot_number += 1

        relay = RelayState(
            relay_id="relay-{}".format(slot),
            slot_number=slot,
            player_name="선수 {}".format(slot),
            robot_id="EV3-{}".format(slot),
            controller_label="Xbox {}".format(slot),
        )

        self.relays.append(relay)
        self.auto_assign_controllers()

        if persist:
            self.save_profile()

    def remove_relay(self, relay):
        if len(self.relays) <= 1:
            return

        relay.relay_enabled = False
        self.relays.remove(relay)
        self.auto_assign_controllers()
        self.save_profile()
        self.clamp_scroll()

    def reset_ev3_binding(self, relay, message=None):
        relay.relay_enabled = False
        relay.ev3_ip = None
        relay.last_ev3_seen = 0.0
        relay.last_rtt_ms = None
        relay.pending_pings = {}

        if message:
            relay.message = message

    def open_edit(self, relay):
        self.edit_relay_id = relay.relay_id
        self.edit_field_index = 0
        self.edit_values = {
            "player_name": relay.player_name,
            "robot_id": relay.robot_id,
            "controller_label": relay.controller_label,
        }
        self.edit_error = ""
        pygame.key.start_text_input()

    def close_edit(self):
        self.edit_relay_id = None
        self.edit_values = {}
        self.edit_error = ""
        pygame.key.stop_text_input()

    def save_edit(self):
        relay = self.relay_by_id(self.edit_relay_id)

        if relay is None:
            self.close_edit()
            return

        player_name = self.edit_values.get("player_name", "").strip()
        robot_id = self.edit_values.get("robot_id", "").strip()
        controller_label = self.edit_values.get("controller_label", "").strip()

        if not player_name:
            self.edit_error = "선수 이름을 입력하세요."
            return

        if not ROBOT_ID_PATTERN.fullmatch(robot_id):
            self.edit_error = (
                "EV3 ID는 영문/숫자/.-_ 조합 1~32자로 입력하세요."
            )
            return

        if not controller_label:
            self.edit_error = "Xbox 이름을 입력하세요."
            return

        for other in self.relays:
            if other is not relay and other.robot_id == robot_id:
                self.edit_error = "같은 EV3 ID를 두 중계에 사용할 수 없습니다."
                return

        robot_changed = relay.robot_id != robot_id

        relay.player_name = player_name
        relay.robot_id = robot_id
        relay.controller_label = controller_label

        if robot_changed:
            self.reset_ev3_binding(
                relay,
                "{} EV3를 자동으로 찾는 중입니다.".format(robot_id),
            )
            self.apply_discovery(robot_id)

        self.save_profile()
        self.close_edit()

    # ------------------------------------------------------------------
    # EV3 automatic discovery
    # ------------------------------------------------------------------

    def record_discovery(self, robot_id, ip_address):
        by_ip = self.discovery_by_id.setdefault(robot_id, {})
        by_ip[ip_address] = time.monotonic()
        self.apply_discovery(robot_id)

    def receive_discovery(self):
        changed_ids = self.prune_discovery()

        for robot_id in changed_ids:
            self.apply_discovery(robot_id)

    def prune_discovery(self):
        cutoff = time.monotonic() - DISCOVERY_ACTIVE_SECONDS
        changed_ids = set()

        for robot_id in list(self.discovery_by_id.keys()):
            by_ip = self.discovery_by_id[robot_id]
            before = set(by_ip.keys())

            by_ip = {
                ip_address: seen_at
                for ip_address, seen_at in by_ip.items()
                if seen_at >= cutoff
            }

            after = set(by_ip.keys())

            if before != after:
                changed_ids.add(robot_id)

            if by_ip:
                self.discovery_by_id[robot_id] = by_ip
            else:
                del self.discovery_by_id[robot_id]

        return changed_ids

    def apply_discovery(self, robot_id):
        matches = [
            relay for relay in self.relays
            if relay.robot_id == robot_id
        ]

        if not matches:
            return

        if len(matches) > 1:
            for relay in matches:
                self.reset_ev3_binding(
                    relay,
                    "Relay 설정에 같은 EV3 ID {}가 중복되어 있습니다.".format(
                        robot_id
                    ),
                )
            return

        active_ips = list(
            self.discovery_by_id.get(robot_id, {}).keys()
        )

        if len(active_ips) > 1:
            for relay in matches:
                self.reset_ev3_binding(
                    relay,
                    "EV3 ID {}가 여러 대에서 발견되었습니다.".format(
                        robot_id
                    ),
                )
            return

        if len(active_ips) != 1:
            return

        ip_address = active_ips[0]

        for relay in matches:
            if relay.ev3_ip == ip_address:
                continue

            was_running = relay.relay_enabled

            relay.relay_enabled = False
            relay.ev3_ip = ip_address
            relay.last_ev3_seen = 0.0
            relay.last_rtt_ms = None
            relay.pending_pings = {}

            if was_running:
                relay.message = (
                    "{}의 IP가 변경되었습니다. 확인 후 중계를 다시 시작하세요."
                    .format(robot_id)
                )
            else:
                relay.message = "{} 발견 · 연결 확인 중".format(robot_id)

            self.send_heartbeat(relay)

    # ------------------------------------------------------------------
    # Xbox controller discovery
    # ------------------------------------------------------------------

    def scan_controllers(self, force=False):
        now = time.monotonic()

        if not force and now - self.last_controller_scan < 1.0:
            return

        self.last_controller_scan = now

        current = {}

        try:
            count = pygame.joystick.get_count()
        except pygame.error:
            count = 0

        for index in range(count):
            try:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
                current[joystick.get_instance_id()] = joystick
            except pygame.error:
                continue

        previous_ids = set(self.controllers.keys())
        current_ids = set(current.keys())
        missing = previous_ids - current_ids

        self.controllers = current

        if missing:
            for relay in self.relays:
                if relay.controller_instance_id in missing:
                    relay.controller_instance_id = None
                    relay.controller_name = ""
                    relay.relay_enabled = False
                    relay.message = "{} Xbox 연결이 끊겼습니다.".format(
                        relay.player_name
                    )

        self.auto_assign_controllers()

    def auto_assign_controllers(self):
        used = {
            relay.controller_instance_id
            for relay in self.relays
            if relay.controller_instance_id is not None
        }

        free_ids = [
            instance_id
            for instance_id in self.controllers
            if instance_id not in used
        ]

        waiting = [
            relay
            for relay in self.relays
            if relay.controller_instance_id is None
        ]

        if len(free_ids) == 1 and len(waiting) == 1:
            relay = waiting[0]
            instance_id = free_ids[0]
            joystick = self.controllers[instance_id]
            relay.controller_instance_id = instance_id
            relay.controller_name = joystick.get_name()
            relay.message = "Xbox를 찾았습니다. EV3 연결을 확인합니다."

    def cycle_controller(self, relay):
        ids = list(self.controllers.keys())

        if not ids:
            relay.controller_instance_id = None
            relay.controller_name = ""
            relay.relay_enabled = False
            relay.message = "Xbox 컨트롤러를 찾지 못했습니다."
            return

        available = []

        for instance_id in ids:
            owner = None

            for other in self.relays:
                if other is relay:
                    continue

                if other.controller_instance_id == instance_id:
                    owner = other
                    break

            if owner is None:
                available.append(instance_id)

        if relay.controller_instance_id in ids:
            available.insert(0, relay.controller_instance_id)

        seen = set()
        available = [
            item
            for item in available
            if not (item in seen or seen.add(item))
        ]

        if not available:
            relay.message = "사용 가능한 Xbox가 없습니다."
            return

        if relay.controller_instance_id not in available:
            new_id = available[0]
        else:
            pos = available.index(relay.controller_instance_id)
            new_id = available[(pos + 1) % len(available)]

        joystick = self.controllers[new_id]
        relay.controller_instance_id = new_id
        relay.controller_name = joystick.get_name()
        relay.relay_enabled = False
        relay.message = "{}에 사용할 Xbox를 변경했습니다.".format(
            relay.player_name
        )

    def controller_connected(self, relay):
        instance_id = relay.controller_instance_id

        if instance_id is None:
            return False

        joystick = self.controllers.get(instance_id)

        if joystick is None:
            return False

        try:
            return bool(joystick.get_attached())
        except (pygame.error, AttributeError):
            return True

    # ------------------------------------------------------------------
    # Relay transport
    # ------------------------------------------------------------------

    def ev3_connected(self, relay):
        if not relay.ev3_ip or relay.last_ev3_seen <= 0:
            return False

        return (time.monotonic() - relay.last_ev3_seen) < EV3_TIMEOUT

    def endpoint(self, relay):
        if not relay.ev3_ip:
            return None
        return relay.ev3_ip, DEFAULT_EV3_PORT

    def send_heartbeat(self, relay):
        endpoint = self.endpoint(relay)

        if endpoint is None:
            return

        relay.ping_id += 1
        ping_id = relay.ping_id
        relay.pending_pings[ping_id] = time.monotonic()

        packet = {
            "type": "heartbeat",
            "relay_id": relay.relay_id,
            "session_id": self.session_id,
            "ping_id": ping_id,
        }

        try:
            self.sock.sendto(
                json.dumps(packet).encode("utf-8"),
                endpoint,
            )
        except OSError:
            pass

        cutoff = time.monotonic() - 5.0
        relay.pending_pings = {
            key: sent
            for key, sent in relay.pending_pings.items()
            if sent >= cutoff
        }

    def send_all_heartbeats(self):
        for relay in self.relays:
            self.send_heartbeat(relay)

    def send_discovery_request(self):
        packet = {
            "type": "discover_request",
            "version": 1,
        }

        try:
            self.sock.sendto(
                json.dumps(packet).encode("utf-8"),
                ("255.255.255.255", DEFAULT_EV3_PORT),
            )
        except OSError:
            pass

    def receive_packets(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
            except BlockingIOError:
                return
            except OSError:
                return

            try:
                packet = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue

            packet_type = packet.get("type")

            if packet_type == "ev3_discover_reply":
                robot_id = str(packet.get("robot_id") or "").strip()

                try:
                    service_port = int(
                        packet.get("service_port", DEFAULT_EV3_PORT)
                    )
                except (TypeError, ValueError):
                    continue

                if robot_id and service_port == DEFAULT_EV3_PORT:
                    self.record_discovery(robot_id, addr[0])

                continue

            relay = self.relay_by_id(packet.get("relay_id"))

            if relay is None or not relay.ev3_ip:
                continue

            if addr[0] != relay.ev3_ip:
                continue

            if packet_type not in ("heartbeat_ack", "control_ack"):
                continue

            packet_session = packet.get("session_id")

            if packet_session not in (None, self.session_id):
                continue

            packet_robot_id = packet.get("robot_id")

            if packet_robot_id and packet_robot_id != relay.robot_id:
                self.reset_ev3_binding(
                    relay,
                    "EV3 ID가 일치하지 않아 자동 재검색합니다.",
                )
                continue

            relay.last_ev3_seen = time.monotonic()

            if packet_type == "heartbeat_ack":
                ping_id = packet.get("ping_id")
                sent_at = relay.pending_pings.pop(ping_id, None)

                if sent_at is not None:
                    relay.last_rtt_ms = (
                        time.monotonic() - sent_at
                    ) * 1000.0

                if not relay.relay_enabled:
                    relay.message = "{} 준비됨".format(relay.robot_id)

    def send_controls(self):
        for relay in self.relays:
            if not relay.relay_enabled:
                continue

            if not self.controller_connected(relay):
                relay.relay_enabled = False
                relay.message = "{} Xbox 연결이 끊겼습니다.".format(
                    relay.player_name
                )
                continue

            if not self.ev3_connected(relay):
                relay.relay_enabled = False
                relay.message = "{} EV3 연결이 끊겼습니다.".format(
                    relay.robot_id
                )
                continue

            joystick = self.controllers.get(relay.controller_instance_id)

            if joystick is None:
                relay.relay_enabled = False
                continue

            try:
                lx = apply_deadzone(joystick.get_axis(0))
                ly = apply_deadzone(joystick.get_axis(1))
                rx = apply_deadzone(joystick.get_axis(2))
                ry = apply_deadzone(joystick.get_axis(3))
                lt = trigger_value(joystick.get_axis(LT_AXIS))
                rt = trigger_value(joystick.get_axis(RT_AXIS))

                buttons = {
                    name: button_down(joystick, index)
                    for name, index in XBOX_BUTTONS.items()
                }
            except pygame.error:
                relay.relay_enabled = False
                relay.message = "{} Xbox 입력 오류입니다.".format(
                    relay.player_name
                )
                continue

            relay.seq += 1

            packet = {
                "type": "control",
                "relay_id": relay.relay_id,
                "session_id": self.session_id,
                "seq": relay.seq,
                "lx": round(lx, 3),
                "ly": round(ly, 3),
                "rx": round(rx, 3),
                "ry": round(ry, 3),
                "lt": round(lt, 3),
                "rt": round(rt, 3),
                "buttons": buttons,
            }

            try:
                self.sock.sendto(
                    json.dumps(packet).encode("utf-8"),
                    self.endpoint(relay),
                )
            except OSError:
                relay.relay_enabled = False
                relay.message = "{} 네트워크 오류입니다.".format(
                    relay.robot_id
                )

    def toggle_relay(self, relay):
        if relay.relay_enabled:
            relay.relay_enabled = False
            relay.message = "{} 중계를 정지했습니다.".format(
                relay.robot_id
            )
            return

        if not self.controller_connected(relay):
            relay.message = "{} Xbox가 연결되지 않았습니다.".format(
                relay.player_name
            )
            return

        if not relay.ev3_ip:
            relay.message = "{} EV3를 자동으로 찾는 중입니다.".format(
                relay.robot_id
            )
            return

        if not self.ev3_connected(relay):
            relay.message = "{} EV3가 아직 응답하지 않습니다.".format(
                relay.robot_id
            )
            self.send_heartbeat(relay)
            return

        relay.relay_enabled = True
        relay.message = "{} 중계 중입니다.".format(relay.robot_id)

    def start_all(self):
        for relay in self.relays:
            if self.controller_connected(relay) and self.ev3_connected(relay):
                relay.relay_enabled = True
                relay.message = "{} 중계 중입니다.".format(
                    relay.robot_id
                )
            else:
                relay.relay_enabled = False

                if not self.controller_connected(relay):
                    relay.message = "{} Xbox 연결을 확인하세요.".format(
                        relay.player_name
                    )
                elif not relay.ev3_ip:
                    relay.message = "{} EV3를 찾는 중입니다.".format(
                        relay.robot_id
                    )
                else:
                    relay.message = "{} EV3 연결을 확인하세요.".format(
                        relay.robot_id
                    )

    def reconnect_relay(self, relay):
        self.scan_controllers(force=True)
        relay.last_ev3_seen = 0.0
        relay.last_rtt_ms = None
        relay.pending_pings = {}

        if relay.ev3_ip:
            self.send_heartbeat(relay)
            relay.message = "{} 연결을 다시 확인합니다.".format(
                relay.robot_id
            )
        else:
            relay.message = "{} EV3를 자동으로 찾는 중입니다.".format(
                relay.robot_id
            )

    def stop_all(self):
        for relay in self.relays:
            relay.relay_enabled = False
            relay.message = "전체 긴급 정지로 중계를 정지했습니다."

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def fit_text(self, text, font, max_width):
        text = str(text)

        if font.size(text)[0] <= max_width:
            return text

        suffix = "..."

        while text and font.size(text + suffix)[0] > max_width:
            text = text[:-1]

        return text + suffix

    def draw_text(self, text, font, color, pos):
        image = font.render(str(text), True, color)
        self.screen.blit(image, pos)
        return image.get_rect(topleft=pos)

    def draw_button(self, key, rect, label, danger=False):
        mouse = pygame.mouse.get_pos()
        bg = DANGER if danger else BUTTON

        if rect.collidepoint(mouse) and not danger:
            bg = BUTTON_HOVER

        pygame.draw.rect(self.screen, bg, rect, border_radius=8)
        pygame.draw.rect(
            self.screen,
            BORDER,
            rect,
            width=1,
            border_radius=8,
        )

        image = self.font_button.render(label, True, TEXT)
        image_rect = image.get_rect(center=rect.center)
        self.screen.blit(image, image_rect)
        self.button_rects[key] = rect

    def draw_status(self, x, y, connected, label, max_width):
        color = GREEN if connected else RED
        pygame.draw.circle(self.screen, color, (x + 7, y + 9), 7)

        label = self.fit_text(
            label,
            self.font_normal,
            max_width - 22,
        )

        self.draw_text(
            label,
            self.font_normal,
            TEXT,
            (x + 22, y),
        )

    def status_counts(self):
        ready = 0
        running = 0

        for relay in self.relays:
            if (
                self.controller_connected(relay)
                and self.ev3_connected(relay)
            ):
                ready += 1

            if relay.relay_enabled:
                running += 1

        return ready, running

    def draw_relay_card(self, relay, y):
        rect = pygame.Rect(24, y, WINDOW_W - 48, CARD_H)

        if rect.bottom < HEADER_H or rect.top > WINDOW_H - FOOTER_H:
            return

        pygame.draw.rect(self.screen, CARD, rect, border_radius=12)
        pygame.draw.rect(
            self.screen,
            BORDER,
            rect,
            width=1,
            border_radius=12,
        )

        title = "{} / {}".format(
            relay.player_name,
            relay.robot_id,
        )
        title = self.fit_text(title, self.font_header, 520)

        self.draw_text(
            title,
            self.font_header,
            TEXT,
            (42, y + 13),
        )

        controller_ok = self.controller_connected(relay)
        ev3_ok = self.ev3_connected(relay)

        if relay.relay_enabled:
            pair_label = "중계 중"
            pair_color = GREEN
        elif controller_ok and ev3_ok:
            pair_label = "준비됨"
            pair_color = GREEN
        elif controller_ok or relay.ev3_ip:
            pair_label = "확인 필요"
            pair_color = AMBER
        else:
            pair_label = "검색 중"
            pair_color = AMBER

        pair_image = self.font_header.render(
            pair_label,
            True,
            pair_color,
        )
        self.screen.blit(
            pair_image,
            (
                WINDOW_W - 42 - pair_image.get_width(),
                y + 13,
            ),
        )

        xbox_label = "Xbox: {}".format(relay.controller_label)

        if controller_ok and relay.controller_name:
            xbox_label += " · " + relay.controller_name

        self.draw_status(
            44,
            y + 45,
            controller_ok,
            xbox_label,
            790,
        )

        if relay.ev3_ip:
            ev3_label = "EV3: {} · {}".format(
                relay.robot_id,
                relay.ev3_ip,
            )
        else:
            ev3_label = "EV3: {} · 자동 검색 중".format(
                relay.robot_id
            )

        if ev3_ok and relay.last_rtt_ms is not None:
            ev3_label += "  ({:.1f} ms)".format(relay.last_rtt_ms)

        self.draw_status(
            44,
            y + 71,
            ev3_ok,
            ev3_label,
            790,
        )

        message = self.fit_text(
            relay.message,
            self.font_small,
            790,
        )

        self.draw_text(
            message,
            self.font_small,
            MUTED,
            (44, y + 99),
        )

        button_y = y + 123

        self.draw_button(
            ("controller", relay.relay_id),
            pygame.Rect(44, button_y, 112, 30),
            "Xbox 선택",
        )
        self.draw_button(
            ("reconnect", relay.relay_id),
            pygame.Rect(164, button_y, 112, 30),
            "다시 연결",
        )
        self.draw_button(
            ("edit", relay.relay_id),
            pygame.Rect(284, button_y, 112, 30),
            "정보 수정",
        )
        self.draw_button(
            ("toggle", relay.relay_id),
            pygame.Rect(404, button_y, 136, 30),
            "중계 정지" if relay.relay_enabled else "중계 시작",
            danger=relay.relay_enabled,
        )

        if len(self.relays) > 1:
            self.draw_button(
                ("remove", relay.relay_id),
                pygame.Rect(WINDOW_W - 104, button_y, 62, 30),
                "삭제",
            )

    def max_scroll(self):
        content_height = (
            len(self.relays) * CARD_H
            + max(0, len(self.relays) - 1) * CARD_GAP
        )
        viewport_height = WINDOW_H - HEADER_H - FOOTER_H
        return max(0, content_height - viewport_height + 10)

    def clamp_scroll(self):
        self.scroll_offset = max(
            0,
            min(self.scroll_offset, self.max_scroll()),
        )

    def draw_edit_modal(self):
        relay = self.relay_by_id(self.edit_relay_id)

        if relay is None:
            return

        overlay = pygame.Surface(
            (WINDOW_W, WINDOW_H),
            pygame.SRCALPHA,
        )
        overlay.fill(OVERLAY)
        self.screen.blit(overlay, (0, 0))

        modal = pygame.Rect(
            170,
            120,
            WINDOW_W - 340,
            450,
        )

        pygame.draw.rect(
            self.screen,
            CARD,
            modal,
            border_radius=14,
        )
        pygame.draw.rect(
            self.screen,
            BORDER,
            modal,
            width=1,
            border_radius=14,
        )

        self.draw_text(
            "중계 정보 수정",
            self.font_title,
            TEXT,
            (modal.x + 28, modal.y + 24),
        )

        self.draw_text(
            "IP는 입력하지 않습니다. EV3 ID로 현재 주소를 자동으로 찾습니다.",
            self.font_small,
            MUTED,
            (modal.x + 28, modal.y + 64),
        )

        fields = [
            ("player_name", "선수 이름"),
            ("robot_id", "EV3 ID"),
            ("controller_label", "Xbox 이름"),
        ]

        self.edit_field_rects = {}

        for index, (key, label) in enumerate(fields):
            top = modal.y + 104 + index * 88

            self.draw_text(
                label,
                self.font_normal,
                TEXT,
                (modal.x + 30, top),
            )

            field_rect = pygame.Rect(
                modal.x + 30,
                top + 28,
                modal.width - 60,
                42,
            )

            selected = index == self.edit_field_index
            border_color = GREEN if selected else BORDER

            pygame.draw.rect(
                self.screen,
                BG,
                field_rect,
                border_radius=8,
            )
            pygame.draw.rect(
                self.screen,
                border_color,
                field_rect,
                width=2 if selected else 1,
                border_radius=8,
            )

            value = self.fit_text(
                self.edit_values.get(key, ""),
                self.font_normal,
                field_rect.width - 24,
            )

            self.draw_text(
                value,
                self.font_normal,
                TEXT,
                (field_rect.x + 12, field_rect.y + 10),
            )

            self.edit_field_rects[key] = field_rect

        if self.edit_error:
            self.draw_text(
                self.edit_error,
                self.font_small,
                RED,
                (modal.x + 30, modal.bottom - 86),
            )

        self.edit_cancel_rect = pygame.Rect(
            modal.right - 240,
            modal.bottom - 58,
            96,
            34,
        )
        self.edit_save_rect = pygame.Rect(
            modal.right - 132,
            modal.bottom - 58,
            102,
            34,
        )

        self.draw_button(
            ("modal_cancel", None),
            self.edit_cancel_rect,
            "취소",
        )
        self.draw_button(
            ("modal_save", None),
            self.edit_save_rect,
            "저장",
        )

    def draw(self):
        self.screen.fill(BG)
        self.button_rects = {}

        self.draw_text(
            "EV3 Xbox Relay",
            self.font_title,
            TEXT,
            (24, 19),
        )

        ready, running = self.status_counts()
        summary = "준비 {}/{} · 중계 {}/{}".format(
            ready,
            len(self.relays),
            running,
            len(self.relays),
        )

        summary_image = self.font_header.render(
            summary,
            True,
            GREEN if ready == len(self.relays) else AMBER,
        )
        self.screen.blit(
            summary_image,
            (
                WINDOW_W - 24 - summary_image.get_width(),
                25,
            ),
        )

        self.draw_text(
            "EV3 IP는 자동으로 찾습니다. 선수 · EV3 ID · Xbox 이름만 지정하면 됩니다.",
            self.font_normal,
            MUTED,
            (24, 58),
        )

        pygame.draw.line(
            self.screen,
            BORDER,
            (24, 91),
            (WINDOW_W - 24, 91),
            1,
        )

        card_clip = pygame.Rect(
            0,
            HEADER_H - 8,
            WINDOW_W,
            WINDOW_H - HEADER_H - FOOTER_H + 8,
        )
        self.screen.set_clip(card_clip)

        y = HEADER_H - self.scroll_offset

        for relay in self.relays:
            self.draw_relay_card(relay, y)
            y += CARD_H + CARD_GAP

        self.screen.set_clip(None)

        footer_y = WINDOW_H - FOOTER_H

        pygame.draw.rect(
            self.screen,
            BG,
            pygame.Rect(0, footer_y, WINDOW_W, FOOTER_H),
        )
        pygame.draw.line(
            self.screen,
            BORDER,
            (0, footer_y),
            (WINDOW_W, footer_y),
            1,
        )

        self.draw_button(
            ("add", None),
            pygame.Rect(24, footer_y + 12, 104, 36),
            "중계 추가",
        )
        self.draw_button(
            ("rescan", None),
            pygame.Rect(138, footer_y + 12, 126, 36),
            "전체 다시 찾기",
        )
        self.draw_button(
            ("start_all", None),
            pygame.Rect(WINDOW_W - 330, footer_y + 12, 140, 36),
            "전체 중계 시작",
        )
        self.draw_button(
            ("stop_all", None),
            pygame.Rect(WINDOW_W - 180, footer_y + 12, 156, 36),
            "전체 긴급 정지",
            danger=True,
        )

        if self.edit_relay_id is not None:
            self.draw_edit_modal()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def relay_by_id(self, relay_id):
        for relay in self.relays:
            if relay.relay_id == relay_id:
                return relay
        return None

    def handle_modal_click(self, pos):
        fields = [
            "player_name",
            "robot_id",
            "controller_label",
        ]

        for index, key in enumerate(fields):
            rect = self.edit_field_rects.get(key)

            if rect and rect.collidepoint(pos):
                self.edit_field_index = index
                return True

        if self.edit_save_rect and self.edit_save_rect.collidepoint(pos):
            self.save_edit()
            return True

        if self.edit_cancel_rect and self.edit_cancel_rect.collidepoint(pos):
            self.close_edit()
            return True

        return False

    def handle_modal_key(self, event):
        fields = [
            "player_name",
            "robot_id",
            "controller_label",
        ]
        key = fields[self.edit_field_index]

        if event.key == pygame.K_ESCAPE:
            self.close_edit()
            return

        if event.key == pygame.K_TAB:
            direction = -1 if event.mod & pygame.KMOD_SHIFT else 1
            self.edit_field_index = (
                self.edit_field_index + direction
            ) % len(fields)
            return

        if event.key == pygame.K_RETURN:
            if self.edit_field_index < len(fields) - 1:
                self.edit_field_index += 1
            else:
                self.save_edit()
            return

        if event.key == pygame.K_BACKSPACE:
            self.edit_values[key] = self.edit_values.get(key, "")[:-1]
            self.edit_error = ""

    def handle_text_input(self, text):
        fields = [
            "player_name",
            "robot_id",
            "controller_label",
        ]
        key = fields[self.edit_field_index]

        current = self.edit_values.get(key, "")
        max_length = 40 if key != "robot_id" else 32

        if len(current) < max_length:
            self.edit_values[key] = (
                current + text
            )[:max_length]

        self.edit_error = ""

    def handle_click(self, pos):
        if self.edit_relay_id is not None:
            self.handle_modal_click(pos)
            return

        for key, rect in list(self.button_rects.items()):
            if not rect.collidepoint(pos):
                continue

            action, relay_id = key
            relay = self.relay_by_id(relay_id) if relay_id else None

            if action == "add":
                self.add_relay()
                self.scroll_offset = self.max_scroll()

            elif action == "rescan":
                self.scan_controllers(force=True)
                self.send_discovery_request()
                self.send_all_heartbeats()

                for item in self.relays:
                    if not item.ev3_ip:
                        item.message = "{} EV3를 자동으로 찾는 중입니다.".format(
                            item.robot_id
                        )

            elif action == "start_all":
                self.start_all()

            elif action == "stop_all":
                self.stop_all()

            elif relay is not None:
                if action == "controller":
                    self.cycle_controller(relay)
                elif action == "reconnect":
                    self.reconnect_relay(relay)
                elif action == "edit":
                    self.open_edit(relay)
                elif action == "toggle":
                    self.toggle_relay(relay)
                elif action == "remove":
                    self.remove_relay(relay)

            break

    def run(self):
        while self.running:
            now = time.monotonic()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.handle_click(event.pos)

                elif event.type == pygame.MOUSEWHEEL:
                    if self.edit_relay_id is None:
                        self.scroll_offset -= event.y * 46
                        self.clamp_scroll()

                elif event.type == pygame.KEYDOWN:
                    if self.edit_relay_id is not None:
                        self.handle_modal_key(event)

                elif event.type == pygame.TEXTINPUT:
                    if self.edit_relay_id is not None:
                        self.handle_text_input(event.text)

                elif event.type in (
                    pygame.JOYDEVICEADDED,
                    pygame.JOYDEVICEREMOVED,
                ):
                    self.scan_controllers(force=True)

            self.scan_controllers()
            self.receive_discovery()

            if now - self.last_discovery_query >= DISCOVERY_QUERY_INTERVAL:
                self.last_discovery_query = now
                self.send_discovery_request()

            if now - self.last_heartbeat >= HEARTBEAT_INTERVAL:
                self.last_heartbeat = now
                self.send_all_heartbeats()

            self.receive_packets()

            if now - self.last_control >= 1.0 / CONTROL_HZ:
                self.last_control = now
                self.send_controls()

            for relay in self.relays:
                if relay.relay_enabled and not self.ev3_connected(relay):
                    relay.relay_enabled = False
                    relay.message = "{} EV3 연결이 끊겼습니다.".format(
                        relay.robot_id
                    )

            self.draw()
            self.clock.tick(60)

        self.stop_all()
        self.sock.close()
        pygame.quit()


def main():
    app = RelayApp()
    app.run()


if __name__ == "__main__":
    main()
