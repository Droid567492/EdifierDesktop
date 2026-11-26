"""Tests for GitHub release auto-updater, version comparison, and repo-move detection."""

from __future__ import annotations

import httpx
import pytest

from backend.updater import (
    UpdateManager,
    is_newer_version,
    parse_version,
    select_release_asset,
)


def test_version_parsing_and_comparison() -> None:
    assert parse_version("v1.2.0") == (1, 2, 0)
    assert parse_version("1.10.2") == (1, 10, 2)
    assert is_newer_version("v1.2.0", "1.1.0") is True
    assert is_newer_version("v1.1.0", "1.1.0") is False
    assert is_newer_version("v1.0.9", "1.1.0") is False


def test_asset_selection_windows_and_linux() -> None:
    assets = [
        {"name": "EdifierM60Control-v1.2.0-win64-setup.exe", "browser_download_url": "u1"},
        {"name": "EdifierM60Control-v1.2.0-win64-portable.exe", "browser_download_url": "u2"},
        {"name": "edifier-m60-control_1.2.0_amd64.deb", "browser_download_url": "u3"},
        {"name": "edifier-m60-control-v1.2.0-linux-x86_64.tar.gz", "browser_download_url": "u4"},
    ]

    assert select_release_asset(assets, "win32", "windows_installer")["name"].endswith("setup.exe")
    assert select_release_asset(assets, "win32", "windows_portable")["name"].endswith("portable.exe")
    assert select_release_asset(assets, "linux", "linux_deb")["name"].endswith(".deb")
    assert select_release_asset(assets, "linux", "linux_portable")["name"].endswith(".tar.gz")


@pytest.mark.asyncio
async def test_check_updates_available_and_up_to_date() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "tag_name": "v1.3.0",
                "html_url": "https://github.com/Droid567492/EdifierDesktop/releases/tag/v1.3.0",
                "body": "Release notes",
                "assets": [
                    {
                        "name": "EdifierM60Control-v1.3.0-win64-portable.exe",
                        "browser_download_url": "https://example.com/win.exe",
                        "size": 12345,
                    },
                    {
                        "name": "edifier-m60-control-v1.3.0-linux-x86_64.tar.gz",
                        "browser_download_url": "https://example.com/linux.tar.gz",
                        "size": 23456,
                    },
                ],
            },
        )

    mgr = UpdateManager(current_version="1.1.0")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        st = await mgr.check_for_updates(client=client)
    assert st["status"] == "update_available"
    assert st["latest_version"] == "1.3.0"
    assert st["asset_url"] is not None

    mgr_same = UpdateManager(current_version="1.3.0")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        st_same = await mgr_same.check_for_updates(client=client)
    assert st_same["status"] == "up_to_date"


@pytest.mark.asyncio
async def test_check_updates_detects_repo_redirect_and_404() -> None:
    # 301 redirect -> repo_moved
    def redirect_handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            301,
            headers={"Location": "https://api.github.com/repositories/999999/releases/latest"},
        )

    mgr = UpdateManager(current_version="1.1.0")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(redirect_handler), follow_redirects=False
    ) as client:
        st = await mgr.check_for_updates(client=client)
    assert st["status"] == "repo_moved"
    assert "Edifier M60 Desktop Control" in st["message"]
    assert st["repo_search_url"].startswith("https://github.com/search")

    # 200 whose html_url points to a renamed repo -> repo_moved
    def renamed_handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "tag_name": "v1.2.0",
                "html_url": "https://github.com/Droid567492/RenamedRepo/releases/tag/v1.2.0",
                "assets": [],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(renamed_handler)) as client:
        st2 = await mgr.check_for_updates(client=client)
    assert st2["status"] == "repo_moved"

    # 404 -> repo_not_found
    def not_found_handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(not_found_handler)) as client:
        st3 = await mgr.check_for_updates(client=client)
    assert st3["status"] == "repo_not_found"
    assert "Edifier M60 Desktop Control" in st3["message"]
