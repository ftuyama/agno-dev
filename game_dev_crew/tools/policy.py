"""Which tools each agent gets (Auditor/Senior: read + glob + optional shell; Reviewer: optional validate)."""

from __future__ import annotations

from pathlib import Path

from game_dev_crew.config import repo_shell_tools_enabled, validate_scenes_tool_enabled
from game_dev_crew.tools.allowlisted_shell import make_bash_tool, make_execute_command_tool
from game_dev_crew.tools.repo_glob import make_glob_repo_tool
from game_dev_crew.tools.repo_read import make_read_repo_file_tool
from game_dev_crew.tools.validate_scenes import make_run_validate_scenes_tool


def repo_probe_tools(repo_root: Path) -> list:
    """Shared kit: read files, glob paths, and optionally allowlisted npm at repo root."""
    tools: list = [make_read_repo_file_tool(repo_root), make_glob_repo_tool(repo_root)]
    if repo_shell_tools_enabled():
        tools.append(make_execute_command_tool(repo_root))
        tools.append(make_bash_tool(repo_root))
    return tools


def auditor_tools(repo_root: Path) -> list:
    return repo_probe_tools(repo_root)


def senior_developer_tools(repo_root: Path) -> list:
    return repo_probe_tools(repo_root)


def reviewer_tools(repo_root: Path) -> list:
    if validate_scenes_tool_enabled():
        return [make_run_validate_scenes_tool(repo_root)]
    return []
