import json
import os
import subprocess
import time
from dotenv import load_dotenv  # type: ignore[import-untyped]
from groq import Groq  # type: ignore[import-untyped]

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

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
        prompt = f"""You are an expert software architect and elite AI developer. Your task is to generate a complete, production-quality project based on the user's description.

Before writing any code, follow this internal reasoning process (do not output your reasoning):
STEP 1: Read the ENTIRE project description carefully. Never ignore details, summarize the request, or invent unrelated features.
STEP 2: Identify the project type, framework, target users, required pages, navigation, components, APIs, authentication, database, dashboard, responsiveness, animations, color theme, required libraries, and deployment requirements.
STEP 3: Mentally organize the application architecture. Plan the routing, reusable components, state management, folder structure, and scalability. Determine which external libraries are required (e.g., React Router, Axios, Firebase, Framer Motion, Zustand, Tailwind, Material UI, Chart.js, React Icons).

USER'S PROJECT DESCRIPTION:
{project_description}

CRITICAL INSTRUCTIONS:
1. USER INTENT IS ABSOLUTE: The user's description is your highest priority. Implement exactly what is requested. Never replace requested features with easier alternatives. If the user specifies themes (dark theme, glassmorphism), animations, specific dashboards, auth, databases (Firebase, MongoDB), or payment gateways, you MUST include them.
2. NO PLACEHOLDERS: Never generate placeholder code, empty pages, TODO comments, or fake implementations unless explicitly requested. Generate fully working, production-ready code.
3. DEPENDENCY AWARENESS: Naturally include imports and code consistent with the external libraries you determined are necessary.
4. CODE QUALITY: Prefer reusable components/widgets, modular files, readable naming, and production-level organization. Avoid duplicated code, giant monolithic components, and unnecessary nesting.

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
- For react: The Vite project has already been scaffolded. Only generate the application code. Do not regenerate framework or configuration files. Generate files such as src/App.jsx, and optional support files in src/components/, src/pages/, src/hooks/, src/utils/, or src/styles/. Explicitly do NOT generate package.json, package-lock.json, vite.config.js, eslint.config.js, README.md, src/main.jsx, index.html, public/index.html, or src/index.js.
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

        # ─────────────────────────────────────────
        # 🚀 VITE SCAFFOLDING FOR REACT PROJECTS
        # ─────────────────────────────────────────
        project_type = project_data.get("project_type", "").lower()
        protected_files = set()

        if project_type == "react":
            print(f"🔧 Creating Vite React project: {final_project_name}")
            try:
                # Create parent directory if needed
                parent_dir = os.path.dirname(project_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)

                # Run npm create vite
                vite_cmd = f'npm create -y vite@latest "{final_project_name}" -- --template react --eslint --no-interactive'
                print(f"   Running: {vite_cmd}")
                result = subprocess.run(
                    vite_cmd,
                    cwd=desktop,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode != 0:
                    print(f"   ⚠️ Vite scaffolding failed: {result.stderr[:200]}")
                    # Fallback: create empty folder and continue with AI-only approach
                    os.makedirs(project_path, exist_ok=True)
                else:
                    print(f"   ✅ Vite scaffolding successful")

                    # Run npm install
                    print(f"   Running: npm install")
                    install_result = subprocess.run(
                        "npm install",
                        cwd=project_path,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )

                    if install_result.returncode != 0:
                        print(f"   ⚠️ npm install failed: {install_result.stderr[:200]}")
                    else:
                        print(f"   ✅ Dependencies installed")

                    # Define protected files (Vite-generated, should not be overwritten)
                    protected_files = {
                        "package.json",
                        "package-lock.json",
                        "vite.config.js",
                        "eslint.config.js",
                        "src/main.jsx",
                        "index.html",
                        "README.md",
                        ".gitignore",
                        "public/vite.svg",
                    }
                    print(f"   🔒 Protected {len(protected_files)} Vite files from AI overwrite")

            except subprocess.TimeoutExpired:
                print(f"   ⚠️ Vite scaffolding timed out, using AI-only approach")
                os.makedirs(project_path, exist_ok=True)
            except Exception as e:
                print(f"   ⚠️ Vite scaffolding failed: {str(e)}, using AI-only approach")
                os.makedirs(project_path, exist_ok=True)
        else:
            os.makedirs(project_path, exist_ok=True)

        print(f"📁 Project folder: {final_project_name}")

        created_files = []
        structure = project_data.get("structure", {})

        for file_path, content in structure.items():
            if not content or content.strip() == "":
                continue

            # Skip protected Vite files for React projects
            if file_path in protected_files:
                print(f"   🔒 Skipping protected file: {file_path}")
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



        files_summary = ", ".join(created_files[:5])
        if len(created_files) > 5:
            files_summary += f" + {len(created_files) - 5} more"

        return (
            f"✅ AI Project Created: '{final_project_name}'\n"
            f"📂 Type: {project_data.get('project_type', 'N/A')}\n"
            f"📝 Files: {files_summary}\n"
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