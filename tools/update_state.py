#!/usr/bin/env python3
"""Regenerate the STATE block in PROGRESS.md from git log, module STATUS
files, and the latest pytest JSON report. Run as the last step of every
module's workflow, right before the commit.

    python tools/update_state.py
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = ROOT / "PROGRESS.md"
MODULES_DIR = ROOT / "modules"
REPORT_PATH = ROOT / ".report.json"

STATE_START = "<!-- STATE:START -->"
STATE_END = "<!-- STATE:END -->"

N_COMMITS = 10


def get_recent_commits(n=N_COMMITS):
    try:
        out = subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return []
    return out.splitlines() if out else []


def get_module_statuses():
    statuses = {}
    if not MODULES_DIR.exists():
        return statuses
    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir():
            continue
        status_file = module_dir / "STATUS"
        status = (
            status_file.read_text(encoding="utf-8").strip()
            if status_file.exists()
            else "unknown"
        )
        statuses[module_dir.name] = status
    return statuses


def get_test_summary():
    if not REPORT_PATH.exists():
        return "no test report found (.report.json missing — run pytest --json-report)"
    try:
        data = json.loads(REPORT_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return "test report unreadable"
    summary = data.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    return f"{passed}/{total} passed, {failed} failed"


def build_state_block():
    lines = [STATE_START, ""]

    lines.append("### Recent commits")
    commits = get_recent_commits()
    if commits:
        for c in commits:
            lines.append(f"- `{c}`")
    else:
        lines.append("- (no commits yet)")
    lines.append("")

    lines.append("### Module status")
    statuses = get_module_statuses()
    if statuses:
        for name, status in statuses.items():
            lines.append(f"- **{name}**: {status}")
    else:
        lines.append("- (no modules under `modules/` yet)")
    lines.append("")

    lines.append("### Latest test run")
    lines.append(f"- {get_test_summary()}")
    lines.append("")

    lines.append(STATE_END)
    return "\n".join(lines)


def main():
    if not PROGRESS_PATH.exists():
        raise SystemExit(f"{PROGRESS_PATH} does not exist — cannot update state block")

    content = PROGRESS_PATH.read_text(encoding="utf-8")
    if STATE_START not in content or STATE_END not in content:
        raise SystemExit(
            f"{PROGRESS_PATH} is missing {STATE_START}/{STATE_END} markers"
        )

    before, rest = content.split(STATE_START, 1)
    _, after = rest.split(STATE_END, 1)

    new_content = before + build_state_block() + after
    PROGRESS_PATH.write_text(new_content, encoding="utf-8")
    print(f"Updated state block in {PROGRESS_PATH}")


if __name__ == "__main__":
    main()
