import json
import os
import subprocess
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None


def create_ai_project(project_description: str, project_name: str = None):
    """
    Creates a complete project using AI:
    1. Generates project structure based on description
    2. Creates all files and folders
    3. Writes AI-generated code
    4. Opens the project in VS Code
    """

    if not client:
        return "❌ Groq API key is missing. Please add GROQ_API_KEY to your .env file in the backend folder."

    try:
        prompt = f"""You are a project generator. Create a JSON response for: {project_description}

Return ONLY this exact JSON structure (no extra text, no code blocks, no explanations):

{{
  "project_name": "snake_game",
  "project_type": "python",
  "description": "A simple terminal-based snake game",
  "structure": {{
    "main.py": "FULL_PYTHON_CODE_HERE",
    "README.md": "# Project Title\\n\\nInstructions here"
  }}
}}

Rules:
- project_name: lowercase_with_underscores for python, lowercase-with-hyphens for web
- project_type: python, react, html, nodejs, or flutter
- structure: Each file path maps to COMPLETE working code
- Put actual code in the values, not placeholders
- For python: include main.py and README.md (add requirements.txt if needed)
- For react: include package.json, src/App.js, src/index.js, public/index.html
- For html: include index.html, style.css, script.js

CRITICAL: Your response must START with {{ and END with }}. Nothing else."""

        print("🤖 AI is analyzing your project idea...")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON generator. You ONLY output valid JSON. Never output code directly. Never use markdown. Never add explanations.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.5,
            max_tokens=8000,
            response_format={"type": "json_object"},
        )

        ai_output = response.choices[0].message.content.strip()

        # Clean markdown code blocks if present
        if ai_output.startswith("```json"):
            ai_output = ai_output.replace("```json", "").replace("```", "").strip()
        elif ai_output.startswith("```"):
            ai_output = ai_output.replace("```", "").strip()

        # Find JSON boundaries
        if "{" in ai_output and "}" in ai_output:
            start = ai_output.find("{")
            end = ai_output.rfind("}") + 1
            ai_output = ai_output[start:end]

        print(f"📄 Received {len(ai_output)} characters from AI")

        project_data = json.loads(ai_output)

        if "structure" not in project_data or not project_data["structure"]:
            return "❌ AI didn't generate any files. Try again with a more specific description."

        final_project_name = (
            project_name if project_name else project_data.get("project_name", "my_project")
        )
        final_project_name = final_project_name.replace(" ", "_").lower()

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        project_path = os.path.join(desktop, final_project_name)
        os.makedirs(project_path, exist_ok=True)
        print(f"📁 Created project folder: {final_project_name}")

        created_files = []
        structure = project_data.get("structure", {})

        for file_path, content in structure.items():
            if not content or content.strip() == "":
                continue

            full_path = os.path.join(project_path, file_path)
            parent_dir = os.path.dirname(full_path)
            if parent_dir and parent_dir != project_path:
                os.makedirs(parent_dir, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            created_files.append(file_path)
            print(f"   ✅ Created: {file_path}")

        if not created_files:
            return "❌ No files were created. AI response might be invalid."

        # Open project in VS Code
        time.sleep(0.5)
        subprocess.Popen(f'code "{project_path}"', shell=True)

        time.sleep(1)
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle("Visual Studio Code")
            if windows:
                windows[0].activate()
        except Exception:
            pass

        files_summary = ", ".join(created_files[:5])
        if len(created_files) > 5:
            files_summary += f" + {len(created_files) - 5} more"

        return (
            f"✅ AI Project Created: '{final_project_name}'\n"
            f"📂 Type: {project_data.get('project_type', 'N/A')}\n"
            f"📝 Files: {files_summary}\n"
            f"💻 Opened in VS Code\n"
            f"📍 Location: Desktop/{final_project_name}"
        )

    except json.JSONDecodeError as e:
        error_file = os.path.join(os.path.expanduser("~"), "Desktop", "ai_error_output.txt")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(ai_output)
        return (
            f"❌ AI response parsing failed.\n"
            f"Error: {str(e)}\n"
            f"Raw output saved to: Desktop/ai_error_output.txt\n"
            f"Try the command again."
        )

    except Exception as e:
        return f"❌ Project creation failed: {str(e)}"


def parse_create_command(command: str):
    """
    Extracts project description and optional name from a natural language command.

    Examples:
    - "create calculator project using python"     -> ("calculator using python", None)
    - "create project of calculator using python"  -> ("calculator using python", None)
    - "build attendance tracker using html css js" -> ("attendance tracker using html css js", None)
    - "make a snake game in python"                -> ("snake game in python", None)
    - "create project named todo-app for task mgr" -> ("task manager", "todo-app")
    - "build me a calculator"                      -> ("calculator", None)
    """
    command = command.lower().strip()

    # ── Step 1: Remove trigger words longest-first ─────────────────────────
    for trigger in [
        "create ai project",
        "create project for",
        "create project of",        # ✅ "create project of calculator"
        "create project named",
        "create project called",
        "create project",
        "build project for",
        "build project of",
        "build project",
        "make project for",
        "make project of",
        "make project",
        "make me an",
        "make me a",
        "make me",
        "build me an",
        "build me a",
        "build me",
        "make an",
        "make a",
        "create an",
        "create a",
        "build an",
        "build a",
        "create",
        "build",
        "make",
    ]:
        if command.startswith(trigger):
            command = command[len(trigger):].strip()
            break

    # ── Step 2: Strip leftover connector words at the start ────────────────
    # Handles: "of calculator", "for a snake game", "me a todo app"
    for connector in ["of ", "for a ", "for an ", "for ", "me a ", "me an ", "me "]:
        if command.startswith(connector):
            command = command[len(connector):].strip()
            break

    # ── Step 3: Extract optional project name ──────────────────────────────
    project_name = None
    description = command

    if "named" in command:
        parts = command.split("named", 1)
        description = parts[0].strip()
        if len(parts) > 1:
            name_part = parts[1].strip()
            if "for" in name_part:
                project_name = name_part.split("for")[0].strip()
                description = name_part.split("for")[1].strip() + " " + description
            else:
                project_name = name_part

    elif "called" in command:
        parts = command.split("called", 1)
        description = parts[0].strip()
        if len(parts) > 1:
            name_part = parts[1].strip()
            if "for" in name_part:
                project_name = name_part.split("for")[0].strip()
                description = name_part.split("for")[1].strip() + " " + description
            else:
                project_name = name_part

    # ── Step 4: Clean up ───────────────────────────────────────────────────
    if project_name:
        project_name = project_name.strip().replace(" ", "-")

    description = description.strip()
    for prefix in ["for ", "of "]:
        if description.startswith(prefix):
            description = description[len(prefix):].strip()

    return description, project_name