#!/usr/bin/env python3
"""Install/update xbox_service.py as a persistent systemd service on one EV3."""

from pathlib import Path
import re
import shlex
import subprocess
import sys

from ev3_deploy import EV3Target, ROOT, load_config, fail, discover_robot_ip


SERVICE_NAME = "ev3-xbox-service.service"
LOCAL_SERVICE = ROOT / "ev3" / "xbox_service.py"
LOCAL_UNIT = ROOT / "ev3" / "systemd" / SERVICE_NAME

REMOTE_DIR = "/home/robot/ev3-xbox"
REMOTE_SERVICE = REMOTE_DIR + "/xbox_service.py"
REMOTE_ROBOT_ID = REMOTE_DIR + "/robot_id"
REMOTE_UNIT_TMP = "/tmp/" + SERVICE_NAME

ROBOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


def q(value):
    return shlex.quote(str(value))


def validate_robot_id(robot_id):
    value = str(robot_id or "").strip()

    if not ROBOT_ID_PATTERN.fullmatch(value):
        fail(
            "robot_id must be 1-32 characters using only "
            "A-Z, a-z, 0-9, dot, underscore, or hyphen."
        )

    return value


def remote_tty(target, script):
    args = target.ssh_args()
    args.insert(len(args) - 1, "-tt")
    command = "sh -lc " + shlex.quote(script)
    subprocess.run(args + [command], check=True)


def install(target, robot_id=None):
    if not LOCAL_SERVICE.exists():
        fail("Missing local service file: {}".format(LOCAL_SERVICE))
    if not LOCAL_UNIT.exists():
        fail("Missing local unit file: {}".format(LOCAL_UNIT))

    print("[EV3] Preparing persistent Xbox service on", target.login)

    target.remote("mkdir -p {}".format(q(REMOTE_DIR)))
    target.copy_file(LOCAL_SERVICE, REMOTE_SERVICE)
    target.copy_file(LOCAL_UNIT, REMOTE_UNIT_TMP)

    robot_id_script = ""

    if robot_id:
        robot_id = validate_robot_id(robot_id)
        robot_id_script = """
printf '%s\\n' {robot_id} > {robot_id_file}
chmod 644 {robot_id_file}
echo "ROBOT_ID={robot_id}"
""".format(
            robot_id=q(robot_id),
            robot_id_file=q(REMOTE_ROBOT_ID),
        )
    else:
        robot_id_script = """
if [ -s {robot_id_file} ]; then
    printf 'ROBOT_ID='
    cat {robot_id_file}
else
    echo "ROBOT_ID=NOT_CONFIGURED (hostname fallback will be used)"
fi
""".format(robot_id_file=q(REMOTE_ROBOT_ID))

    print("[EV3] Installing systemd unit.")
    print("[EV3] sudo may request the EV3 password.")

    script = """
set -e

chmod 755 {service}

{robot_id_script}

sudo cp {unit_tmp} /etc/systemd/system/{service_name}
sudo chmod 644 /etc/systemd/system/{service_name}
sudo systemctl daemon-reload
sudo systemctl enable {service_name}
sudo systemctl restart {service_name}

sleep 0.5

echo
echo "=== service status ==="
sudo systemctl --no-pager --full status {service_name} || true
""".format(
        service=q(REMOTE_SERVICE),
        robot_id_script=robot_id_script,
        unit_tmp=q(REMOTE_UNIT_TMP),
        service_name=SERVICE_NAME,
    )

    remote_tty(target, script)

    print("[EV3] Persistent Xbox service installed.")
    print("[EV3] It will start automatically after EV3 boot.")


def set_robot_id(target, robot_id):
    robot_id = validate_robot_id(robot_id)

    print("[EV3] Setting Robot ID on", target.login, "->", robot_id)

    script = """
set -e
mkdir -p {remote_dir}
printf '%s\\n' {robot_id} > {robot_id_file}
chmod 644 {robot_id_file}

if systemctl list-unit-files {service_name} >/dev/null 2>&1; then
    sudo systemctl restart {service_name}
fi

echo "ROBOT_ID={robot_id}"
""".format(
        remote_dir=q(REMOTE_DIR),
        robot_id=q(robot_id),
        robot_id_file=q(REMOTE_ROBOT_ID),
        service_name=SERVICE_NAME,
    )

    remote_tty(target, script)
    print("[EV3] Robot ID saved. Relay discovery will use:", robot_id)


def status(target):
    script = """
echo "=== robot id ==="
if [ -s {robot_id_file} ]; then
    cat {robot_id_file}
else
    echo "NOT_CONFIGURED"
fi

echo
echo "=== systemd ==="
systemctl is-enabled {name} 2>/dev/null || true
systemctl is-active {name} 2>/dev/null || true

echo
echo "=== recent log ==="
journalctl -u {name} -n 20 --no-pager 2>/dev/null || true
""".format(
        name=SERVICE_NAME,
        robot_id_file=q(REMOTE_ROBOT_ID),
    )

    target.remote(script)


def usage():
    print(
        "Usage:\n"
        "  python tools/ev3_service.py install [config-path]\n"
        "  python tools/ev3_service.py status [config-path]\n"
        "  python tools/ev3_service.py set-id ROBOT_ID [config-path]",
        file=sys.stderr,
    )


def main():
    if len(sys.argv) < 2:
        usage()
        raise SystemExit(2)

    command = sys.argv[1]

    if command not in ("install", "status", "set-id"):
        usage()
        raise SystemExit(2)

    if command == "set-id":
        if len(sys.argv) < 3:
            usage()
            raise SystemExit(2)

        robot_id = sys.argv[2]
        config_path = (
            sys.argv[3]
            if len(sys.argv) >= 4
            else ".vscode/ev3-target.json"
        )
    else:
        robot_id = None
        config_path = (
            sys.argv[2]
            if len(sys.argv) >= 3
            else ".vscode/ev3-target.json"
        )

    config, _ = load_config(config_path)

    # Status checks must find the current IP after a DHCP address change.
    # Installation/pairing remain explicit, to avoid modifying a wrong robot.
    if command == "status":
        robot_id = str(config.get("robot_id") or "").strip()
        if robot_id:
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
        if command == "install":
            install(target, config.get("robot_id"))
        elif command == "set-id":
            set_robot_id(target, robot_id)
        else:
            status(target)
    except subprocess.CalledProcessError as exc:
        fail(
            "Service command failed with exit code {}.".format(
                exc.returncode
            ),
            exc.returncode,
        )


if __name__ == "__main__":
    main()
