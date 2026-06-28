import os
import re
import requests
import subprocess
import webbrowser
from utils.os_utils import _result, _bring_window_to_front
from handlers import project_handler

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"

LAST_RESULTS = []
FILLER_WORDS = {"on", "the", "a", "an", "in", "at"}


def save_last_results(results):
    pass


def log_youtube_api_status():
    if os.getenv("YOUTUBE_API_KEY"):
        print("YouTube API Loaded: Yes")
    else:
        print("YouTube API Loaded: No")


def _get_youtube_api_key() -> str | None:
    return os.getenv("YOUTUBE_API_KEY")


def search_youtube(query: str):
    global LAST_RESULTS
    youtube_api_key = _get_youtube_api_key()
    if not youtube_api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not configured in backend/.env")

    response = requests.get(
        YOUTUBE_API_URL,
        params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 5,
            "key": youtube_api_key,
        },
        timeout=10,
    )
    response.raise_for_status()

    payload = response.json()
    if not payload.get("items"):
        return []

    if "error" in payload:
        message = payload["error"].get("message", "Unknown YouTube API error")
        raise RuntimeError(message)

    results = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        title = item.get("snippet", {}).get("title")
        if video_id and title:
            results.append({"videoId": video_id, "title": title})

    LAST_RESULTS = results
    save_last_results(results)
    return results


def play_video(index: int):
    global LAST_RESULTS
    if not LAST_RESULTS:
        return _result(
            "No YouTube results available. "
            "Use 'play <query> on youtube' first."
        )

    if index < 0 or index >= len(LAST_RESULTS):
        return _result(
            f"Invalid video number. Choose between 1 and {len(LAST_RESULTS)}."
        )

    video = LAST_RESULTS[index]
    video_url = f"https://www.youtube.com/watch?v={video['videoId']}&autoplay=1"
    webbrowser.open(video_url)
    _bring_window_to_front(["youtube", "edge", "chrome"])
    return _result(f"Playing video {index + 1}: '{video['title']}'")


def _get_video_index(command: str):
    global LAST_RESULTS
    cmd = command.strip().lower()
    word_map = {
        "play 1": 0, "first": 0,  "1": 0, "one": 0, "option 1": 0, "option one": 0, "play option 1": 0,
        "play 2": 1, "second": 1, "2": 1, "two": 1, "option 2": 1, "option two": 1, "play option 2": 1,
        "play 3": 2, "third": 2,  "3": 2, "three": 2, "option 3": 2, "option three": 2, "play option 3": 2,
        "play 4": 3, "fourth": 3, "4": 3, "four": 3, "option 4": 3, "option four": 3, "play option 4": 3,
        "play 5": 4, "fifth": 4,  "5": 4, "five": 4, "option 5": 4, "option five": 4, "play option 5": 4,
    }

    if cmd in word_map:
        return word_map[cmd]

    if cmd.startswith("option "):
        try: return int(cmd.split()[1]) - 1
        except: pass

    if cmd.startswith("play option "):
        try: return int(cmd.split()[2]) - 1
        except: pass

    if LAST_RESULTS:
        for idx, video in enumerate(LAST_RESULTS):
            title = video.get("title", "").lower()
            if cmd == title or (len(cmd) > 3 and cmd in title):
                return idx

        if cmd.startswith("play "):
            play_query = cmd[5:].strip()
            for idx, video in enumerate(LAST_RESULTS):
                title = video.get("title", "").lower()
                if play_query == title or (len(play_query) > 3 and play_query in title):
                    return idx

    return None


def _extract_youtube_play_query(raw_command: str):
    query = raw_command.lower()

    noise_phrases = [
        "on youtube", "in youtube", "on the youtube",
        "youtube search", "search youtube for",
        "search youtube", "search on youtube",
        "find on youtube", "play on youtube",
        "play in youtube", "youtube play",
        "on yt", "in yt", "youtube",
    ]

    for phrase in noise_phrases:
        query = query.replace(phrase, "").strip()

    if query.startswith("play "):
        query = query[5:].strip()

    query = " ".join(w for w in query.split() if w.lower() not in FILLER_WORDS)
    query = " ".join(query.split()).strip()

    return query if query else None


def handle_media_command(
    normalized_command: str,
    raw_command: str,
    is_project_command=None,
):
    global LAST_RESULTS

    video_index = _get_video_index(normalized_command)
    if video_index is not None and LAST_RESULTS:
        return play_video(video_index)

    if re.search(r'\byoutube\b', normalized_command) or re.search(r'\byt\b', normalized_command):
        query = _extract_youtube_play_query(raw_command)
        if query:
            try:
                results = search_youtube(query)
            except requests.RequestException as exc:
                LAST_RESULTS = []
                return _result(f"YouTube API request failed: {exc}")
            except RuntimeError as exc:
                LAST_RESULTS = []
                return _result(f"YouTube search is not available: {exc}")
            except Exception as exc:
                LAST_RESULTS = []
                return _result(f"Failed to search YouTube: {exc}")

            if not results:
                LAST_RESULTS = []
                return _result("No results found")

            LAST_RESULTS = results
            save_last_results(results)
            return {
                "result": f"YouTube results for '{query}'. Say which to play.",
                "options": [result["title"] for result in results],
            }

        webbrowser.open("https://www.youtube.com")
        _bring_window_to_front(["youtube", "edge", "chrome"])
        return _result("YouTube opened.")

    if normalized_command.startswith("play ") and not project_handler.is_project_command(normalized_command):
        try:
            index = int(normalized_command.split()[1]) - 1
            if LAST_RESULTS:
                return play_video(index)
        except (ValueError, IndexError):
            pass

        query = normalized_command[5:].strip()
        query = " ".join(w for w in query.split() if w.lower() not in FILLER_WORDS)
        if query:
            try:
                results = search_youtube(query)
            except Exception as exc:
                LAST_RESULTS = []
                return _result(f"YouTube search failed: {exc}")

            if not results:
                LAST_RESULTS = []
                return _result("No results found")

            LAST_RESULTS = results
            save_last_results(results)
            return {
                "result": f"YouTube results for '{query}'. Say which to play.",
                "options": [result["title"] for result in results],
            }
        return _result("Please specify a song name.")

    if re.fullmatch(r"open\s+\d+", normalized_command):
        try:
            index = int(normalized_command.split()[1]) - 1
            return play_video(index)
        except Exception:
            return _result("Invalid selection")

    if "play music" in normalized_command or "play song" in normalized_command:
        subprocess.run("start wmplayer", shell=True)
        _bring_window_to_front(["windows media player", "wmplayer"])
        return _result("Music player opened.")

    return None
