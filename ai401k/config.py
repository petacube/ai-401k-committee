"""Paths and YAML loading. Everything lives under the kit folder so it can be zipped and moved."""
from __future__ import annotations

import copy
import os
from datetime import date
from pathlib import Path

import yaml

from . import SLEEVES

ROOT = Path(os.environ.get("AI401K_HOME", Path(__file__).resolve().parent.parent))
CONFIG = ROOT / "config"
DATA = ROOT / "data"
PORTFOLIO = ROOT / "portfolio"
PROPOSALS = PORTFOLIO / "proposals"
JOURNAL = ROOT / "journal"
REPORTS = ROOT / "reports"

GOALS = ["target", "max_wealth", "conservative", "balanced", "aggressive", "momentum"]


_CACHE: dict = {}


def load_yaml(path: Path) -> dict:
    """Parsed YAML, cached until the file changes (back-tests read the configs thousands of times)."""
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _CACHE:
        with open(path) as fh:
            _CACHE[key] = yaml.safe_load(fh) or {}
    return copy.deepcopy(_CACHE[key])


def save_yaml(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.safe_dump(obj, fh, sort_keys=False)


def universe() -> dict:
    return load_yaml(CONFIG / "universe.yaml")["sleeves"]


def cma() -> dict:
    return load_yaml(CONFIG / "cma.yaml")


def profiles() -> dict:
    return load_yaml(CONFIG / "profiles.yaml")


def guardrails(goal: str | None = None) -> dict:
    """Base guardrails, with the goal's `guardrail_overrides` merged on top."""
    g = load_yaml(CONFIG / "guardrails.yaml")
    if goal:
        over = profiles()["profiles"].get(goal, {}).get("guardrail_overrides", {})
        g = _merge(g, over)
    return g


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def profile_path() -> Path:
    return PORTFOLIO / "profile.yaml"


def investor() -> dict:
    p = profile_path()
    if not p.exists():
        raise SystemExit("No portfolio/profile.yaml yet. Run `ai401k init` (or /onboard in Claude Code) first.")
    prof = load_yaml(p)
    prof["start_date"] = _as_date(prof["start_date"])
    return prof


def _as_date(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def years_left(prof: dict, today: date) -> float:
    elapsed = (today - prof["start_date"]).days / 365.25
    return max(0.0, prof["horizon_years"] - elapsed)


def years_elapsed(prof: dict, today: date) -> float:
    return max(0.0, (today - prof["start_date"]).days / 365.25)


def monthly_contribution(prof: dict, today: date) -> float:
    """Annual contribution / 12, grown each full year by `contribution_growth` (pay raises)."""
    yrs = int(years_elapsed(prof, today))
    return prof["annual_contribution"] * (1 + prof.get("contribution_growth", 0.0)) ** yrs / 12.0


def check_sleeves(d: dict) -> None:
    missing = [s for s in SLEEVES if s not in d]
    if missing:
        raise ValueError(f"missing sleeves {missing}")


def nominal_target(prof: dict) -> float | None:
    """Dollar goal at the horizon date. If `target_real` (default), the goal is in start-date dollars and
    is grown by the CMA inflation rate, because $1M in 25 years buys only about half of what it buys today."""
    t = prof.get("target_amount")
    if not t:
        return None
    if prof.get("target_real", True):
        return t * (1 + cma()["inflation"]) ** prof["horizon_years"]
    return t
