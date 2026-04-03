from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


ENV_FILE_NAME = ".env"
ENV_WORKSPACE_FILE_NAME = ".piespector.env.json"
REQUESTS_FILE_NAME = ".piespector.requests.json"
HISTORY_FILE_NAME = ".piespector.history.jsonl"
LOG_FILE_NAME = ".piespector.log"
APP_DATA_DIRECTORY_NAME = "piespector"


@dataclass(frozen=True)
class WorkspaceStoragePaths:
    env_workspace_path: Path
    env_workspace_source_path: Path
    legacy_env_path: Path | None
    requests_path: Path
    requests_source_path: Path
    history_path: Path
    history_source_path: Path
    log_path: Path

    @property
    def needs_env_workspace_migration(self) -> bool:
        return self.env_workspace_source_path != self.env_workspace_path

    @property
    def needs_requests_migration(self) -> bool:
        return self.requests_source_path != self.requests_path

    @property
    def needs_history_migration(self) -> bool:
        return self.history_source_path != self.history_path


def app_data_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        return base_dir

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_DATA_DIRECTORY_NAME
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            return Path(appdata).expanduser() / APP_DATA_DIRECTORY_NAME
        return home / "AppData" / "Roaming" / APP_DATA_DIRECTORY_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / APP_DATA_DIRECTORY_NAME
    return home / ".local" / "share" / APP_DATA_DIRECTORY_NAME


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def env_file_path(base_dir: Path | None = None) -> Path:
    return app_data_dir(base_dir) / ENV_FILE_NAME


def env_workspace_path(base_dir: Path | None = None) -> Path:
    return app_data_dir(base_dir) / ENV_WORKSPACE_FILE_NAME


def requests_file_path(base_dir: Path | None = None) -> Path:
    return app_data_dir(base_dir) / REQUESTS_FILE_NAME


def history_file_path(base_dir: Path | None = None) -> Path:
    return app_data_dir(base_dir) / HISTORY_FILE_NAME


def log_file_path(base_dir: Path | None = None) -> Path:
    return app_data_dir(base_dir) / LOG_FILE_NAME


def discover_workspace_paths(
    *,
    base_dir: Path | None = None,
    cwd: Path | None = None,
) -> WorkspaceStoragePaths:
    env_path = env_workspace_path(base_dir)
    legacy_env_workspace = _legacy_env_workspace_path(cwd)
    if not env_path.exists() and legacy_env_workspace.exists():
        env_source_path = legacy_env_workspace
        legacy_env_path: Path | None = None
    else:
        env_source_path = env_path
        legacy_env_path = _legacy_env_file_path(cwd)

    requests_path_value = requests_file_path(base_dir)
    legacy_requests_path = _legacy_requests_file_path(cwd)
    requests_source_path = (
        legacy_requests_path
        if not requests_path_value.exists() and legacy_requests_path.exists()
        else requests_path_value
    )

    history_path_value = history_file_path(base_dir)
    legacy_history_path = _legacy_history_file_path(cwd)
    history_source_path = (
        legacy_history_path
        if not history_path_value.exists() and legacy_history_path.exists()
        else history_path_value
    )

    return WorkspaceStoragePaths(
        env_workspace_path=env_path,
        env_workspace_source_path=env_source_path,
        legacy_env_path=legacy_env_path,
        requests_path=requests_path_value,
        requests_source_path=requests_source_path,
        history_path=history_path_value,
        history_source_path=history_source_path,
        log_path=log_file_path(base_dir),
    )


def _legacy_root(cwd: Path | None = None) -> Path:
    return cwd or Path.cwd()


def _legacy_env_file_path(cwd: Path | None = None) -> Path:
    return _legacy_root(cwd) / ENV_FILE_NAME


def _legacy_env_workspace_path(cwd: Path | None = None) -> Path:
    return _legacy_root(cwd) / ENV_WORKSPACE_FILE_NAME


def _legacy_requests_file_path(cwd: Path | None = None) -> Path:
    return _legacy_root(cwd) / REQUESTS_FILE_NAME


def _legacy_history_file_path(cwd: Path | None = None) -> Path:
    return _legacy_root(cwd) / HISTORY_FILE_NAME
