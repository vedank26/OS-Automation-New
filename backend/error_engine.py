import re
from dataclasses import dataclass


ERROR_PATTERNS = [
    (r"Module not found", "dependency_or_import"),
    (r"Cannot find module", "dependency_or_import"),
    (r"Can't resolve", "dependency_or_import"),
    (r"Could not resolve", "dependency_or_import"),
    (r"ModuleNotFoundError", "python_import"),
    (r"ImportError", "python_import"),
    (r"SyntaxError", "syntax"),
    (r"TypeError", "runtime"),
    (r"ReferenceError", "runtime"),
    (r"npm ERR!", "npm"),
    (r"Build failed", "build"),
    (r"Failed to compile", "build"),
    (r"Compilation failed", "build"),
    (r"Gradle task .* failed", "flutter"),
    (r"Error: .*", "runtime"),
]

NOISE_PATTERNS = [
    r"warning",
    r"deprecated",
    r"funding",
    r"audited .* packages",
    r"compiled successfully",
]

SUCCESS_PATTERNS = [
    r"Local:\s+http://",
    r"ready in \d+",
    r"compiled successfully",
    r"running on http://",
    r"development server is running",
]


@dataclass
class ErrorSummary:
    has_error: bool
    category: str = ""
    root_message: str = ""
    error_text: str = ""

    def to_dict(self) -> dict:
        return {
            "has_error": self.has_error,
            "category": self.category,
            "root_message": self.root_message,
            "error_text": self.error_text,
        }


def _is_noise(line: str) -> bool:
    lowered = line.lower()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in NOISE_PATTERNS)


def is_success_log(log_text: str) -> bool:
    return any(re.search(pattern, log_text, re.IGNORECASE) for pattern in SUCCESS_PATTERNS)


def extract_error(log_text: str) -> dict:
    lines = [line.rstrip() for line in log_text.replace("\r\n", "\n").split("\n")]
    meaningful = [line for line in lines if line.strip() and not _is_noise(line)]

    for index, line in enumerate(meaningful):
        for pattern, category in ERROR_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                start = max(0, index - 6)
                end = min(len(meaningful), index + 14)
                context = "\n".join(meaningful[start:end]).strip()
                return ErrorSummary(
                    has_error=True,
                    category=category,
                    root_message=line.strip(),
                    error_text=context,
                ).to_dict()

    return ErrorSummary(has_error=False).to_dict()


def has_meaningful_error(log_text: str) -> bool:
    return bool(extract_error(log_text).get("has_error"))
