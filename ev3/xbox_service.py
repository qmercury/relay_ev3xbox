import glob
import json
import os
import socket
import time

UDP_HOST = "0.0.0.0"
UDP_PORT = 5005

LOCAL_STATE_HOST = "127.0.0.1"
LOCAL_STATE_PORT = 5006

ROBOT_ID_FILE = os.path.join(os.path.dirname(__file__), "robot_id")

CONTROL_FAILSAFE_SECONDS = 0.25
SOCKET_POLL_SECONDS = 0.05


def load_robot_id():
    try:
        with open(ROBOT_ID_FILE, "r") as f:
            value = f.read().strip()
        if value:
            return value
    except OSError:
        pass

    # This fallback keeps development installations working, but competition
    # robots should always receive an explicit unique ID.
    return socket.gethostname()


ROBOT_ID = load_robot_id()


def neutral_state(relay_id="default", session_id="legacy"):
    return {
        "relay_id": relay_id,
        "session_id": session_id,
        "connected": False,
        "lx": 0.0,
        "ly": 0.0,
        "rx": 0.0,
        "ry": 0.0,
        "lt": 0.0,
        "rt": 0.0,
        "buttons": {
            "a": False,
            "b": False,
            "x": False,
            "y": False,
            "lb": False,
            "rb": False,
            "dpad_up": False,
            "dpad_down": False,
            "dpad_left": False,
            "dpad_right": False,
        },
    }


def emergency_stop_all_motors():
    """Best-effort independent safety stop for every EV3 tacho motor."""
    for motor_dir in glob.glob("/sys/class/tacho-motor/motor*"):
        try:
            stop_action = os.path.join(motor_dir, "stop_action")
            command = os.path.join(motor_dir, "command")

            if os.path.exists(stop_action):
                with open(stop_action, "w") as f:
                    f.write("brake")

            if os.path.exists(command):
                with open(command, "w") as f:
                    f.write("stop")
        except OSError:
            pass


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_HOST, UDP_PORT))
sock.settimeout(SOCKET_POLL_SECONDS)

local_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

active_session_by_relay = {}
last_seq_by_relay = {}
last_control_time = None
last_relay_id = "default"
last_session_id = "legacy"
timed_out = True

print("EV3 Xbox service")
print("Robot ID:", ROBOT_ID)
print("Relay/discovery UDP port:", UDP_PORT)
print("Student state port:", LOCAL_STATE_PORT)
print("Failsafe: {:.0f} ms".format(CONTROL_FAILSAFE_SECONDS * 1000))
print("Waiting for relay host...")
print("Ctrl+C to stop")


def publish_state(state):
    try:
        local_sock.sendto(
            json.dumps(state).encode("utf-8"),
            (LOCAL_STATE_HOST, LOCAL_STATE_PORT),
        )
    except OSError:
        pass


try:
    while True:
        now = time.monotonic()

        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            data = None

        if data is not None:
            try:
                packet = json.loads(data.decode("utf-8"))
            except Exception:
                packet = None

            if packet is not None:
                packet_type = packet.get("type")
                relay_id = packet.get("relay_id", "default")
                session_id = packet.get("session_id", "legacy")

                if packet_type == "discover_request":
                    reply = {
                        "type": "ev3_discover_reply",
                        "version": 1,
                        "robot_id": ROBOT_ID,
                        "service_port": UDP_PORT,
                    }
                    sock.sendto(json.dumps(reply).encode("utf-8"), addr)

                elif packet_type == "heartbeat":
                    previous_session = active_session_by_relay.get(relay_id)

                    if previous_session != session_id:
                        active_session_by_relay[relay_id] = session_id
                        last_seq_by_relay[relay_id] = -1

                        last_relay_id = relay_id
                        last_session_id = session_id
                        last_control_time = None
                        timed_out = True

                        emergency_stop_all_motors()
                        publish_state(neutral_state(relay_id, session_id))
                        print("New relay session:", relay_id, session_id[:8])

                    reply = {
                        "type": "heartbeat_ack",
                        "relay_id": relay_id,
                        "session_id": session_id,
                        "ping_id": packet.get("ping_id"),
                        "robot_id": ROBOT_ID,
                    }
                    sock.sendto(json.dumps(reply).encode("utf-8"), addr)

                elif packet_type == "control":
                    if active_session_by_relay.get(relay_id) != session_id:
                        continue

                    seq = int(packet.get("seq", 0))
                    if seq <= last_seq_by_relay.get(relay_id, -1):
                        continue

                    last_seq_by_relay[relay_id] = seq
                    last_relay_id = relay_id
                    last_session_id = session_id
                    last_control_time = time.monotonic()
                    timed_out = False

                    state = {
                        "relay_id": relay_id,
                        "session_id": session_id,
                        "connected": True,
                        "lx": float(packet.get("lx", 0.0)),
                        "ly": float(packet.get("ly", 0.0)),
                        "rx": float(packet.get("rx", 0.0)),
                        "ry": float(packet.get("ry", 0.0)),
                        "lt": float(packet.get("lt", 0.0)),
                        "rt": float(packet.get("rt", 0.0)),
                        "buttons": packet.get("buttons") or {},
                    }
                    publish_state(state)

                    reply = {
                        "type": "control_ack",
                        "relay_id": relay_id,
                        "session_id": session_id,
                        "seq": seq,
                        "robot_id": ROBOT_ID,
                    }
                    sock.sendto(json.dumps(reply).encode("utf-8"), addr)

        if last_control_time is not None:
            age = time.monotonic() - last_control_time
            if age > CONTROL_FAILSAFE_SECONDS and not timed_out:
                timed_out = True
                last_control_time = None

                emergency_stop_all_motors()
                publish_state(neutral_state(last_relay_id, last_session_id))
                print("FAILSAFE: control timeout -> all motors stopped")

except KeyboardInterrupt:
    print("\nStopping Xbox service...")

finally:
    emergency_stop_all_motors()
    publish_state(neutral_state(last_relay_id, last_session_id))
    sock.close()
    local_sock.close()
    print("Xbox service stopped.")
