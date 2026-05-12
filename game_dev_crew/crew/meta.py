"""Stable paths for crew components — serialized into SQLite via ``Agent`` / ``Team`` ``metadata``."""

from __future__ import annotations

# Repo-relative path (for humans, Studio, and DB search).
CREW_DIR = "game_dev_crew/crew"
CREW_PACKAGE = "game_dev_crew.crew"

AGENTS_PY_METADATA: dict[str, str] = {
    "crew_dir": CREW_DIR,
    "crew_package": CREW_PACKAGE,
    "defined_in": f"{CREW_DIR}/agents.py",
}

TEAMS_PY_METADATA: dict[str, str] = {
    "crew_dir": CREW_DIR,
    "crew_package": CREW_PACKAGE,
    "defined_in": f"{CREW_DIR}/teams.py",
}
