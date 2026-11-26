"""Desktop launcher for Edifier M60 Control (FastAPI + Edge App Window + System Tray)."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

# Support running either `python -m backend.app` or `python backend/app.py`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.autostart import is_autostart_enabled, set_autostart
from backend.icon import create_app_icon_image, ensure_ico_file
from backend.server import create_app


def _find_free_port(host: str, preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, preferred))
            return preferred
        except OSError:
            s.bind((host, 0))
            return int(s.getsockname()[1])


def _find_app_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _apply_window_icon_later(ico_path: Path, title_substring: str = "Edifier M60") -> None:
    """Apply the shared .ico to the launched browser app window via Win32 WM_SETICON."""
    if sys.platform != "win32":
        return

    def _worker() -> None:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1

            hicon_small = user32.LoadImageW(
                None, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
            )
            hicon_big = user32.LoadImageW(
                None, str(ico_path), IMAGE_ICON, 48, 48, LR_LOADFROMFILE
            )
            if not hicon_small and not hicon_big:
                return

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            for _ in range(40):
                matched = False

                def _enum_cb(hwnd: int, _lparam: int) -> bool:
                    nonlocal matched
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length <= 0:
                        return True
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if title_substring in buf.value:
                        if hicon_small:
                            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                        if hicon_big:
                            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                        matched = True
                    return True

                user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
                if matched:
                    break
                time.sleep(0.2)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="M60WindowIcon").start()


def open_app_window(url: str) -> None:
    app_data_dir = (
        Path(os.environ.get("LOCALAPPDATA", Path.cwd())) / "EdifierM60Desktop"
    )
    ico_path: Path | None = None
    try:
        ico_path = ensure_ico_file(app_data_dir / "app.ico")
    except OSError:
        try:
            ico_path = ensure_ico_file(Path.cwd() / "data" / "app.ico")
        except OSError:
            ico_path = None

    browser = _find_app_browser()
    if browser:
        profile_dir = app_data_dir / "browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(
                [
                    browser,
                    f"--app={url}",
                    f"--user-data-dir={profile_dir}",
                    "--window-size=1160,820",
                    "--no-first-run",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ico_path is not None:
                _apply_window_icon_later(ico_path)
            return
        except Exception:
            pass
    webbrowser.open(url)
    if ico_path is not None:
        _apply_window_icon_later(ico_path)


def _create_tray_image():
    return create_app_icon_image(64)


def _ensure_stdio_streams() -> None:
    """Redirect None stdio streams when running under PyInstaller --windowed."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _ensure_stdio_streams()
    parser = argparse.ArgumentParser(description="Edifier M60 Desktop Control")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18600)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-tray", action="store_true")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start quietly in the system tray without opening the window.",
    )
    args = parser.parse_args(argv)
    if args.background:
        args.no_browser = True

    port = _find_free_port(args.host, args.port)
    url = f"http://{args.host}:{port}"

    app = create_app()
    config = uvicorn.Config(
        app,
        host=args.host,
        port=port,
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    server = uvicorn.Server(config)

    if args.no_tray:
        if not args.no_browser:
            def _open_later() -> None:
                time.sleep(0.8)
                open_app_window(url)

            threading.Thread(target=_open_later, daemon=True).start()
        server.run()
        return 0

    server_loop_holder: list[asyncio.AbstractEventLoop] = []

    def _run_server() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        server_loop_holder.append(loop)
        loop.run_until_complete(server.serve())

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    # Wait briefly until uvicorn binds
    for _ in range(40):
        if server.started:
            break
        time.sleep(0.1)

    if not args.no_browser:
        open_app_window(url)

    def _dispatch_ble(coro_fn) -> None:
        if not server_loop_holder:
            return
        loop = server_loop_holder[0]
        ctx = getattr(app.state, "ctx", None)
        if ctx is None:
            return
        asyncio.run_coroutine_threadsafe(coro_fn(ctx), loop)

    try:
        import pystray

        def _quit(icon, _item=None) -> None:
            server.should_exit = True
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("Open Edifier M60 Studio", lambda _i, _it: open_app_window(url), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Volume +1",
                lambda _i, _it: _dispatch_ble(lambda ctx: ctx.ble.step_volume(1)),
            ),
            pystray.MenuItem(
                "Volume -1",
                lambda _i, _it: _dispatch_ble(lambda ctx: ctx.ble.step_volume(-1)),
            ),
            pystray.MenuItem(
                "Input Source",
                pystray.Menu(
                    pystray.MenuItem(
                        "Bluetooth",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_input("bluetooth")
                        ),
                    ),
                    pystray.MenuItem(
                        "USB-C",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_input("usb")
                        ),
                    ),
                    pystray.MenuItem(
                        "AUX",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_input("aux")
                        ),
                    ),
                ),
            ),
            pystray.MenuItem(
                "EQ Preset",
                pystray.Menu(
                    pystray.MenuItem(
                        "Music",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_eq_preset("music")
                        ),
                    ),
                    pystray.MenuItem(
                        "Monitor",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_eq_preset("monitor")
                        ),
                    ),
                    pystray.MenuItem(
                        "Game",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_eq_preset("game")
                        ),
                    ),
                    pystray.MenuItem(
                        "Movie",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_eq_preset("movie")
                        ),
                    ),
                    pystray.MenuItem(
                        "Customized",
                        lambda _i, _it: _dispatch_ble(
                            lambda ctx: ctx.ble.set_eq_preset("customized")
                        ),
                    ),
                ),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start with Windows",
                lambda _i, _it: set_autostart(not is_autostart_enabled()),
                checked=lambda _it: is_autostart_enabled(),
            ),
            pystray.MenuItem("Quit", _quit),
        )

        icon = pystray.Icon(
            "EdifierM60Control",
            _create_tray_image(),
            "Edifier M60 Studio Control",
            menu,
        )
        icon.run()
    except KeyboardInterrupt:
        server.should_exit = True
    except Exception:
        # Fallback: keep waiting if tray backend is unavailable
        server_thread.join()

    server.should_exit = True
    server_thread.join(timeout=3.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
