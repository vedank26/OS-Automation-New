import json
import os
import re
import shutil
import subprocess
import time
from typing import Any

from dotenv import load_dotenv
from groq import Groq


load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_api_key = os.getenv("GROQ_API_KEY")
_client = Groq(api_key=_api_key) if _api_key else None

SAFE_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9_./@+-]+$")


def _clean_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = text.replace("```", "").strip()
    if "{" in text and "}" in text:
        text = text[text.find("{"): text.rfind("}") + 1]
    return json.loads(text)


def _heuristic_analysis(error_text: str) -> dict:
    actions = []
    root_cause = "The project failed during execution."
    exact_fix = "Review the captured error and apply a safe local fix."
    # matched=True means a known deterministic error was detected and Groq can be bypassed
    matched = False

    missing_relative = re.search(
        r"(?:Can't resolve|Could not resolve)\s+['\"](\.\.[^'\"]+)['\"]",
        error_text,
        re.IGNORECASE,
    )
    if missing_relative:
        matched = True
        missing_path = missing_relative.group(1).replace("/", os.sep)
        root_cause = f"Missing local file {missing_relative.group(1)}."
        exact_fix = f"Create {missing_relative.group(1)} so the import can resolve."
        if missing_path.endswith(".css"):
            content = "/* FlowForge auto-created missing stylesheet. */\n"
        elif missing_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            content = "export default function Placeholder() { return null; }\n"
        else:
            content = ""
        actions.append({
            "type": "create_file",
            "path": missing_path,
            "content": content,
        })

    missing_python = re.search(
        r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]",
        error_text,
    )
    if missing_python:
        matched = True
        package = missing_python.group(1).split(".")[0]
        root_cause = f"Missing Python package {package}."
        exact_fix = f"Install Python package {package}."
        actions.append({"type": "install_python_package", "package": package})

    # Expanded npm pattern: covers Vite, Rolldown, Rollup, Node resolver errors
    # Supports standard, scoped (@scope/pkg), and nested (pkg/subpath) package names
    missing_npm = re.search(
        r"(?:failed to resolve import|Can't resolve|Could not resolve|Cannot find module)\s+['\"]([^.'\"][^'\"]*)['\"]",
        error_text,
        re.IGNORECASE,
    )
    if missing_npm:
        matched = True
        raw = missing_npm.group(1)
        # For scoped packages (@scope/pkg or @scope/pkg/subpath), keep first two segments
        if raw.startswith("@"):
            parts = raw.split("/")
            package = "/".join(parts[:2])
        else:
            # For standard and nested imports (pkg or pkg/subpath), keep first segment only
            package = raw.split("/")[0]
        root_cause = f"Missing npm package {package}."
        exact_fix = f"Install npm package {package}."
        actions.append({"type": "install_npm_package", "package": package})

    return {
        "root_cause": root_cause,
        "exact_fix": exact_fix,
        "files_to_modify": [],
        "actions": actions,
        "matched": matched,
    }


def analyze_error(error_text: str) -> dict:
    # Step 1: Run deterministic heuristic analysis first
    heuristic = _heuristic_analysis(error_text)

    # Step 2: If the heuristic confidently matched a known error, bypass Groq entirely
    if heuristic.get("matched"):
        result = heuristic.copy()
        result.pop("matched", None)  # Strip internal flag before returning to caller
        return result

    # Step 3: No deterministic match — fall back to Groq for complex errors
    if not _client:
        result = heuristic.copy()
        result.pop("matched", None)
        return result

    prompt = f"""You are an expert software engineer.

Analyze this error:

{error_text}

Return ONLY valid JSON with this structure:
{{
  "root_cause": "short explanation",
  "exact_fix": "short exact fix",
  "files_to_modify": [
    {{"path": "relative/path.ext", "content": "complete corrected file content"}}
  ],
  "actions": [
    {{"type": "create_file", "path": "relative/path.ext", "content": "file content"}},
    {{"type": "install_npm_package", "package": "package-name"}},
    {{"type": "install_python_package", "package": "package-name"}}
  ]
}}

Only include safe project-local file edits. Do not include unrelated refactors."""

    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You analyze build/runtime errors and return strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        analysis = _clean_json(response.choices[0].message.content)
    except Exception:
        result = heuristic.copy()
        result.pop("matched", None)
        return result

    # Merge heuristic actions into Groq result if Groq returned nothing actionable
    if not analysis.get("actions") and not analysis.get("files_to_modify"):
        analysis["actions"] = heuristic.get("actions", [])
    return analysis


def _safe_project_path(project_path: str, relative_path: str) -> str:
    base = os.path.abspath(project_path)
    target = os.path.abspath(os.path.join(base, relative_path))
    if target != base and not target.startswith(base + os.sep):
        raise ValueError(f"Unsafe path outside project: {relative_path}")
    return target


def _backup_file(project_path: str, target: str) -> None:
    if not os.path.exists(target):
        return
    base = os.path.abspath(project_path)
    rel = os.path.relpath(target, base)
    backup_root = os.path.join(base, ".flowforge_backups", time.strftime("%Y%m%d_%H%M%S"))
    backup_path = os.path.join(backup_root, rel)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(target, backup_path)


def _write_project_file(project_path: str, relative_path: str, content: str, overwrite: bool) -> str:
    target = _safe_project_path(project_path, relative_path)
    if os.path.exists(target) and not overwrite:
        return f"[FIX] File already exists, skipped: {relative_path}"

    _backup_file(project_path, target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as file:
        file.write(content)
    return f"[FIX] Wrote {relative_path}"


def _run_install(project_path: str, command: list[str], package: str) -> str:
    if not SAFE_PACKAGE_RE.match(package):
        return f"[FIX] Skipped unsafe package name: {package}"

    executable = shutil.which(command[0])
    if not executable:
        return f"[FIX] Installer not found: {command[0]}"

    completed = subprocess.run(
        [executable, *command[1:], package],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode == 0:
        return f"[FIX] Installed {package}"
    return f"[ERROR] Failed to install {package}: {(completed.stderr or completed.stdout).strip()[:400]}"


def apply_fix(project_path: str, analysis: dict[str, Any]) -> dict:
    logs = []
    changed = False

    for file_patch in analysis.get("files_to_modify", []) or []:
        relative_path = file_patch.get("path")
        content = file_patch.get("content")
        if not relative_path or content is None:
            continue
        logs.append(_write_project_file(project_path, relative_path, content, overwrite=True))
        changed = True

    for action in analysis.get("actions", []) or []:
        action_type = action.get("type")
        try:
            if action_type == "create_file":
                logs.append(
                    _write_project_file(
                        project_path,
                        action.get("path", ""),
                        action.get("content", ""),
                        overwrite=False,
                    )
                )
                changed = True
            elif action_type == "install_npm_package":
                logs.append(_run_install(project_path, ["npm", "install"], action.get("package", "")))
                changed = True
            elif action_type == "install_python_package":
                logs.append(_run_install(project_path, ["pip", "install"], action.get("package", "")))
                changed = True
        except Exception as exc:
            logs.append(f"[ERROR] Fix action failed: {exc}")

    if not logs:
        logs.append("[FIX] No safe automatic fix was available")

    return {"changed": changed, "logs": logs}
