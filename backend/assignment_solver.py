import os
import re
import json
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# Groq client (reuses existing env key)
# ─────────────────────────────────────────
_api_key = os.getenv("GROQ_API_KEY")
_client = Groq(api_key=_api_key) if _api_key else None


def _ensure_ai_client() -> None:
    if not _client:
        raise RuntimeError(
            "Groq API key is missing. Please set GROQ_API_KEY in .env or your environment."
        )

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
# (Replaces Windows-only winreg approach)
# ─────────────────────────────────────────

def _get_real_desktop() -> str:
    """
    Gets the Desktop path cross-platform.
    On Windows: tries Registry first, then falls back.
    On Linux/Mac: uses ~/Desktop.
    """
    # Try Windows Registry first
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

    # Cross-platform fallback
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path

    return home  # last resort


def _get_search_roots() -> list[str]:
    """
    Returns all meaningful locations to search for a file.
    Cross-platform: works on Windows, Linux, and Mac.
    """
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

    # On Windows, add all drive roots
    try:
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.isdir(drive) and drive not in roots:
                roots.append(drive)
    except Exception:
        pass

    # On Linux/Mac, add common mount points
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
    """
    Returns True if the assignment command contains a description
    (not just a filename). Heuristic: if the remaining text after
    the trigger is longer than a typical filename and contains
    common sentence words, it's a description.
    """
    description = _extract_description_or_filename(command)
    if description is None:
        return False

    # If it looks like a filename (has extension, no spaces or short)
    has_extension = bool(re.search(r'\.\w{1,5}$', description.strip()))
    word_count = len(description.split())

    if has_extension and word_count <= 3:
        return False

    # If it's long or contains sentence-like words, it's a description
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
            # Strip filler words
            filler = r"^(called|named|file|for|my|the|:)\s+"
            remainder = re.sub(filler, "", remainder, flags=re.IGNORECASE).strip()
            return remainder if remainder else None

    return None


def parse_filename(command: str) -> str | None:
    """
    Extract the filename from the command.
    Only returns a filename if the input looks like a file reference.

    Examples:
      "complete assignment homework.txt"        -> "homework.txt"
      "do my assignment called math_task.pdf"   -> "math_task.pdf"
      "solve assignment file notes.docx"        -> "notes.docx"
    """
    remainder = _extract_description_or_filename(command)
    if remainder is None:
        return None

    # Check if it looks like a filename
    has_extension = bool(re.search(r'\.\w{1,5}$', remainder.strip()))
    word_count = len(remainder.split())

    if has_extension and word_count <= 3:
        return remainder.strip()

    # Could be a filename without extension (short, no sentence words)
    if word_count <= 3 and not any(
        w in remainder.lower()
        for w in ["about", "on", "regarding", "write", "explain", "describe", "discuss", "topic", "question"]
    ):
        return remainder.strip()

    return None


def parse_description(command: str) -> str | None:
    """
    Extract the assignment description from the command.
    Returns None if the command references a file instead.

    Examples:
      "solve my assignment about thermodynamics laws and their applications"
        -> "thermodynamics laws and their applications"
      "complete assignment write an essay on climate change"
        -> "write an essay on climate change"
    """
    if not is_description_only_command(command):
        return None

    remainder = _extract_description_or_filename(command)
    if remainder is None:
        return None

    # Strip filler words more aggressively for descriptions
    filler = r"^(called|named|file|for|my|the|:|about|on|regarding)\s+"
    cleaned = re.sub(filler, "", remainder, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else remainder.strip()


# ─────────────────────────────────────────
# File finder — searches Desktop + common dirs
# ─────────────────────────────────────────

def _find_file(filename: str) -> str | None:
    """
    Searches for `filename` across common user directories.
    Returns the full path of the first match, or None.
    """
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
# File reader — supports multiple formats
# ─────────────────────────────────────────

def _read_file(filepath: str) -> str:
    """
    Read content from a file. Supports:
      - Plain text: .txt .md .py .js .ts .html .css .json .csv .xml
      - Word docs:  .docx  (python-docx)
      - PDFs:       .pdf   (PyMuPDF)
      - Excel:      .xlsx  (openpyxl)
      - Images:     .png .jpg .jpeg .bmp .tiff (OCR via pytesseract, optional)
    """
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

    # Image OCR (optional dependency)
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"):
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(filepath)
            text = pytesseract.image_to_string(img)
            return text
        except ImportError:
            raise RuntimeError(
                "Image OCR requires: pip install pytesseract Pillow "
                "(and Tesseract-OCR must be installed on the system)"
            )

    raise RuntimeError(
        f"Unsupported file type '{ext}'. "
        "Supported: .txt .md .py .js .html .pdf .docx .xlsx .csv .json "
        ".png .jpg .jpeg (with OCR)"
    )


# ─────────────────────────────────────────
# AI solver — multi-pass for quality
# ─────────────────────────────────────────

def _build_system_prompt(subject: str, source_type: str) -> str:
    """Build a subject-specific, source-aware system prompt."""

    subject_instructions = {
        "mathematics": (
            "You are solving a MATHEMATICS assignment. Follow these rules strictly:\n"
            "- Show ALL step-by-step working. Never skip steps.\n"
            "- Clearly label each step (Step 1, Step 2, etc.).\n"
            "- State all formulas BEFORE using them.\n"
            "- Double-check every calculation.\n"
            "- Box or highlight final answers.\n"
            "- If a diagram/figure is described, describe it textually.\n"
            "- Use proper mathematical notation.\n"
        ),
        "physics": (
            "You are solving a PHYSICS assignment. Follow these rules strictly:\n"
            "- State the given quantities and what to find.\n"
            "- Identify the relevant physics principle/formula.\n"
            "- Show complete step-by-step derivation.\n"
            "- Include units at every step.\n"
            "- Verify the answer with dimensional analysis.\n"
            "- Draw diagrams mentally and describe them.\n"
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
        ),
        "computer_science": (
            "You are solving a COMPUTER SCIENCE assignment. Follow these rules strictly:\n"
            "- For coding questions: write COMPLETE, RUNNABLE code with proper indentation.\n"
            "- Add clear comments explaining the logic.\n"
            "- Include time/space complexity analysis.\n"
            "- For theory: provide precise, well-structured answers.\n"
            "- For algorithms: trace through with an example input.\n"
            "- For database: show proper SQL with expected output.\n"
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
        ),
        "engineering": (
            "You are solving an ENGINEERING assignment. Follow these rules strictly:\n"
            "- Show all derivations step by step.\n"
            "- Include proper units and dimensions.\n"
            "- Draw circuit/block diagrams described textually.\n"
            "- Verify answers using alternative methods where possible.\n"
            "- State all assumptions clearly.\n"
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

    format_instruction = (
        "\nFORMATTING RULES:\n"
        "- Use markdown-style headings: # for main headings, ## for sub-headings\n"
        "- Use numbered lists for sequential steps\n"
        "- Use **bold** for key terms and final answers\n"
        "- Separate sections with blank lines\n"
        "- For code blocks, use triple backticks with the language name\n"
        "- For math, use clear notation (e.g., x^2 for x squared)\n"
        "- Include a brief introduction and conclusion where appropriate\n"
    )

    return base + subject_specific + source_instruction + format_instruction


def _ask_ai(assignment_content: str, filename_or_description: str, subject: str, source_type: str = "file") -> str:
    """
    Send assignment content to Groq and return the completed answer.
    Uses a two-pass approach: first generate, then verify/improve.
    """
    system_prompt = _build_system_prompt(subject, source_type)

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
        )

    print(f"[Assignment Solver] Pass 1: Generating solution (subject: {subject})...")

    _ensure_ai_client()

    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=8000,
        )
        first_pass = response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"AI generation failed: {e}")

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
        "7. Maintain the same heading structure but improve content quality.\n\n"
        "Output only the final, polished solution document."
    )

    print(f"[Assignment Solver] Pass 2: Reviewing and improving solution...")

    try:
        review_response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a thorough academic reviewer and improver. Output only the final improved solution."},
                {"role": "user",   "content": review_prompt},
            ],
            temperature=0.2,
            max_tokens=8000,
        )
        final_solution = review_response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Assignment Solver] Review pass failed, using first pass: {e}")
        final_solution = first_pass

    return final_solution


# ─────────────────────────────────────────
# Docx builder — professional formatting
# ─────────────────────────────────────────

def _save_result(source_path_or_dir: str, title: str, result: str, source_type: str = "file") -> str:
    """
    Save completed assignment as a formatted .docx Word document.

    Args:
        source_path_or_dir: Directory to save the file in (for file mode)
                           or fallback directory (for description mode)
        title: Title for the document
        result: The AI-generated solution text
        source_type: "file" or "description"

    Returns:
        The full path to the saved .docx file
    """
    import docx
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    # Generate a clean, specific filename
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    safe_title = re.sub(r'[\s]+', '_', safe_title)
    # Truncate if too long
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

    def _build_doc() -> docx.Document:
        doc = docx.Document()

        # ── Set default font ───────────────────────────────────────────────
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)

        # ── Title ──────────────────────────────────────────────────────────
        title_para = doc.add_heading(f"Completed Assignment", level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in title_para.runs:
            run.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

        # ── Subtitle with source info ──────────────────────────────────────
        sub = doc.add_paragraph(f"Source: {title}")
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in sub.runs:
            run.font.size = Pt(10)
            run.font.italic = True
            run.font.color.rgb = RGBColor(0x70, 0x70, 0x70)

        # ── Date/time stamp ────────────────────────────────────────────────
        date_para = doc.add_paragraph(f"Solved: {time.strftime('%B %d, %Y at %I:%M %p')}")
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in date_para.runs:
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(0x90, 0x90, 0x90)

        # ── Horizontal rule ────────────────────────────────────────────────
        doc.add_paragraph("─" * 60)

        # ── Parse and render the solution ──────────────────────────────────
        _render_markdown_to_docx(doc, result)

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

    print(f"[Assignment Solver] Saved: {out_path}")
    return out_path


def _render_markdown_to_docx(doc, text: str):
    """
    Render markdown-like text into a python-docx Document with proper formatting.
    Handles: headings, bold, code blocks, numbered lists, bullet points, tables.
    """
    import docx as dx
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    lines = text.split('\n')
    i = 0
    in_code_block = False
    code_lines = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── Code block handling ────────────────────────────────────────────
        if stripped.startswith('```'):
            if in_code_block:
                # End of code block
                code_text = '\n'.join(code_lines)
                p = doc.add_paragraph()
                run = p.add_run(code_text)
                run.font.name = 'Consolas'
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x20, 0x20, 0x20)
                # Add background shading
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

        # ── Empty line ─────────────────────────────────────────────────────
        if not stripped:
            i += 1
            continue

        # ── Headings ───────────────────────────────────────────────────────
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

        # ── Horizontal rules ───────────────────────────────────────────────
        if re.match(r'^[-=_]{3,}$', stripped):
            doc.add_paragraph("─" * 50)
            i += 1
            continue

        # ── Numbered list items ────────────────────────────────────────────
        if re.match(r'^\d+[\.\)]\s', stripped):
            p = doc.add_paragraph(style='List Number')
            content = re.sub(r'^\d+[\.\)]\s*', '', stripped)
            _add_formatted_runs(p, content)
            i += 1
            continue

        # ── Bullet list items ──────────────────────────────────────────────
        if stripped.startswith(('- ', '* ', '+ ')):
            p = doc.add_paragraph(style='List Bullet')
            content = stripped[2:].strip()
            _add_formatted_runs(p, content)
            i += 1
            continue

        # ── Bold heading line ──────────────────────────────────────────────
        if stripped.startswith('**') and stripped.endswith('**') and not ' ' in stripped[2:-2]:
            p = doc.add_paragraph()
            run = p.add_run(stripped.strip('*'))
            run.bold = True
            run.font.size = Pt(12)
            i += 1
            continue

        # ── Regular paragraph ──────────────────────────────────────────────
        p = doc.add_paragraph()
        _add_formatted_runs(p, stripped)
        i += 1


def _add_formatted_runs(paragraph, text: str):
    """
    Add text to a paragraph with inline **bold** and *italic* formatting.
    """
    # Split on bold markers
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            # Split on italic markers
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
    # 1. Extract filename from command
    filename = parse_filename(command)
    if not filename:
        # Maybe it's a description-only command
        description = parse_description(command)
        if description:
            return solve_assignment_from_description(description)
        return (
            "Couldn't detect a filename or description.\n"
            "Try: 'complete assignment homework.txt' or "
            "'solve my assignment about thermodynamics laws'"
        )

    # 2. Search filesystem for the file
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

    # 3. Read the file
    try:
        content = _read_file(filepath)
    except RuntimeError as e:
        return f"Could not read file: {e}"
    except Exception as e:
        return f"Unexpected error reading file: {e}"

    if not content.strip():
        return f"File '{found_name}' appears to be empty - nothing to complete."

    # 4. Detect subject and solve
    subject = _detect_subject(content)
    print(f"[Assignment Solver] Read {len(content)} chars from '{found_name}' (subject: {subject})")
    print(f"[Assignment Solver] Sending to AI for completion...")

    try:
        result = _ask_ai(content, found_name, subject, source_type="file")
    except Exception as e:
        return f"AI error: {e}"

    # 5. Save result
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
    No file needed - just describe what the assignment is about.

    Args:
        description: The assignment description / topic

    Returns:
        Result message with solution summary and file location
    """
    if not description or not description.strip():
        return (
            "Please provide an assignment description.\n"
            "Example: 'solve my assignment about thermodynamics laws and their applications'"
        )

    # Detect subject
    subject = _detect_subject(description)
    print(f"[Assignment Solver] Description mode (subject: {subject})")
    print(f"[Assignment Solver] Description: {description[:100]}...")
    print(f"[Assignment Solver] Sending to AI for completion...")

    try:
        result = _ask_ai(description, description, subject, source_type="description")
    except Exception as e:
        return f"AI error: {e}"

    # Save result
    try:
        # Create a short title from description
        title_words = description.split()[:8]
        title = " ".join(title_words)
        desktop = _get_real_desktop()
        out_path = _save_result(desktop, title, result, source_type="description")
        saved_name = os.path.basename(out_path)
    except Exception as e:
        return (
            f"Assignment solved!\n"
            f"Could not save file: {e}\n\n"
            f"{'='*50}\n{result}"
        )

    return (
        f"Assignment solved from description!\n"
        f"Topic: {description[:80]}{'...' if len(description) > 80 else ''}\n"
        f"Subject detected: {subject}\n"
        f"Saved as: {saved_name} (Word .docx on Desktop)\n"
        f"{'─'*50}\n"
        f"{result[:800]}{'...[see saved .docx for full answer]' if len(result) > 800 else ''}\n"
        f"{'─'*50}"
    )


def solve_assignment_from_file_upload(filepath: str) -> str:
    """
    Solve an assignment from an uploaded file path.
    Called from the new API endpoint for file uploads.

    Args:
        filepath: Full path to the assignment file

    Returns:
        Result message with solution summary and file location
    """
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"

    found_name = os.path.basename(filepath)

    # Read the file
    try:
        content = _read_file(filepath)
    except RuntimeError as e:
        return f"Could not read file: {e}"
    except Exception as e:
        return f"Unexpected error reading file: {e}"

    if not content.strip():
        return f"File '{found_name}' appears to be empty - nothing to complete."

    # Detect subject and solve
    subject = _detect_subject(content)
    print(f"[Assignment Solver] File upload mode: '{found_name}' (subject: {subject})")
    print(f"[Assignment Solver] Sending to AI for completion...")

    try:
        result = _ask_ai(content, found_name, subject, source_type="file")
    except Exception as e:
        return f"AI error: {e}"

    # Save result
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
        f"Saved as: {saved_name} (Word .docx)\n"
        f"{'─'*50}\n"
        f"{result[:800]}{'...[see saved .docx for full answer]' if len(result) > 800 else ''}\n"
        f"{'─'*50}"
    )


# ─────────────────────────────────────────
# Utility: Get list of recently solved files
# ─────────────────────────────────────────

def get_solved_files(directory: str | None = None) -> list[dict]:
    """
    Returns a list of recently solved assignment files in the given directory.
    Each entry: {"name": filename, "path": full_path, "date": modification_time}
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
    return solved[:20]  # Return last 20
