import os
import re
import shutil
import subprocess
import time
import webbrowser
import json
import pyautogui
from dotenv import load_dotenv

from app_launcher import launch_app
from handlers import (
    desktop_handler,
    window_handler,
    system_handler,
    media_handler,
    assignment_handler,
    search_handler,
    launcher_handler,
    workflow_handler,
    project_handler,
)


load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

pyautogui.FAILSAFE = True

media_handler.log_youtube_api_status()

from utils.os_utils import _bring_window_to_front


def _result(message: str, options: list[str] | None = None):
    payload = {"result": message}
    if options is not None:
        payload["options"] = options
    return payload


def execute_command(command: str):
    try:
        raw_command = command.strip()
        normalized_command = raw_command.lower()

        if not normalized_command:
            return _result("No command provided.")

        # ─────────────────────────────────────────
        # 🖥️ APPS — must be FIRST
        # ─────────────────────────────────────────

        if launcher_handler.can_handle_launch(raw_command):
            return launcher_handler.handle_launch(raw_command)

        # ─────────────────────────────────────────
        # 📝 ASSIGNMENT SOLVER  <<< NEW BLOCK
        # ─────────────────────────────────────────

        elif assignment_handler.can_handle_assignment(normalized_command):
            return assignment_handler.handle_assignment(raw_command)

        # ─────────────────────────────────────────
        # 🎯 VIDEO SELECTION (after YouTube search)
        # ─────────────────────────────────────────

        media_result = media_handler.handle_media_command(
            normalized_command,
            raw_command,
        )
        if media_result is not None:
            return media_result

        # ─────────────────────────────────────────
        # ▶️ YOUTUBE SEARCH
        # ─────────────────────────────────────────

        # ─────────────────────────────────────────
        # 🎵 PLAY without youtube keyword
        # ─────────────────────────────────────────

        # ─────────────────────────────────────────
        # 📁 FOLDER CREATION
        # ─────────────────────────────────────────

        elif project_handler.can_handle_folder_creation(normalized_command):
            return project_handler.handle_folder_creation(raw_command)

        # ─────────────────────────────────────────
        # ⚛️ REACT PROJECT
        # ─────────────────────────────────────────

        elif project_handler.can_handle_react_creation(normalized_command):
            return project_handler.handle_react_creation(raw_command)

        # ─────────────────────────────────────────
        # 🐍 PYTHON PROJECT
        # ─────────────────────────────────────────

        elif project_handler.can_handle_python_creation(normalized_command):
            return project_handler.handle_python_creation(raw_command)

        # ─────────────────────────────────────────
        # 🤖 AI PROJECT CREATION
        # ─────────────────────────────────────────

        elif project_handler.is_project_command(normalized_command):
            return project_handler.handle_ai_creation(raw_command, normalized_command)

        # ─────────────────────────────────────────
        # ⚡ WORKFLOW
        # ─────────────────────────────────────────

        elif workflow_handler.can_handle_workflow(normalized_command):
            return workflow_handler.handle_workflow()

        # ─────────────────────────────────────────
        # 🚀 RUN PROJECT
        # ─────────────────────────────────────────

        elif project_handler.can_handle_project_execution(normalized_command):
            # Exclude workflow commands from generic start pattern
            if normalized_command.startswith("start ") and workflow_handler.can_handle_workflow(normalized_command):
                return workflow_handler.handle_workflow()
            return project_handler.handle_project_execution(normalized_command)

        # ─────────────────────────────────────────
        # 🔍 GOOGLE SEARCH
        # ─────────────────────────────────────────

        elif search_handler.can_handle_search(normalized_command):
            return search_handler.handle_search(raw_command)

        # ─────────────────────────────────────────
        # 📸 SCREENSHOT
        # ─────────────────────────────────────────

        elif "screenshot" in normalized_command or "take screenshot" in normalized_command:
            return desktop_handler.handle_screenshot()

        # ─────────────────────────────────────────
        # 🖱️ CURSOR / MOUSE
        # ─────────────────────────────────────────

        elif "move cursor to center" in normalized_command:
            return desktop_handler.handle_move_cursor_center()

        elif "move cursor to top left" in normalized_command:
            return desktop_handler.handle_move_cursor_top_left()

        elif "move cursor to top right" in normalized_command:
            return desktop_handler.handle_move_cursor_top_right()

        elif "move cursor to bottom left" in normalized_command:
            return desktop_handler.handle_move_cursor_bottom_left()

        elif "move cursor to bottom right" in normalized_command:
            return desktop_handler.handle_move_cursor_bottom_right()

        elif "move cursor to" in normalized_command:
            return desktop_handler.handle_move_cursor_to(raw_command)

        elif "click at" in normalized_command:
            return desktop_handler.handle_click_at(raw_command)

        elif "double click" in normalized_command:
            return desktop_handler.handle_double_click()

        elif "right click" in normalized_command:
            return desktop_handler.handle_right_click()

        elif normalized_command == "click":
            return desktop_handler.handle_click()

        # ─────────────────────────────────────────
        # ⌨️ KEYBOARD
        # ─────────────────────────────────────────

        elif normalized_command.startswith("type "):
            return desktop_handler.handle_type(raw_command)

        elif normalized_command.startswith("write "):
            return desktop_handler.handle_write(raw_command)

        elif "press ctrl c" in normalized_command:
            return desktop_handler.handle_press_ctrl_c()

        elif "press ctrl v" in normalized_command:
            return desktop_handler.handle_press_ctrl_v()

        elif "press ctrl s" in normalized_command:
            return desktop_handler.handle_press_ctrl_s()

        elif "press ctrl z" in normalized_command:
            return desktop_handler.handle_press_ctrl_z()

        elif "press ctrl a" in normalized_command:
            return desktop_handler.handle_press_ctrl_a()

        elif "press alt tab" in normalized_command:
            return desktop_handler.handle_press_alt_tab()

        elif "press alt f4" in normalized_command:
            return desktop_handler.handle_press_alt_f4()

        elif "press win d" in normalized_command:
            return desktop_handler.handle_press_win_d()

        elif "press enter" in normalized_command:
            return desktop_handler.handle_press_enter()

        elif "press escape" in normalized_command:
            return desktop_handler.handle_press_escape()

        elif "press space" in normalized_command:
            return desktop_handler.handle_press_space()

        elif "press tab" in normalized_command:
            return desktop_handler.handle_press_tab()

        elif "press backspace" in normalized_command:
            return desktop_handler.handle_press_backspace()

        elif "press delete" in normalized_command:
            return desktop_handler.handle_press_delete()

        elif "scroll up" in normalized_command:
            return desktop_handler.handle_scroll_up(raw_command)

        elif "scroll down" in normalized_command:
            return desktop_handler.handle_scroll_down(raw_command)

        # ─────────────────────────────────────────
        # 🪟 WINDOW MANAGEMENT
        # ─────────────────────────────────────────

        elif "focus chrome" in normalized_command:
            return window_handler.handle_focus_chrome()

        elif "focus edge" in normalized_command:
            return window_handler.handle_focus_edge()

        elif "focus vscode" in normalized_command:
            return window_handler.handle_focus_vscode()

        elif "focus notepad" in normalized_command:
            return window_handler.handle_focus_notepad()

        elif "focus terminal" in normalized_command:
            return window_handler.handle_focus_terminal()

        elif "switch window" in normalized_command:
            return window_handler.handle_switch_window()

        elif "minimize window" in normalized_command:
            return window_handler.handle_minimize_window()

        elif "maximize window" in normalized_command:
            return window_handler.handle_maximize_window()

        elif "close window" in normalized_command:
            return window_handler.handle_close_window()

        elif "show desktop" in normalized_command:
            return window_handler.handle_show_desktop()

        # ─────────────────────────────────────────
        # 🎵 MUSIC
        # ─────────────────────────────────────────

        # ─────────────────────────────────────────
        # 💻 SYSTEM
        # ─────────────────────────────────────────

        elif "shutdown" in normalized_command:
            return system_handler.handle_shutdown()

        elif "restart" in normalized_command:
            return system_handler.handle_restart()

        # ─────────────────────────────────────────
        # ❌ UNRECOGNIZED
        # ─────────────────────────────────────────

        return _result(f"Command not recognized: '{raw_command}'")

    except Exception as exc:
        return _result(f"System error: {exc}")
