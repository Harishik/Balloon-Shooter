"""Launches the real game with the autoplay bot. Needs a display (use xvfb-run),
so it only runs when BALLOON_SHOOTER_SMOKE=1."""

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(os.environ.get("BALLOON_SHOOTER_SMOKE") != "1", reason="set BALLOON_SHOOTER_SMOKE=1")
@pytest.mark.parametrize("mode", ["time", "survival", "zen"])
def test_autoplay_session(tmp_path, mode):
    shot = tmp_path / "shot.png"
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "--mute", "--no-msaa", "--size", "640x360",
           "--data-dir", str(tmp_path), "--seed", "5", "--mode", mode, "--autoplay",
           "--screenshot", f"8:{shot}", "--quit-after", "9"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "Traceback" not in out.stderr, out.stderr[-2000:]
    assert shot.exists()
    assert "[quit]" in out.stdout
    score = int(out.stdout.split("score=")[1].split()[0])
    assert score > 0
