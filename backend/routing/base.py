from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class CommandContext:
    """
    Context object that flows through the routing handlers.
    Used to pass session details, environment configuration, and local cache.
    """
    def __init__(self, last_results: Optional[List[Dict[str, Any]]] = None):
        self.last_results = last_results if last_results is not None else []
        self.extra_data: Dict[str, Any] = {}


class BaseCommandHandler(ABC):
    """
    Abstract base class for all modular command handlers.
    """
    @abstractmethod
    def can_handle(self, normalized_command: str, raw_command: str, context: CommandContext) -> bool:
        """
        Returns True if this handler matches the command.
        """
        pass

    @abstractmethod
    def handle(self, normalized_command: str, raw_command: str, context: CommandContext) -> Dict[str, Any]:
        """
        Processes the command and returns the JSON-serializable response payload.
        """
        pass
