# 🤖 AI Project Creator - Setup Guide

## What This Does

When you say **"create ai project for a snake game in python"**, the AI:
1. ✅ Analyzes your request using Gemini AI
2. ✅ Generates complete project structure (folders + files)
3. ✅ Writes production-ready code for all files
4. ✅ Opens the project in VS Code automatically
5. ✅ Brings VS Code window to the front

---

## 🚀 Setup Instructions

### Step 1: Install Dependencies

Open your terminal in the `backend` folder and run:

```bash
pip install -r requirements.txt --break-system-packages
```

**What this installs:**
- `fastapi` - Web framework
- `uvicorn` - Server
- `google-generativeai` - Gemini AI SDK
- `pygetwindow` - Window management (to bring VS Code to front)

---

### Step 2: Get Your FREE Gemini API Key

1. Go to: **https://aistudio.google.com**
2. Click "Get API Key"
3. Create a new API key (it's completely free)
4. Copy the key

---

### Step 3: Add Your API Key

Open `backend/ai_project_creator.py` and replace this line:

```python
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
```

With your actual key:

```python
GEMINI_API_KEY = "AIzaSyBa3KLM5nOp6QrStUvWxYz0123456789ABC"
```

---

## 🎯 Supported Commands

### Basic AI Project Creation

```
"create ai project for a snake game in python"
"build me a calculator app"
"make a weather dashboard"
"create a todo list app in react"
```

### With Custom Project Names

```
"create project named snake-game for a python snake game"
"build me a project called my-calc for a calculator in html"
```

### What It Can Build

- **Python projects** - Games, CLI tools, automation scripts
- **React apps** - Web applications with components
- **HTML/CSS/JS** - Websites, dashboards, interactive pages
- **Node.js apps** - Backend APIs, servers
- **Any code project** - The AI is smart enough to handle most requests!

---

## 📂 What Gets Created

### Example: "create ai project for a snake game"

The AI creates:

```
Desktop/snake_game/
├── main.py              ← Complete working snake game code
├── utils.py             ← Helper functions (if needed)
├── requirements.txt     ← Dependencies (if needed)
└── README.md            ← Instructions on how to run it
```

All files have **real, working code** - not placeholders!

---

## ⚡ How It Works Internally

1. **User command** → `"create ai project for X"`
2. **Backend** calls `create_ai_project(description)`
3. **Gemini AI** receives a detailed prompt asking for:
   - Project structure (folders + files)
   - Complete code for each file
   - README with setup instructions
4. **AI responds** with JSON containing all the code
5. **Backend**:
   - Creates project folder on Desktop
   - Creates all subdirectories
   - Writes all files with AI-generated code
   - Opens VS Code with `code "path/to/project"`
   - Brings VS Code to front using `pygetwindow`

---

## 🔥 Example Session

**User types:** `create ai project for a tic tac toe game in python`

**Backend logs:**
```
🤖 AI is analyzing your project idea...
📁 Created project folder: tic_tac_toe
   ✅ Created: main.py
   ✅ Created: game_logic.py
   ✅ Created: README.md
```

**Frontend shows:**
```
✅ AI Project Created: 'tic_tac_toe'
📂 Type: python
📝 Files: main.py, game_logic.py, README.md
💻 Opened in VS Code
📍 Location: Desktop/tic_tac_toe
```

**VS Code opens** with:
- `main.py` - Complete tic tac toe game with board, input, win detection
- `game_logic.py` - Helper functions for game mechanics
- `README.md` - How to run the game

**User can immediately run:** `python main.py` ✅

---

## 🛠️ Troubleshooting

### "Module 'google.generativeai' not found"
```bash
pip install google-generativeai --break-system-packages
```

### "Invalid API key"
- Make sure you copied the full key from aistudio.google.com
- Check for spaces or quotes around the key in `ai_project_creator.py`

### "VS Code doesn't open"
Make sure VS Code is installed and accessible from terminal:
```bash
code --version
```

If not working, add VS Code to PATH or reinstall VS Code.

### "Window doesn't come to front"
The `pygetwindow` library only works on Windows. On Mac/Linux, VS Code will open but might not automatically focus. You can manually click on it.

---

## 🏆 Why This Is a Winning Feature

### For Judges:
✅ **True AI OS integration** - Uses AI to control the OS (file creation, VS Code launch)  
✅ **Real productivity boost** - Goes from idea → working code in seconds  
✅ **Flexible and smart** - Handles any project type, any framework  
✅ **Production-ready output** - AI writes complete, runnable code  

### Compared to Generic Assistants:
❌ ChatGPT/Copilot: Give you code to copy-paste manually  
✅ **FlowForge**: Creates the entire project structure AND opens it for you  

---

## 📊 Demo Script for Presentation

**Opening:**
> "FlowForge AI doesn't just answer questions - it builds entire projects for you using AI, then opens them in VS Code automatically."

**Demo commands to show:**
1. `"create ai project for a snake game in python"` ← Classic example
2. `"build me a calculator app in html css js"` ← Web project
3. `"create project named todo-app for a task manager in react"` ← Named project

**For each:**
- Show the command being typed
- Show the AI response
- Show VS Code opening with the files
- **Run the code** to prove it actually works!

**Closing:**
> "Traditional assistants give you code. FlowForge gives you ready-to-run projects. This is what an AI OS should do."

---

## 🎯 Next Steps to Make It Even Better (Optional Enhancements)

1. **Add voice confirmation**: After creating, ask "Would you like me to run it?"
2. **Support more frameworks**: Add Flutter, Next.js, Django templates
3. **Git integration**: Auto-initialize git repo and make first commit
4. **Install dependencies**: Auto-run `npm install` or `pip install -r requirements.txt`
5. **Open terminal**: Also open integrated terminal in VS Code

---

## 📝 Quick Reference

| Command Pattern | Example | What It Creates |
|----------------|---------|-----------------|
| `create ai project for X` | `create ai project for a snake game` | Auto-named project with AI code |
| `create project named Y for X` | `create project named my-game for a snake game` | Custom-named project |
| `build me X` | `build me a calculator` | Auto-named project |
| `make a X` | `make a weather app` | Auto-named project |

---

## 🔐 Security Note

- Your Gemini API key is stored locally in `ai_project_creator.py`
- Never commit this file to public GitHub repos
- Add `ai_project_creator.py` to `.gitignore` if sharing code
- Or use environment variables: `os.getenv("GEMINI_API_KEY")`

---

## 📞 Support

If something doesn't work:
1. Check the terminal running `uvicorn` for error messages
2. Verify your API key is correct
3. Make sure all dependencies are installed
4. Test Gemini API separately: https://aistudio.google.com

---

**Built with ❤️ for the hackathon. This feature alone could win you the competition! 🏆**
