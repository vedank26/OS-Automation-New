import json
import os
import re
import subprocess
import webbrowser
from ai_project_creator import create_ai_project, parse_create_command
from app_launcher import launch_app
from retry_engine import run_project_with_repair
from utils.os_utils import _result, _bring_window_to_front


PROJECT_KEYWORDS = {
    "python", "html", "css", "javascript", "js", "react",
    "nodejs", "node", "flutter", "django", "flask",
    "project", "app", "website", "game", "tracker",
    "dashboard", "calculator", "todo", "portfolio",
    "chatbot", "api", "backend", "frontend",
}


def is_project_command(command: str) -> bool:
    """Check if command is an AI project creation request"""
    has_verb = re.search(r"\b(create|build|make)\b", command)
    if not has_verb:
        return False
    words = set(command.lower().split())
    return bool(words & PROJECT_KEYWORDS)


def can_handle_folder_creation(normalized_command: str) -> bool:
    """Check if command is a folder creation request"""
    return "create folder" in normalized_command


def handle_folder_creation(raw_command: str) -> dict:
    """Handle folder creation command"""
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


def can_handle_react_creation(normalized_command: str) -> bool:
    """Check if command is a React project creation request"""
    return (
        "create react app" in normalized_command
        or "create react project" in normalized_command
    )


def handle_react_creation(raw_command: str) -> dict:
    """Handle React project creation command"""
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


def can_handle_python_creation(normalized_command: str) -> bool:
    """Check if command is a Python project creation request"""
    return (
        "create python project" in normalized_command
        and "using" not in normalized_command
        and "for" not in normalized_command
    )


def handle_python_creation(raw_command: str) -> dict:
    """Handle Python project creation command"""
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


def can_handle_project_execution(normalized_command: str) -> bool:
    """Check if command is a project execution request"""
    return (
        any(phrase in normalized_command for phrase in [
            "run project", "run the project", "execute project", "start project",
            "run my project", "start the app", "start app", "npm run dev",
            "run app", "execute my project", "run this project", "execute the project",
            "launch project", "launch the project", "launch app", "run the app",
            "start my project", "run latest project"
        ])
        or normalized_command.startswith("run ")
        or normalized_command.startswith("start ")
    )


def handle_project_execution(normalized_command: str) -> dict:
    """Handle project execution command"""
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


def can_handle_ai_creation(normalized_command: str) -> bool:
    """Check if command is an AI project creation request"""
    # This function will be called from automation_1.py where _is_project_command is checked
    # For now, this is a placeholder - the actual check is done by _is_project_command in automation_1.py
    return False


def handle_ai_creation(raw_command: str, normalized_command: str) -> dict:
    """Handle AI project creation command"""
    description, project_name = parse_create_command(raw_command)
    if description:
        creation_result = create_ai_project(description, project_name)
        if "AI Project Created" in creation_result:
            try:
                loc_line = [line for line in creation_result.split('\n') if "Location: Desktop/" in line]
                if loc_line:
                    folder_name = loc_line[0].split("Desktop/")[1].strip()
                    # Direct function call instead of recursion through execute_command
                    run_result = handle_project_execution(f"run {folder_name}")
                    if isinstance(run_result, dict) and "result" in run_result:
                        # Open VS Code AFTER project execution is initiated.
                        # Path reconstructed from folder_name (Option A — no signature change).
                        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                        project_path = os.path.join(desktop, folder_name)
                        subprocess.Popen(f'code "{project_path}"', shell=True)
                        creation_result += "\n\n" + run_result["result"]
                        return {
                            "result": creation_result,
                            "logs": run_result.get("logs", []),
                            "options": run_result.get("options", []),
                        }
            except Exception:
                pass
        return {
            "result": creation_result,
            "logs": [],
            "options": [],
        }
    return _result(
        "Please specify what to build.\n"
        "Example: 'create calculator project using python'\n"
        "Example: 'build attendance tracker using html css js'"
    )

