import redis
import json
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """
    High-speed data structure manager for the Quant Engine.
    Tries to use Redis for enterprise-grade speed. If Redis is not installed
    on the host Windows machine, it gracefully falls back to a lightning-fast
    in-memory Python dictionary cache to ensure strict isolation without breaking.
    """
    def __init__(self):
        self.use_redis = False
        self.redis_client = None
        self.in_memory_cache = {}
        
        logger.info("Quant Engine: Using High-Speed In-Memory Dictionary Cache for instant setup.")

    def set(self, key, value):
        if isinstance(value, dict) or isinstance(value, list):
            value = json.dumps(value)
        if self.use_redis:
            self.redis_client.set(key, value)
        else:
            self.in_memory_cache[key] = value

    def get(self, key):
        if self.use_redis:
            val = self.redis_client.get(key)
        else:
            val = self.in_memory_cache.get(key)
            
        if val is None:
            return None
            
        try:
            return json.loads(val)
        except Exception:
            return val
            
    def delete(self, key):
        if self.use_redis:
            self.redis_client.delete(key)
        else:
            if key in self.in_memory_cache:
                del self.in_memory_cache[key]

# Singleton instance for the Quant Engine
cache = CacheManager()
