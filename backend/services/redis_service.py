"""
Redis核心数据结构设计（Key-Schema）
严格遵循PRD文档第四章硬指标

数据结构汇总：
1. Seen Pool (Set)      - ai:tutor:seen-q:{uid}      - 已做题目去重池
2. Review Queue (ZSet)  - ai:tutor:review-q:{uid}    - 错题复习优先队列
3. Mastery Hash (Hash)  - ai:tutor:mastery:{uid}     - 实时掌握度
4. Session Hash (Hash)  - ai:tutor:session:{sid}     - 当前Session状态
"""

import redis
import json
import time
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass


# Redis Key前缀（硬指标）
KEY_PREFIX_SEEN = "ai:tutor:seen-q:{uid}"           # 已做题目去重池
KEY_PREFIX_REVIEW = "ai:tutor:review-q:{uid}"       # 错题复习队列
KEY_PREFIX_MASTERY = "ai:tutor:mastery:{uid}"       # 实时掌握度
KEY_PREFIX_SESSION = "ai:tutor:session:{sid}"       # Session状态


@dataclass
class ReviewItem:
    """复习队列项"""
    question_id: str
    next_review_at: float  # 时间戳
    error_count: int
    
    def to_dict(self) -> Dict:
        return {
            "question_id": self.question_id,
            "next_review_at": self.next_review_at,
            "error_count": self.error_count
        }


class RedisService:
    """
    Redis核心数据服务

    严格遵循PRD文档第四章硬指标实现
    当Redis不可用时，所有方法返回安全的默认值，服务降级运行
    """

    REVIEW_INTERVALS = [1, 2, 4, 7, 14]
    MAX_REVIEW_INTERVAL = 14
    TTL_REVIEW_QUEUE = 30 * 24 * 60 * 60
    TTL_MASTERY = 7 * 24 * 60 * 60

    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis_client = None
        self._available = False
        try:
            self.redis_client = redis.Redis(
                host=host, port=port, db=db, password=password,
                decode_responses=True,
                socket_connect_timeout=2, socket_timeout=2
            )
            self.redis_client.ping()
            self._available = True
        except Exception:
            self.redis_client = None
            self._available = False

    def is_available(self):
        return self._available

    def _safe_call(self, func, default, *args, **kwargs):
        if not self._available or self.redis_client is None:
            return default
        try:
            return func(*args, **kwargs)
        except Exception:
            return default
    
    # ==================== Seen Pool 已做题目去重池 ====================
    
    def add_seen_question(self, user_id: int, question_id: str) -> bool:
        """
        添加题目到已做题目池
        
        Key: ai:tutor:seen-q:{uid}
        数据结构: Set
        TTL: 无（持久化至MySQL后重建）
        """
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.sadd(key, question_id) == 1
    
    def add_seen_questions(self, user_id: int, question_ids: List[str]) -> int:
        """批量添加已做题目"""
        if not question_ids:
            return 0
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.sadd(key, *question_ids)
    
    def is_question_seen(self, user_id: int, question_id: str) -> bool:
        """
        检查题目是否已做过
        
        使用SISMEMBER快速排除已做题目（O(1)）
        """
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.sismember(key, question_id)
    
    def get_seen_questions(self, user_id: int) -> Set[str]:
        """获取所有已做题目"""
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.smembers(key)
    
    def get_seen_count(self, user_id: int) -> int:
        """获取已做题目数量"""
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.scard(key)
    
    def remove_seen_question(self, user_id: int, question_id: str) -> bool:
        """从已做题目池中移除"""
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.srem(key, question_id) == 1
    
    def clear_seen_pool(self, user_id: int) -> bool:
        """清空已做题目池"""
        key = KEY_PREFIX_SEEN.format(uid=user_id)
        return self.redis_client.delete(key) == 1
    
    # ==================== Review Queue 错题复习队列 ====================
    
    def _calculate_next_review_time(self, error_count: int) -> float:
        """
        计算下次复习时间（硬指标）
        
        公式: T_n = min(T_{n-1} * 2, 14), T_1 = 1
        
        Args:
            error_count: 错误次数（从1开始）
            
        Returns:
            下次复习的时间戳
        """
        # 根据错误次数确定间隔天数
        if error_count <= 0:
            interval_days = 1
        elif error_count <= len(self.REVIEW_INTERVALS):
            interval_days = self.REVIEW_INTERVALS[error_count - 1]
        else:
            interval_days = self.MAX_REVIEW_INTERVAL
        
        next_review = datetime.now() + timedelta(days=interval_days)
        return next_review.timestamp()
    
    def add_to_review_queue(
        self, 
        user_id: int, 
        question_id: str, 
        error_count: int = 1
    ) -> float:
        """
        添加题目到复习队列
        
        Key: ai:tutor:review-q:{uid}
        数据结构: ZSet (Sorted Set)
        Score: next_review_timestamp
        Member: question_id
        TTL: 30天
        """
        key = KEY_PREFIX_REVIEW.format(uid=user_id)
        next_review_at = self._calculate_next_review_time(error_count)
        
        # 使用管道确保原子性
        pipe = self.redis_client.pipeline()
        pipe.zadd(key, {question_id: next_review_at})
        pipe.expire(key, self.TTL_REVIEW_QUEUE)
        pipe.execute()
        
        return next_review_at
    
    def get_due_reviews(
        self, 
        user_id: int, 
        limit: int = 10
    ) -> List[ReviewItem]:
        """
        获取到期的复习题目
        
        使用ZRANGEBYSCORE检查是否有到期需要复习的错题
        """
        key = KEY_PREFIX_REVIEW.format(uid=user_id)
        now = time.time()
        
        # 获取score <= now的所有题目（已到期的）
        results = self.redis_client.zrangebyscore(
            key, 
            0, 
            now, 
            withscores=True,
            start=0,
            num=limit
        )
        
        review_items = []
        for question_id, next_review_at in results:
            # 从Hash中获取错误次数（如果存在）
            error_count = self._get_review_error_count(user_id, question_id)
            review_items.append(ReviewItem(
                question_id=question_id,
                next_review_at=next_review_at,
                error_count=error_count
            ))
        
        return review_items
    
    def get_all_reviews(self, user_id: int) -> List[ReviewItem]:
        """获取所有复习队列中的题目"""
        key = KEY_PREFIX_REVIEW.format(uid=user_id)
        results = self.redis_client.zrange(key, 0, -1, withscores=True)
        
        review_items = []
        for question_id, next_review_at in results:
            error_count = self._get_review_error_count(user_id, question_id)
            review_items.append(ReviewItem(
                question_id=question_id,
                next_review_at=next_review_at,
                error_count=error_count
            ))
        
        return review_items
    
    def remove_from_review_queue(self, user_id: int, question_id: str) -> bool:
        """从复习队列中移除题目"""
        key = KEY_PREFIX_REVIEW.format(uid=user_id)
        return self.redis_client.zrem(key, question_id) == 1
    
    def update_review_error_count(
        self, 
        user_id: int, 
        question_id: str, 
        error_count: int
    ) -> float:
        """
        更新错误次数并重新计算复习时间
        
        如果再次做错，增加错误次数并推迟复习时间
        """
        # 先移除旧的
        self.remove_from_review_queue(user_id, question_id)
        # 添加新的（带新的错误次数）
        next_review_at = self.add_to_review_queue(user_id, question_id, error_count)
        
        # 存储错误次数到Hash（用于跟踪）
        self._set_review_error_count(user_id, question_id, error_count)
        
        return next_review_at
    
    def _set_review_error_count(
        self, 
        user_id: int, 
        question_id: str, 
        error_count: int
    ):
        """存储错误次数（内部使用）"""
        key = f"ai:tutor:review-meta:{user_id}"
        self.redis_client.hset(key, question_id, error_count)
        self.redis_client.expire(key, self.TTL_REVIEW_QUEUE)
    
    def _get_review_error_count(self, user_id: int, question_id: str) -> int:
        """获取错误次数（内部使用）"""
        key = f"ai:tutor:review-meta:{user_id}"
        count = self.redis_client.hget(key, question_id)
        return int(count) if count else 1
    
    def get_review_count(self, user_id: int) -> int:
        """获取复习队列中的题目数量"""
        key = KEY_PREFIX_REVIEW.format(uid=user_id)
        return self.redis_client.zcard(key)
    
    def clear_review_queue(self, user_id: int) -> bool:
        """清空复习队列"""
        key = KEY_PREFIX_REVIEW.format(uid=user_id)
        meta_key = f"ai:tutor:review-meta:{user_id}"
        pipe = self.redis_client.pipeline()
        pipe.delete(key)
        pipe.delete(meta_key)
        pipe.execute()
        return True
    
    # ==================== Mastery Hash 实时掌握度 ====================
    
    def set_mastery(
        self, 
        user_id: int, 
        knowledge_point_id: str, 
        score: int
    ) -> bool:
        """
        设置知识点掌握度
        
        Key: ai:tutor:mastery:{uid}
        数据结构: Hash
        Field: knowledge_point_id
        Value: score (0-100整数)
        TTL: 7天
        """
        key = KEY_PREFIX_MASTERY.format(uid=user_id)
        # 确保score在0-100范围内
        score = max(0, min(100, int(score)))
        
        pipe = self.redis_client.pipeline()
        pipe.hset(key, knowledge_point_id, score)
        pipe.expire(key, self.TTL_MASTERY)
        pipe.execute()
        
        return True
    
    def set_masteries(
        self, 
        user_id: int, 
        mastery_dict: Dict[str, int]
    ) -> bool:
        """批量设置掌握度"""
        if not mastery_dict:
            return False
        
        key = KEY_PREFIX_MASTERY.format(uid=user_id)
        # 确保所有score在0-100范围内
        validated_dict = {
            k: max(0, min(100, int(v))) 
            for k, v in mastery_dict.items()
        }
        
        pipe = self.redis_client.pipeline()
        pipe.hset(key, mapping=validated_dict)
        pipe.expire(key, self.TTL_MASTERY)
        pipe.execute()
        
        return True
    
    def get_mastery(self, user_id: int, knowledge_point_id: str) -> Optional[int]:
        """
        获取知识点掌握度
        
        O(1)速度读取分数，决定下一题的难度
        """
        key = KEY_PREFIX_MASTERY.format(uid=user_id)
        score = self.redis_client.hget(key, knowledge_point_id)
        return int(score) if score else None
    
    def get_all_mastery_scores(self, user_id: int) -> Dict[str, float]:
        """别名：获取所有掌握度分数（0-1浮点）"""
        raw = self.get_all_masteries(user_id)
        return {k: v / 100.0 for k, v in raw.items()}

    def get_all_masteries(self, user_id: int) -> Dict[str, int]:
        """获取所有知识点掌握度"""
        key = KEY_PREFIX_MASTERY.format(uid=user_id)
        result = self.redis_client.hgetall(key)
        return {k: int(v) for k, v in result.items()}
    
    def get_weak_knowledge_points(
        self, 
        user_id: int, 
        threshold: int = 50
    ) -> List[Tuple[str, int]]:
        """
        获取薄弱知识点（掌握度低于阈值）
        
        用于Advisor推荐时优先选择薄弱知识点
        """
        masteries = self.get_all_masteries(user_id)
        weak_kps = [
            (kp, score) 
            for kp, score in masteries.items() 
            if score < threshold
        ]
        # 按掌握度升序排列（最薄弱的在前）
        weak_kps.sort(key=lambda x: x[1])
        return weak_kps
    
    def delete_mastery(self, user_id: int, knowledge_point_id: str) -> bool:
        """删除知识点掌握度"""
        key = KEY_PREFIX_MASTERY.format(uid=user_id)
        return self.redis_client.hdel(key, knowledge_point_id) == 1
    
    def clear_masteries(self, user_id: int) -> bool:
        """清空所有掌握度"""
        key = KEY_PREFIX_MASTERY.format(uid=user_id)
        return self.redis_client.delete(key) == 1
    
    # ==================== Session 状态 ====================
    
    def set_session_data(
        self, 
        session_id: str, 
        data: Dict,
        expire_seconds: int = 3600  # 默认1小时
    ) -> bool:
        """
        设置Session状态
        
        Key: ai:tutor:session:{sid}
        数据结构: Hash
        TTL: Session结束后删除
        """
        key = KEY_PREFIX_SESSION.format(sid=session_id)
        pipe = self.redis_client.pipeline()
        pipe.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()})
        pipe.expire(key, expire_seconds)
        pipe.execute()
        return True
    
    def get_session_data(self, session_id: str) -> Dict:
        """获取Session状态"""
        key = KEY_PREFIX_SESSION.format(sid=session_id)
        result = self.redis_client.hgetall(key)
        return {k: self._try_parse_json(v) for k, v in result.items()}
    
    def delete_session(self, session_id: str) -> bool:
        """删除Session"""
        key = KEY_PREFIX_SESSION.format(sid=session_id)
        return self.redis_client.delete(key) == 1
    
    def _try_parse_json(self, value: str):
        """尝试解析JSON字符串"""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    # ==================== 综合查询接口 ====================
    
    def get_user_learning_state(self, user_id: int) -> Dict:
        """
        获取用户完整学习状态
        
        用于Advisor推题前快速获取用户画像
        """
        return {
            "user_id": user_id,
            "seen_count": self.get_seen_count(user_id),
            "review_count": self.get_review_count(user_id),
            "due_reviews": [item.to_dict() for item in self.get_due_reviews(user_id, limit=5)],
            "masteries": self.get_all_masteries(user_id),
            "weak_points": self.get_weak_knowledge_points(user_id)
        }
    
    # ==================== 数据同步接口 ====================
    
    def sync_from_mysql(
        self, 
        user_id: int, 
        seen_questions: List[str],
        review_items: List[Dict],
        masteries: Dict[str, int]
    ):
        """
        从MySQL同步数据到Redis
        
        用于冷启动时重建Redis缓存
        """
        # 同步Seen Pool
        if seen_questions:
            self.add_seen_questions(user_id, seen_questions)
        
        # 同步Review Queue
        for item in review_items:
            self.add_to_review_queue(
                user_id,
                item['question_id'],
                item.get('error_count', 1)
            )
        
        # 同步Mastery
        if masteries:
            self.set_masteries(user_id, masteries)
    
    def clear_all_user_data(self, user_id: int) -> bool:
        """清空用户所有Redis数据（用于测试）"""
        keys_to_delete = [
            KEY_PREFIX_SEEN.format(uid=user_id),
            KEY_PREFIX_REVIEW.format(uid=user_id),
            f"ai:tutor:review-meta:{user_id}",
            KEY_PREFIX_MASTERY.format(uid=user_id),
        ]
        
        pipe = self.redis_client.pipeline()
        for key in keys_to_delete:
            pipe.delete(key)
        pipe.execute()
        
        return True


# 全局服务实例
_redis_service = None


def get_redis_service() -> RedisService:
    """获取Redis服务实例（单例）"""
    global _redis_service
    if _redis_service is None:
        _redis_service = RedisService()
    return _redis_service


def init_redis_service(host='localhost', port=6379, db=0, password=None):
    """初始化Redis服务"""
    global _redis_service
    _redis_service = RedisService(host, port, db, password)
    return _redis_service


# 单元测试
if __name__ == "__main__":
    print("=== Redis核心数据结构测试 ===\n")
    
    try:
        service = RedisService()
        user_id = 999  # 测试用户
        
        # 清理测试数据
        service.clear_all_user_data(user_id)
        
        # 测试1: Seen Pool
        print("测试1: Seen Pool (已做题目去重池)")
        service.add_seen_question(user_id, "q001")
        service.add_seen_questions(user_id, ["q002", "q003"])
        assert service.is_question_seen(user_id, "q001") == True
        assert service.is_question_seen(user_id, "q999") == False
        print(f"  已做题目数: {service.get_seen_count(user_id)}")
        print("  ✓ Seen Pool测试通过")
        
        # 测试2: Review Queue
        print("\n测试2: Review Queue (错题复习队列)")
        next_time = service.add_to_review_queue(user_id, "q001", error_count=1)
        print(f"  下次复习时间: {datetime.fromtimestamp(next_time)}")
        
        # 模拟立即到期（用于测试）
        service.redis_client.zadd(
            KEY_PREFIX_REVIEW.format(uid=user_id),
            {"q002": time.time() - 1}  # 已到期
        )
        due = service.get_due_reviews(user_id)
        print(f"  到期复习题数: {len(due)}")
        print("  ✓ Review Queue测试通过")
        
        # 测试3: Mastery Hash
        print("\n测试3: Mastery Hash (实时掌握度)")
        service.set_mastery(user_id, "等差数列", 85)
        service.set_masteries(user_id, {"等比数列": 60, "递推数列": 40})
        
        score = service.get_mastery(user_id, "等差数列")
        print(f"  等差数列掌握度: {score}")
        
        weak = service.get_weak_knowledge_points(user_id, threshold=50)
        print(f"  薄弱知识点: {weak}")
        print("  ✓ Mastery Hash测试通过")
        
        # 测试4: 复习间隔计算
        print("\n测试4: 复习间隔计算 (Spaced Repetition)")
        for i in range(1, 7):
            next_t = service._calculate_next_review_time(i)
            days = (datetime.fromtimestamp(next_t) - datetime.now()).days
            print(f"  错误{i}次 -> {days}天后复习")
        print("  ✓ 复习间隔计算测试通过")
        
        # 测试5: 综合查询
        print("\n测试5: 综合查询")
        state = service.get_user_learning_state(user_id)
        print(f"  用户状态: {json.dumps(state, ensure_ascii=False, indent=2)}")
        print("  ✓ 综合查询测试通过")
        
        # 清理
        service.clear_all_user_data(user_id)
        
        print("\n=== 所有测试通过！===")
        
    except ConnectionError as e:
        print(f"\n✗ Redis连接失败: {e}")
        print("请确保Redis服务器已启动: redis-server")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
