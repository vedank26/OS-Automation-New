import asyncio
import os
import shutil
import time
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from automation_1 import execute_command
from speech_engine import listen_once_result, stop_listening
from assignment_solver import (
    solve_assignment,
    solve_assignment_from_description,
    solve_assignment_from_file_upload,
    save_assignment_docx,
    get_solved_files,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class Command(BaseModel):
    text: str


class AssignmentDescription(BaseModel):
    description: str


class SaveDocxRequest(BaseModel):
    solution_text: str
    title: str


@app.get("/")
def home():
    return {"message": "FlowForge AI Backend is running"}


async def _execute_command_text(text: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, execute_command, text)


@app.post("/execute")
async def execute(cmd: Command):
    return await _execute_command_text(cmd.text)


@app.post("/smart-execute")
async def smart_execute(cmd: Command):
    return await _execute_command_text(cmd.text)


@app.post("/listen")
async def listen_command():
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, listen_once_result),
            timeout=135,
        )
        return result
    except asyncio.TimeoutError:
        print("[speech] /listen timed out safely")
        return {"text": "", "status": "timeout"}
    except Exception as exc:
        print(f"[speech] /listen failed safely: {exc}")
        return {"text": "", "status": "error"}


@app.post("/listen-stop")
async def listen_stop():
    stop_listening()
    return {"status": "stopping"}


# ─────────────────────────────────────────
# ASSIGNMENT SOLVER ENDPOINTS
# ─────────────────────────────────────────

@app.post("/solve-assignment/file")
async def solve_assignment_file(
    file: UploadFile = File(...),
    instructions: str = Form(""),
):
    """
    Upload an assignment file and get it solved.
    Optionally provide instructions on how it should be done.
    Returns: solution text for preview (NOT saved yet).
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    temp_path = os.path.join(UPLOAD_DIR, safe_name)

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        print(f"[Assignment API] File uploaded: {safe_name} ({len(content)} bytes)")
        if instructions:
            print(f"[Assignment API] Instructions: {instructions[:100]}...")

        # Solve the assignment in a thread to not block
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, solve_assignment_from_file_upload, temp_path, instructions
        )

        return {"result": result, "status": "success"}

    except Exception as e:
        return {"result": f"Error processing file: {e}", "status": "error"}

    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


@app.post("/solve-assignment/description")
async def solve_assignment_description(data: AssignmentDescription):
    """
    Describe your assignment in text and get it solved.
    Returns: solution text for preview (NOT saved yet).
    """
    if not data.description or not data.description.strip():
        return {
            "result": "Please provide an assignment description.",
            "status": "error",
        }

    print(f"[Assignment API] Description: {data.description[:100]}...")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, solve_assignment_from_description, data.description.strip()
        )

        return {"result": result, "status": "success"}

    except Exception as e:
        return {"result": f"Error solving assignment: {e}", "status": "error"}


@app.post("/solve-assignment/save-docx")
async def save_assignment_docx_endpoint(data: SaveDocxRequest):
    """
    Save a solution text as a .docx file on the Desktop.
    Called after the user has previewed and optionally edited the solution.
    """
    if not data.solution_text or not data.solution_text.strip():
        return {
            "result": "No solution text provided to save.",
            "status": "error",
        }

    if not data.title or not data.title.strip():
        data.title = "Assignment"

    print(f"[Assignment API] Save docx: title='{data.title}' ({len(data.solution_text)} chars)")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, save_assignment_docx, data.solution_text.strip(), data.title.strip()
        )

        return {"result": result, "status": "success"}

    except Exception as e:
        return {"result": f"Error saving document: {e}", "status": "error"}


@app.get("/solve-assignment/history")
async def assignment_history():
    """
    Returns a list of recently solved assignment files.
    """
    try:
        files = get_solved_files()
        return {"files": files, "status": "success"}
    except Exception as e:
        return {"files": [], "status": "error", "message": str(e)}
