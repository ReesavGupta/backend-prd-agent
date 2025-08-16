import redis
import json
from typing import Optional, Dict, Any
import os

class RedisService:
    def __init__(self):
        try:
            # self.redis_client = redis.Redis(
            #     host=os.getenv("REDIS_HOST", "localhost"),
            #     port=int(os.getenv("REDIS_PORT", 6379)),
            #     db=0,
            #     decode_responses=True
            # )
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST"),
                port=int(os.getenv("REDIS_PORT")),
                decode_responses=True,
                username=os.getenv("REDIS_USERNAME"),
                password=os.getenv("REDIS_PASSWORD"),
            )
            # Test connection
            self.redis_client.ping()
            print("Redis connected successfully")
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self.redis_client = None
    
    def cache_prd(self, session_id: str, prd_data: Dict, ttl: int = 3600) -> None:
        """Cache PRD data in Redis for quick access"""
        key = f"prd:cache:{session_id}"
        self.redis_client.setex(key, ttl, json.dumps(prd_data))
    
    def get_cached_prd(self, session_id: str) -> Optional[Dict]:
        """Get cached PRD data"""
        key = f"prd:cache:{session_id}"
        data = self.redis_client.get(key)
        return json.loads(data) if data else None
    
    def cache_diagram(self, session_id: str, diagram_type: str, mermaid_code: str) -> None:
        """Cache generated diagrams"""
        key = f"diagram:{session_id}:{diagram_type}"
        self.redis_client.setex(key, 7200, mermaid_code)  # 2 hour TTL
    
    def get_cached_diagram(self, session_id: str, diagram_type: str) -> Optional[str]:
        """Get cached diagram"""
        key = f"diagram:{session_id}:{diagram_type}"
        return self.redis_client.get(key)