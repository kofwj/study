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
    ver = app_version()
    if ver.lower().startswith("v"):
        return "V " + ver[1:].lstrip()
    return f"V {ver}"


def parse_version(text: str):
    raw = (text or "").strip()
    if raw.lower().startswith("v"):
        raw = raw[1:].lstrip()
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError("版本号必须是 a.b.c，例如 0.1.0")
    nums = [int(p) for p in parts]
    if any(n < 0 or n > 99 for n in nums):
        raise ValueError("版本号每一位最多两位数（0–99）")
    return nums


def next_version(text: str) -> str:
    major, minor, patch = parse_version(text)
    patch += 1
    if patch > 99:
        patch = 0
        minor += 1
    if minor > 99:
        minor = 0
        major += 1
    if major > 99:
        raise ValueError("版本号已到 99.99.99，不能再自动递增")
    return f"{major}.{minor}.{patch}"


def bump_version_file(path=None) -> str:
    p = Path(path) if path else _VERSION_FILE
    current = p.read_text(encoding="utf-8")
    nxt = next_version(current)
    p.write_text(nxt + "\n", encoding="utf-8")
    return nxt
