"""
Test script for AI Project Creator
Run this to verify everything is working before the demo
"""

import os
import sys

def test_imports():
    """Test if all required packages are installed"""
    print("🧪 Testing imports...")
    
    required_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("requests", "Requests"),
    ]
    
    failed = []
    
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {name} installed")
        except ImportError:
            print(f"   ❌ {name} NOT installed")
            failed.append(package)
    
    if failed:
        print(f"\n❌ Missing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt --break-system-packages")
        return False
    
    print("✅ All packages installed!\n")
    return True


def test_ai_module():
    """Test if ai_project_creator module loads"""
    print("🧪 Testing AI module...")
    
    try:
        from ai_project_creator import create_ai_project, parse_create_command
        print("   ✅ ai_project_creator imported successfully")
        
        # Test command parsing
        desc, name = parse_create_command("create ai project for a snake game")
        print(f"   ✅ Command parser works: '{desc}' -> name: {name}")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_api_key():
    """Test if API key is configured"""
    print("🧪 Testing API key configuration...")
    
    try:
        from ai_project_creator import GROQ_API_KEY
        
        if GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
            print("   ⚠️  API key not configured yet")
            print("   📝 Edit ai_project_creator.py and add your Groq API key")
            print("   🔗 Get it from: https://console.groq.com/keys")
            return False
        elif not GROQ_API_KEY or len(GROQ_API_KEY) < 20:
            print("   ❌ API key looks invalid (too short)")
            return False
        else:
            print(f"   ✅ API key configured ({GROQ_API_KEY[:10]}...)")
            return True
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_groq_connection():
    """Test if Groq API is accessible"""
    print("🧪 Testing Groq API connection...")
    
    try:
        import requests
        from ai_project_creator import GROQ_API_KEY
        
        if GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
            print("   ⏭️  Skipped (API key not set)")
            return None
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "user", "content": "Say 'Hello FlowForge!' and nothing else"}
            ],
            "max_tokens": 20
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result["choices"][0]["message"]["content"].strip()
            print(f"   ✅ Groq responded: {text}")
            return True
        else:
            print(f"   ❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        print("   💡 Check your API key and internet connection")
        return False


def test_vscode():
    """Test if VS Code is installed and accessible"""
    print("🧪 Testing VS Code availability...")
    
    try:
        import subprocess
        result = subprocess.run(
            "code --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"   ✅ VS Code installed: {version}")
            return True
        else:
            print("   ❌ VS Code not accessible from terminal")
            print("   💡 Make sure VS Code is in your PATH")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def run_all_tests():
    """Run all tests and show summary"""
    print("=" * 60)
    print("🚀 FLOWFORGE AI - PROJECT CREATOR TEST SUITE")
    print("=" * 60)
    print()
    
    results = {
        "Imports": test_imports(),
        "AI Module": test_ai_module(),
        "API Key": test_api_key(),
        "Groq API": test_groq_connection(),
        "VS Code": test_vscode(),
    }
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⏭️  SKIP"
        print(f"{status}  {test_name}")
    
    print("=" * 60)
    
    # Overall status
    failed = [name for name, result in results.items() if result is False]
    
    if not failed:
        print("\n🎉 ALL TESTS PASSED! You're ready to demo!")
        print("\n📝 Next steps:")
        print("   1. Start backend: python -m uvicorn main:app --reload")
        print("   2. Start frontend: flutter run -d windows")
        print("   3. Try: 'create ai project for a snake game in python'")
    else:
        print(f"\n⚠️  {len(failed)} test(s) failed: {', '.join(failed)}")
        print("\n📝 Fix the issues above before running your demo")
    
    print()


if __name__ == "__main__":
    run_all_tests()