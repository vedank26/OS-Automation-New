import time
import pyautogui
from utils.os_utils import _result, _bring_window_to_front

def handle_focus_chrome() -> dict:
    _bring_window_to_front(["chrome"])
    return _result("Chrome focused.")

def handle_focus_edge() -> dict:
    _bring_window_to_front(["edge"])
    return _result("Edge focused.")

def handle_focus_vscode() -> dict:
    _bring_window_to_front(["visual studio code", "vscode"])
    return _result("VS Code focused.")

def handle_focus_notepad() -> dict:
    _bring_window_to_front(["notepad"])
    return _result("Notepad focused.")

def handle_focus_terminal() -> dict:
    _bring_window_to_front(["cmd", "powershell", "terminal", "command prompt"])
    return _result("Terminal focused.")

def handle_switch_window() -> dict:
    pyautogui.hotkey("alt", "tab")
    time.sleep(0.3)
    return _result("Switched window.")

def handle_minimize_window() -> dict:
    pyautogui.hotkey("win", "down")
    time.sleep(0.3)
    return _result("Window minimized.")

def handle_maximize_window() -> dict:
    pyautogui.hotkey("win", "up")
    time.sleep(0.3)
    return _result("Window maximized.")

def handle_close_window() -> dict:
    pyautogui.hotkey("alt", "f4")
    time.sleep(0.3)
    return _result("Window closed.")

def handle_show_desktop() -> dict:
    pyautogui.hotkey("win", "d")
    time.sleep(0.3)
    return _result("Desktop shown.")
