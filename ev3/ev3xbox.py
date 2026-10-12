import json
import socket
import threading
import time


LOCAL_STATE_HOST = "127.0.0.1"
LOCAL_STATE_PORT = 5006


class XboxButton:
    A = "A"
    B = "B"
    X = "X"
    Y = "Y"

    LB = "LB"
    RB = "RB"

    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


_BUTTON_MAP = {
    "a": XboxButton.A,
    "b": XboxButton.B,
    "x": XboxButton.X,
    "y": XboxButton.Y,
    "lb": XboxButton.LB,
    "rb": XboxButton.RB,
    "dpad_up": XboxButton.UP,
    "dpad_down": XboxButton.DOWN,
    "dpad_left": XboxButton.LEFT,
    "dpad_right": XboxButton.RIGHT,
}


class _Buttons:
    def __init__(self, controller):
        self._controller = controller

    def pressed(self):
        with self._controller._lock:
            raw = dict(self._controller._state.get("buttons", {}))

        return {
            public_name
            for raw_name, public_name in _BUTTON_MAP.items()
            if raw.get(raw_name, False)
        }


class XboxController:
    """Read Xbox state forwarded by the teacher relay.

    xbox_service.py on the EV3 publishes the latest normalized controller
    state to localhost UDP port 5006. Student code only needs this class.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._state = self._neutral_state()
        self._running = True

        self.buttons = _Buttons(self)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((LOCAL_STATE_HOST, LOCAL_STATE_PORT))
        self._sock.settimeout(0.2)

        self._thread = threading.Thread(target=self._receiver_loop)
        self._thread.daemon = True
        self._thread.start()

    @staticmethod
    def _neutral_state():
        return {
            "connected": False,
            "lx": 0.0,
            "ly": 0.0,
            "rx": 0.0,
            "ry": 0.0,
            "lt": 0.0,
            "rt": 0.0,
            "buttons": {},
        }

    @staticmethod
    def _stick_value(value):
        value = max(-1.0, min(1.0, float(value)))
        return int(round(value * 100))

    @staticmethod
    def _trigger_value(value):
        value = max(0.0, min(1.0, float(value)))
        return int(round(value * 100))

    def _receiver_loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                state = json.loads(data.decode("utf-8"))
            except Exception:
                continue

            with self._lock:
                self._state = state

    def joystick_left(self):
        """Return left stick as (x, y), each from -100 to 100."""
        with self._lock:
            lx = self._state.get("lx", 0.0)
            ly = self._state.get("ly", 0.0)

        return (
            self._stick_value(lx),
            self._stick_value(-ly),
        )

    def joystick_right(self):
        """Return right stick as (x, y), each from -100 to 100."""
        with self._lock:
            rx = self._state.get("rx", 0.0)
            ry = self._state.get("ry", 0.0)

        return (
            self._stick_value(rx),
            self._stick_value(-ry),
        )

    def triggers(self):
        """Return (LT, RT), each from 0 to 100."""
        with self._lock:
            lt = self._state.get("lt", 0.0)
            rt = self._state.get("rt", 0.0)

        return (
            self._trigger_value(lt),
            self._trigger_value(rt),
        )

    def connected(self):
        with self._lock:
            return bool(self._state.get("connected", False))

    def close(self):
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass

    def wait_until_connected(self, timeout=None, poll=0.05):
        """Wait until relay control data is available.

        Returns True when connected. Returns False when timeout expires.
        timeout=None waits forever.
        """
        started = time.monotonic()

        while not self.connected():
            if timeout is not None:
                if time.monotonic() - started >= float(timeout):
                    return False
            time.sleep(float(poll))

        return True


__all__ = ["XboxController", "XboxButton"]
