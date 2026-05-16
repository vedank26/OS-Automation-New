import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import automation_1
from speech_engine import listen, listen_short

def start_assistant():
    print("=======================================")
    print("🚀 Voice Assistant Started")
    print("=======================================")
    print("Press Ctrl+C to stop.")
    print("=======================================\n")

    try:
        while True:
            print("👂 Waiting for command...\n")
            command = listen()

            if not command:
                print("⏳ No command recognized. Listening again...\n")
                continue

            # ── keyword check ──────────────────────────────────
            known_keywords = [
                "open", "search", "create", "run", "start", "launch",
                "press", "click", "type", "write", "scroll", "move",
                "screenshot", "shutdown", "restart", "focus", "play",
                "take", "minimize", "maximize", "close", "show",
                "switch", "double", "right", "save", "execute"
            ]

            has_keyword = any(
                command.lower().startswith(k) for k in known_keywords
            )

            if not has_keyword and "youtube" not in command.lower():
                print(f"🎵 No keyword — treating as YouTube search")
                command = f"play {command} on youtube"
                print(f"⚙️ Modified command: {command}")

            print(f"⚙️ Executing: {command}")
            response = automation_1.execute_command(command)  # ✅ use module

            if isinstance(response, dict):
                result_text = response.get('result', 'No result')
                options = response.get('options', None)
            else:
                result_text = 'Command executed.'
                options = None

            print(f"➡️ {result_text}\n")

            # ── YouTube options ────────────────────────────────
            if options:
                print("🎵 Results:")
                for i, title in enumerate(options, 1):
                    print(f"  {i}. {title}")
                print("\n👂 Say a number (e.g. 'play 2' or 'second')...\n")

                max_attempts = 3
                attempts = 0

                while attempts < max_attempts:
                    selection = listen_short()

                    if not selection:
                        attempts += 1
                        print(f"⏳ Didn't catch that. {max_attempts - attempts} attempts left...\n")
                        continue

                    print(f"⚙️ Selection: {selection}")
                    sel_response = automation_1.execute_command(selection)  # ✅ use module

                    if isinstance(sel_response, dict):
                        sel_result = sel_response.get('result', 'No result')
                    else:
                        sel_result = 'Done.'

                    print(f"➡️ {sel_result}\n")

                    if "Playing video" in sel_result:
                        print("✅ Video playing! Back to listening...\n")
                        break
                    elif "Invalid" in sel_result or "No YouTube" in sel_result:
                        attempts += 1
                        print(f"❌ Invalid. Try again ({max_attempts - attempts} left)...\n")
                    else:
                        break

                if attempts >= max_attempts:
                    print("⚠️ No valid selection. Back to listening...\n")

    except KeyboardInterrupt:
        print("\n\n🛑 Voice Assistant stopped.")


if __name__ == "__main__":
    start_assistant()