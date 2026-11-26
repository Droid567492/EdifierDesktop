"""GitHub Releases auto-updater with repository move/rename detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from typing import Any, Callable

import httpx

from .version import (
    APP_VERSION,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_REPO_URL,
    GITHUB_SEARCH_URL,
    PROJECT_NAME,
)

logger = logging.getLogger(__name__)


def parse_version(tag: str) -> tuple[int, ...]:
    """Parse a release tag like 'v1.2.3' or '1.2.3' into a numeric tuple."""
    clean = tag.strip().lstrip("vV")
    nums = [int(m) for m in re.findall(r"\d+", clean.split("-", 1)[0])]
    return tuple(nums) if nums else (0,)


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    a = list(parse_version(latest))
    b = list(parse_version(current))
    max_len = max(len(a), len(b))
    a.extend([0] * (max_len - len(a)))
    b.extend([0] * (max_len - len(b)))
    return tuple(a) > tuple(b)


def detect_install_mode() -> str:
    """Identify how the app is currently installed/running."""
    if not getattr(sys, "frozen", False):
        return "source"
    exe_path = Path(sys.executable).resolve()
    if sys.platform == "win32":
        if (exe_path.parent / "unins000.exe").exists() or "program files" in str(
            exe_path
        ).lower():
            return "windows_installer"
        return "windows_portable"
    if sys.platform.startswith("linux"):
        if str(exe_path).startswith("/opt/edifier-m60-control"):
            return "linux_deb"
        return "linux_portable"
    return "portable"


def select_release_asset(
    assets: list[dict[str, Any]],
    platform_name: str | None = None,
    install_mode: str | None = None,
) -> dict[str, Any] | None:
    """Select the best matching release asset for the current OS and install mode."""
    plat = platform_name or sys.platform
    mode = install_mode or detect_install_mode()

    def _find_matching(preds: list[Callable[[str], bool]]) -> dict[str, Any] | None:
        for pred in preds:
            for asset in assets:
                name = str(asset.get("name") or "").lower()
                if pred(name):
                    return asset
        return None

    if plat == "win32":
        if mode == "windows_installer":
            return _find_matching(
                [
                    lambda n: n.endswith("win64-setup.exe") or "setup" in n and n.endswith(".exe"),
                    lambda n: n.endswith("win64-portable.exe") or n == "edifierm60control.exe",
                    lambda n: n.endswith(".exe"),
                ]
            )
        return _find_matching(
            [
                lambda n: n.endswith("win64-portable.exe") or n == "edifierm60control.exe",
                lambda n: n.endswith(".exe") and "setup" not in n,
                lambda n: n.endswith(".exe"),
            ]
        )

    if plat.startswith("linux"):
        if mode == "linux_deb":
            return _find_matching(
                [
                    lambda n: n.endswith(".deb"),
                    lambda n: n.endswith("linux-x86_64.tar.gz") or n.endswith(".tar.gz"),
                ]
            )
        return _find_matching(
            [
                lambda n: n.endswith("linux-x86_64.tar.gz") or ("linux" in n and n.endswith(".tar.gz")),
                lambda n: n.endswith(".tar.gz"),
                lambda n: n.endswith(".deb"),
            ]
        )

    return None


@dataclass
class UpdateState:
    status: str = "idle"  # idle | checking | up_to_date | update_available | updating | updated | repo_moved | repo_not_found | error
    current_version: str = APP_VERSION
    latest_version: str | None = None
    release_url: str | None = None
    release_notes: str | None = None
    asset_name: str | None = None
    asset_url: str | None = None
    asset_size: int | None = None
    install_mode: str = detect_install_mode()
    message: str | None = None
    repo_url: str = GITHUB_REPO_URL
    repo_search_url: str = GITHUB_SEARCH_URL
    checked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _update_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.cwd())) / "EdifierM60Desktop"
    else:
        base = (
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "EdifierM60Desktop"
        )
    path = base / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


class UpdateManager:
    """Checks GitHub Releases and installs compatible updates for Windows & Linux."""

    def __init__(
        self,
        owner: str = GITHUB_OWNER,
        repo: str = GITHUB_REPO,
        current_version: str = APP_VERSION,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.current_version = current_version
        self.state = UpdateState(
            current_version=current_version,
            install_mode=detect_install_mode(),
            repo_url=f"https://github.com/{owner}/{repo}",
        )

    def _repo_moved_message(self, location: str | None = None) -> str:
        extra = f" (returned location: {location})" if location else ""
        return (
            f"The GitHub repository '{self.owner}/{self.repo}' appears to have been "
            f"renamed or moved{extra}, so auto-update could not verify the release. "
            f"Please look up '{PROJECT_NAME}' on GitHub to confirm the new repository "
            "name and avoid mistaking a renamed repo for a broken updater."
        )

    def _repo_not_found_message(self) -> str:
        return (
            f"The GitHub repository '{self.owner}/{self.repo}' could not be found "
            "(HTTP 404). It may have changed name, moved, or been deleted. "
            f"Please look up '{PROJECT_NAME}' on GitHub to verify whether the "
            "repository changed its name."
        )

    async def check_for_updates(
        self, client: httpx.AsyncClient | None = None
    ) -> dict[str, Any]:
        from datetime import datetime, timezone

        self.state.status = "checking"
        self.state.message = None
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"EdifierM60Desktop/{self.current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(
                headers=headers, follow_redirects=False, timeout=12.0
            )
        try:
            resp = await client.get(api_url, headers=headers)
            self.state.checked_at = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )

            if resp.status_code in (301, 302, 307, 308):
                loc = resp.headers.get("location")
                self.state.status = "repo_moved"
                self.state.message = self._repo_moved_message(loc)
                return self.state.to_dict()

            if resp.status_code in (404, 410):
                self.state.status = "repo_not_found"
                self.state.message = self._repo_not_found_message()
                return self.state.to_dict()

            if resp.status_code >= 400:
                self.state.status = "error"
                self.state.message = (
                    f"Update check failed (GitHub HTTP {resp.status_code})."
                )
                return self.state.to_dict()

            data = resp.json()
            html_url = str(data.get("html_url") or "")
            expected_prefix = f"https://github.com/{self.owner}/{self.repo}/".lower()
            if html_url and not html_url.lower().startswith(expected_prefix):
                self.state.status = "repo_moved"
                self.state.release_url = html_url
                self.state.message = self._repo_moved_message(html_url)
                return self.state.to_dict()

            tag = str(data.get("tag_name") or "").strip()
            self.state.latest_version = tag.lstrip("vV") or None
            self.state.release_url = html_url or self.state.repo_url
            self.state.release_notes = str(data.get("body") or "")[:1500] or None

            assets = list(data.get("assets") or [])
            chosen = select_release_asset(
                assets, platform_name=sys.platform, install_mode=self.state.install_mode
            )
            if chosen:
                self.state.asset_name = chosen.get("name")
                self.state.asset_url = chosen.get("browser_download_url")
                self.state.asset_size = chosen.get("size")
            else:
                self.state.asset_name = None
                self.state.asset_url = None
                self.state.asset_size = None

            if tag and is_newer_version(tag, self.current_version):
                self.state.status = "update_available"
                self.state.message = (
                    f"Version {self.state.latest_version} is available "
                    f"(you have {self.current_version})."
                )
            else:
                self.state.status = "up_to_date"
                self.state.message = (
                    f"You are running the latest version ({self.current_version})."
                )
            return self.state.to_dict()
        except Exception as exc:
            self.state.status = "error"
            self.state.message = f"Could not check for updates: {exc}"
            return self.state.to_dict()
        finally:
            if own_client and client is not None:
                await client.aclose()

    async def apply_update(
        self, shutdown_cb: Callable[[], None] | None = None
    ) -> dict[str, Any]:
        """Download and install the latest compatible release asset."""
        if self.state.status != "update_available" or not self.state.asset_url:
            await self.check_for_updates()
        if self.state.status != "update_available":
            return self.state.to_dict()

        mode = detect_install_mode()
        self.state.install_mode = mode
        if mode == "source":
            self.state.message = (
                "Running from source — pull the latest commit with 'git pull' or "
                "download the release binary from GitHub."
            )
            return self.state.to_dict()

        if not self.state.asset_url or not self.state.asset_name:
            self.state.status = "error"
            self.state.message = (
                "No compatible binary asset was found on the latest GitHub release."
            )
            return self.state.to_dict()

        self.state.status = "updating"
        self.state.message = f"Downloading {self.state.asset_name}..."
        cache_dir = _update_cache_dir()
        dest_file = cache_dir / Path(self.state.asset_name).name

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=180.0) as client:
                async with client.stream("GET", self.state.asset_url) as resp:
                    resp.raise_for_status()
                    with dest_file.open("wb") as f:
                        async for chunk in resp.aiter_bytes(65536):
                            f.write(chunk)
        except Exception as exc:
            self.state.status = "error"
            self.state.message = f"Update download failed: {exc}"
            return self.state.to_dict()

        try:
            if mode == "windows_installer":
                subprocess.Popen(
                    [
                        str(dest_file),
                        "/SILENT",
                        "/CLOSEAPPLICATIONS",
                        "/RESTARTAPPLICATIONS",
                    ],
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )
                self.state.status = "updated"
                self.state.message = "Installer launched. Restarting app to finish update..."
                if shutdown_cb:
                    shutdown_cb()
                return self.state.to_dict()

            if mode == "windows_portable":
                current_exe = Path(sys.executable).resolve()
                bat_path = cache_dir / "apply_update.bat"
                bat_content = (
                    "@echo off\r\n"
                    "timeout /t 2 /nobreak >nul\r\n"
                    ":retry\r\n"
                    f'move /y "{dest_file}" "{current_exe}" >nul 2>&1\r\n'
                    "if errorlevel 1 (\r\n"
                    "  timeout /t 1 /nobreak >nul\r\n"
                    "  goto retry\r\n"
                    ")\r\n"
                    f'start "" "{current_exe}"\r\n'
                    'del "%~f0"\r\n'
                )
                bat_path.write_text(bat_content, encoding="utf-8")
                subprocess.Popen(
                    ["cmd", "/c", str(bat_path)],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "DETACHED_PROCESS", 0),
                )
                self.state.status = "updated"
                self.state.message = "Replacing portable executable and restarting..."
                if shutdown_cb:
                    shutdown_cb()
                return self.state.to_dict()

            if mode == "linux_deb":
                proc = subprocess.Popen(
                    ["pkexec", "apt-get", "install", "-y", str(dest_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.state.status = "updated"
                self.state.message = (
                    f"Downloaded {dest_file.name} and launched package installer (pid {proc.pid})."
                )
                return self.state.to_dict()

            if mode == "linux_portable":
                extract_dir = cache_dir / "extracted"
                if extract_dir.exists():
                    import shutil

                    shutil.rmtree(extract_dir, ignore_errors=True)
                extract_dir.mkdir(parents=True, exist_ok=True)
                with tarfile.open(dest_file, "r:gz") as tf:
                    tf.extractall(extract_dir)
                current_exe = Path(sys.executable).resolve()
                app_dir = current_exe.parent
                sh_path = cache_dir / "apply_update.sh"
                # Locate extracted binary directory
                src_dir = extract_dir
                for candidate in extract_dir.rglob(current_exe.name):
                    if candidate.is_file():
                        src_dir = candidate.parent
                        break
                sh_script = (
                    "#!/bin/sh\n"
                    "sleep 2\n"
                    f'cp -rf "{src_dir}/." "{app_dir}/"\n'
                    f'chmod +x "{current_exe}"\n'
                    f'nohup "{current_exe}" >/dev/null 2>&1 &\n'
                    'rm -f "$0"\n'
                )
                sh_path.write_text(sh_script, encoding="utf-8")
                os.chmod(sh_path, 0o755)
                subprocess.Popen(["/bin/sh", str(sh_path)], start_new_session=True)
                self.state.status = "updated"
                self.state.message = "Replacing Linux portable bundle and restarting..."
                if shutdown_cb:
                    shutdown_cb()
                return self.state.to_dict()
        except Exception as exc:
            self.state.status = "error"
            self.state.message = f"Failed to launch updater: {exc}"
        return self.state.to_dict()
