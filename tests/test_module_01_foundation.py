"""Module 01 tests: repo scaffold, doctrine files, and state script exist
and behave as specified."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_doctrine_files_exist():
    assert (ROOT / "CLAUDE.md").exists()
    assert (ROOT / "PROGRESS.md").exists()


def test_repo_layout_exists():
    for rel in [
        "docs/TOOLING.md",
        "docs/architecture.md",
        "specs/core",
        "specs/domains",
        "decisions/0001-index.md",
        "modules/01-foundation",
        "tools/update_state.py",
        "tests",
        ".gitignore",
    ]:
        assert (ROOT / rel).exists(), f"missing: {rel}"


def test_progress_has_state_markers():
    content = (ROOT / "PROGRESS.md").read_text()
    assert "<!-- STATE:START -->" in content
    assert "<!-- STATE:END -->" in content


def test_module_01_has_status_marker():
    status_file = ROOT / "modules" / "01-foundation" / "STATUS"
    assert status_file.exists()
    assert status_file.read_text().strip() in {"not-started", "in-progress", "done"}


def test_update_state_script_runs_and_populates_state_block():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "update_state.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    content = (ROOT / "PROGRESS.md").read_text()
    start = content.index("<!-- STATE:START -->")
    end = content.index("<!-- STATE:END -->")
    state_block = content[start:end]

    assert "Recent commits" in state_block
    assert "Module status" in state_block
    assert "Latest test run" in state_block
