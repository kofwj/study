"""应用版本：给孩子端/家长端和 /api/health 看这次部署是不是新的。"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = ROOT / "VERSION"
_REVISION_FILE = ROOT / "REVISION"


def app_version() -> str:
    try:
        v = _VERSION_FILE.read_text(encoding="utf-8").strip()
        if v:
            return v
    except OSError:
        pass
    return "dev"


def app_revision() -> str:
    env = (os.environ.get("APP_REVISION") or os.environ.get("GIT_SHA") or "").strip()
    if env:
        return env[:12]
    try:
        r = _REVISION_FILE.read_text(encoding="utf-8").strip()
        if r:
            return r[:12]
    except OSError:
        pass
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()[:12]
    except (OSError, subprocess.CalledProcessError):
        return "dev"


def app_label() -> str:
    ver, rev = app_version(), app_revision()
    if rev and rev != "dev":
        return f"{ver} · {rev}"
    return ver
