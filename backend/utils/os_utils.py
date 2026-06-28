import os
import re
import shutil
import subprocess
import time
import webbrowser

APP_ALIASES = {
    "calc": ["calc"],
    "calculator": ["calc", "calculator"],
    "chrome": ["chrome", "google chrome"],
    "discord": ["discord"],
    "explorer": ["explorer"],
    "file explorer": ["explorer"],
    "files": ["explorer"],
    "google chrome": ["chrome", "google chrome"],
    "notepad": ["notepad"],
    "spotify": ["spotify"],
    "task manager": ["taskmgr"],
    "telegram": ["telegram"],
    "vs code": ["code"],
    "vscode": ["code"],
    "visual studio code": ["code"],
    "whatsapp": ["whatsapp"],
    "youtube": ["youtube"],
}

WEB_FALLBACKS = {
    "chatgpt": ("ChatGPT", "https://chat.openai.com"),
    "discord": ("Discord", "https://discord.com/app"),
    "github": ("GitHub", "https://github.com"),
    "gmail": ("Gmail", "https://mail.google.com"),
    "instagram": ("Instagram", "https://instagram.com"),
    "linkedin": ("LinkedIn", "https://linkedin.com"),
    "spotify": ("Spotify", "https://open.spotify.com"),
    "whatsapp": ("WhatsApp", "https://web.whatsapp.com"),
    "youtube": ("YouTube", "https://youtube.com"),
}


def _result(message: str, options: list[str] | None = None):
    payload = {"result": message}
    if options is not None:
        payload["options"] = options
    return payload


def _bring_window_to_front(keywords: list[str]):
    try:
        import pygetwindow as gw
        time.sleep(1.5)
        all_windows = gw.getAllTitles()
        for keyword in keywords:
            for title in all_windows:
                if keyword.lower() in title.lower() and title.strip():
                    try:
                        windows = gw.getWindowsWithTitle(title)
                        if not windows:
                            continue
                        window = windows[0]
                        try:
                            if window.isMinimized:
                                window.restore()
                                time.sleep(0.3)
                            window.activate()
                            time.sleep(0.3)
                            return "focused"
                        except Exception:
                            continue
                    except Exception:
                        continue
        return "opened"
    except Exception:
        return "opened"


def _clean_app_name(app_name: str) -> str:
    app_name = re.sub(r"\b(please|app|application)\b", "", app_name, flags=re.IGNORECASE)
    return " ".join(app_name.split()).strip()


def _display_app_name(app_name: str) -> str:
    fallback = WEB_FALLBACKS.get(app_name)
    if fallback:
        return fallback[0]
    return " ".join(part.capitalize() for part in app_name.split())


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _launch_with_start_apps(app_name: str) -> bool:
    try:
        pattern = f"*{app_name}*"
        quoted = _powershell_quote(pattern)
        command = (
            "Get-StartApps | "
            f"Where-Object {{ $_.Name -like {quoted} -or $_.AppID -like {quoted} }} | "
            "Select-Object -First 1 -ExpandProperty AppID"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=5,
        )
        app_id = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
        if not app_id:
            return False
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return True
    except Exception:
        return False


def _launch_candidate(candidate: str) -> bool:
    try:
        resolved = shutil.which(candidate)
        if resolved:
            subprocess.Popen([resolved])
            return True

        if os.path.exists(candidate):
            os.startfile(candidate)
            return True

        if _launch_with_start_apps(candidate):
            return True

        return False
    except Exception:
        return False


def _open_web_fallback(app_name: str):
    fallback = WEB_FALLBACKS.get(app_name)
    if not fallback:
        return None

    display_name, url = fallback
    webbrowser.open(url)
    _bring_window_to_front([display_name, "chrome", "edge", "firefox", "browser"])
    return _result(
        f"{display_name} desktop app not found. "
        f"Opened {display_name} Web instead."
    )


def _open_dynamic_app(app_name: str):
    app_name = _clean_app_name(app_name).lower()
    if not app_name:
        return _result("Please specify which app to open.")

    if re.fullmatch(r"\d+", app_name):
        return None

    if app_name == "yt":
        app_name = "youtube"

    candidates = []
    candidates.extend(APP_ALIASES.get(app_name, []))
    candidates.append(app_name)

    seen = set()
    candidates = [item for item in candidates if not (item in seen or seen.add(item))]

    for candidate in candidates:
        if _launch_candidate(candidate):
            focus_words = [app_name, *[c.replace(":", "") for c in candidates]]
            _bring_window_to_front(focus_words)
            return _result(f"{_display_app_name(app_name)} desktop app opened.")

    fallback_result = _open_web_fallback(app_name)
    if fallback_result is not None:
        return fallback_result

    return _result(f"Could not open {_display_app_name(app_name)}.")
