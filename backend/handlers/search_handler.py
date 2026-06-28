import webbrowser
from urllib.parse import quote_plus

from utils.os_utils import _result, _bring_window_to_front


def can_handle_search(normalized_command: str) -> bool:
    return "search" in normalized_command


def handle_search(raw_command: str) -> dict:
    query = raw_command.lower().replace("search", "").strip()
    noise_phrases = [
        "on chrome", "on google", "in chrome", "in google",
        "in browser", "on browser", "using chrome", "using google",
        "on the internet", "on internet", "on web", "on the web",
    ]
    for phrase in noise_phrases:
        query = query.replace(phrase, "").strip()
    query = " ".join(query.split()).strip()
    if query:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url)
        _bring_window_to_front(["chrome", "edge", "google"])
        return _result(f"Searching Google for '{query}'.")
    webbrowser.open("https://www.google.com")
    _bring_window_to_front(["chrome", "edge"])
    return _result("Google opened.")
