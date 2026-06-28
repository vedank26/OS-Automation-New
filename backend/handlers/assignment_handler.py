from assignment_solver import is_assignment_command, solve_assignment
from utils.os_utils import _result


def can_handle_assignment(normalized_command: str) -> bool:
    return is_assignment_command(normalized_command)


def handle_assignment(raw_command: str) -> dict:
    result = solve_assignment(raw_command)
    return _result(result)
