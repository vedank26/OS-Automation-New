"""
PATCH INSTRUCTIONS for automation_1.py
========================================

Apply these 2 changes to your existing automation_1.py:

CHANGE 1: Add import at the top (after line 15)
────────────────────────────────────────────────
After:
    from ai_project_creator import create_ai_project, parse_create_command
    from retry_engine import run_project_with_repair

Add:
    from assignment_solver import (
        is_assignment_command,
        solve_assignment,
    )


CHANGE 2: Add the assignment solver handler block
──────────────────────────────────────────────────
Insert this block AFTER the "🖥️ APPS" section (after the open_match block)
and BEFORE the "🎯 VIDEO SELECTION" section.

The assignment handler should be placed early so it catches assignment
commands before they get misrouted to YouTube/search handlers.

Add this block:

        # ─────────────────────────────────────────
        # 📝 ASSIGNMENT SOLVER
        # ─────────────────────────────────────────

        elif is_assignment_command(normalized_command):
            from assignment_solver import solve_assignment
            result = solve_assignment(raw_command)
            return _result(result)
"""

# ──────────────────────────────────────────────────────────
# Below is the FULL patched automation_1.py for convenience
# (only the changes are highlighted with comments)
# ──────────────────────────────────────────────────────────

import os
import re
import shutil
import subprocess
import time
import webbrowser
import json
from urllib.parse import quote_plus

import pyautogui
import requests
from dotenv import load_dotenv

from ai_project_creator import create_ai_project, parse_create_command
from retry_engine import run_project_with_repair
# >>> NEW: Assignment solver import
from assignment_solver import (
    is_assignment_command,
    solve_assignment,
)
from app_launcher import launch_app


load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

pyautogui.FAILSAFE = True

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if YOUTUBE_API_KEY:
    print("YouTube API Loaded: Yes")
else:
    print("YouTube API Loaded: No")

LAST_RESULTS = []

def save_last_results(results):
    pass

FILLER_WORDS = {"on", "the", "a", "an", "in", "at"}

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

PROJECT_KEYWORDS = {
    "python", "html", "css", "javascript", "js", "react",
    "nodejs", "node", "flutter", "django", "flask",
    "project", "app", "website", "game", "tracker",
    "dashboard", "calculator", "todo", "portfolio",
    "chatbot", "api", "backend", "frontend",
}


def _is_project_command(command: str) -> bool:
    has_verb = re.search(r"\b(create|build|make)\b", command)
    if not has_verb:
        return False
    words = set(command.lower().split())
    return bool(words & PROJECT_KEYWORDS)


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


def search_youtube(query: str):
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not configured in backend/.env")

    response = requests.get(
        YOUTUBE_API_URL,
        params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 5,
            "key": YOUTUBE_API_KEY,
        },
        timeout=10,
    )
    response.raise_for_status()

    payload = response.json()
    if not payload.get("items"):
        return []

    if "error" in payload:
        message = payload["error"].get("message", "Unknown YouTube API error")
        raise RuntimeError(message)

    results = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        title = item.get("snippet", {}).get("title")
        if video_id and title:
            results.append({"videoId": video_id, "title": title})

    return results


def play_video(index: int):
    if not LAST_RESULTS:
        return _result(
            "No YouTube results available. "
            "Use 'play <query> on youtube' first."
        )

    if index < 0 or index >= len(LAST_RESULTS):
        return _result(
            f"Invalid video number. Choose between 1 and {len(LAST_RESULTS)}."
        )

    video = LAST_RESULTS[index]
    video_url = f"https://www.youtube.com/watch?v={video['videoId']}&autoplay=1"
    webbrowser.open(video_url)
    _bring_window_to_front(["youtube", "edge", "chrome"])
    return _result(f"Playing video {index + 1}: '{video['title']}'")


def _get_video_index(command: str):
    global LAST_RESULTS
    cmd = command.strip().lower()
    word_map = {
        "play 1": 0, "first": 0,  "1": 0, "one": 0, "option 1": 0, "option one": 0, "play option 1": 0,
        "play 2": 1, "second": 1, "2": 1, "two": 1, "option 2": 1, "option two": 1, "play option 2": 1,
        "play 3": 2, "third": 2,  "3": 2, "three": 2, "option 3": 2, "option three": 2, "play option 3": 2,
        "play 4": 3, "fourth": 3, "4": 3, "four": 3, "option 4": 3, "option four": 3, "play option 4": 3,
        "play 5": 4, "fifth": 4,  "5": 4, "five": 4, "option 5": 4, "option five": 4, "play option 5": 4,
    }

    if cmd in word_map:
        return word_map[cmd]

    if cmd.startswith("option "):
        try: return int(cmd.split()[1]) - 1
        except: pass

    if cmd.startswith("play option "):
        try: return int(cmd.split()[2]) - 1
        except: pass

    if LAST_RESULTS:
        for idx, video in enumerate(LAST_RESULTS):
            title = video.get("title", "").lower()
            if cmd == title or (len(cmd) > 3 and cmd in title):
                return idx

        if cmd.startswith("play "):
            play_query = cmd[5:].strip()
            for idx, video in enumerate(LAST_RESULTS):
                title = video.get("title", "").lower()
                if play_query == title or (len(play_query) > 3 and play_query in title):
                    return idx

    return None


def _extract_youtube_play_query(raw_command: str):
    query = raw_command.lower()

    noise_phrases = [
        "on youtube", "in youtube", "on the youtube",
        "youtube search", "search youtube for",
        "search youtube", "search on youtube",
        "find on youtube", "play on youtube",
        "play in youtube", "youtube play",
        "on yt", "in yt", "youtube",
    ]

    for phrase in noise_phrases:
        query = query.replace(phrase, "").strip()

    if query.startswith("play "):
        query = query[5:].strip()

    query = " ".join(w for w in query.split() if w.lower() not in FILLER_WORDS)
    query = " ".join(query.split()).strip()

    return query if query else None


def execute_command(command: str):
    global LAST_RESULTS

    try:
        raw_command = command.strip()
        normalized_command = raw_command.lower()

        if not normalized_command:
            return _result("No command provided.")

        # ─────────────────────────────────────────
        # 🖥️ APPS — must be FIRST
        # ─────────────────────────────────────────

        open_match = re.match(r"^open\s+(.+)$", raw_command, flags=re.IGNORECASE)
        if open_match:
            app_name = open_match.group(1).strip()
            if not re.fullmatch(r"\d+", app_name):
                app_result = launch_app(app_name)
                return _result(app_result.message)

        # ─────────────────────────────────────────
        # 📝 ASSIGNMENT SOLVER  <<< NEW BLOCK
        # ─────────────────────────────────────────

        elif is_assignment_command(normalized_command):
            result = solve_assignment(raw_command)
            return _result(result)

        # ─────────────────────────────────────────
        # 🎯 VIDEO SELECTION (after YouTube search)
        # ─────────────────────────────────────────

        elif _get_video_index(normalized_command) is not None and LAST_RESULTS:
            index = _get_video_index(normalized_command)
            return play_video(index)

        # ─────────────────────────────────────────
        # ▶️ YOUTUBE SEARCH
        # ─────────────────────────────────────────

        elif "youtube" in normalized_command or "yt" in normalized_command:
            query = _extract_youtube_play_query(raw_command)
            if query:
                try:
                    results = search_youtube(query)
                except requests.RequestException as exc:
                    LAST_RESULTS = []
                    return _result(f"YouTube API request failed: {exc}")
                except RuntimeError as exc:
                    LAST_RESULTS = []
                    return _result(f"YouTube search is not available: {exc}")
                except Exception as exc:
                    LAST_RESULTS = []
                    return _result(f"Failed to search YouTube: {exc}")

                if not results:
                    LAST_RESULTS = []
                    return _result("No results found")

                LAST_RESULTS = results
                save_last_results(results)
                return {
                    "result": f"YouTube results for '{query}'. Say which to play.",
                    "options": [result["title"] for result in results],
                }

            webbrowser.open("https://www.youtube.com")
            _bring_window_to_front(["youtube", "edge", "chrome"])
            return _result("YouTube opened.")

        # ─────────────────────────────────────────
        # 🎵 PLAY without youtube keyword
        # ─────────────────────────────────────────

        elif normalized_command.startswith("play ") and not _is_project_command(normalized_command):
            try:
                index = int(normalized_command.split()[1]) - 1
                if LAST_RESULTS:
                    return play_video(index)
            except (ValueError, IndexError):
                pass

            query = normalized_command[5:].strip()
            query = " ".join(w for w in query.split() if w.lower() not in FILLER_WORDS)
            if query:
                try:
                    results = search_youtube(query)
                except Exception as exc:
                    LAST_RESULTS = []
                    return _result(f"YouTube search failed: {exc}")

                if not results:
                    LAST_RESULTS = []
                    return _result("No results found")

                LAST_RESULTS = results
                save_last_results(results)
                return {
                    "result": f"YouTube results for '{query}'. Say which to play.",
                    "options": [result["title"] for result in results],
                }
            return _result("Please specify a song name.")

        elif re.fullmatch(r"open\s+\d+", normalized_command):
            try:
                index = int(normalized_command.split()[1]) - 1
                return play_video(index)
            except Exception:
                return _result("Invalid selection")

        # ─────────────────────────────────────────
        # 📁 FOLDER CREATION
        # ─────────────────────────────────────────

        elif "create folder" in normalized_command:
            folder_name = "NewFolder"
            named_match = re.search(
                r"(?:named|called)\s+(.+)$", raw_command, flags=re.IGNORECASE
            )
            if named_match:
                folder_name = named_match.group(1).strip()
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            path = os.path.join(desktop, folder_name)
            os.makedirs(path, exist_ok=True)
            subprocess.run(f'explorer "{desktop}"', shell=True)
            _bring_window_to_front(["file explorer", "explorer", "desktop"])
            return _result(f"Folder '{folder_name}' created on Desktop.")

        # ─────────────────────────────────────────
        # ⚛️ REACT PROJECT
        # ─────────────────────────────────────────

        elif (
            "create react app" in normalized_command
            or "create react project" in normalized_command
        ):
            app_name = "my-react-app"
            named_match = re.search(
                r"(?:named|called)\s+([^\s].+?)(?:\s+(?:in|on|at|for)\b|$)",
                raw_command, flags=re.IGNORECASE,
            )
            if named_match:
                app_name = named_match.group(1).strip().replace(" ", "-").lower()
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            vite_cmd = (
                f"npm create vite@latest {app_name} -- --template react"
                f" && cd {app_name} && npm install"
            )
            subprocess.Popen(f'start cmd /k "{vite_cmd}"', shell=True, cwd=desktop)
            _bring_window_to_front(["cmd", "command prompt", "terminal"])
            return _result(
                f"Creating React app '{app_name}' on Desktop using Vite.\n"
                f"npm install will run automatically after scaffolding.\n"
                f"When done, run: cd Desktop\\{app_name} && npm run dev"
            )

        # ─────────────────────────────────────────
        # 🐍 PYTHON PROJECT
        # ─────────────────────────────────────────

        elif "create python project" in normalized_command and "using" not in normalized_command and "for" not in normalized_command:
            project_name = "my_python_project"
            named_match = re.search(
                r"(?:named|called)\s+(.+)$", raw_command, flags=re.IGNORECASE
            )
            if named_match:
                project_name = named_match.group(1).strip().replace(" ", "_")
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            project_path = os.path.join(desktop, project_name)
            os.makedirs(project_path, exist_ok=True)
            with open(os.path.join(project_path, "main.py"), "w", encoding="utf-8") as f:
                f.write('# Main Python file\n\nprint("Hello World")\n')
            with open(os.path.join(project_path, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {project_name}\n\nCreated by FlowForge AI")
            launch_result = launch_app("vs code", [project_path])
            if launch_result.success:
                return _result(f"Python project '{project_name}' created and opened in VS Code.")
            return _result(f"Python project '{project_name}' created on Desktop, but VS Code could not be opened.")

        # ─────────────────────────────────────────
        # 🤖 AI PROJECT CREATION
        # ─────────────────────────────────────────

        elif _is_project_command(normalized_command):
            description, project_name = parse_create_command(raw_command)
            if description:
                creation_result = create_ai_project(description, project_name)
                if "AI Project Created" in creation_result:
                    try:
                        loc_line = [line for line in creation_result.split('\n') if "Location: Desktop/" in line]
                        if loc_line:
                            folder_name = loc_line[0].split("Desktop/")[1].strip()
                            run_result = execute_command(f"run {folder_name}")
                            if isinstance(run_result, dict) and "result" in run_result:
                                creation_result += "\n\n" + run_result["result"]
                    except Exception:
                        pass
                return _result(creation_result)
            return _result(
                "Please specify what to build.\n"
                "Example: 'create calculator project using python'\n"
                "Example: 'build attendance tracker using html css js'"
            )

        # ─────────────────────────────────────────
        # 🚀 RUN PROJECT
        # ─────────────────────────────────────────

        elif (
            any(phrase in normalized_command for phrase in [
                "run project", "run the project", "execute project", "start project",
                "run my project", "start the app", "start app", "npm run dev",
                "run app", "execute my project", "run this project", "execute the project",
                "launch project", "launch the project", "launch app", "run the app",
                "start my project", "run latest project"
            ])
            or normalized_command.startswith("run ")
            or normalized_command.startswith("start ")
        ):
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            try:
                folders = [
                    f for f in os.listdir(desktop)
                    if os.path.isdir(os.path.join(desktop, f))
                ]
                if not folders:
                    return _result("No projects found on Desktop")

                latest_project = None
                project_name = None
                target_requested = False

                generic_run = any(p == normalized_command.strip() for p in [
                    "run project", "start project", "run app", "open project", "run my project"
                ])

                if not generic_run:
                    target_name = re.sub(r'^(run|start|launch|execute)\s+', '', normalized_command)
                    target_name = target_name.replace("project", "").replace("app", "").replace("game", "").strip()
                    if target_name:
                        target_requested = True
                        stripped_target = re.sub(r'[^a-z0-9]', '', target_name)
                        if stripped_target:
                            for folder in folders:
                                stripped_folder = re.sub(r'[^a-zA-Z0-9]', '', folder.lower())
                                if stripped_target in stripped_folder:
                                    latest_project = os.path.join(desktop, folder)
                                    project_name = folder
                                    break

                if not latest_project:
                    if target_requested:
                        return _result(f"Could not find a project matching '{target_name}' on Desktop.")
                    folders.sort(
                        key=lambda f: os.path.getctime(os.path.join(desktop, f)),
                        reverse=True
                    )
                    latest_project = os.path.join(desktop, folders[0])
                    project_name = folders[0]

                files_in_project = os.listdir(latest_project)
                repair_result = run_project_with_repair(latest_project, project_name)
                if repair_result is not None:
                    return repair_result

                if "package.json" in files_in_project:
                    src_exists = os.path.exists(os.path.join(latest_project, "src"))
                    if src_exists:
                        package_json_path = os.path.join(latest_project, "package.json")
                        run_script = "start"
                        try:
                            with open(package_json_path, "r") as f:
                                pkg = json.load(f)
                            scripts = pkg.get("scripts", {})
                            if "dev" in scripts:
                                run_script = "dev"
                            elif "start" in scripts:
                                run_script = "start"
                        except Exception:
                            run_script = "start"
                        run_cmd = (
                            f'cd /d "{latest_project}" '
                            f'&& echo Installing dependencies... '
                            f'&& npm install '
                            f'&& echo Starting app... '
                            f'&& npm run {run_script}'
                        )
                        subprocess.Popen(f'start cmd /k "{run_cmd}"', shell=True)
                        _bring_window_to_front(["cmd", "command prompt"])
                        port = "5173" if run_script == "dev" else "3000"
                        return _result(
                            f"Running '{project_name}'\n"
                            f"Installing dependencies...\n"
                            f"Will open on http://localhost:{port}"
                        )
                    else:
                        run_cmd = (
                            f'cd /d "{latest_project}" '
                            f'&& npm install '
                            f'&& node index.js'
                        )
                        subprocess.Popen(f'start cmd /k "{run_cmd}"', shell=True)
                        _bring_window_to_front(["cmd", "command prompt"])
                        return _result(f"Running '{project_name}' - Node.js app")

                elif "main.py" in files_in_project:
                    main_py_path = os.path.join(latest_project, "main.py")
                    imports_to_install = []
                    try:
                        with open(main_py_path, "r") as f:
                            content = f.read()
                        import_lines = re.findall(r'^(?:import|from)\s+(\w+)', content, re.MULTILINE)
                        stdlib_modules = {
                            "os", "sys", "re", "time", "math", "random",
                            "json", "datetime", "pathlib", "collections",
                            "itertools", "functools", "string", "io",
                            "subprocess", "threading", "multiprocessing",
                            "urllib", "http", "email", "html", "xml",
                            "sqlite3", "csv", "logging", "unittest",
                            "abc", "copy", "gc", "inspect", "types",
                            "typing", "enum", "dataclasses", "contextlib",
                            "warnings", "traceback", "pprint", "textwrap"
                        }
                        for module in import_lines:
                            if module not in stdlib_modules:
                                imports_to_install.append(module)
                    except Exception:
                        pass
                    if imports_to_install:
                        install_list = " ".join(imports_to_install)
                        run_cmd = (
                            f'cd /d "{latest_project}" '
                            f'&& pip install {install_list} '
                            f'&& python main.py'
                        )
                        dep_msg = f"Installing: {install_list}"
                    else:
                        run_cmd = f'cd /d "{latest_project}" && python main.py'
                        dep_msg = "Running directly"
                    subprocess.Popen(f'start cmd /k "{run_cmd}"', shell=True)
                    _bring_window_to_front(["cmd", "command prompt"])
                    return _result(
                        f"Running '{project_name}'\n"
                        f"{dep_msg}\n"
                        f"Check the terminal window for output"
                    )

                elif "app.py" in files_in_project:
                    run_cmd = f'cd /d "{latest_project}" && pip install flask && python app.py'
                    subprocess.Popen(f'start cmd /k "{run_cmd}"', shell=True)
                    _bring_window_to_front(["cmd", "command prompt"])
                    return _result(f"Running '{project_name}' - Flask app on http://localhost:5000")

                elif "manage.py" in files_in_project:
                    run_cmd = f'cd /d "{latest_project}" && pip install django && python manage.py runserver'
                    subprocess.Popen(f'start cmd /k "{run_cmd}"', shell=True)
                    _bring_window_to_front(["cmd", "command prompt"])
                    return _result(f"Running '{project_name}' - Django on http://localhost:8000")

                elif "index.html" in files_in_project:
                    index_file = os.path.join(latest_project, "index.html")
                    webbrowser.open(f"file:///{index_file}")
                    _bring_window_to_front(["chrome", "edge", "firefox"])
                    return _result(f"Opened '{project_name}' in browser")

                else:
                    subprocess.Popen(
                        f'start cmd /k "cd /d "{latest_project}" && echo Project folder opened."',
                        shell=True
                    )
                    return _result(f"Opened terminal for '{project_name}'")

            except Exception as e:
                return _result(f"Could not run project: {str(e)}")

        # ─────────────────────────────────────────
        # 🔍 GOOGLE SEARCH
        # ─────────────────────────────────────────

        elif "search" in normalized_command:
            query = raw_command.lower().replace("search", "").strip()
            noise_phrases = [
                "on chrome", "on google", "in chrome", "in google",
                "in browser", "on browser", "using chrome", "using google",
                "on the internet", "on internet", "on web", "on the web",
            ]
            for phrase in noise_phrases:
                query = query.replace(phrase, "").strip()
            query = " ".join(query.split()).strip()
            if query:
                url = f"https://www.google.com/search?q={quote_plus(query)}"
                webbrowser.open(url)
                _bring_window_to_front(["chrome", "edge", "google"])
                return _result(f"Searching Google for '{query}'.")
            webbrowser.open("https://www.google.com")
            _bring_window_to_front(["chrome", "edge"])
            return _result("Google opened.")

        # ─────────────────────────────────────────
        # 📸 SCREENSHOT
        # ─────────────────────────────────────────

        elif "screenshot" in normalized_command or "take screenshot" in normalized_command:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(desktop, filename)
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            subprocess.run(f'explorer "{desktop}"', shell=True)
            _bring_window_to_front(["file explorer", "explorer", "desktop"])
            return _result("Screenshot saved to Desktop.")

        # ─────────────────────────────────────────
        # 🖱️ CURSOR / MOUSE
        # ─────────────────────────────────────────

        elif "move cursor to center" in normalized_command:
            width, height = pyautogui.size()
            pyautogui.moveTo(width // 2, height // 2)
            return _result("Cursor moved to center.")

        elif "move cursor to top left" in normalized_command:
            pyautogui.moveTo(0, 0)
            return _result("Cursor moved to top-left.")

        elif "move cursor to top right" in normalized_command:
            width, _ = pyautogui.size()
            pyautogui.moveTo(width, 0)
            return _result("Cursor moved to top-right.")

        elif "move cursor to bottom left" in normalized_command:
            _, height = pyautogui.size()
            pyautogui.moveTo(0, height)
            return _result("Cursor moved to bottom-left.")

        elif "move cursor to bottom right" in normalized_command:
            width, height = pyautogui.size()
            pyautogui.moveTo(width, height)
            return _result("Cursor moved to bottom-right.")

        elif "move cursor to" in normalized_command:
            nums = re.findall(r"\d+", raw_command)
            if len(nums) >= 2:
                x, y = int(nums[0]), int(nums[1])
                pyautogui.moveTo(x, y)
                return _result(f"Cursor moved to ({x}, {y}).")
            return _result("Could not parse coordinates.")

        elif "click at" in normalized_command:
            nums = re.findall(r"\d+", raw_command)
            if len(nums) >= 2:
                x, y = int(nums[0]), int(nums[1])
                pyautogui.click(x, y)
                return _result(f"Clicked at ({x}, {y}).")
            return _result("Could not parse coordinates.")

        elif "double click" in normalized_command:
            pyautogui.doubleClick()
            return _result("Double-clicked.")

        elif "right click" in normalized_command:
            pyautogui.rightClick()
            return _result("Right-clicked.")

        elif normalized_command == "click":
            pyautogui.click()
            return _result("Clicked.")

        # ─────────────────────────────────────────
        # ⌨️ KEYBOARD
        # ─────────────────────────────────────────

        elif normalized_command.startswith("type "):
            text = raw_command[5:].strip()
            pyautogui.typewrite(text, interval=0.05)
            return _result(f"Typed: '{text}'.")

        elif normalized_command.startswith("write "):
            text = raw_command[6:].strip()
            pyautogui.typewrite(text, interval=0.05)
            return _result(f"Written: '{text}'.")

        elif "press ctrl c" in normalized_command:
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.3)
            return _result("Pressed Ctrl+C.")

        elif "press ctrl v" in normalized_command:
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            return _result("Pressed Ctrl+V.")

        elif "press ctrl s" in normalized_command:
            pyautogui.hotkey("ctrl", "s")
            time.sleep(0.3)
            return _result("Pressed Ctrl+S.")

        elif "press ctrl z" in normalized_command:
            pyautogui.hotkey("ctrl", "z")
            time.sleep(0.3)
            return _result("Pressed Ctrl+Z.")

        elif "press ctrl a" in normalized_command:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.3)
            return _result("Pressed Ctrl+A.")

        elif "press alt tab" in normalized_command:
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.3)
            return _result("Pressed Alt+Tab.")

        elif "press alt f4" in normalized_command:
            pyautogui.hotkey("alt", "f4")
            time.sleep(0.3)
            return _result("Pressed Alt+F4.")

        elif "press win d" in normalized_command:
            pyautogui.hotkey("win", "d")
            time.sleep(0.3)
            return _result("Pressed Win+D.")

        elif "press enter" in normalized_command:
            pyautogui.press("enter")
            return _result("Pressed Enter.")

        elif "press escape" in normalized_command:
            pyautogui.press("escape")
            return _result("Pressed Escape.")

        elif "press space" in normalized_command:
            pyautogui.press("space")
            return _result("Pressed Space.")

        elif "press tab" in normalized_command:
            pyautogui.press("tab")
            return _result("Pressed Tab.")

        elif "press backspace" in normalized_command:
            pyautogui.press("backspace")
            return _result("Pressed Backspace.")

        elif "press delete" in normalized_command:
            pyautogui.press("delete")
            return _result("Pressed Delete.")

        elif "scroll up" in normalized_command:
            nums = re.findall(r"\d+", raw_command)
            amount = int(nums[0]) if nums else 3
            pyautogui.scroll(amount)
            return _result(f"Scrolled up {amount}.")

        elif "scroll down" in normalized_command:
            nums = re.findall(r"\d+", raw_command)
            amount = int(nums[0]) if nums else 3
            pyautogui.scroll(-amount)
            return _result(f"Scrolled down {amount}.")

        # ─────────────────────────────────────────
        # 🪟 WINDOW MANAGEMENT
        # ─────────────────────────────────────────

        elif "focus chrome" in normalized_command:
            _bring_window_to_front(["chrome"])
            return _result("Chrome focused.")

        elif "focus edge" in normalized_command:
            _bring_window_to_front(["edge"])
            return _result("Edge focused.")

        elif "focus vscode" in normalized_command:
            _bring_window_to_front(["visual studio code", "vscode"])
            return _result("VS Code focused.")

        elif "focus notepad" in normalized_command:
            _bring_window_to_front(["notepad"])
            return _result("Notepad focused.")

        elif "focus terminal" in normalized_command:
            _bring_window_to_front(["cmd", "powershell", "terminal", "command prompt"])
            return _result("Terminal focused.")

        elif "switch window" in normalized_command:
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.3)
            return _result("Switched window.")

        elif "minimize window" in normalized_command:
            pyautogui.hotkey("win", "down")
            time.sleep(0.3)
            return _result("Window minimized.")

        elif "maximize window" in normalized_command:
            pyautogui.hotkey("win", "up")
            time.sleep(0.3)
            return _result("Window maximized.")

        elif "close window" in normalized_command:
            pyautogui.hotkey("alt", "f4")
            time.sleep(0.3)
            return _result("Window closed.")

        elif "show desktop" in normalized_command:
            pyautogui.hotkey("win", "d")
            time.sleep(0.3)
            return _result("Desktop shown.")

        # ─────────────────────────────────────────
        # ⚡ WORKFLOW
        # ─────────────────────────────────────────

        elif "start coding session" in normalized_command:
            folder_path = os.path.join(os.path.expanduser("~"), "Desktop", "TodayWork")
            os.makedirs(folder_path, exist_ok=True)
            vscode_result = launch_app("vs code")
            chrome_result = launch_app("chrome")
            if vscode_result.success and chrome_result.success:
                return _result("Coding session started. VS Code and Chrome opened, TodayWork folder created.")
            failures = [result.message for result in [vscode_result, chrome_result] if not result.success]
            return _result(
                "Coding session started partially. "
                f"TodayWork folder created. {' '.join(failures)}"
            )

        # ─────────────────────────────────────────
        # 🎵 MUSIC
        # ─────────────────────────────────────────

        elif "play music" in normalized_command or "play song" in normalized_command:
            subprocess.run("start wmplayer", shell=True)
            _bring_window_to_front(["windows media player", "wmplayer"])
            return _result("Music player opened.")

        # ─────────────────────────────────────────
        # 💻 SYSTEM
        # ─────────────────────────────────────────

        elif "shutdown" in normalized_command:
            subprocess.run("shutdown /s /t 5", shell=True)
            return _result("PC will shut down in 5 seconds.")

        elif "restart" in normalized_command:
            subprocess.run("shutdown /r /t 5", shell=True)
            return _result("PC will restart in 5 seconds.")

        # ─────────────────────────────────────────
        # ❌ UNRECOGNIZED
        # ─────────────────────────────────────────

        return _result(f"Command not recognized: '{raw_command}'")

    except Exception as exc:
        return _result(f"System error: {exc}")
