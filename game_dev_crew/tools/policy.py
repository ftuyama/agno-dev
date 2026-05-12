"""Crew toolkits: one shared set for all agents (role-specific lists can split out later)."""

from __future__ import annotations

from pathlib import Path

from game_dev_crew.config import repo_shell_tools_enabled, validate_scenes_tool_enabled
from game_dev_crew.tools.allowlisted_shell import make_bash_tool, make_execute_command_tool
from game_dev_crew.tools.repo_glob import make_glob_repo_tool
from game_dev_crew.tools.repo_read import make_read_repo_file_tool
from game_dev_crew.tools.repo_write import make_apply_patch_tool, make_write_repo_file_tool
from game_dev_crew.tools.validate_scenes import make_run_validate_scenes_tool


def repo_probe_tools(repo_root: Path) -> list:
    """Read files, glob paths, and optionally allowlisted shell at repo root."""
    tools: list = [make_read_repo_file_tool(repo_root), make_glob_repo_tool(repo_root)]
    if repo_shell_tools_enabled():
        tools.append(make_execute_command_tool(repo_root))
        tools.append(make_bash_tool(repo_root))
    return tools


def crew_tools(repo_root: Path) -> list:
    """Full crew toolset: repo probe + write + optional validate:scenes (every agent gets the same list).

    Write tools (``write_repo_file`` / ``apply_patch``) are always wired. They
    are scoped to anywhere under ``repo_root`` except ``.git/``. Safety relies
    on the AuditFlow clean-tree guard and the throwaway audit branch, not on
    an opt-in flag.
    """
    tools = repo_probe_tools(repo_root)
    if validate_scenes_tool_enabled():
        tools.append(make_run_validate_scenes_tool(repo_root))
    tools.append(make_write_repo_file_tool(repo_root))
    tools.append(make_apply_patch_tool(repo_root))
    return tools


# Aliases for future per-role overrides; today all map to ``crew_tools``.
auditor_tools = crew_tools
senior_developer_tools = crew_tools
reviewer_tools = crew_tools
