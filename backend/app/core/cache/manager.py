#==========================#
#    core.cache.manager    #
#==========================#
"""This file acts like a repository layer targeted for redis cache operations"""


from __future__ import annotations
from collections.abc import Callable , Awaitable
from typing import Any , TypeVar

from app.core.cache.redis import get_redis
from app.core.cache.serialization import dumps , loads

from app.config.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CacheManager:
    """
    Small wrapper around Redis 

    This keeps raw Redis operations out of services and module cache files.
    If Redis is unavailable , these methods fail safely without crashing the app 
    """

    @staticmethod
    async def get_json(
        key : str 
    ) -> None | Any:
        """
        Get a JSON value from Redis 
        Returns None when
        - Redis is unavailable
        - The key does not exist
        - the cached value cannot be decoded
        """
        redis = get_redis()
        if redis is None:
            return None
        
        try:
            cached_value = await redis.get(key)
            return loads(cached_value)

        except Exception:
            logger.exception(f"Failed to get JSON value for key: {key}")
            return None
        




    @staticmethod
    async def set_json(
        key : str,
        value : Any,
        ttl : int 
    ) -> bool:
        """
        Stores a JSON value in Redis

        ttl is in seconds, sets the time for the value to expire
        """

        redis = get_redis()
        if redis is None:
            return False
        

        try:
            await redis.set(key, dumps(value), ex=ttl)
            return True
        except Exception:
            logger.exception(f"Failed to set JSON value for key: {key}")
            return False
        
    

    @staticmethod
    async def delete(
        key : str
    ) -> bool:
        """
        Delete a cache key
        """

        redis = get_redis()
        if redis is None:
            return False
        

        try:
            await redis.delete(key)
            return True
        
        except Exception:
            logger.exception(f"Failed to delete cache key: {key}")
            return False
        


    @staticmethod
    async def delete_many(
        keys : list[str]
    ) -> int:
        """
        Delete multiple cache keys
        returns the number of deleted keys
        """

        if not keys:
            return 0
        

        redis = get_redis()
        if redis is None:
            return 0
        

        try:
            delete_count = await redis.delete(*keys)
            return int(delete_count)
        except Exception:
            logger.exception(f"Failed to delete cache keys: {keys}")
            return 0
        



    @staticmethod
    async def delete_pattern(
        pattern : str,
        batch_size : int = 1000
    ) -> int:
        """
        Delete keys matching a pattern

        Example:
           tenant:123:subjects:*  will delete all keys starting with tenant:123:subjects:

           Uses SCAN  instead of KEYS, so it is safer for production to avoid blocking
        """

        redis = get_redis()
        if redis is None:
            return 0
        
        deleted_count = 0

        try:
            cursor = 0 

            while True:
                cursor , keys = await redis.scan(cursor=cursor, match=pattern, count=batch_size)
                if keys:
                    deleted_count += await redis.delete(*keys)


                if cursor == 0:
                    break

            return deleted_count
    
        except Exception:
            logger.exception(f"Failed to delete cache keys with pattern: {pattern}")
            return 0
        



    @staticmethod
    async def exists(
        key : str
    ) -> bool:
        """
        Check if a cache key exists
        """

        redis = get_redis()
        if redis is None:
            return False
        
        try:
            return bool(await redis.exists(key))
        except Exception:
            logger.exception(f"Failed to check existence of cache key: {key}")
            return False
        



    @staticmethod
    async def get_or_set(
        key  : str ,
        fetcher : Callable[[], Awaitable[T]] ,
        ttl : int
    ):
        """
        Try cace first , if missing , call fetcher to get the value and cache it

        this is useful for caching database queries or other expensive operations
        """

        cached_value = await CacheManager.get_json(key)
        if cached_value is not None:
            return cached_value
        
        fresh_value = await fetcher()
        await CacheManager.set_json(key, fresh_value, ttl)
        return fresh_value
