#!/usr/bin/env python3
"""Install relay Python dependencies into an isolated venv on first launch.

Only Python 3.9-3.13 and Python's bundled venv are prerequisites.
After setup, starting the relay does not require the Internet.
"""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PYTHON = (
    VENV / "Scripts" / "python.exe"
    if os.name == "nt"
    else VENV / "bin" / "python"
)
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".relay-requirements.sha256"


def run(command, **kwargs):
    """Run a command and surface failures instead of silently ignoring them."""
    return subprocess.run([str(part) for part in command], check=True, **kwargs)


def check_python_version():
    if not ((3, 9) <= sys.version_info[:2] <= (3, 13)):
        raise RuntimeError(
            "Python 3.9-3.13 is required for the tested pygame 2.6.1 setup. "
            "Current: {}.{}".format(*sys.version_info[:2])
        )


def dependency_stamp():
    if not REQUIREMENTS.is_file():
        raise RuntimeError("Missing requirements.txt in {}".format(ROOT))
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def python_available():
    if not VENV_PYTHON.is_file():
        return False
    try:
        run(
            [VENV_PYTHON, "-c", "import sys; print(sys.version.split()[0])"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def dependencies_ready(checksum):
    if not python_available():
        return False
    try:
        if STAMP.read_text(encoding="ascii").strip() != checksum:
            return False
    except OSError:
        return False

    try:
        run(
            [VENV_PYTHON, "-c", "import pygame"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1"),
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def ensure_setup():
    check_python_version()
    checksum = dependency_stamp()

    if not VENV.exists():
        print("[Relay] Creating isolated Python environment (.venv) ...", flush=True)
        run([sys.executable, "-m", "venv", VENV])
    elif not python_available():
        raise RuntimeError(
            "Existing .venv is broken or belongs to another system. "
            "Rename the .venv directory and try again."
        )

    if dependencies_ready(checksum):
        print("[Relay] Dependencies already installed. No Internet needed.", flush=True)
        return

    print("[Relay] Installing packages from requirements.txt ...", flush=True)
    print("[Relay] First-time setup requires an Internet connection.", flush=True)
    run([
        VENV_PYTHON, "-m", "pip", "install",
        "--disable-pip-version-check", "-r", REQUIREMENTS,
    ])

    run(
        [VENV_PYTHON, "-c", "import pygame"],
        stdout=subprocess.DEVNULL,
        env=dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1"),
    )
    STAMP.write_text(checksum + "\n", encoding="ascii")
    print("[Relay] Setup complete.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Launch EV3 Xbox Relay.")
    parser.add_argument(
        "--setup-only", action="store_true",
        help="Prepare and verify pygame without opening the GUI.",
    )
    args = parser.parse_args()

    try:
        ensure_setup()
        if args.setup_only:
            print("[Relay] SETUP=OK", flush=True)
            return 0

        gui = ROOT / "desktop" / "relay_gui.py"
        if not gui.is_file():
            raise RuntimeError("Missing desktop/relay_gui.py")

        print("[Relay] Starting Xbox Relay ...", flush=True)
        env = dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1")
        return subprocess.call([str(VENV_PYTHON), str(gui)], cwd=str(ROOT), env=env)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print("[Relay] ERROR: {}".format(exc), file=sys.stderr)
        print(
            "[Relay] If this is the first setup, connect to the Internet, "
            "then run the launcher again. Python 3.9-3.13 must be installed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
