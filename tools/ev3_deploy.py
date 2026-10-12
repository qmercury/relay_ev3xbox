#!/usr/bin/env python3
"""Deploy and run one student's main.py on one assigned EV3.

This tool deliberately manages only the student program inside remote_dir.
It never stops xbox_service.py or the teacher relay.
"""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".vscode" / "ev3-target.json"
EV3_SUPPORT_FILES = [ROOT / "ev3" / "ev3xbox.py"]

DISCOVERY_PORT = 5005
DISCOVERY_TIMEOUT_SECONDS = 4.0


def fail(message, code=2):
    print("[EV3] ERROR:", message, file=sys.stderr)
    raise SystemExit(code)


def load_config(path):
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path

    if not config_path.exists():
        fail(
            "Target config not found: {}\n"
            "Copy .vscode/ev3-target.example.json to "
            ".vscode/ev3-target.json and set this student's EV3 IP.".format(
                config_path
            )
        )

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("Could not read {}: {}".format(config_path, exc))

    required = ("host", "user", "remote_dir", "main_file")
    missing = [key for key in required if not config.get(key)]
    if missing:
        fail("Missing config keys: {}".format(", ".join(missing)))

    remote_dir = str(config["remote_dir"])
    if not remote_dir.startswith("/"):
        fail("remote_dir must be an absolute EV3 path.")
    if any(ch.isspace() for ch in remote_dir):
        fail("remote_dir must not contain spaces.")

    config.setdefault("port", 22)
    config.setdefault("python", "python3")
    config.setdefault("connect_timeout", 5)
    config.setdefault("sync_library", True)

    return config, config_path


def require_program(name):
    path = shutil.which(name)
    if not path:
        fail(
            "{} was not found. Install/enable the OpenSSH client first.".format(
                name
            )
        )
    return path


def default_identity_path():
    return Path.home() / ".ssh" / "ev3_classroom_ed25519"


def discover_robot_ip(robot_id, known_host=None, timeout=DISCOVERY_TIMEOUT_SECONDS):
    """Find one EV3 by persistent Robot ID on the current local network.

    Broadcast is the primary discovery path. When a previously known host is
    available, also probe it directly. This makes repeated classroom deploys
    more reliable on Wi-Fi networks that occasionally drop broadcast packets,
    while broadcast still allows discovery after DHCP changes the EV3 address.
    """
    robot_id = str(robot_id or "").strip()
    if not robot_id:
        return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", 0))
    sock.settimeout(0.20)

    packet = json.dumps(
        {
            "type": "discover_request",
            "version": 1,
        }
    ).encode("utf-8")

    deadline = time.monotonic() + float(timeout)
    next_query = 0.0
    first_found_at = None
    found = set()

    targets = [("255.255.255.255", DISCOVERY_PORT)]
    known_host = str(known_host or "").strip()
    if known_host:
        targets.append((known_host, DISCOVERY_PORT))

    try:
        while time.monotonic() < deadline:
            now = time.monotonic()

            if first_found_at is not None and now - first_found_at >= 0.50:
                break

            if now >= next_query:
                next_query = now + 0.25

                for target in targets:
                    try:
                        sock.sendto(packet, target)
                    except OSError:
                        pass

            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                reply = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue

            if reply.get("type") != "ev3_discover_reply":
                continue

            if str(reply.get("robot_id") or "").strip() != robot_id:
                continue

            found.add(addr[0])

            if first_found_at is None:
                first_found_at = time.monotonic()

            if len(found) > 1:
                fail(
                    "Robot ID {} was found at multiple IP addresses: {}. "
                    "Give every EV3 a unique Robot ID.".format(
                        robot_id,
                        ", ".join(sorted(found)),
                    )
                )
    finally:
        sock.close()

    if len(found) == 1:
        return next(iter(found))

    return None


class EV3Target:
    def __init__(self, config):
        self.config = config
        self.ssh = require_program("ssh")
        self.scp = require_program("scp")

        self.host = str(config["host"])
        self.user = str(config["user"])
        self.port = int(config["port"])
        self.remote_dir = str(config["remote_dir"])
        self.python = str(config["python"])
        self.timeout = int(config["connect_timeout"])

        self.identity_file = config.get("identity_file")
        if self.identity_file:
            identity = Path(os.path.expanduser(str(self.identity_file)))
            if not identity.is_absolute():
                identity = ROOT / identity
            self.identity_file = str(identity)
        else:
            default_identity = default_identity_path()
            if default_identity.exists():
                self.identity_file = str(default_identity)

    @property
    def login(self):
        return "{}@{}".format(self.user, self.host)

    @property
    def remote_main(self):
        return self.remote_dir.rstrip("/") + "/main.py"

    @property
    def remote_pid(self):
        return self.remote_dir.rstrip("/") + "/.student.pid"

    @property
    def remote_log(self):
        return self.remote_dir.rstrip("/") + "/student.log"

    def ssh_args(self):
        args = [
            self.ssh,
            "-p",
            str(self.port),
            "-o",
            "ConnectTimeout={}".format(self.timeout),
            "-o",
            "ServerAliveInterval=3",
            "-o",
            "ServerAliveCountMax=2",
        ]

        if self.identity_file:
            args.extend(["-i", self.identity_file])

        args.append(self.login)
        return args

    def scp_args(self):
        args = [
            self.scp,
            "-P",
            str(self.port),
            "-o",
            "ConnectTimeout={}".format(self.timeout),
        ]

        if self.identity_file:
            args.extend(["-i", self.identity_file])

        return args

    def remote(self, script, check=True):
        command = "sh -lc " + shlex.quote(script)
        return subprocess.run(
            self.ssh_args() + [command],
            check=check,
        )

    def copy_file(self, local_path, remote_path):
        target = "{}:{}".format(self.login, remote_path)
        subprocess.run(
            self.scp_args() + [str(local_path), target],
            check=True,
        )

    def copy_dir(self, local_dir, remote_parent):
        target = "{}:{}".format(self.login, remote_parent)
        subprocess.run(
            self.scp_args() + ["-r", str(local_dir), target],
            check=True,
        )


def q(value):
    return shlex.quote(str(value))


def stop_student_script(target, stop_motors=True):
    motor_stop = ""
    if stop_motors:
        motor_stop = r'''
for motor in /sys/class/tacho-motor/motor*; do
    [ -d "$motor" ] || continue
    printf 'brake' > "$motor/stop_action" 2>/dev/null || true
    printf 'stop' > "$motor/command" 2>/dev/null || true
done
'''

    return """
pidfile={pidfile}
main={main}

if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile" 2>/dev/null || true)

    case "$pid" in
        ''|*[!0-9]*)
            ;;
        *)
            if [ -r "/proc/$pid/cmdline" ]; then
                cmdline=$(tr '\\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
            else
                cmdline=""
            fi

            case "$cmdline" in
                *"$main"*)
                    kill "$pid" 2>/dev/null || true

                    count=0
                    while kill -0 "$pid" 2>/dev/null && [ "$count" -lt 20 ]; do
                        sleep 0.1
                        count=$((count + 1))
                    done

                    if kill -0 "$pid" 2>/dev/null; then
                        kill -9 "$pid" 2>/dev/null || true
                    fi
                    ;;
            esac
            ;;
    esac

    rm -f "$pidfile"
fi

{motor_stop}
""".format(
        pidfile=q(target.remote_pid),
        main=q(target.remote_main),
        motor_stop=motor_stop,
    )


def resolve_main(config):
    path = Path(str(config["main_file"]))
    if not path.is_absolute():
        path = ROOT / path

    if not path.exists():
        fail("Student main file not found: {}".format(path))

    return path


def cmd_pair(target, config, config_path):
    ssh_keygen = require_program("ssh-keygen")

    identity_text = config.get("identity_file")
    if identity_text:
        identity = Path(os.path.expanduser(str(identity_text)))
        if not identity.is_absolute():
            identity = ROOT / identity
    else:
        identity = default_identity_path()

    identity.parent.mkdir(parents=True, exist_ok=True)
    public_key = Path(str(identity) + ".pub")

    if not identity.exists() or not public_key.exists():
        print("[EV3] Creating classroom SSH key:", identity)
        subprocess.run(
            [
                ssh_keygen,
                "-t",
                "ed25519",
                "-f",
                str(identity),
                "-N",
                "",
                "-C",
                "ev3-classroom",
            ],
            check=True,
        )
    else:
        print("[EV3] Reusing classroom SSH key:", identity)

    key_text = public_key.read_text(encoding="utf-8").strip()
    if not key_text.startswith("ssh-"):
        fail("Unexpected public key format: {}".format(public_key))

    print("[EV3] Installing public key on {} ...".format(target.login))
    print("[EV3] The EV3 password may be requested once.")

    install_script = """
umask 077
mkdir -p "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 700 "$HOME/.ssh"
chmod 600 "$HOME/.ssh/authorized_keys"

key={key}

if ! grep -qxF "$key" "$HOME/.ssh/authorized_keys"; then
    printf '%s\n' "$key" >> "$HOME/.ssh/authorized_keys"
fi

echo "SSH_KEY=INSTALLED"
""".format(key=q(key_text))

    target.remote(install_script)

    print("[EV3] Testing passwordless SSH ...")
    test_config = dict(config)
    test_config["identity_file"] = str(identity)
    test_target = EV3Target(test_config)

    test_command = "echo SSH_KEY=OK"
    args = test_target.ssh_args()
    args[1:1] = ["-o", "BatchMode=yes"]

    subprocess.run(
        args + ["sh -lc " + shlex.quote(test_command)],
        check=True,
    )

    print("[EV3] Pairing complete.")
    print("[EV3] SSH key:", identity)


def cmd_check(target):
    print("[EV3] Checking {} ...".format(target.login))

    script = """
echo "SSH=OK"
printf "PYTHON="
{python} --version 2>&1 || true

if ps ax 2>/dev/null | grep '[x]box_service.py' >/dev/null 2>&1; then
    echo "XBOX_SERVICE=RUNNING"
else
    echo "XBOX_SERVICE=NOT_RUNNING"
fi

pidfile={pidfile}
main={main}

if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile" 2>/dev/null || true)

    case "$pid" in
        ''|*[!0-9]*)
            rm -f "$pidfile"
            echo "STUDENT_PROGRAM=NOT_RUNNING"
            ;;
        *)
            if [ -r "/proc/$pid/cmdline" ]; then
                cmdline=$(tr '\\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
            else
                cmdline=""
            fi

            case "$cmdline" in
                *"$main"*)
                    if kill -0 "$pid" 2>/dev/null; then
                        echo "STUDENT_PROGRAM=RUNNING pid=$pid"
                    else
                        rm -f "$pidfile"
                        echo "STUDENT_PROGRAM=NOT_RUNNING"
                    fi
                    ;;
                *)
                    rm -f "$pidfile"
                    echo "STUDENT_PROGRAM=NOT_RUNNING"
                    ;;
            esac
            ;;
    esac
else
    echo "STUDENT_PROGRAM=NOT_RUNNING"
fi
""".format(
        python=q(target.python),
        pidfile=q(target.remote_pid),
        main=q(target.remote_main),
    )

    target.remote(script)


def cmd_stop(target):
    print("[EV3] Stopping only the student program ...")
    target.remote(stop_student_script(target, stop_motors=True))
    print("[EV3] Student program stopped. xbox_service.py was not touched.")


def cmd_logs(target, lines=80, follow=False):
    lines = max(1, min(1000, int(lines)))

    if follow:
        script = """
log={log}
touch "$log"
tail -n {lines} -f "$log"
""".format(log=q(target.remote_log), lines=lines)
    else:
        script = """
log={log}
if [ -f "$log" ]; then
    tail -n {lines} "$log"
else
    echo "No student.log yet."
fi
""".format(log=q(target.remote_log), lines=lines)

    target.remote(script)


def cmd_deploy(target, config):
    main_file = resolve_main(config)

    if config.get("sync_library", True):
        missing_support = [
            path for path in EV3_SUPPORT_FILES if not path.exists()
        ]
        if missing_support:
            fail(
                "EV3 support file not found: {}".format(
                    ", ".join(str(path) for path in missing_support)
                )
            )

    print("[EV3] Target: {}".format(target.login))
    print("[EV3] Source: {}".format(main_file))
    print("[EV3] 1/5 Checking SSH ...")
    target.remote("true")

    print("[EV3] 2/5 Stopping previous student program ...")
    target.remote(stop_student_script(target, stop_motors=True))

    print("[EV3] 3/5 Preparing student directory ...")
    prepare = "mkdir -p {remote}".format(remote=q(target.remote_dir))
    if config.get("sync_library", True):
        prepare += "\nrm -f {remote}/ev3xbox.py".format(
            remote=q(target.remote_dir)
        )
    target.remote(prepare)

    print("[EV3] 4/5 Uploading main.py ...")
    target.copy_file(main_file, target.remote_main)

    if config.get("sync_library", True):
        print("[EV3]     Uploading EV3 classroom support library ...")
        for support_file in EV3_SUPPORT_FILES:
            remote_path = (
                target.remote_dir.rstrip("/")
                + "/"
                + support_file.name
            )
            target.copy_file(support_file, remote_path)

    print("[EV3] 5/5 Starting student program ...")
    start_script = """
cd {remote}
rm -f student.log

nohup env PYTHONPATH={remote} {python} -u {main} \
    > {log} 2>&1 < /dev/null &

pid=$!
printf '%s\\n' "$pid" > {pidfile}

sleep 0.35

if kill -0 "$pid" 2>/dev/null; then
    echo "STUDENT_PROGRAM=RUNNING pid=$pid"
else
    rm -f {pidfile}

    if grep -q 'Traceback (most recent call last)' {log} 2>/dev/null; then
        echo "STUDENT_PROGRAM=ERROR"
        tail -n 40 {log}
        exit 3
    fi

    echo "STUDENT_PROGRAM=FINISHED"
    if [ -s {log} ]; then
        tail -n 40 {log}
    fi
fi
""".format(
        remote=q(target.remote_dir),
        python=q(target.python),
        main=q(target.remote_main),
        log=q(target.remote_log),
        pidfile=q(target.remote_pid),
    )

    target.remote(start_script)
    print("[EV3] Deploy complete.")
    print("[EV3] Teacher Xbox relay/service remains independent.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Deploy a student Python program to one EV3."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG.relative_to(ROOT)),
        help="Target JSON config relative to repository root.",
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "pair",
        help="Install a classroom SSH key on this student's EV3.",
    )
    sub.add_parser("deploy", help="Upload support files + main.py and run it.")
    sub.add_parser("stop", help="Stop only the current student program.")
    sub.add_parser("check", help="Check EV3, Xbox service, and student process.")

    logs = sub.add_parser("logs", help="Show student.log.")
    logs.add_argument("--lines", type=int, default=80)
    logs.add_argument("--follow", action="store_true")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    config, config_path = load_config(args.config)
    print("[EV3] Config:", config_path)

    robot_id = str(config.get("robot_id") or "").strip()

    if robot_id and args.command != "pair":
        print("[EV3] Finding Robot ID {} on the local network ...".format(robot_id))
        discovered_host = discover_robot_ip(
            robot_id,
            known_host=config.get("host"),
        )

        if discovered_host:
            config["host"] = discovered_host
            print("[EV3] Robot ID {} -> {}".format(robot_id, discovered_host))
        else:
            print(
                "[EV3] Robot ID {} was not discovered; "
                "using configured host {}.".format(
                    robot_id,
                    config.get("host"),
                )
            )

    target = EV3Target(config)

    try:
        if args.command == "pair":
            cmd_pair(target, config, config_path)
        elif args.command == "deploy":
            cmd_deploy(target, config)
        elif args.command == "stop":
            cmd_stop(target)
        elif args.command == "check":
            cmd_check(target)
        elif args.command == "logs":
            cmd_logs(target, args.lines, args.follow)
    except subprocess.CalledProcessError as exc:
        fail("Command failed with exit code {}.".format(exc.returncode), exc.returncode)


if __name__ == "__main__":
    main()
