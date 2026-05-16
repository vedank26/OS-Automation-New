import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from automation_1 import execute_command
from speech_engine import listen_once_result, stop_listening

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Command(BaseModel):
    text: str

@app.get("/")
def home():
    return {"message": "FlowForge AI Backend is running ✅"}

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
