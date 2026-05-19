"""
Redis 客户端封装
-----------------
Key Schema（参考 docs/list.md §4）：
  ai:tutor:seen-q:{uid}     -> Set   已做题目去重池（无TTL，Session结束后异步同步到MySQL）
  ai:tutor:review-q:{uid}   -> ZSet  错题复习优先队列（Score = next_review_timestamp, TTL 30天）
  ai:tutor:mastery:{uid}    -> Hash  实时掌握度缓存（Field=知识点名, Value=0-100整数, TTL 7天）
  ai:tutor:session:{sid}    -> Hash  Session临时状态（TTL 2小时）
  ai:tutor:profile:{uid}    -> Hash  用户基础画像缓存（Field=theta/total_q/..., TTL 30min）
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional, Set

import redis.asyncio as aioredis

from utils.config import settings
from utils.logger import logger

# ---------------------------------------------------------------------------
# 全局连接池（懒初始化）
# ---------------------------------------------------------------------------

_redis: Optional[aioredis.Redis] = None
_redis_available: bool = True  # 缓存 Redis 可用状态，首次失败后快速跳过
_redis_check_time: float = 0.0


async def is_redis_available() -> bool:
    """快速检查 Redis 是否可用（每 30 秒重试一次）"""
    global _redis_available, _redis_check_time
    if not _redis_available:
        now = time.time()
        if now - _redis_check_time < 30:
            return False
        _redis_check_time = now
    return True


def mark_redis_unavailable():
    """标记 Redis 不可用"""
    global _redis_available, _redis_check_time
    _redis_available = False
    _redis_check_time = time.time()
    logger.warning("Redis 不可用，切换到离线模式")


async def get_redis() -> aioredis.Redis:
    global _redis, _redis_available, _redis_check_time
    if not _redis_available:
        now = time.time()
        if now - _redis_check_time < 30:
            raise Exception("Redis unavailable (cached)")
        _redis_check_time = now
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            # Test connection
            await _redis.ping()
            _redis_available = True
        except Exception:
            _redis = None
            _redis_available = False
            _redis_check_time = time.time()
            logger.warning("Redis 不可用，切换到离线模式")
            raise Exception("Redis unavailable")
    return _redis


async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


# ---------------------------------------------------------------------------
# TTL 常量
# ---------------------------------------------------------------------------

TTL_REVIEW_QUEUE = 30 * 86400   # 30 天
TTL_MASTERY_CACHE = 7 * 86400   # 7 天
TTL_SESSION = 2 * 3600          # 2 小时
TTL_PROFILE_CACHE = 30 * 60     # 30 分钟


# ---------------------------------------------------------------------------
# 已做题目 Seen Set  ( ai:tutor:seen-q:{uid} )
# ---------------------------------------------------------------------------

def _seen_key(uid: int) -> str:
    return f"ai:tutor:seen-q:{uid}"


async def seen_add(uid: int, question_id: int) -> None:
    """标记题目已做"""
    try:
        r = await get_redis()
        await r.sadd(_seen_key(uid), question_id)
    except Exception as e:
        logger.warning(f"[Redis] seen_add failed uid={uid} qid={question_id}: {e}")


async def seen_add_batch(uid: int, question_ids: List[int]) -> None:
    try:
        if not question_ids:
            return
        r = await get_redis()
        await r.sadd(_seen_key(uid), *question_ids)
    except Exception as e:
        logger.warning(f"[Redis] seen_add_batch failed uid={uid}: {e}")


async def seen_contains(uid: int, question_id: int) -> bool:
    try:
        r = await get_redis()
        return bool(await r.sismember(_seen_key(uid), question_id))
    except Exception as e:
        logger.warning(f"[Redis] seen_contains failed uid={uid}: {e}")
        return False


async def seen_get_all(uid: int) -> Set[int]:
    try:
        r = await get_redis()
        raw = await r.smembers(_seen_key(uid))
        return {int(v) for v in raw}
    except Exception as e:
        logger.warning(f"[Redis] seen_get_all failed uid={uid}: {e}")
        return set()


async def seen_rebuild_from_mysql(uid: int, question_ids: List[int]) -> None:
    """从 MySQL 重建 Seen Set（冷启动）"""
    try:
        if not question_ids:
            return
        r = await get_redis()
        key = _seen_key(uid)
        await r.delete(key)
        await r.sadd(key, *question_ids)
        logger.info(f"[Redis] seen_rebuild uid={uid}, {len(question_ids)} questions loaded")
    except Exception as e:
        logger.warning(f"[Redis] seen_rebuild failed uid={uid}: {e}")


# ---------------------------------------------------------------------------
# 错题复习队列 Review ZSet  ( ai:tutor:review-q:{uid} )
# ---------------------------------------------------------------------------

def _review_key(uid: int) -> str:
    return f"ai:tutor:review-q:{uid}"


async def review_add(uid: int, question_id: int, next_review_ts: float) -> None:
    """加入或更新复习队列"""
    try:
        r = await get_redis()
        key = _review_key(uid)
        await r.zadd(key, {str(question_id): next_review_ts})
        await r.expire(key, TTL_REVIEW_QUEUE)
    except Exception as e:
        logger.warning(f"[Redis] review_add failed uid={uid} qid={question_id}: {e}")


async def review_get_due(uid: int, limit: int = 5) -> List[int]:
    """获取到期需复习的题目 ID 列表（score <= now）"""
    try:
        r = await get_redis()
        now = time.time()
        raw = await r.zrangebyscore(_review_key(uid), 0, now, start=0, num=limit)
        return [int(v) for v in raw]
    except Exception as e:
        logger.warning(f"[Redis] review_get_due failed uid={uid}: {e}")
        return []


async def review_remove(uid: int, question_id: int) -> None:
    """从复习队列移除（已掌握）"""
    try:
        r = await get_redis()
        await r.zrem(_review_key(uid), str(question_id))
    except Exception as e:
        logger.warning(f"[Redis] review_remove failed uid={uid}: {e}")


# ---------------------------------------------------------------------------
# 掌握度 Hash  ( ai:tutor:mastery:{uid} )
# ---------------------------------------------------------------------------

def _mastery_key(uid: int) -> str:
    return f"ai:tutor:mastery:{uid}"


async def mastery_set(uid: int, kp_name: str, score: float) -> None:
    """更新单个知识点掌握度（0-100 整数）"""
    try:
        r = await get_redis()
        key = _mastery_key(uid)
        await r.hset(key, kp_name, int(round(score * 100)))
        await r.expire(key, TTL_MASTERY_CACHE)
    except Exception as e:
        logger.warning(f"[Redis] mastery_set failed uid={uid} kp={kp_name}: {e}")


async def mastery_set_bulk(uid: int, kp_map: Dict[str, float]) -> None:
    """批量更新掌握度"""
    try:
        if not kp_map:
            return
        r = await get_redis()
        key = _mastery_key(uid)
        mapping = {k: int(round(v * 100)) for k, v in kp_map.items()}
        await r.hset(key, mapping=mapping)
        await r.expire(key, TTL_MASTERY_CACHE)
    except Exception as e:
        logger.warning(f"[Redis] mastery_set_bulk failed uid={uid}: {e}")


async def mastery_get_all(uid: int) -> Dict[str, float]:
    """读取所有知识点掌握度（返回 0-1 浮点）"""
    try:
        r = await get_redis()
        raw = await r.hgetall(_mastery_key(uid))
        return {k: int(v) / 100.0 for k, v in raw.items()}
    except Exception as e:
        logger.warning(f"[Redis] mastery_get_all failed uid={uid}: {e}")
        return {}


async def mastery_get_weakest(uid: int, top_n: int = 3) -> List[str]:
    """返回掌握度最低的 top_n 个知识点名称"""
    mastery = await mastery_get_all(uid)
    if not mastery:
        return []
    sorted_kps = sorted(mastery.items(), key=lambda x: x[1])
    return [kp for kp, _ in sorted_kps[:top_n]]


# ---------------------------------------------------------------------------
# 用户画像缓存 Hash  ( ai:tutor:profile:{uid} )
# ---------------------------------------------------------------------------

def _profile_key(uid: int) -> str:
    return f"ai:tutor:profile:{uid}"


async def profile_cache_set(uid: int, profile_data: dict) -> None:
    try:
        r = await get_redis()
        key = _profile_key(uid)
        await r.set(key, json.dumps(profile_data, ensure_ascii=False, default=str), ex=TTL_PROFILE_CACHE)
    except Exception as e:
        logger.warning(f"[Redis] profile_cache_set failed uid={uid}: {e}")


async def profile_cache_get(uid: int) -> Optional[dict]:
    try:
        r = await get_redis()
        raw = await r.get(_profile_key(uid))
        if raw:
            return json.loads(raw)
        return None
    except Exception as e:
        logger.warning(f"[Redis] profile_cache_get failed uid={uid}: {e}")
        return None


async def profile_cache_invalidate(uid: int) -> None:
    try:
        r = await get_redis()
        await r.delete(_profile_key(uid))
    except Exception as e:
        logger.warning(f"[Redis] profile_cache_invalidate failed uid={uid}: {e}")


# ---------------------------------------------------------------------------
# Session 状态 Hash  ( ai:tutor:session:{sid} )
# ---------------------------------------------------------------------------

def _session_key(sid: str) -> str:
    return f"ai:tutor:session:{sid}"


async def session_set(sid: str, field: str, value: str) -> None:
    try:
        r = await get_redis()
        key = _session_key(sid)
        await r.hset(key, field, value)
        await r.expire(key, TTL_SESSION)
    except Exception as e:
        logger.warning(f"[Redis] session_set failed sid={sid}: {e}")


async def session_get(sid: str, field: str) -> Optional[str]:
    try:
        r = await get_redis()
        return await r.hget(_session_key(sid), field)
    except Exception as e:
        logger.warning(f"[Redis] session_get failed sid={sid}: {e}")
        return None


async def session_delete(sid: str) -> None:
    try:
        r = await get_redis()
        await r.delete(_session_key(sid))
    except Exception as e:
        logger.warning(f"[Redis] session_delete failed sid={sid}: {e}")


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------

async def redis_ping() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception:
        return False
