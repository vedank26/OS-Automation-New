import os
from app_launcher import launch_app
from utils.os_utils import _result


def can_handle_workflow(normalized_command: str) -> bool:
    """Check if command is a workflow request"""
    return "start coding session" in normalized_command


def handle_workflow() -> dict:
    """Handle workflow commands"""
    folder_path = os.path.join(os.path.expanduser("~"), "Desktop", "TodayWork")
    os.makedirs(folder_path, exist_ok=True)
    vscode_result = launch_app("vs code")
    chrome_result = launch_app("chrome")
    
    if vscode_result.success and chrome_result.success:
        return _result("Coding session started. VS Code and Chrome opened, TodayWork folder created.")
    
    failures = [result.message for result in [vscode_result, chrome_result] if not result.success]
    return _result(
        "Coding session started partially. "
        f"TodayWork folder created. {' '.join(failures)}"
    )
