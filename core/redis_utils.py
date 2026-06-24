"""
Redis utility functions for message buffering and processing.
"""

import json
import time
import logging
from typing import List, Optional, Dict, Any
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# All Redis keys are namespaced under "pantheon:" to isolate from other
# applications sharing the same Redis instance.  When multi-tenancy lands
# (S1-AUTH-1/S1-AUTH-2), extend _ns() to accept tenant_id.
_NS = "pantheon"


def _ns(key: str) -> str:
    """Return the namespaced Redis key."""
    return f"{_NS}:{key}"


# Message buffering functions
async def add_message_to_buffer(redis: Redis, user_id: str, message_text: str) -> None:
    """Add a message to the user's buffer with timestamp"""
    message_data = {
        "text": message_text,
        "timestamp": time.time()
    }

    buffer_key = _ns(f"user:{user_id}:buffer")

    async with redis.pipeline() as pipe:
        await pipe.rpush(buffer_key, json.dumps(message_data))
        await pipe.expire(buffer_key, 300)  # 5 minutes expiry
        await pipe.execute()

    logger.info(f"Added message to buffer for user {user_id}: {message_text[:20]}...")

async def get_buffered_messages_without_clearing(redis: Redis, user_id: str) -> List[str]:
    """Retrieve messages from buffer without clearing it"""
    buffer_key = _ns(f"user:{user_id}:buffer")
    try:
        messages = await redis.lrange(buffer_key, 0, -1)
        return [json.loads(m)["text"] for m in messages if m]
    except Exception as e:
        logger.error(f"Buffer retrieval error: {str(e)}")
        return []

async def get_buffered_messages_with_timestamps(redis: Redis, user_id: str) -> List[Dict[str, Any]]:
    """Retrieve messages from buffer with their timestamps without clearing it"""
    buffer_key = _ns(f"user:{user_id}:buffer")
    try:
        messages = await redis.lrange(buffer_key, 0, -1)
        return [json.loads(m) for m in messages if m]
    except Exception as e:
        logger.error(f"Buffer retrieval error: {str(e)}")
        return []

async def clear_message_buffer(redis: Redis, user_id: str) -> None:
    """Clear the message buffer after processing"""
    buffer_key = _ns(f"user:{user_id}:buffer")
    await redis.delete(buffer_key)

async def get_buffered_messages(redis: Redis, user_id: str) -> List[str]:
    """Retrieve and clear messages (legacy method, use get_buffered_messages_without_clearing instead)"""
    buffer_key = _ns(f"user:{user_id}:buffer")
    try:
        async with redis.pipeline(transaction=True) as pipe:
            await pipe.lrange(buffer_key, 0, -1)
            await pipe.delete(buffer_key)
            results = await pipe.execute()
        return [json.loads(m)["text"] for m in results[0] if m]
    except Exception as e:
        logger.error(f"Buffer retrieval error: {str(e)}")
        return []

async def is_buffer_active(redis: Redis, user_id: str) -> bool:
    """Check if there's an active processing flag for this user"""
    processing_key = _ns(f"user:{user_id}:processing")
    is_active = bool(await redis.exists(processing_key))
    if is_active:
        logger.info(f"Buffer is already being processed for user {user_id}")
    return is_active

async def set_buffer_processing(redis: Redis, user_id: str, timeout: int = 15) -> None:
    """Set processing flag with extended timeout"""
    await redis.setex(_ns(f"user:{user_id}:processing"), timeout, "1")

async def schedule_processing(redis: Redis, user_id: str, delay_seconds: float) -> bool:
    """Schedule message processing for a user

    Returns:
        bool: True if scheduled, False if already scheduled
    """
    scheduled_key = _ns(f"user:{user_id}:scheduled")

    was_set = await redis.setnx(scheduled_key, str(time.time() + delay_seconds))

    if was_set:
        await redis.expire(scheduled_key, int(delay_seconds * 2))
        logger.info(f"Scheduled processing for user {user_id} in {delay_seconds}s")
    else:
        logger.info(f"Processing already scheduled for user {user_id}")

    return bool(was_set)

async def is_processing_scheduled(redis: Redis, user_id: str) -> bool:
    """Check if processing is scheduled for a user"""
    scheduled_key = _ns(f"user:{user_id}:scheduled")
    return bool(await redis.exists(scheduled_key))

async def clear_processing_schedule(redis: Redis, user_id: str) -> None:
    """Clear the processing schedule flag"""
    scheduled_key = _ns(f"user:{user_id}:scheduled")
    await redis.delete(scheduled_key)
    logger.info(f"Cleared processing schedule for user {user_id}")

async def get_last_processed_time(redis: Redis, user_id: str) -> float:
    """Get the timestamp when messages were last processed for a user

    Returns:
        float: Timestamp of last processing, or 0 if never processed
    """
    last_processed_key = _ns(f"user:{user_id}:last_processed")
    timestamp = await redis.get(last_processed_key)
    return float(timestamp) if timestamp else 0

async def set_last_processed_time(redis: Redis, user_id: str, timestamp: float = None) -> None:
    """Set the timestamp when messages were last processed for a user"""
    last_processed_key = _ns(f"user:{user_id}:last_processed")
    await redis.set(last_processed_key, str(timestamp or time.time()))

# Rate limiting for LLM calls
async def check_llm_rate_limit(redis: Redis, user_id: str, llm_calls_per_minute: int = 5, window_seconds: int = 60) -> Optional[str]:
    """Check if user has exceeded LLM call rate limits

    Returns:
        Optional[str]: Error message if rate limited, None otherwise
    """
    if not redis:
        return None

    key = _ns(f"rate:llm:{user_id}")
    count = await redis.incr(key)

    if count == 1:
        await redis.expire(key, window_seconds)

    if count > llm_calls_per_minute:
        return "You've sent too many messages. Please wait a moment before sending more."

    return None
