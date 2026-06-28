import re
from app_launcher import launch_app
from utils.os_utils import _result


def can_handle_launch(raw_command: str) -> bool:
    """Check if command is an app launch request (excluding digit-only for media selection)"""
    open_match = re.match(r"^open\s+(.+)$", raw_command, flags=re.IGNORECASE)
    if open_match:
        app_name = open_match.group(1).strip()
        # Digit-only commands (e.g., "open 1") are for media video selection
        # They must NOT be handled by launcher_handler
        return not re.fullmatch(r"\d+", app_name)
    return False


def handle_launch(raw_command: str) -> dict:
    """Handle app launch command"""
    open_match = re.match(r"^open\s+(.+)$", raw_command, flags=re.IGNORECASE)
    if open_match:
        app_name = open_match.group(1).strip()
        app_result = launch_app(app_name)
        return _result(app_result.message)
    return _result("Invalid launch command.")
