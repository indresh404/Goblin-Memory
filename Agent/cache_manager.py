# cache_manager.py - Response caching system

import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict

CACHE_DIR = Path(__file__).parent.parent / "Memory" / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

class ResponseCache:
    def __init__(self, ttl_hours: int = 24):
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_file = CACHE_DIR / "responses.json"
        self.cache = self._load()
    
    def _load(self) -> Dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    now = datetime.now().isoformat()
                    return {k: v for k, v in data.items() if v.get('expires', '') > now}
            except:
                return {}
        return {}
    
    def _save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _get_key(self, query: str, context_hash: str) -> str:
        combined = f"{query}:{context_hash}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, query: str, context: str) -> Optional[str]:
        context_hash = hashlib.md5(context.encode()).hexdigest()
        key = self._get_key(query, context_hash)
        
        if key in self.cache:
            if datetime.now().isoformat() < self.cache[key]['expires']:
                return self.cache[key]['response']
            else:
                del self.cache[key]
                self._save()
        return None
    
    def set(self, query: str, context: str, response: str):
        context_hash = hashlib.md5(context.encode()).hexdigest()
        key = self._get_key(query, context_hash)
        
        expires = (datetime.now() + self.ttl).isoformat()
        self.cache[key] = {
            'response': response,
            'expires': expires,
            'query': query[:100],
            'timestamp': datetime.now().isoformat()
        }
        self._save()
    
    def clear(self):
        self.cache = {}
        self._save()
    
    def stats(self) -> Dict:
        return {'size': len(self.cache), 'ttl_hours': self.ttl.total_seconds() / 3600}

# Global instance
_cache = ResponseCache()

def get_cached_response(query: str, context: str) -> Optional[str]:
    return _cache.get(query, context)

def cache_response(query: str, context: str, response: str):
    _cache.set(query, context, response)

def clear_cache():
    _cache.clear()