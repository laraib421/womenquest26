"""Run before the competition:  python check_setup.py
Checks Python, virtual environment, packages, .env, the Gemini API, git, and other languages."""
import os
import shutil
import subprocess
import sys

OK, BAD, WARN = "[ OK ]", "[FAIL]", "[WARN]"
failed = 0


def report(status, msg):
    global failed
    if status == BAD:
        failed += 1
    print(f"{status} {msg}")


def version_of(cmd):
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return None


# Python and virtual environment
report(OK, f"Python {sys.version.split()[0]}")
in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
if in_venv:
    report(OK, f"Virtual environment active: {sys.prefix}")
else:
    report(WARN, "No virtual environment active. Create one:  python -m venv venv  then  venv\\Scripts\\activate")

# Packages
for pkg in ("openai", "dotenv", "pydantic"):
    try:
        __import__(pkg)
        report(OK, f"package '{pkg}' installed")
    except ImportError:
        name = "python-dotenv" if pkg == "dotenv" else pkg
        report(BAD if pkg != "pydantic" else WARN, f"package '{pkg}' missing:  pip install {name}")

# .env and API key
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
ALLOWED = {"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"}
report(OK if key else BAD, "GEMINI_API_KEY is set" if key else "GEMINI_API_KEY missing in .env")
report(OK if model in ALLOWED else BAD,
       f"model '{model}' is allowed" if model in ALLOWED else f"model '{model}' is NOT allowed -> use one of {sorted(ALLOWED)}")

# Live API call
if key:
    try:
        import llm
        reply = llm.ask("Reply with the single word: ready", max_tokens=20)
        report(OK, f"Gemini API call works -> {reply.strip()[:40]!r}")
    except Exception as e:
        report(BAD, f"Gemini API call failed: {str(e)[:150]}")

# Git and .env safety
if shutil.which("git"):
    report(OK, version_of("git"))
    ignored = subprocess.run(["git", "check-ignore", ".env"], capture_output=True).returncode == 0
    report(OK if ignored else BAD, ".env is git-ignored" if ignored else ".env is NOT git-ignored! add it to .gitignore")
else:
    report(BAD, "git not found")

# Other languages (for choosing)
print("\nLanguages / tools on this laptop:")
for cmd in ("python", "node", "npm"):
    v = version_of(cmd)
    print(f"  {cmd:7} {v or 'not installed'}")

print("\nAll good!" if not failed else f"\n{failed} problem(s) to fix before the event.")
sys.exit(1 if failed else 0)
