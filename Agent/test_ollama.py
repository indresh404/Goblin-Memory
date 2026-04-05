# test_ollama.py - Test Ollama connection and speed

import requests
import time

OLLAMA_URL = "http://localhost:11434"

def test_ollama():
    print("Testing Ollama connection...")
    
    # Check if Ollama is running
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json()
            print(f"✓ Ollama is running")
            print(f"  Available models: {[m['name'] for m in models.get('models', [])]}")
        else:
            print(f"✗ Ollama returned status {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Cannot connect to Ollama: {e}")
        print("\nPlease start Ollama first:")
        print("  ollama serve")
        return False
    
    # Test a simple prompt
    print("\nTesting simple prompt...")
    start = time.time()
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "mistral",
                "prompt": "Say 'Hello World' in one line.",
                "stream": False,
                "options": {"num_predict": 20}
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            elapsed = time.time() - start
            print(f"✓ Response received in {elapsed:.1f} seconds")
            print(f"  Response: {result.get('response', '')[:100]}")
            return True
        else:
            print(f"✗ Error: {resp.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout after 30 seconds - Ollama might be overloaded")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    test_ollama()