from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from glob import glob
from typing import Iterable, Sequence
from urllib.parse import quote_plus


# ═══════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LaunchConfig:
    """Static configuration for a priority/well-known application."""

    key: str
    display_name: str
    aliases: tuple[str, ...]
    known_paths: tuple[str, ...] = ()
    start_commands: tuple[tuple[str, ...], ...] = ()
    windows_aliases: tuple[str, ...] = ()
    web_fallback: str | None = None
    prefer_web: bool = False
    focus_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaunchResult:
    success: bool
    message: str
    used_fallback: bool = False


# ═══════════════════════════════════════════════════════════════
# Text Normalization
# ═══════════════════════════════════════════════════════════════


def normalize_command_text(command: str) -> str:
    command = command.lower().strip()
    command = re.sub(r"[^\w\s]", "", command)
    return " ".join(command.split())


# ═══════════════════════════════════════════════════════════════
# Window Management
# ═══════════════════════════════════════════════════════════════


def bring_window_to_front(keywords: Sequence[str]) -> str:
    try:
        import pygetwindow as gw  # type: ignore[import-untyped]

        time.sleep(1.2)
        all_windows = gw.getAllTitles()
        for keyword in keywords:
            for title in all_windows:
                if keyword.lower() in title.lower() and title.strip():
                    try:
                        windows = gw.getWindowsWithTitle(title)
                        if not windows:
                            continue
                        window = windows[0]
                        if window.isMinimized:
                            window.restore()
                            time.sleep(0.2)
                        window.activate()
                        time.sleep(0.2)
                        return "focused"
                    except Exception:
                        continue
        return "opened"
    except Exception:
        return "opened"


# ═══════════════════════════════════════════════════════════════
# Process Launching Utilities
# ═══════════════════════════════════════════════════════════════


def _expand_path(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


def _start_process(command: Sequence[str] | str) -> bool:
    """
    Launch a command and verify it didn't fail immediately.
    Reliable ONLY for direct .exe calls — NOT for shell wrappers
    like `cmd /c start` or `explorer shell:AppsFolder` which always
    exit 0. Use _launch_via_shell() for those instead.
    """
    try:
        process = subprocess.Popen(command)
        time.sleep(0.5)          # slightly longer for crash detection
        return_code = process.poll()
        return return_code is None or return_code == 0
    except Exception:
        return False


def _snapshot_windows() -> set[str]:
    """Capture the set of all current window titles (for before/after diff)."""
    try:
        import pygetwindow as gw  # type: ignore[import-untyped]
        return set(gw.getAllTitles())
    except Exception:
        return set()


def _verify_window_appeared(
    keywords: Sequence[str],
    pre_titles: set[str],
    timeout: float = 8.0,
) -> bool:
    """
    Poll for `timeout` seconds for a NEW window whose title contains
    any of `keywords`, OR if an existing matching window becomes Active.

    Used to validate shell-wrapper launches (cmd /c start, explorer
    shell:AppsFolder) whose exit code is always 0 and therefore
    cannot be trusted as a success signal.

    Returns True only when a matching window is confirmed open.
    Falls back gracefully to False if pygetwindow is unavailable.
    """
    try:
        import pygetwindow as gw  # type: ignore[import-untyped]
        deadline = time.time() + timeout
        while time.time() < deadline:
            # 1. Check if a newly created window matches
            all_titles = gw.getAllTitles()
            new_titles = set(all_titles) - pre_titles
            for keyword in keywords:
                kw_lower = keyword.lower()
                if any(kw_lower in t.lower() for t in new_titles if t.strip()):
                    return True
            
            # 2. Check if an already existing window was brought to front
            active = gw.getActiveWindow()
            if active and active.title.strip():
                active_lower = active.title.lower()
                if any(k.lower() in active_lower for k in keywords):
                    return True

            time.sleep(0.35)
        return False
    except Exception:
        # pygetwindow unavailable — cannot confirm, be conservative
        return False


def _launch_via_shell(
    command: Sequence[str] | str,
    verify_keywords: Sequence[str],
    timeout: float = 4.0,
) -> bool:
    """
    Launch a shell-wrapper command (cmd /c start, explorer shell:AppsFolder)
    and validate success by checking for a new matching window.

    These commands ALWAYS return exit code 0, so exit code alone cannot
    confirm that the target app actually opened.  Window appearance is
    the only reliable signal.
    """
    pre = _snapshot_windows()
    try:
        subprocess.Popen(command)
    except Exception:
        return False
    return _verify_window_appeared(verify_keywords, pre, timeout)


def _launch_existing_path(executable_path: str, extra_args: Sequence[str]) -> bool:
    expanded_path = _expand_path(executable_path)
    matches = (
        glob(expanded_path)
        if any(c in expanded_path for c in "*?")
        else [expanded_path]
    )
    for matched_path in matches:
        if os.path.isfile(matched_path) and _start_process([matched_path, *extra_args]):
            return True
    return False


def _launch_known_paths(config: LaunchConfig, extra_args: Sequence[str]) -> bool:
    for executable_path in config.known_paths:
        if _launch_existing_path(executable_path, extra_args):
            return True
    return False


def _has_known_path(config: LaunchConfig) -> bool:
    for executable_path in config.known_paths:
        expanded_path = _expand_path(executable_path)
        matches = (
            glob(expanded_path)
            if any(c in expanded_path for c in "*?")
            else [expanded_path]
        )
        if any(os.path.isfile(m) for m in matches):
            return True
    return False


def _launch_start_commands(config: LaunchConfig, extra_args: Sequence[str]) -> bool:
    """
    Run each start_command in the config and verify the app actually opened.

    Uses _launch_via_shell() for 'cmd /c start' style commands whose exit
    code is always 0 regardless of whether the target app launched.
    Falls back to direct _start_process() for non-shell commands.
    """
    # Build keyword list from config for window verification
    verify_keywords = list(
        config.focus_keywords or (config.display_name.lower(),)
    )
    if config.display_name.lower() not in [k.lower() for k in verify_keywords]:
        verify_keywords.append(config.display_name.lower())

    for command in config.start_commands:
        cmd_list = list(command) + list(extra_args)
        # Detect shell-wrapper patterns — these need window verification
        is_shell_wrapper = (
            len(cmd_list) >= 2
            and cmd_list[0].lower() in ("cmd", "cmd.exe")
            and "/c" in [p.lower() for p in cmd_list]
        )
        if is_shell_wrapper:
            if _launch_via_shell(cmd_list, verify_keywords, timeout=4.0):
                return True
        else:
            if _start_process(cmd_list):
                return True
    return False


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _launch_start_apps(
    alias: str,
    focus_keywords: Sequence[str] = (),
) -> bool:
    """
    Use PowerShell Get-StartApps to find and launch a Windows/UWP app.

    explorer.exe shell:AppsFolder always exits 0. Since we positively
    identified the app via Get-StartApps, we consider the launch successful
    if subprocess.Popen succeeds, even if window verification times out
    (UWP apps often launch asynchronously or have delayed window creation).
    """
    try:
        pattern = f"*{alias}*"
        quoted = _powershell_quote(pattern)
        ps_command = (
            "Get-StartApps | "
            f"Where-Object {{ $_.Name -like {quoted} -or $_.AppID -like {quoted} }} | "
            "Select-Object -First 1 -ExpandProperty AppID"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=5,
        )
        app_id = (
            completed.stdout.strip().splitlines()[0]
            if completed.stdout.strip()
            else ""
        )
        if not app_id:
            return False

        # Build verification keywords
        verify_keywords = [alias] + list(focus_keywords)

        # We call _launch_via_shell to attempt focusing the window,
        # but DO NOT strictly require it to return True.
        # The UWP package exists and explorer.exe will launch it.
        _launch_via_shell(
            ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
            verify_keywords,
            timeout=5.0,
        )
        return True
    except Exception:
        return False


def _launch_windows_aliases(config: LaunchConfig, extra_args: Sequence[str]) -> bool:
    verify_keywords = list(config.focus_keywords or (config.display_name.lower(),))
    if config.display_name.lower() not in [k.lower() for k in verify_keywords]:
        verify_keywords.append(config.display_name.lower())

    for alias in config.windows_aliases:
        resolved = shutil.which(alias)
        if resolved and _start_process([resolved, *extra_args]):
            return True
        if not extra_args and _launch_start_apps(alias, focus_keywords=verify_keywords):
            return True
    return False


def _has_windows_alias(config: LaunchConfig) -> bool:
    return any(shutil.which(alias) for alias in config.windows_aliases)


# ═══════════════════════════════════════════════════════════════
# URL / Directory helpers
# ═══════════════════════════════════════════════════════════════


def _validate_domain(domain: str) -> bool:
    """Validate if a domain exists via quick DNS resolution."""
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False


def open_url(
    url: str,
    display_name: str = "Browser",
    focus_keywords: Iterable[str] | None = None,
) -> bool:
    try:
        opened = webbrowser.open(url)
        if not opened:
            return False
        bring_window_to_front(
            list(focus_keywords or [display_name, "chrome", "edge", "browser"])
        )
        return True
    except Exception:
        return False


def open_directory(path: str | None = None) -> LaunchResult:
    command = "explorer" if not path else ["explorer", _expand_path(path)]
    if _start_process(command):
        bring_window_to_front(["file explorer", "explorer", "desktop"])
        return LaunchResult(True, "[SUCCESS] File Explorer opened.")
    return LaunchResult(False, "[ERROR] Could not open File Explorer.")


# ═══════════════════════════════════════════════════════════════
# Name cleaning / canonical key resolution
# ═══════════════════════════════════════════════════════════════


def _clean_app_name(app_name: str) -> str:
    cleaned = normalize_command_text(app_name)
    cleaned = re.sub(r"\b(please|the|app|application)\b", "", cleaned)
    return " ".join(cleaned.split()).strip()


def _canonical_app_key(app_name: str) -> str:
    """Map a user-provided name to a static config key, or return cleaned name."""
    cleaned_name = _clean_app_name(app_name)
    if cleaned_name == "yt":
        cleaned_name = "youtube"

    for config in APP_CONFIGS.values():
        if cleaned_name == config.key or cleaned_name in config.aliases:
            return config.key
    return cleaned_name


def _name_variants(name: str) -> list[str]:
    """Generate plausible search variants from a cleaned app name."""
    variants = [name]
    no_spaces = name.replace(" ", "")
    if no_spaces != name:
        variants.append(no_spaces)
    hyphenated = name.replace(" ", "-")
    if hyphenated != name:
        variants.append(hyphenated)
    return variants


# ═══════════════════════════════════════════════════════════════
# Static Priority App Configs  (always checked first)
# ═══════════════════════════════════════════════════════════════


APP_CONFIGS: dict[str, LaunchConfig] = {
    "chrome": LaunchConfig(
        key="chrome",
        display_name="Chrome",
        aliases=("chrome", "google chrome"),
        known_paths=(
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        ),
        start_commands=(("cmd", "/c", "start", "", "chrome"),),
        windows_aliases=("chrome", "Google Chrome"),
        web_fallback="https://www.google.com",
        focus_keywords=("chrome", "google chrome"),
    ),
    "vs code": LaunchConfig(
        key="vs code",
        display_name="VS Code",
        aliases=("vs code", "vscode", "visual studio code", "code"),
        known_paths=(
            r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe",
            r"%ProgramFiles%\Microsoft VS Code\Code.exe",
            r"%ProgramFiles(x86)%\Microsoft VS Code\Code.exe",
        ),
        start_commands=(("cmd", "/c", "start", "", "code"),),
        windows_aliases=("code", "Visual Studio Code", "VS Code"),
        focus_keywords=("visual studio code", "vscode", "code"),
    ),
    "youtube": LaunchConfig(
        key="youtube",
        display_name="YouTube",
        aliases=("youtube", "yt"),
        web_fallback="https://youtube.com",
        prefer_web=True,
        focus_keywords=("youtube", "chrome", "edge"),
    ),
    "file explorer": LaunchConfig(
        key="file explorer",
        display_name="File Explorer",
        aliases=("file explorer", "explorer", "files"),
        focus_keywords=("file explorer", "explorer"),
    ),
    "whatsapp": LaunchConfig(
        key="whatsapp",
        display_name="WhatsApp",
        aliases=("whatsapp",),
        known_paths=(
            r"%LocalAppData%\WhatsApp\WhatsApp.exe",
            r"%ProgramFiles%\WindowsApps\5319275A.WhatsAppDesktop_*",
        ),
        windows_aliases=("WhatsApp", "whatsapp"),
        web_fallback="https://web.whatsapp.com",
        focus_keywords=("whatsapp",),
    ),
    "instagram": LaunchConfig(
        key="instagram",
        display_name="Instagram",
        aliases=("instagram",),
        web_fallback="https://instagram.com",
        focus_keywords=("instagram", "chrome", "edge"),
    ),
    "spotify": LaunchConfig(
        key="spotify",
        display_name="Spotify",
        aliases=("spotify",),
        known_paths=(
            r"%AppData%\Spotify\Spotify.exe",
            r"%LocalAppData%\Microsoft\WindowsApps\Spotify.exe",
        ),
        windows_aliases=("spotify", "Spotify"),
        web_fallback="https://open.spotify.com",
        focus_keywords=("spotify",),
    ),
    "github": LaunchConfig(
        key="github",
        display_name="GitHub",
        aliases=("github", "github desktop"),
        known_paths=(
            r"%LocalAppData%\GitHubDesktop\GitHubDesktop.exe",
            r"%ProgramFiles%\GitHub Desktop\GitHubDesktop.exe",
        ),
        start_commands=(("cmd", "/c", "start", "", "github"),),
        windows_aliases=("GitHub Desktop", "github"),
        web_fallback="https://github.com",
        focus_keywords=("github", "chrome", "edge"),
    ),
    "notepad": LaunchConfig(
        key="notepad",
        display_name="Notepad",
        aliases=("notepad",),
        known_paths=(r"%SystemRoot%\system32\notepad.exe",),
        start_commands=(("notepad",),),
        windows_aliases=("notepad", "Notepad"),
        focus_keywords=("notepad",),
    ),
    "task manager": LaunchConfig(
        key="task manager",
        display_name="Task Manager",
        aliases=("task manager", "taskmgr"),
        known_paths=(r"%SystemRoot%\system32\Taskmgr.exe",),
        start_commands=(("taskmgr",),),
        windows_aliases=("taskmgr", "Task Manager"),
        focus_keywords=("task manager", "taskmgr"),
    ),
}


# ═══════════════════════════════════════════════════════════════
# Web Fallback Registry
#
# If the desktop app is not installed, these URLs are opened
# instead.  This dict is checked AFTER dynamic discovery fails.
# ═══════════════════════════════════════════════════════════════


WEB_FALLBACKS: dict[str, str] = {
    # Social & Communication
    "whatsapp": "https://web.whatsapp.com",
    "instagram": "https://instagram.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "discord": "https://discord.com/app",
    "slack": "https://app.slack.com",
    "telegram": "https://web.telegram.org",
    "signal": "https://signal.org",
    "skype": "https://web.skype.com",
    "teams": "https://teams.microsoft.com",
    "microsoft teams": "https://teams.microsoft.com",
    "zoom": "https://app.zoom.us",
    "facebook": "https://facebook.com",
    "snapchat": "https://web.snapchat.com",
    "linkedin": "https://linkedin.com",
    # Media
    "spotify": "https://open.spotify.com",
    "youtube": "https://youtube.com",
    "netflix": "https://netflix.com",
    "twitch": "https://twitch.tv",
    "soundcloud": "https://soundcloud.com",
    "apple music": "https://music.apple.com",
    "google photos": "https://photos.google.com",
    # Dev Tools
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "figma": "https://figma.com",
    "linear": "https://linear.app",
    "notion": "https://notion.so",
    "jira": "https://jira.atlassian.com",
    "replit": "https://replit.com",
    "codepen": "https://codepen.io",
    "vercel": "https://vercel.com",
    "google colab": "https://colab.research.google.com",
    # Productivity
    "gmail": "https://mail.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com",
    "google drive": "https://drive.google.com",
    "google calendar": "https://calendar.google.com",
    "google meet": "https://meet.google.com",
    "google maps": "https://maps.google.com",
    "outlook": "https://outlook.live.com",
    "onedrive": "https://onedrive.live.com",
    "trello": "https://trello.com",
    "asana": "https://app.asana.com",
    # AI Tools
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "perplexity": "https://perplexity.ai",
    # Other
    "reddit": "https://reddit.com",
    "pinterest": "https://pinterest.com",
    "amazon": "https://amazon.com",
    "flipkart": "https://flipkart.com",
    "steam": "https://store.steampowered.com",
    "epic games": "https://store.epicgames.com",
    "gpay": "https://pay.google.com",
    "google pay": "https://pay.google.com",
    "phonepe": "https://www.phonepe.com",
    "playstore": "https://play.google.com",
}


# ═══════════════════════════════════════════════════════════════
# Dynamic App Discovery Engine
# ═══════════════════════════════════════════════════════════════


# ── Shortcut Cache ────────────────────────────────────────────
# Caches Start Menu shortcuts to avoid re-scanning every call.

_shortcut_cache: dict[str, str] = {}
_shortcut_cache_time: float = 0.0
_CACHE_TTL: float = 300.0  # 5 minutes


def _build_shortcut_cache() -> dict[str, str]:
    """Walk Start Menu directories and index all .lnk shortcut files."""
    global _shortcut_cache, _shortcut_cache_time

    cache: dict[str, str] = {}
    start_menu_dirs = [
        os.path.join(
            os.environ.get("ProgramData", r"C:\ProgramData"),
            "Microsoft", "Windows", "Start Menu", "Programs",
        ),
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs",
        ),
    ]

    for menu_dir in start_menu_dirs:
        if not os.path.isdir(menu_dir):
            continue
        try:
            for root, _dirs, files in os.walk(menu_dir):
                for fname in files:
                    if fname.lower().endswith(".lnk"):
                        name_key = fname[:-4].lower().strip()
                        full_path = os.path.join(root, fname)
                        if name_key not in cache:
                            cache[name_key] = full_path
        except (PermissionError, OSError):
            continue

    _shortcut_cache = cache
    _shortcut_cache_time = time.time()
    return cache


def _get_shortcut_cache() -> dict[str, str]:
    """Return the shortcut cache, rebuilding if stale."""
    if _shortcut_cache and (time.time() - _shortcut_cache_time) < _CACHE_TTL:
        return _shortcut_cache
    return _build_shortcut_cache()


def _score_match(query: str, candidate: str) -> int:
    """
    Score how well a candidate name matches the query.
    Higher is better.  Returns 0 for no match.
    """
    if candidate == query:
        return 100
    if candidate.startswith(query):
        return 85
    if query.startswith(candidate):
        return 75
    if query in candidate:
        return 65 - len(candidate)  # prefer shorter containing names
    if candidate in query:
        return 50
    # Check individual words overlap
    query_words = set(query.split())
    candidate_words = set(candidate.split())
    overlap = query_words & candidate_words
    if overlap and len(overlap) >= len(query_words) * 0.5:
        return 40
    return 0


def _find_best_shortcut(app_name: str) -> str | None:
    """Search the Start Menu shortcut cache for the best match."""
    cache = _get_shortcut_cache()
    app_lower = app_name.lower().strip()

    # Exact match — fastest path
    if app_lower in cache:
        return cache[app_lower]

    # Fuzzy match — score all candidates
    scored: list[tuple[int, str, str]] = []
    for name, path in cache.items():
        score = _score_match(app_lower, name)
        if score > 0:
            scored.append((score, name, path))

    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][2]

    return None


def _launch_shortcut(shortcut_path: str) -> bool:
    """Launch a .lnk shortcut file using os.startfile (Windows-native)."""
    try:
        os.startfile(shortcut_path)
        time.sleep(0.5)
        return True
    except OSError:
        return False


# ── Program Files / AppData Discovery ─────────────────────────


def _find_exe_in_dir(dir_path: str, app_name: str, depth: int = 1) -> str | None:
    """
    Search for an .exe matching app_name inside dir_path.
    Only descends `depth` levels to avoid deep recursion.
    """
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file() and entry.name.lower().endswith(".exe"):
                base = entry.name[:-4].lower()
                if app_name in base or base in app_name:
                    return entry.path
    except (PermissionError, OSError):
        return None

    if depth <= 0:
        return None

    try:
        for entry in os.scandir(dir_path):
            if entry.is_dir():
                result = _find_exe_in_dir(entry.path, app_name, depth - 1)
                if result:
                    return result
    except (PermissionError, OSError):
        pass

    return None


def _discover_in_install_dirs(app_name: str) -> str | None:
    """
    Search Program Files, AppData, and common install locations
    for an executable matching app_name.
    """
    app_lower = app_name.lower().replace(" ", "")

    search_roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.path.join(os.environ.get("LocalAppData", ""), "Programs"),
        os.environ.get("LocalAppData", ""),
        os.environ.get("AppData", ""),
    ]

    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for entry in os.scandir(root):
                if not entry.is_dir():
                    continue
                dir_lower = entry.name.lower().replace(" ", "")
                if app_lower in dir_lower or dir_lower in app_lower:
                    exe = _find_exe_in_dir(entry.path, app_lower, depth=2)
                    if exe:
                        return exe
        except (PermissionError, OSError):
            continue

    return None


# ── PATH Discovery ────────────────────────────────────────────


def _discover_on_path(app_name: str) -> str | None:
    """Check PATH for executables matching app_name or its variants."""
    for variant in _name_variants(app_name):
        resolved = shutil.which(variant)
        if resolved:
            return resolved
    return None


# ── Master Discovery ──────────────────────────────────────────


def _discover_app(app_name: str) -> str | None:
    """
    Dynamically discover an installed app by name.

    Search order:
      1. Start Menu shortcuts  (fastest, most comprehensive)
      2. PATH lookup            (catches CLI-installed tools)
      3. Program Files / AppData scan (catches manually installed apps)

    Returns a path to an .exe or .lnk file, or None.
    """
    # 1. Start Menu shortcuts
    shortcut = _find_best_shortcut(app_name)
    if shortcut:
        return shortcut

    # 2. PATH lookup
    path_exe = _discover_on_path(app_name)
    if path_exe:
        return path_exe

    # 3. Program Files / AppData scan
    install_exe = _discover_in_install_dirs(app_name)
    if install_exe:
        return install_exe

    return None


# ═══════════════════════════════════════════════════════════════
# Config-based Launch  (for priority/static apps)
# ═══════════════════════════════════════════════════════════════


def _focus_after_launch(config: LaunchConfig) -> None:
    keywords = list(config.focus_keywords or (config.display_name,))
    if config.display_name.lower() not in [k.lower() for k in keywords]:
        keywords.append(config.display_name)
    bring_window_to_front(keywords)


def _launch_from_config(config: LaunchConfig, extra_args: list[str]) -> LaunchResult:
    """
    Try all static launch methods for a known app config.
    Returns LaunchResult (may be unsuccessful if nothing works).
    """
    if config.prefer_web:
        if open_url(
            config.web_fallback or "",
            config.display_name,
            config.focus_keywords,
        ):
            return LaunchResult(True, f"[SUCCESS] {config.display_name} opened.")
        return LaunchResult(False, f"[ERROR] Could not open {config.display_name}.")

    if _launch_known_paths(config, extra_args):
        _focus_after_launch(config)
        return LaunchResult(True, f"[SUCCESS] {config.display_name} opened.")

    if _launch_start_commands(config, extra_args):
        _focus_after_launch(config)
        return LaunchResult(True, f"[SUCCESS] {config.display_name} opened.")

    if _launch_windows_aliases(config, extra_args):
        _focus_after_launch(config)
        return LaunchResult(True, f"[SUCCESS] {config.display_name} opened.")

    # Config-based launch failed
    return LaunchResult(False, f"[ERROR] Could not open {config.display_name}.")


# ═══════════════════════════════════════════════════════════════
# Main Launch Orchestrator
#
# Launch strategy (in order):
#   1. Static config   — priority apps with known paths/aliases
#   2. Dynamic shortcut — Start Menu .lnk scan
#   3. Dynamic PATH     — shutil.which variants
#   4. Dynamic scan     — Program Files / AppData directories
#   5. Get-StartApps    — PowerShell UWP/Store app query
#   6. Web fallback     — known web URLs for popular services
#   7. Google search    — absolute last resort
# ═══════════════════════════════════════════════════════════════


def launch_app(app_name: str, extra_args: Sequence[str] | None = None) -> LaunchResult:
    extra_args = list(extra_args or [])
    canonical_key = _canonical_app_key(app_name)

    if canonical_key in {"", "open"}:
        return LaunchResult(False, "[ERROR] Could not determine which app to open.")

    if canonical_key == "file explorer":
        directory = extra_args[0] if extra_args else None
        return open_directory(directory)

    # ── Stage 1: Static config launch ────────────────────────
    config = APP_CONFIGS.get(canonical_key)
    if config is not None:
        result = _launch_from_config(config, extra_args)
        if result.success:
            return result
        # Static config exists but failed — fall through to dynamic

    # ── Derive display name ──────────────────────────────────
    cleaned = _clean_app_name(app_name)
    display = " ".join(w.capitalize() for w in cleaned.split())

    # ── Stage 2: Dynamic discovery ───────────────────────────
    discovered = _discover_app(cleaned)
    if discovered:
        launched = False
        if discovered.lower().endswith(".lnk"):
            launched = _launch_shortcut(discovered)
        else:
            launched = _start_process([discovered, *extra_args])

        if launched:
            bring_window_to_front([cleaned, display])
            return LaunchResult(True, f"[SUCCESS] {display} opened.")

    # ── Stage 3: Get-StartApps (UWP / Store apps) ────────────
    for variant in _name_variants(cleaned):
        if _launch_start_apps(variant):
            bring_window_to_front([variant, cleaned, display])
            return LaunchResult(True, f"[SUCCESS] {display} opened.")

    # ── Stage 4: Web fallback ────────────────────────────────
    # Try static config fallback first
    if config and config.web_fallback:
        if open_url(config.web_fallback, config.display_name, config.focus_keywords):
            return LaunchResult(
                True,
                f"[SUCCESS] {config.display_name} desktop app not found. "
                f"Opened web version instead.",
                used_fallback=True,
            )

    # Then check the web fallback registry
    web_url = WEB_FALLBACKS.get(cleaned)
    if web_url and open_url(web_url, display, [cleaned, "chrome", "edge"]):
        return LaunchResult(
            True,
            f"[SUCCESS] {display} desktop app not found. "
            f"Opened web version instead.",
            used_fallback=True,
        )

    # ── Stage 5: Intelligent Domain Inference ────────────────
    no_spaces = cleaned.replace(" ", "")
    if no_spaces:
        for domain in [f"{no_spaces}.com", f"www.{no_spaces}.com"]:
            if _validate_domain(domain):
                web_url = f"https://{domain}"
                if open_url(web_url, display, [cleaned, "chrome", "edge"]):
                    return LaunchResult(
                        True,
                        f"[SUCCESS] {display} desktop app not found. "
                        f"Inferred and opened {domain} instead.",
                        used_fallback=True,
                    )

    # ── Stage 6: Google search as last resort ────────────────
    search_url = f"https://www.google.com/search?q={quote_plus(cleaned + ' official website')}"
    if open_url(search_url, f"Search: {display}", ["chrome", "edge", "google"]):
        return LaunchResult(
            True,
            f"[SUCCESS] {display} is not installed. "
            f"Opened Google search to help you find it.",
            used_fallback=True,
        )

    return LaunchResult(False, f"[ERROR] Could not open {display}.")
