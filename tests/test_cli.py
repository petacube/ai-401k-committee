"""End-to-end: a fresh folder, offline data, one full monthly cycle through the command line."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent


def ai(home, *args):
    env = {**os.environ, "AI401K_HOME": str(home)}
    return subprocess.run([sys.executable, "-m", "ai401k", *args], cwd=KIT, env=env, capture_output=True, text=True)


def test_monthly_cycle(tmp_path):
    shutil.copytree(KIT / "config", tmp_path / "config")
    (tmp_path / "data").mkdir()
    shutil.copy(KIT / "data" / "prices_snapshot.csv", tmp_path / "data" / "prices_snapshot.csv")

    assert ai(tmp_path, "init", "--name", "T", "--initial", "100000", "--contribution", "20000", "--years", "25",
              "--goal", "balanced").returncode == 0
    assert ai(tmp_path, "data", "--offline").returncode == 0
    assert ai(tmp_path, "plan").returncode == 0
    r = ai(tmp_path, "propose", "--month", "2030-01")
    assert r.returncode == 0, r.stdout + r.stderr
    bad = ai(tmp_path, "override", "--month", "2030-01", "--set", "US_EQ=-0.2,CASH=0.2", "--reason", "no")
    assert bad.returncode == 2 and "REJECTED" in bad.stdout
    assert ai(tmp_path, "validate", "--month", "2030-01").returncode == 0
    assert ai(tmp_path, "approve", "--month", "2030-01", "--yes", "--by", "T").returncode == 0
    again = ai(tmp_path, "approve", "--month", "2030-01", "--yes")
    assert again.returncode != 0  # cannot approve twice
    st = json.loads(ai(tmp_path, "status", "--json").stdout)
    assert abs(st["value"] - 100_000) < 1
    assert st["last_proposal_status"] == "approved"
