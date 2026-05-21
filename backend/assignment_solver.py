import os
import re
import json
import time
import base64
import tempfile
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ─────────────────────────────────────────
# Groq client (reuses existing env key)
# ─────────────────────────────────────────
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────
# Command trigger phrases — expanded
# ─────────────────────────────────────────
ASSIGNMENT_TRIGGERS = [
    "complete assignment",
    "complete my assignment",
    "do my assignment",
    "do assignment",
    "solve assignment",
    "solve my assignment",
    "finish assignment",
    "finish my assignment",
    "answer assignment",
    "answer my assignment",
    "write assignment",
    "write my assignment",
    "help with assignment",
    "help me with assignment",
    "solve homework",
    "do homework",
    "complete homework",
]

# ─────────────────────────────────────────
# Subject detection keywords
# ─────────────────────────────────────────
SUBJECT_KEYWORDS = {
    "mathematics": ["math", "maths", "mathematics", "calculus", "algebra", "trigonometry", "geometry", "statistics", "probability", "derivative", "integral", "equation", "matrix", "linear algebra"],
    "physics": ["physics", "mechanics", "thermodynamics", "optics", "electromagnetism", "quantum", "relativity", "wave", "force", "energy", "momentum"],
    "chemistry": ["chemistry", "organic", "inorganic", "reaction", "molecule", "compound", "element", "bond", "acid", "base", "redox"],
    "biology": ["biology", "cell", "genetics", "evolution", "ecology", "anatomy", "physiology", "dna", "protein", "enzyme"],
    "computer_science": ["programming", "coding", "algorithm", "data structure", "python", "java", "c++", "javascript", "database", "os", "operating system", "network", "compiler"],
    "english": ["essay", "grammar", "literature", "poem", "story", "writing", "comprehension", "vocabulary", "shakespeare"],
    "history": ["history", "civilization", "war", "revolution", "empire", "ancient", "medieval", "modern history"],
    "economics": ["economics", "microeconomics", "macroeconomics", "gdp", "inflation", "market", "supply", "demand", "fiscal", "monetary"],
    "engineering": ["engineering", "circuit", "signal", "control system", "fluid", "thermodynamics", "structural", "mechanical"],
}


def _detect_subject(text: str) -> str:
    """Detect the academic subject from assignment content or description."""
    text_lower = text.lower()
    scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[subject] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


# ─────────────────────────────────────────
# Platform-independent path helpers
# ─────────────────────────────────────────

def _get_real_desktop() -> str:
    """
    Gets the Desktop path cross-platform.
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        desktop, _ = winreg.QueryValueEx(key, "Desktop")
        winreg.CloseKey(key)
        if os.path.isdir(desktop):
            return desktop
    except (ImportError, Exception):
        pass

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return home


def _get_search_roots() -> list[str]:
    """Returns all meaningful locations to search for a file."""
    home = os.path.expanduser("~")
    roots = []

    priority_dirs = [
        _get_real_desktop(),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "OneDrive"),
        home,
    ]
    for d in priority_dirs:
        if os.path.isdir(d) and d not in roots:
            roots.append(d)

    try:
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.isdir(drive) and drive not in roots:
                roots.append(drive)
    except Exception:
        pass

    for mount in ["/mnt", "/media", "/Volumes"]:
        if os.path.isdir(mount):
            try:
                for entry in os.listdir(mount):
                    full = os.path.join(mount, entry)
                    if os.path.isdir(full) and full not in roots:
                        roots.append(full)
            except PermissionError:
                pass

    return roots


# ─────────────────────────────────────────
# Command parsing
# ─────────────────────────────────────────

def is_assignment_command(command: str) -> bool:
    """Return True if the command is an assignment completion request."""
    cmd = command.lower().strip()
    return any(trigger in cmd for trigger in ASSIGNMENT_TRIGGERS)


def is_description_only_command(command: str) -> bool:
    """Returns True if the command contains a description (not just a filename)."""
    description = _extract_description_or_filename(command)
    if description is None:
        return False

    has_extension = bool(re.search(r'\.\w{1,5}$', description.strip()))
    word_count = len(description.split())

    if has_extension and word_count <= 3:
        return False

    sentence_indicators = [
        "about", "on", "regarding", "for", "topic", "question",
        "chapter", "unit", "subject", "write", "explain", "describe",
        "discuss", "analyze", "compare", "define", "list", "calculate",
    ]
    desc_lower = description.lower()
    has_sentence_word = any(ind in desc_lower for ind in sentence_indicators)

    if word_count > 5 or has_sentence_word:
        return True

    return False


def _extract_description_or_filename(command: str) -> str | None:
    """Extract everything after the trigger phrase."""
    cmd = command.strip()

    for trigger in sorted(ASSIGNMENT_TRIGGERS, key=len, reverse=True):
        if trigger in cmd.lower():
            idx = cmd.lower().find(trigger)
            remainder = cmd[idx + len(trigger):].strip()
            filler = r"^(called|named|file|for|my|the|:)\s+"
            remainder = re.sub(filler, "", remainder, flags=re.IGNORECASE).strip()
            return remainder if remainder else None

    return None


def parse_filename(command: str) -> str | None:
    """Extract the filename from the command."""
    remainder = _extract_description_or_filename(command)
    if remainder is None:
        return None

    has_extension = bool(re.search(r'\.\w{1,5}$', remainder.strip()))
    word_count = len(remainder.split())

    if has_extension and word_count <= 3:
        return remainder.strip()

    if word_count <= 3 and not any(
        w in remainder.lower()
        for w in ["about", "on", "regarding", "write", "explain", "describe", "discuss", "topic", "question"]
    ):
        return remainder.strip()

    return None


def parse_description(command: str) -> str | None:
    """Extract the assignment description from the command."""
    if not is_description_only_command(command):
        return None

    remainder = _extract_description_or_filename(command)
    if remainder is None:
        return None

    filler = r"^(called|named|file|for|my|the|:|about|on|regarding)\s+"
    cleaned = re.sub(filler, "", remainder, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else remainder.strip()


# ─────────────────────────────────────────
# File finder
# ─────────────────────────────────────────

def _find_file(filename: str) -> str | None:
    """Searches for `filename` across common user directories."""
    lower_fn = filename.lower()
    base_fn = os.path.splitext(lower_fn)[0]
    has_ext = bool(os.path.splitext(lower_fn)[1])

    SKIP_DIRS = {
        "windows", "system32", "syswow64", "program files",
        "program files (x86)", "programdata", "appdata",
        "$recycle.bin", "recovery", "perflogs",
        "node_modules", ".git", "__pycache__",
        "venv", ".venv", "env", ".env",
    }

    roots = _get_search_roots()
    searched_paths = set()

    for root in roots:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                real_dirpath = os.path.realpath(dirpath)
                if real_dirpath in searched_paths:
                    dirnames.clear()
                    continue
                searched_paths.add(real_dirpath)

                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in SKIP_DIRS
                ]

                for fname in filenames:
                    lower_fname = fname.lower()
                    base_fname = os.path.splitext(lower_fname)[0]

                    if lower_fname == lower_fn:
                        return os.path.join(dirpath, fname)

                    if not has_ext and base_fname == base_fn:
                        return os.path.join(dirpath, fname)

        except PermissionError:
            continue
        except Exception:
            continue

    return None


# ─────────────────────────────────────────
# File reader — supports multiple formats + images
# ─────────────────────────────────────────

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}


def _is_image_file(filepath: str) -> bool:
    """Return True if the file is an image based on extension."""
    return os.path.splitext(filepath)[1].lower() in IMAGE_EXTENSIONS


def _read_file(filepath: str) -> str:
    """Read content from a file. Supports multiple formats including images."""
    ext = os.path.splitext(filepath)[1].lower()

    plain_text_exts = {
        ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
        ".html", ".css", ".json", ".csv", ".xml", ".yaml", ".yml",
        ".java", ".c", ".cpp", ".cs", ".go", ".rs", ".rb", ".php",
        ".r", ".sql", ".sh", ".bat", ".ps1", ".dart", ".swift",
        ".kt", ".scala", ".tex", ".log", ".ini", ".cfg", ".conf",
        ".env", ".toml",
    }
    if ext in plain_text_exts:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    if ext == ".docx":
        try:
            import docx
            doc = docx.Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError("Run: pip install python-docx")

    if ext == ".pdf":
        try:
            import fitz
            pdf = fitz.open(filepath)
            text = "".join(page.get_text() for page in pdf)
            pdf.close()
            return text
        except ImportError:
            raise RuntimeError("Run: pip install PyMuPDF")

    if ext in (".xlsx", ".xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, data_only=True)
            lines = []
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                lines.append(f"=== Sheet: {sheet} ===")
                for row in ws.iter_rows(values_only=True):
                    lines.append(
                        "\t".join(str(c) if c is not None else "" for c in row)
                    )
            return "\n".join(lines)
        except ImportError:
            raise RuntimeError("Run: pip install openpyxl")

    # ── Images — Groq Vision model ────────────────────────────────────────
    if ext in IMAGE_EXTENSIONS:
        return _read_image(filepath)

    raise RuntimeError(
        f"Unsupported file type '{ext}'. "
        "Supported: .txt .md .py .js .html .pdf .docx .xlsx .csv .json "
        ".png .jpg .jpeg .bmp .webp"
    )


# ─────────────────────────────────────────
# Image reader — uses Groq Vision model
# ─────────────────────────────────────────

def _read_image(filepath: str) -> str:
    """
    Read an assignment image using Groq's vision model.
    Encodes the image as base64 and sends it to the vision-capable LLM,
    which extracts all text, questions, and content from the image.
    """
    ext = os.path.splitext(filepath)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    mime_type = mime_map.get(ext, "image/jpeg")

    with open(filepath, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    data_url = f"data:{mime_type};base64,{image_data}"

    print(f"[Assignment Solver] Reading image with Groq Vision: {os.path.basename(filepath)}")

    response = _client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise document reader. "
                    "The user will provide an image of an assignment, handwritten notes, or printed document. "
                    "Your job is to extract ALL text, questions, formulas, diagrams descriptions, and content from the image. "
                    "Reproduce the content exactly as written — do not solve or answer anything. "
                    "If the image contains handwritten text, transcribe it as accurately as possible. "
                    "If there are numbered questions, preserve the numbering. "
                    "If there are formulas, write them in a readable text format. "
                    "If something is unclear, make your best attempt and note it in brackets like [unclear]."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Please read and extract all the content from this assignment image. "
                            "Include every question, instruction, and piece of text you can see. "
                            "Preserve numbering and formatting as closely as possible."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            },
        ],
        temperature=0.2,
        max_tokens=4000,
    )

    extracted = response.choices[0].message.content.strip()
    if not extracted:
        raise RuntimeError("Could not extract any text from the image. The image may be unclear or empty.")

    print(f"[Assignment Solver] Extracted {len(extracted)} characters from image")
    return extracted


# ─────────────────────────────────────────
# Image generator — Pollinations.ai (FREE)
# ─────────────────────────────────────────

def _generate_image(prompt: str, index: int) -> str | None:
    """
    Generate an image using Pollinations.ai (completely free, no API key).
    Returns the path to the saved image file, or None on failure.

    Pollinations.ai works via a simple GET request:
      https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024
    """
    try:
        clean_prompt = prompt.strip()
        full_prompt = f"{clean_prompt}, educational diagram, clean style, labeled, professional, high quality"

        # Use a unique seed based on index + time for reproducibility
        import hashlib
        seed = int(hashlib.md5(clean_prompt.encode()).hexdigest()[:8], 16)
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(full_prompt)}?width=1024&height=1024&nologo=true&seed={seed}"

        print(f"[Assignment Solver] Generating image {index}: {clean_prompt[:80]}...")
        print(f"[Assignment Solver]   URL: {url[:120]}...")

        response = requests.get(url, timeout=90)
        if response.status_code != 200:
            print(f"   Warning: Image generation returned status {response.status_code}")
            return None

        # Check we got actual image data (not an error page)
        content_type = response.headers.get("content-type", "")
        content_len = len(response.content)
        print(f"[Assignment Solver]   Response: status={response.status_code}, content-type={content_type}, size={content_len}")

        # If content is too small, it's likely an error
        if content_len < 500:
            print(f"   Warning: Response too small ({content_len} bytes), likely not an image")
            # Print first 200 chars to help debug
            try:
                print(f"   Response body preview: {response.text[:200]}")
            except Exception:
                pass
            return None

        # Save to temp file
        temp_dir = tempfile.gettempdir()
        img_path = os.path.join(temp_dir, f"assignment_diagram_{index}_{os.getpid()}.png")

        with open(img_path, "wb") as f:
            f.write(response.content)

        file_size = os.path.getsize(img_path)
        if file_size < 2000:
            print(f"   Warning: Generated image too small ({file_size} bytes), likely an error")
            os.remove(img_path)
            return None

        print(f"   Image saved: {file_size:,} bytes")
        return img_path

    except requests.Timeout:
        print(f"   Warning: Image generation timed out")
        return None
    except Exception as e:
        print(f"   Warning: Image generation failed: {e}")
        return None


def _extract_diagram_markers(text: str) -> list[str]:
    """
    Extract all [DIAGRAM: description] markers from the text.
    Returns a list of description strings.
    """
    pattern = r'\[DIAGRAM:\s*(.+?)\]'
    return re.findall(pattern, text)


# ─────────────────────────────────────────
# AI solver — multi-pass for quality
# ─────────────────────────────────────────

def _build_system_prompt(subject: str, source_type: str, instructions: str = "") -> str:
    """Build a subject-specific, source-aware system prompt."""

    subject_instructions = {
        "mathematics": (
            "You are solving a MATHEMATICS assignment. Follow these rules strictly:\n"
            "- Show ALL step-by-step working. Never skip steps.\n"
            "- Clearly label each step (Step 1, Step 2, etc.).\n"
            "- State all formulas BEFORE using them.\n"
            "- Double-check every calculation.\n"
            "- Box or highlight final answers.\n"
            "- Use proper mathematical notation.\n"
        ),
        "physics": (
            "You are solving a PHYSICS assignment. Follow these rules strictly:\n"
            "- State the given quantities and what to find.\n"
            "- Identify the relevant physics principle/formula.\n"
            "- Show complete step-by-step derivation.\n"
            "- Include units at every step.\n"
            "- Verify the answer with dimensional analysis.\n"
            "- When a force diagram, circuit diagram, ray diagram, or similar visual would help, "
            "insert a [DIAGRAM: ...] marker.\n"
        ),
        "chemistry": (
            "You are solving a CHEMISTRY assignment. Follow these rules strictly:\n"
            "- Show balanced equations for all reactions.\n"
            "- Include states of matter (s, l, g, aq).\n"
            "- Show all calculation steps with units.\n"
            "- Explain the underlying chemical principles.\n"
            "- Use proper IUPAC nomenclature.\n"
        ),
        "biology": (
            "You are solving a BIOLOGY assignment. Follow these rules strictly:\n"
            "- Use precise scientific terminology.\n"
            "- Explain processes step-by-step.\n"
            "- Include relevant examples.\n"
            "- Describe structures and functions clearly.\n"
            "- Reference classifications and taxonomies where applicable.\n"
            "- When a diagram of a cell, organ, process flow, or similar visual would help, "
            "insert a [DIAGRAM: ...] marker.\n"
        ),
        "computer_science": (
            "You are solving a COMPUTER SCIENCE assignment. Follow these rules strictly:\n"
            "- For coding questions: write COMPLETE, RUNNABLE code with proper indentation.\n"
            "- Add clear comments explaining the logic.\n"
            "- Include time/space complexity analysis.\n"
            "- For theory: provide precise, well-structured answers.\n"
            "- For algorithms: trace through with an example input.\n"
            "- For database: show proper SQL with expected output.\n"
            "- When a flowchart, tree diagram, architecture diagram, or similar visual would help, "
            "insert a [DIAGRAM: ...] marker.\n"
        ),
        "english": (
            "You are solving an ENGLISH assignment. Follow these rules strictly:\n"
            "- Write in formal academic English.\n"
            "- Structure essays with clear introduction, body, and conclusion.\n"
            "- Use topic sentences for each paragraph.\n"
            "- Include relevant quotes/references when applicable.\n"
            "- Ensure proper grammar, punctuation, and vocabulary.\n"
        ),
        "history": (
            "You are solving a HISTORY assignment. Follow these rules strictly:\n"
            "- Provide accurate dates, names, and events.\n"
            "- Present multiple perspectives where relevant.\n"
            "- Support arguments with historical evidence.\n"
            "- Use chronological organization.\n"
            "- Distinguish between facts and interpretations.\n"
        ),
        "economics": (
            "You are solving an ECONOMICS assignment. Follow these rules strictly:\n"
            "- Define all economic terms before using them.\n"
            "- Show all calculations step by step.\n"
            "- Use proper graphs/charts descriptions where applicable.\n"
            "- Cite real-world examples.\n"
            "- Distinguish between micro and macro concepts.\n"
            "- When a supply-demand graph, economic model diagram, or similar visual would help, "
            "insert a [DIAGRAM: ...] marker.\n"
        ),
        "engineering": (
            "You are solving an ENGINEERING assignment. Follow these rules strictly:\n"
            "- Show all derivations step by step.\n"
            "- Include proper units and dimensions.\n"
            "- Verify answers using alternative methods where possible.\n"
            "- State all assumptions clearly.\n"
            "- When a circuit diagram, block diagram, signal flow graph, or similar visual would help, "
            "insert a [DIAGRAM: ...] marker.\n"
        ),
        "general": (
            "You are solving an academic assignment. Follow these rules:\n"
            "- Provide thorough, well-structured answers.\n"
            "- Support claims with evidence or reasoning.\n"
            "- Use appropriate academic language.\n"
            "- Organize answers with clear headings and sub-headings.\n"
            "- Double-check all facts and calculations.\n"
        ),
    }

    base = (
        "You are an expert academic assistant with deep knowledge across all subjects.\n"
        "Your job is to COMPLETE the assignment THOROUGHLY and CORRECTLY.\n"
        "Every answer must be accurate, well-structured, and detailed.\n"
        "Never provide incorrect or made-up information.\n"
        "If you are unsure about something, state it clearly rather than guessing.\n\n"
    )

    subject_specific = subject_instructions.get(subject, subject_instructions["general"])

    source_instruction = ""
    if source_type == "file":
        source_instruction = (
            "\nThe user has provided an assignment FILE. Read the content carefully and answer "
            "every question or complete every task mentioned in the file.\n"
            "If the file contains multiple questions, answer ALL of them.\n"
        )
    elif source_type == "description":
        source_instruction = (
            "\nThe user has DESCRIBED their assignment in text. Based on their description, "
            "produce a complete, well-formatted solution document.\n"
            "Create appropriate headings and structure based on the description.\n"
        )

    # User instructions (how the assignment should be done)
    instructions_section = ""
    if instructions and instructions.strip():
        instructions_section = (
            "\nUSER INSTRUCTIONS FOR THIS ASSIGNMENT:\n"
            f"{'='*60}\n"
            f"{instructions.strip()}\n"
            f"{'='*60}\n"
            "Follow these user instructions carefully while solving the assignment.\n"
        )

    # ── Diagram marker instructions — VERY PROMINENT ─────────────────────
    diagram_instruction = (
        "\n" + "="*60 + "\n"
        "*** MANDATORY: DIAGRAM MARKERS ***\n"
        "="*60 + "\n"
        "You MUST include [DIAGRAM: ...] markers in your solution whenever a visual would help.\n"
        "This is NOT optional — diagrams are a critical part of the output.\n\n"
        "Format (on its OWN LINE):\n"
        "  [DIAGRAM: detailed description of what the image should show]\n\n"
        "Examples:\n"
        "  [DIAGRAM: Free body diagram showing forces on a block on an inclined plane with friction]\n"
        "  [DIAGRAM: Flowchart of the water cycle with evaporation, condensation, and precipitation]\n"
        "  [DIAGRAM: Circuit diagram of a full-wave bridge rectifier with labeled components]\n"
        "  [DIAGRAM: Venn diagram comparing mitosis and meiosis]\n"
        "  [DIAGRAM: Supply and demand curve showing equilibrium price and quantity]\n"
        "  [DIAGRAM: Structure of an animal cell with labeled organelles]\n"
        "  [DIAGRAM: Block diagram of a microprocessor with ALU, CU, registers]\n\n"
        "RULES:\n"
        "- You MUST include at least 1 [DIAGRAM: ...] marker for subjects like Physics, Engineering, "
        "Biology, Economics, Computer Science where visuals are standard.\n"
        "- For ANY subject, if you describe something visual (graph, chart, circuit, structure, process), "
        "add a [DIAGRAM: ...] marker instead of just describing it in text.\n"
        "- Place the marker on its OWN LINE, right after the relevant explanation.\n"
        "- The description must be DETAILED and SPECIFIC so an image can be generated from it.\n"
        "- Do NOT just say 'see diagram above' or 'as shown in figure' — use the [DIAGRAM: ...] marker.\n"
        "- Even for Math: geometry problems, coordinate graphs, function plots — add a marker.\n"
        "="*60 + "\n"
    )

    format_instruction = (
        "\nFORMATTING RULES:\n"
        "- Use markdown-style headings: # for main headings, ## for sub-headings\n"
        "- Use numbered lists for sequential steps\n"
        "- Use **bold** for key terms and final answers\n"
        "- Separate sections with blank lines\n"
        "- For code blocks, use triple backticks with the language name\n"
        "- For math, use clear notation (e.g., x^2 for x squared)\n"
        "- Do NOT add any meta-information like 'Completed Assignment', 'Source:', timestamps, "
        "or any introductory/concluding remarks about the solving process.\n"
        "- Start directly with the assignment content/solution.\n"
    )

    return base + subject_specific + source_instruction + instructions_section + diagram_instruction + format_instruction


def _ask_ai(assignment_content: str, filename_or_description: str, subject: str,
            source_type: str = "file", instructions: str = "") -> str:
    """
    Send assignment content to Groq and return the completed answer.
    Uses a two-pass approach: first generate, then verify/improve.
    """
    system_prompt = _build_system_prompt(subject, source_type, instructions)

    # ── Diagram reminder for user prompt ──────────────────────────────
    diagram_reminder = (
        "\n\nIMPORTANT REMINDER: Include [DIAGRAM: ...] markers wherever a diagram, "
        "graph, chart, circuit, flowchart, or any visual illustration would help. "
        "Do NOT skip this — these markers are used to auto-generate images in the document."
    )

    # ── Pass 1: Generate the solution ──────────────────────────────
    if source_type == "file":
        user_prompt = (
            f"Here is the content of my assignment file '{filename_or_description}':\n\n"
            f"{'='*60}\n"
            f"{assignment_content}\n"
            f"{'='*60}\n\n"
            "Please complete this assignment fully and correctly. "
            "Answer EVERY question and complete EVERY task.\n"
            "Detected subject area: " + subject
            + diagram_reminder
        )
    else:
        user_prompt = (
            f"Here is my assignment description:\n\n"
            f"{'='*60}\n"
            f"{assignment_content}\n"
            f"{'='*60}\n\n"
            "Please create a complete, well-structured solution for this assignment. "
            "Include all necessary explanations, calculations, and details.\n"
            "Detected subject area: " + subject
            + diagram_reminder
        )

    print(f"[Assignment Solver] Pass 1: Generating solution (subject: {subject})...")

    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=8000,
        )
        first_pass = response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"AI generation failed: {e}")

    # ── Debug: Check if Pass 1 produced any diagram markers ──────────
    pass1_markers = _extract_diagram_markers(first_pass)
    print(f"[Assignment Solver] Pass 1 found {len(pass1_markers)} diagram marker(s)")
    if pass1_markers:
        for idx, m in enumerate(pass1_markers):
            print(f"   Marker {idx+1}: {m[:80]}")

    # ── Pass 2: Review and improve ─────────────────────────────────
    review_prompt = (
        "You are a meticulous academic reviewer. Review the following assignment solution "
        "for correctness, completeness, and quality.\n\n"
        "ORIGINAL ASSIGNMENT:\n"
        f"{'='*60}\n"
        f"{assignment_content}\n"
        f"{'='*60}\n\n"
        "CURRENT SOLUTION:\n"
        f"{'='*60}\n"
        f"{first_pass}\n"
        f"{'='*60}\n\n"
        "INSTRUCTIONS:\n"
        "1. Check if ALL questions/tasks from the original assignment have been answered.\n"
        "2. Verify factual accuracy and correct any errors.\n"
        "3. Ensure all calculations are correct and steps are shown.\n"
        "4. Improve clarity and formatting if needed.\n"
        "5. Add any missing explanations or details.\n"
        "6. Output the COMPLETE, IMPROVED solution (not just the corrections).\n"
        "7. Maintain the same heading structure but improve content quality.\n"
        "8. Do NOT add meta-information like 'Completed Assignment', 'Source:', timestamps, "
        "or introductory/concluding remarks about the solving process.\n"
        "9. Start directly with the assignment content/solution.\n"
        "10. PRESERVE any [DIAGRAM: ...] markers from the original solution — do not remove them.\n"
        "11. If the original solution has NO [DIAGRAM: ...] markers but should have them (for Physics, "
        "Engineering, Biology, Economics, CS subjects), ADD appropriate [DIAGRAM: ...] markers now.\n"
        "12. EVERY visual concept (graph, circuit, flowchart, structure, process) MUST have a [DIAGRAM: ...] marker.\n\n"
        "Output only the final, polished solution document."
    )

    print(f"[Assignment Solver] Pass 2: Reviewing and improving solution...")

    try:
        review_response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "You are a thorough academic reviewer and improver. "
                    "Output only the final improved solution. "
                    "Do NOT add meta-information about the solving process. "
                    "CRITICAL: PRESERVE all [DIAGRAM: ...] markers. "
                    "If any are missing for visual concepts, ADD them. "
                    "Every diagram/graph/circuit/flowchart/structure MUST have a [DIAGRAM: ...] marker."
                )},
                {"role": "user",   "content": review_prompt},
            ],
            temperature=0.3,
            max_tokens=8000,
        )
        final_solution = review_response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Assignment Solver] Review pass failed, using first pass: {e}")
        final_solution = first_pass

    # ── Debug: Check final markers ──────────────────────────────────
    final_markers = _extract_diagram_markers(final_solution)
    print(f"[Assignment Solver] Final solution has {len(final_markers)} diagram marker(s)")
    if final_markers:
        for idx, m in enumerate(final_markers):
            print(f"   Final Marker {idx+1}: {m[:80]}")
    elif not final_markers and subject in ("physics", "engineering", "biology", "economics", "computer_science", "mathematics"):
        # ── Pass 3: Force-add diagrams if none were generated ──────────
        print(f"[Assignment Solver] No diagrams found for {subject} — forcing diagram generation pass...")
        try:
            diagram_prompt = (
                "You are an expert at creating educational diagrams. "
                "Given the following assignment solution, identify places where a diagram, graph, chart, "
                "circuit, flowchart, or visual illustration would enhance understanding.\n\n"
                "SOLUTION:\n"
                f"{'='*60}\n"
                f"{final_solution}\n"
                f"{'='*60}\n\n"
                "Subject: " + subject + "\n\n"
                "Insert [DIAGRAM: detailed description] markers on their own lines "
                "at appropriate locations in the solution. "
                "For " + subject + ", you should add at least 1-2 diagrams. "
                "Output the COMPLETE solution with the [DIAGRAM: ...] markers added. "
                "Do NOT change any other content.\n\n"
                "Examples of good markers:\n"
                "  [DIAGRAM: Free body diagram showing forces on a block on an inclined plane with friction]\n"
                "  [DIAGRAM: Flowchart of the water cycle with evaporation, condensation, and precipitation]\n"
                "  [DIAGRAM: Circuit diagram of a full-wave bridge rectifier with labeled components]\n"
            )
            diagram_response = _client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You add [DIAGRAM: ...] markers to assignment solutions. Output the full solution with markers added. Do NOT remove or change existing content."},
                    {"role": "user",   "content": diagram_prompt},
                ],
                temperature=0.4,
                max_tokens=8000,
            )
            forced_solution = diagram_response.choices[0].message.content.strip()
            forced_markers = _extract_diagram_markers(forced_solution)
            if forced_markers:
                print(f"[Assignment Solver] Pass 3 added {len(forced_markers)} diagram marker(s)")
                final_solution = forced_solution
            else:
                print(f"[Assignment Solver] Pass 3 also failed to generate markers")
        except Exception as e:
            print(f"[Assignment Solver] Diagram force pass failed: {e}")

    return final_solution


# ─────────────────────────────────────────
# Docx builder — clean formatting + images
# ─────────────────────────────────────────

def _save_result(source_path_or_dir: str, title: str, result: str, source_type: str = "file") -> str:
    """
    Save completed assignment as a formatted .docx Word document.
    - Generates and embeds images for any [DIAGRAM: ...] markers
    - NO extra titles, headers, source info, or timestamps
    """
    import docx
    from docx.shared import Pt, RGBColor

    # Generate a clean, specific filename
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'[\s]+', '_', safe_title)
    if len(safe_title) > 60:
        safe_title = safe_title[:60]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_name = f"{safe_title}_Solved_{timestamp}.docx"

    # Determine save directory
    if source_type == "file" and os.path.isfile(source_path_or_dir):
        source_dir = os.path.dirname(source_path_or_dir)
    elif os.path.isdir(source_path_or_dir):
        source_dir = source_path_or_dir
    else:
        source_dir = _get_real_desktop()

    out_path = os.path.join(source_dir, out_name)

    # ── Pre-generate all images from [DIAGRAM: ...] markers ────────────
    diagram_descriptions = _extract_diagram_markers(result)
    generated_images: dict[int, str] = {}  # index → image file path

    if diagram_descriptions:
        print(f"[Assignment Solver] Found {len(diagram_descriptions)} diagram marker(s), generating images...")
    else:
        print(f"[Assignment Solver] No [DIAGRAM: ...] markers found in solution — no images to generate")

    for idx, desc in enumerate(diagram_descriptions):
        img_path = _generate_image(desc, idx + 1)
        if img_path:
            generated_images[idx] = img_path

    def _build_doc() -> docx.Document:
        doc = docx.Document()

        # Set default font
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)

        # Render the content — pass generated_images for embedding
        _render_markdown_to_docx(doc, result, generated_images)

        return doc

    # Save the document
    doc = _build_doc()
    doc.save(out_path)

    # Also copy to Desktop for convenience
    desktop = _get_real_desktop()
    desk_path = os.path.join(desktop, out_name)
    if os.path.realpath(source_dir) != os.path.realpath(desktop):
        try:
            _build_doc().save(desk_path)
        except Exception:
            pass

    # ── Clean up temp image files ────────────────────────────────────
    for img_path in generated_images.values():
        try:
            os.remove(img_path)
        except Exception:
            pass

    print(f"[Assignment Solver] Saved: {out_path}")
    return out_path


def save_docx_from_text(solution_text: str, title: str) -> str:
    """
    Save an already-generated solution text as a .docx file.
    Used by the preview/save endpoint — takes the (possibly edited) text
    and writes it directly to a docx on Desktop without any AI processing.
    Handles [DIAGRAM: ...] markers by generating and embedding images.
    """
    import docx
    from docx.shared import Pt

    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'[\s]+', '_', safe_title)
    if len(safe_title) > 60:
        safe_title = safe_title[:60]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_name = f"{safe_title}_Solved_{timestamp}.docx"

    desktop = _get_real_desktop()
    out_path = os.path.join(desktop, out_name)

    # ── Pre-generate all images from [DIAGRAM: ...] markers ────────────
    diagram_descriptions = _extract_diagram_markers(solution_text)
    generated_images: dict[int, str] = {}

    if diagram_descriptions:
        print(f"[Assignment Solver] Found {len(diagram_descriptions)} diagram marker(s) in preview text, generating images...")
    else:
        print(f"[Assignment Solver] No [DIAGRAM: ...] markers found in preview text — no images to generate")

    for idx, desc in enumerate(diagram_descriptions):
        img_path = _generate_image(desc, idx + 1)
        if img_path:
            generated_images[idx] = img_path

    doc = docx.Document()

    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    # Render the content with images
    _render_markdown_to_docx(doc, solution_text, generated_images)

    doc.save(out_path)

    # ── Clean up temp image files ────────────────────────────────────
    for img_path in generated_images.values():
        try:
            os.remove(img_path)
        except Exception:
            pass

    print(f"[Assignment Solver] Saved from preview: {out_path}")
    return out_path


def _render_markdown_to_docx(doc, text: str, generated_images: dict | None = None):
    """
    Render markdown-like text into a python-docx Document with proper formatting.
    Handles: headings, bold, code blocks, numbered lists, bullet points,
    and [DIAGRAM: ...] markers (generates and embeds images).
    """
    import docx as dx
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    if generated_images is None:
        generated_images = {}

    lines = text.split('\n')
    i = 0
    in_code_block = False
    code_lines = []
    diagram_counter = 0  # tracks which [DIAGRAM] we're on

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Code block handling
        if stripped.startswith('```'):
            if in_code_block:
                code_text = '\n'.join(code_lines)
                p = doc.add_paragraph()
                run = p.add_run(code_text)
                run.font.name = 'Consolas'
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x20, 0x20, 0x20)
                from docx.oxml.ns import qn
                shading = dx.oxml.OxmlElement('w:shd')
                shading.set(qn('w:val'), 'clear')
                shading.set(qn('w:color'), 'auto')
                shading.set(qn('w:fill'), 'F5F5F5')
                run.font.element.rPr.append(shading)
                in_code_block = False
                code_lines = []
                i += 1
                continue
            else:
                in_code_block = True
                code_lines = []
                i += 1
                continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Empty line
        if not stripped:
            i += 1
            continue

        # ── [DIAGRAM: ...] marker handling ──────────────────────────────
        diag_match = re.match(r'^\[DIAGRAM:\s*(.+?)\]$', stripped)
        if diag_match:
            desc = diag_match.group(1)
            if diagram_counter in generated_images:
                # Add a caption above the image
                cap = doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_run = cap.add_run(f"Figure {diagram_counter + 1}: {desc}")
                cap_run.font.size = Pt(9)
                cap_run.font.italic = True
                cap_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

                # Embed the image
                try:
                    pic = doc.add_picture(generated_images[diagram_counter], width=Inches(4.5))
                    last_paragraph = doc.paragraphs[-1]
                    last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception as e:
                    print(f"   Warning: Could not embed image: {e}")
                    fallback = doc.add_paragraph(f"[Diagram: {desc}]")
                    fallback.alignment = WD_ALIGN_PARAGRAPH.CENTER

                doc.add_paragraph("")  # spacer after image
            else:
                # Image generation failed — leave as text placeholder
                placeholder = doc.add_paragraph()
                placeholder.alignment = WD_ALIGN_PARAGRAPH.CENTER
                ph_run = placeholder.add_run(f"[Diagram: {desc}]")
                ph_run.font.italic = True
                ph_run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

            diagram_counter += 1
            i += 1
            continue

        # Headings
        if stripped.startswith('####'):
            heading_text = stripped.lstrip('#').strip()
            doc.add_heading(heading_text, level=4)
            i += 1
            continue
        if stripped.startswith('###'):
            heading_text = stripped.lstrip('#').strip()
            doc.add_heading(heading_text, level=3)
            i += 1
            continue
        if stripped.startswith('##'):
            heading_text = stripped.lstrip('#').strip()
            doc.add_heading(heading_text, level=2)
            i += 1
            continue
        if stripped.startswith('#'):
            heading_text = stripped.lstrip('#').strip()
            doc.add_heading(heading_text, level=1)
            i += 1
            continue

        # Horizontal rules
        if re.match(r'^[-=_]{3,}$', stripped):
            doc.add_paragraph("─" * 50)
            i += 1
            continue

        # Numbered list items
        if re.match(r'^\d+[\.\)]\s', stripped):
            p = doc.add_paragraph(style='List Number')
            content = re.sub(r'^\d+[\.\)]\s*', '', stripped)
            _add_formatted_runs(p, content)
            i += 1
            continue

        # Bullet list items
        if stripped.startswith(('- ', '* ', '+ ')):
            p = doc.add_paragraph(style='List Bullet')
            content = stripped[2:].strip()
            _add_formatted_runs(p, content)
            i += 1
            continue

        # Bold heading line
        if stripped.startswith('**') and stripped.endswith('**') and not ' ' in stripped[2:-2]:
            p = doc.add_paragraph()
            run = p.add_run(stripped.strip('*'))
            run.bold = True
            run.font.size = Pt(12)
            i += 1
            continue

        # Regular paragraph
        p = doc.add_paragraph()
        _add_formatted_runs(p, stripped)
        i += 1


def _add_formatted_runs(paragraph, text: str):
    """Add text to a paragraph with inline **bold** and *italic* formatting."""
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            italic_parts = re.split(r'(\*.*?\*)', part)
            for ip in italic_parts:
                if ip.startswith('*') and ip.endswith('*') and len(ip) > 2:
                    run = paragraph.add_run(ip[1:-1])
                    run.italic = True
                else:
                    paragraph.add_run(ip)


# ─────────────────────────────────────────
# PUBLIC ENTRY POINTS
# ─────────────────────────────────────────

def solve_assignment(command: str) -> str:
    """
    Main function called from automation_1.py for file-based assignment solving.
    Parses command -> searches filesystem -> reads file -> AI completes -> saves result.
    """
    filename = parse_filename(command)
    if not filename:
        description = parse_description(command)
        if description:
            return solve_assignment_from_description(description)
        return (
            "Couldn't detect a filename or description.\n"
            "Try: 'complete assignment homework.txt' or "
            "'solve my assignment about thermodynamics laws'"
        )

    print(f"[Assignment Solver] Searching for '{filename}'...")
    filepath = _find_file(filename)

    if not filepath:
        desktop = _get_real_desktop()
        try:
            files = [f for f in os.listdir(desktop) if os.path.isfile(os.path.join(desktop, f))]
            file_list = ", ".join(files[:10]) if files else "no files found"
        except Exception:
            file_list = "could not list"

        return (
            f"File '{filename}' was not found anywhere on your system.\n"
            f"Desktop contains: {file_list}\n"
            f"Make sure the filename is spelled correctly.\n\n"
            f"Tip: You can also describe your assignment instead!\n"
            f"Example: 'solve my assignment about Newton's laws of motion'"
        )

    found_name = os.path.basename(filepath)
    print(f"[Assignment Solver] Found: {filepath}")

    try:
        content = _read_file(filepath)
    except RuntimeError as e:
        return f"Could not read file: {e}"
    except Exception as e:
        return f"Unexpected error reading file: {e}"

    if not content.strip():
        return f"File '{found_name}' appears to be empty - nothing to complete."

    subject = _detect_subject(content)
    print(f"[Assignment Solver] Read {len(content)} chars from '{found_name}' (subject: {subject})")
    print(f"[Assignment Solver] Sending to AI for completion...")

    try:
        result = _ask_ai(content, found_name, subject, source_type="file")
    except Exception as e:
        return f"AI error: {e}"

    try:
        base_name = os.path.splitext(found_name)[0]
        out_path = _save_result(filepath, base_name, result, source_type="file")
        saved_name = os.path.basename(out_path)
    except Exception as e:
        return (
            f"Assignment completed for '{found_name}'!\n"
            f"Could not save file: {e}\n\n"
            f"{'='*50}\n{result}"
        )

    return (
        f"Assignment '{found_name}' completed!\n"
        f"Found at: {filepath}\n"
        f"Saved as: {saved_name} (Word .docx)\n"
        f"{'─'*50}\n"
        f"{result[:800]}{'...[see saved .docx for full answer]' if len(result) > 800 else ''}\n"
        f"{'─'*50}"
    )


def solve_assignment_from_description(description: str) -> str:
    """
    Solve an assignment based on a text description.
    Returns the solution text (NOT saved yet — caller decides to save or preview).
    """
    if not description or not description.strip():
        return "Please provide an assignment description."

    subject = _detect_subject(description)
    print(f"[Assignment Solver] Description mode (subject: {subject})")
    print(f"[Assignment Solver] Description: {description[:100]}...")
    print(f"[Assignment Solver] Sending to AI for completion...")

    try:
        result = _ask_ai(description, description, subject, source_type="description")
    except Exception as e:
        return f"AI error: {e}"

    # Just return the solution text — the frontend will handle preview/save
    return result


def solve_assignment_from_file_upload(filepath: str, instructions: str = "") -> str:
    """
    Solve an assignment from an uploaded file path.
    Optionally accepts instructions on how the assignment should be done.
    Returns the solution text (NOT saved yet — caller decides to save or preview).
    """
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"

    found_name = os.path.basename(filepath)

    try:
        content = _read_file(filepath)
    except RuntimeError as e:
        return f"Could not read file: {e}"
    except Exception as e:
        return f"Unexpected error reading file: {e}"

    if not content.strip():
        return f"File '{found_name}' appears to be empty - nothing to complete."

    # Combine file content and instructions for subject detection
    combined = content
    if instructions and instructions.strip():
        combined = f"{content}\n\nInstructions: {instructions}"

    subject = _detect_subject(combined)
    print(f"[Assignment Solver] File upload mode: '{found_name}' (subject: {subject})")
    if instructions:
        print(f"[Assignment Solver] User instructions: {instructions[:100]}...")
    print(f"[Assignment Solver] Sending to AI for completion...")

    try:
        result = _ask_ai(content, found_name, subject, source_type="file", instructions=instructions)
    except Exception as e:
        return f"AI error: {e}"

    # Just return the solution text — the frontend will handle preview/save
    return result


def save_assignment_docx(solution_text: str, title: str) -> str:
    """
    Save a solution text as a .docx file on the Desktop.
    Called from the preview/save endpoint after the user has reviewed and edited.
    Handles [DIAGRAM: ...] markers by generating and embedding images.
    """
    if not solution_text or not solution_text.strip():
        return "No solution text to save."

    try:
        out_path = save_docx_from_text(solution_text.strip(), title)
        saved_name = os.path.basename(out_path)
        return f"Assignment saved as: {saved_name}\nLocation: {out_path}"
    except Exception as e:
        return f"Error saving file: {e}"


# ─────────────────────────────────────────
# Utility: Get list of recently solved files
# ─────────────────────────────────────────

def get_solved_files(directory: str | None = None) -> list[dict]:
    """
    Returns a list of recently solved assignment files in the given directory.
    """
    search_dir = directory or _get_real_desktop()
    solved = []

    try:
        for fname in os.listdir(search_dir):
            if "_Solved_" in fname and fname.endswith(".docx"):
                full_path = os.path.join(search_dir, fname)
                mtime = os.path.getmtime(full_path)
                solved.append({
                    "name": fname,
                    "path": full_path,
                    "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)),
                })
    except Exception:
        pass

    solved.sort(key=lambda x: x["date"], reverse=True)
    return solved[:20]
