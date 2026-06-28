import subprocess
from utils.os_utils import _result

def handle_shutdown() -> dict:
    subprocess.run("shutdown /s /t 5", shell=True)
    return _result("PC will shut down in 5 seconds.")

def handle_restart() -> dict:
    subprocess.run("shutdown /r /t 5", shell=True)
    return _result("PC will restart in 5 seconds.")
