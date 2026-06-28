import os
import re
import time
import subprocess
import pyautogui
from utils.os_utils import _result, _bring_window_to_front

def handle_screenshot() -> dict:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(desktop, filename)
    screenshot = pyautogui.screenshot()
    screenshot.save(filepath)
    subprocess.run(f'explorer "{desktop}"', shell=True)
    _bring_window_to_front(["file explorer", "explorer", "desktop"])
    return _result("Screenshot saved to Desktop.")

def handle_move_cursor_center() -> dict:
    width, height = pyautogui.size()
    pyautogui.moveTo(width // 2, height // 2)
    return _result("Cursor moved to center.")

def handle_move_cursor_top_left() -> dict:
    pyautogui.moveTo(0, 0)
    return _result("Cursor moved to top-left.")

def handle_move_cursor_top_right() -> dict:
    width, _ = pyautogui.size()
    pyautogui.moveTo(width, 0)
    return _result("Cursor moved to top-right.")

def handle_move_cursor_bottom_left() -> dict:
    _, height = pyautogui.size()
    pyautogui.moveTo(0, height)
    return _result("Cursor moved to bottom-left.")

def handle_move_cursor_bottom_right() -> dict:
    width, height = pyautogui.size()
    pyautogui.moveTo(width, height)
    return _result("Cursor moved to bottom-right.")

def handle_move_cursor_to(raw_command: str) -> dict:
    nums = re.findall(r"\d+", raw_command)
    if len(nums) >= 2:
        x, y = int(nums[0]), int(nums[1])
        pyautogui.moveTo(x, y)
        return _result(f"Cursor moved to ({x}, {y}).")
    return _result("Could not parse coordinates.")

def handle_click_at(raw_command: str) -> dict:
    nums = re.findall(r"\d+", raw_command)
    if len(nums) >= 2:
        x, y = int(nums[0]), int(nums[1])
        pyautogui.click(x, y)
        return _result(f"Clicked at ({x}, {y}).")
    return _result("Could not parse coordinates.")

def handle_double_click() -> dict:
    pyautogui.doubleClick()
    return _result("Double-clicked.")

def handle_right_click() -> dict:
    pyautogui.rightClick()
    return _result("Right-clicked.")

def handle_click() -> dict:
    pyautogui.click()
    return _result("Clicked.")

def handle_type(raw_command: str) -> dict:
    text = raw_command[5:].strip()
    pyautogui.typewrite(text, interval=0.05)
    return _result(f"Typed: '{text}'.")

def handle_write(raw_command: str) -> dict:
    text = raw_command[6:].strip()
    pyautogui.typewrite(text, interval=0.05)
    return _result(f"Written: '{text}'.")

def handle_press_ctrl_c() -> dict:
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)
    return _result("Pressed Ctrl+C.")

def handle_press_ctrl_v() -> dict:
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    return _result("Pressed Ctrl+V.")

def handle_press_ctrl_s() -> dict:
    pyautogui.hotkey("ctrl", "s")
    time.sleep(0.3)
    return _result("Pressed Ctrl+S.")

def handle_press_ctrl_z() -> dict:
    pyautogui.hotkey("ctrl", "z")
    time.sleep(0.3)
    return _result("Pressed Ctrl+Z.")

def handle_press_ctrl_a() -> dict:
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)
    return _result("Pressed Ctrl+A.")

def handle_press_alt_tab() -> dict:
    pyautogui.hotkey("alt", "tab")
    time.sleep(0.3)
    return _result("Pressed Alt+Tab.")

def handle_press_alt_f4() -> dict:
    pyautogui.hotkey("alt", "f4")
    time.sleep(0.3)
    return _result("Pressed Alt+F4.")

def handle_press_win_d() -> dict:
    pyautogui.hotkey("win", "d")
    time.sleep(0.3)
    return _result("Pressed Win+D.")

def handle_press_enter() -> dict:
    pyautogui.press("enter")
    return _result("Pressed Enter.")

def handle_press_escape() -> dict:
    pyautogui.press("escape")
    return _result("Pressed Escape.")

def handle_press_space() -> dict:
    pyautogui.press("space")
    return _result("Pressed Space.")

def handle_press_tab() -> dict:
    pyautogui.press("tab")
    return _result("Pressed Tab.")

def handle_press_backspace() -> dict:
    pyautogui.press("backspace")
    return _result("Pressed Backspace.")

def handle_press_delete() -> dict:
    pyautogui.press("delete")
    return _result("Pressed Delete.")

def handle_scroll_up(raw_command: str) -> dict:
    nums = re.findall(r"\d+", raw_command)
    amount = int(nums[0]) if nums else 3
    pyautogui.scroll(amount)
    return _result(f"Scrolled up {amount}.")

def handle_scroll_down(raw_command: str) -> dict:
    nums = re.findall(r"\d+", raw_command)
    amount = int(nums[0]) if nums else 3
    pyautogui.scroll(-amount)
    return _result(f"Scrolled down {amount}.")
