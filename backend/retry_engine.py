import json
import os
import queue
import re
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass

import requests

from error_engine import extract_error, has_meaningful_error, is_success_log
from fix_engine import analyze_error, apply_fix


MAX_RETRIES = 2
MONITOR_SECONDS = 90
READINESS_SECONDS = 15


@dataclass
class ProjectRunConfig:
    command: str
    port: int | None
    kind: str


def _append(logs: list[str], message: str) -> None:
    logs.append(message)


def _read_package_scripts(project_path: str) -> tuple[str, bool]:
    package_json = os.path.join(project_path, "package.json")
    try:
        with open(package_json, "r", encoding="utf-8") as file:
            package = json.load(file)
        scripts = package.get("scripts", {})
        if "dev" in scripts:
            return "dev", "build" in scripts
        if "start" in scripts:
            return "start", "build" in scripts
    except Exception:
        pass
    return "start", False


def _detect_project(project_path: str) -> ProjectRunConfig | None:
    files = set(os.listdir(project_path))

    if "package.json" in files:
        script, has_build = _read_package_scripts(project_path)
        port = 5173 if script == "dev" else 3000
        command = f"npm install && npm run {script}"
        if has_build:
            command = f"npm install && npm run build && npm run {script}"
        return ProjectRunConfig(
            command=command,
            port=port,
            kind=f"npm:{script}",
        )

    if "manage.py" in files:
        return ProjectRunConfig(
            command="python manage.py runserver",
            port=8000,
            kind="django",
        )

    if "app.py" in files:
        return ProjectRunConfig(
            command="python app.py",
            port=5000,
            kind="flask",
        )

    if "main.py" in files:
        return ProjectRunConfig(
            command="python main.py",
            port=None,
            kind="python",
        )

    if "index.html" in files:
        return ProjectRunConfig(
            command="",
            port=None,
            kind="static-html",
        )

    return None


def _verify_localhost(port: int | None) -> bool:
    if port is None:
        return True

    deadline = time.time() + READINESS_SECONDS
    url = f"http://127.0.0.1:{port}"
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code < 500:
                return True
        except Exception:
            time.sleep(0.7)
    return False


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _start_reader(process: subprocess.Popen, output_queue: queue.Queue) -> threading.Thread:
    def _reader() -> None:
        if process.stdout is None:
            return
        for line in iter(process.stdout.readline, ""):
            output_queue.put(line.rstrip())
        output_queue.put(None)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    return thread


def _run_once(project_path: str, config: ProjectRunConfig) -> dict:
    logs: list[str] = []
    combined_output: list[str] = []

    if config.kind == "static-html":
        index_file = os.path.join(project_path, "index.html")
        webbrowser.open(f"file:///{index_file}")
        return {
            "success": True,
            "error": None,
            "logs": ["[SUCCESS] Static HTML project opened in browser"],
        }

    _append(logs, f"[SYS] Running: {config.command}")
    process = subprocess.Popen(
        config.command,
        cwd=project_path,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    output_queue: queue.Queue = queue.Queue()
    _start_reader(process, output_queue)
    deadline = time.time() + MONITOR_SECONDS
    success_seen = False
    stream_closed = False

    while time.time() < deadline:
        try:
            line = output_queue.get(timeout=0.25)
        except queue.Empty:
            line = ""

        if line is None:
            stream_closed = True
        elif line:
            combined_output.append(line)
            if len(combined_output) <= 80:
                logs.append(f"[SYS] {line}")
            current_output = "\n".join(combined_output[-120:])
            if has_meaningful_error(current_output):
                time.sleep(1)
                while not output_queue.empty():
                    extra = output_queue.get_nowait()
                    if extra:
                        combined_output.append(extra)
                _terminate(process)
                error = extract_error("\n".join(combined_output[-160:]))
                return {"success": False, "error": error, "logs": logs}
            if is_success_log(current_output):
                success_seen = True

        if success_seen and _verify_localhost(config.port):
            logs.append("[SUCCESS] Localhost responded successfully")
            return {"success": True, "error": None, "logs": logs}

        if process.poll() is not None and stream_closed:
            break

    if process.poll() is None and config.port and _verify_localhost(config.port):
        logs.append("[SUCCESS] Localhost responded successfully")
        return {"success": True, "error": None, "logs": logs}

    if process.poll() is None:
        _terminate(process)
        return {
            "success": False,
            "error": {
                "has_error": True,
                "category": "timeout",
                "root_message": "Project did not become ready in time.",
                "error_text": "\n".join(combined_output[-120:]),
            },
            "logs": logs + ["[ERROR] Project did not become ready in time"],
        }

    returncode = process.returncode
    output = "\n".join(combined_output[-160:])
    if returncode == 0:
        logs.append("[SUCCESS] Project command completed successfully")
        return {"success": True, "error": None, "logs": logs}

    error = extract_error(output)
    if not error.get("has_error"):
        error = {
            "has_error": True,
            "category": "process",
            "root_message": f"Process exited with code {returncode}",
            "error_text": output,
        }
    return {"success": False, "error": error, "logs": logs}


def run_project_with_repair(project_path: str, project_name: str | None = None, max_retries: int = MAX_RETRIES):
    config = _detect_project(project_path)
    if config is None:
        return None

    project_label = project_name or os.path.basename(project_path)
    workflow_logs: list[str] = [
        f"[SYS] Autonomous run started for {project_label}",
        f"[SYS] Project type detected: {config.kind}",
    ]

    for attempt in range(max_retries + 1):
        workflow_logs.append(f"[SYS] Run attempt {attempt + 1}/{max_retries + 1}")
        run_result = _run_once(project_path, config)
        workflow_logs.extend(run_result.get("logs", []))

        if run_result.get("success"):
            port_line = f"\nLocalhost: http://127.0.0.1:{config.port}" if config.port else ""
            return {
                "result": f"Project fixed successfully.{port_line}",
                "logs": workflow_logs,
                "options": [],
            }

        error = run_result.get("error") or {}
        error_text = error.get("error_text") or error.get("root_message") or ""
        if not error_text.strip():
            workflow_logs.append("[ERROR] No actionable error text was captured")
            break

        workflow_logs.append("[SYS] Detecting error...")
        workflow_logs.append(f"[ERROR] {error.get('root_message', 'Unknown project error')}")

        if attempt >= max_retries:
            workflow_logs.append("[ERROR] Max retry count reached")
            break

        workflow_logs.append("[AI] Analyzing compile/runtime error...")
        analysis = analyze_error(error_text)
        workflow_logs.append(f"[AI] Root cause: {analysis.get('root_cause', 'Unknown')}")
        workflow_logs.append(f"[AI] Exact fix: {analysis.get('exact_fix', 'No safe fix available')}")

        fix_result = apply_fix(project_path, analysis)
        workflow_logs.extend(fix_result.get("logs", []))

        if not fix_result.get("changed"):
            workflow_logs.append("[ERROR] Automatic repair stopped: no safe change was available")
            break

        workflow_logs.append("[SYS] Restarting project after fix...")

    return {
        "result": "Project repair failed. Review the autonomous logs for details.",
        "logs": workflow_logs,
        "options": [],
    }
