import os
import sys
sys.path.append('backend')

from shared.config import settings
import redis

print(f"REDIS_URL from settings: {settings.redis_url}")
print(f"Tenant ID: {settings.tenant_id}")

try:
    r = redis.from_url(settings.redis_url)
    r.ping()
    print("Redis connection: SUCCESS")
except Exception as e:
    print(f"Redis connection: FAILED - {e}")

# Test setting and getting a value
try:
    test_key = f"test:{settings.tenant_id}"
    test_value = {"message": "Redis is working", "timestamp": "2024-01-01"}
    
    r.setex(test_key, 60, str(test_value))  # expires in 1 minute
    retrieved = r.get(test_key)
    
    print(f"Set/Get test: SUCCESS - retrieved {retrieved}")
except Exception as e:
    print(f"Set/Get test: FAILED - {e}")
