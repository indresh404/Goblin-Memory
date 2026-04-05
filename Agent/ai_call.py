"""
ai_call.py — AI backend router
Primary  : Ollama (local, free, GPU-accelerated)
Fallback : Groq   (free cloud, ultra-fast)
"""

import requests
import re
import json
import os
from typing import Optional, Generator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Will be empty if not set
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

# Model configuration - define BEFORE using them
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "phi3:mini")  # Fast model for quick responses
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


# ─── Ollama ───────────────────────────────────────────────────────────────────

def is_ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def call_ollama(
    prompt: str,
    system: Optional[str] = None,
    model: str = OLLAMA_MODEL,
    temperature: float = 0.3,
    timeout: int = 120,
) -> Optional[str]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        session = requests.Session()
        session.timeout = (30, timeout)
        
        resp = session.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 2048},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        print(f"  [Ollama timeout after {timeout}s]")
        return None
    except Exception as e:
        print(f"[Ollama error] {e}")
        return None


def call_ollama_fast(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
    timeout: int = 30,
) -> Optional[str]:
    """Faster version with smaller model and shorter response"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_FAST_MODEL,  # Use phi3:mini for speed
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 256},  # Short responses
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        print(f"[Ollama fast error] {e}")
        return None


def ai_stream(
    prompt: str,
    system: Optional[str] = None,
    model: str = None,
    temperature: float = 0.3,
) -> Generator[str, None, None]:
    """Stream AI response token by token for instant feedback"""
    if model is None:
        model = OLLAMA_FAST_MODEL
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": temperature, "num_predict": 512},
            },
            timeout=60,
            stream=True
        )
        
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if 'message' in data and 'content' in data['message']:
                        yield data['message']['content']
                    if data.get('done', False):
                        break
                except:
                    continue
    except Exception as e:
        yield f"[Error: {e}]"


# ─── Groq ─────────────────────────────────────────────────────────────────────

def call_groq(
    prompt: str,
    system: Optional[str] = None,
    model: str = GROQ_MODEL,
    temperature: float = 0.3,
) -> Optional[str]:
    # Check if API key is set and not the example placeholder
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages, "max_tokens": 2048, "temperature": temperature},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[Groq error] {e}")
        return None


# ─── Smart Router ─────────────────────────────────────────────────────────────

def ai(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.3,
    verbose: bool = True,
) -> str:
    """Call AI with automatic fallback: Ollama -> Groq"""
    
    if is_ollama_running():
        result = call_ollama(prompt, system, temperature=temperature)
        if result:
            if verbose:
                print(f"  [🖥️  Ollama/{OLLAMA_MODEL}]")
            return result

    result = call_groq(prompt, system, temperature=temperature)
    if result:
        if verbose:
            print(f"  [☁️  Groq/{GROQ_MODEL}]")
        return result

    return (
        "⚠️ No AI backend available.\n"
        "→ Install Ollama: https://ollama.com\n"
        "→ Then run: ollama pull mistral\n"
        "→ For faster responses: ollama pull phi3:mini"
    )


def ai_fast(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
    verbose: bool = False,
) -> str:
    """Fast AI call using smaller model for quick responses"""
    
    if is_ollama_running():
        result = call_ollama_fast(prompt, system, temperature=temperature)
        if result:
            return result
    
    # Fallback to regular Ollama
    return ai(prompt, system, temperature=temperature, verbose=verbose)


def ai_json(
    prompt: str,
    system: Optional[str] = None,
    retries: int = 2,
) -> Optional[dict]:
    """Call AI and robustly parse JSON response."""
    sys_prompt = (system or "") + (
        "\n\nCRITICAL: Your entire response must be a JSON array of objects. "
        "Each object represents a node. No markdown. No backticks. No explanation. "
        "Start with [[ and end with ]]."
    )

    for attempt in range(retries + 1):
        raw = ai(prompt, sys_prompt, temperature=0.05, verbose=False)
        if not raw:
            continue

        # Extraction strategies
        candidates = []
        cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).replace("```", "").strip()
        candidates.append(cleaned)
        
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            candidates.append(m.group(0))
        
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            candidates.append(m.group(0))

        for candidate in candidates:
            try:
                result = json.loads(candidate)
                if isinstance(result, dict) or isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        if attempt < retries:
            print(f"  [ai_json] Parse failed, retrying ({attempt+1}/{retries})...")

    return None


# ─── Install helper ───────────────────────────────────────────────────────────

SETUP_GUIDE = """
╔══════════════════════════════════════════════════════════╗
║         FREE AI OPTIONS FOR YOUR 16 GB GPU              ║
╠══════════════════════════════════════════════════════════╣
║  🏆 RECOMMENDED: Ollama (local, GPU, 100% free)         ║
║     1. Download: https://ollama.com/download             ║
║     2. Run:  ollama pull mistral    (quality)           ║
║        OR:   ollama pull phi3:mini  (fastest)           ║
║     3. Ollama starts auto on boot                       ║
╠══════════════════════════════════════════════════════════╣
║  ⚡ For fastest responses:                              ║
║     ollama pull phi3:mini                               ║
║     Then use 'fast' command in main.py                  ║
╚══════════════════════════════════════════════════════════╝
"""

# ─── .env file template ──────────────────────────────────────────────────────

ENV_TEMPLATE = """# Groq API Key (optional - only if you want cloud fallback)
# Get your key from: https://console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# Ollama settings (optional - defaults shown)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_FAST_MODEL=phi3:mini
GROQ_MODEL=llama-3.1-8b-instant
"""


def create_env_file():
    """Create .env file if it doesn't exist"""
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if not os.path.exists(env_path):
        with open(env_path, 'w') as f:
            f.write(ENV_TEMPLATE)
        print(f"✅ Created .env file at {env_path}")
        print("   Edit it to add your Groq API key (optional)")


if __name__ == "__main__":
    create_env_file()
    print(SETUP_GUIDE)
    print("Testing AI connection...")
    print(ai("Say 'AI Brain is ready!' in one line."))