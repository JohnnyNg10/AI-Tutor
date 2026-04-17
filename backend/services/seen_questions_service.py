"""
Redis已做题目标记服务
利用Redis高速读写特性，拦截已做题目，杜绝学生在短时间内刷到重复题目的糟糕体验

对应行号41: 利用 Redis 高速读写特性，拦截已做题目，杜绝学生在短时间内刷到重复题目的糟糕体验

实现文件: backend/services/seen_questions_service.py
"""

import sys
import os
from typing import List, Set, Optional, Dict, Any
from datetime import datetime, timedelta
import json

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


class SeenQuestionsService:
    """
    Redis已做题目标记服务
    
    功能：
    1. 使用Redis Set存储已做题目ID
    2. 推题前检查是否已做过
    3. 支持滑动窗口（最近N题）
    4. 支持时间窗口（最近M天）
    """
    
    # Redis Key前缀
    SEEN_QUESTIONS_KEY = "ai:tutor:seen-q:{user_id}"  # Set结构
    SEEN_QUESTIONS_TIME_KEY = "ai:tutor:seen-q-time:{user_id}"  # ZSet结构（带时间戳）
    
    # 默认配置
    DEFAULT_WINDOW_SIZE = 100  # 滑动窗口大小（最近100题）
    DEFAULT_TIME_WINDOW_DAYS = 30  # 时间窗口（30天）
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("已做题目标记服务初始化完成")
    
    # ==================== 核心功能 ====================
    
    def mark_question_as_seen(
        self,
        user_id: int,
        question_id: str,
        with_timestamp: bool = True
    ) -> bool:
        """
        标记题目为已做
        
        对应行号41: 将已做题目存入Redis Set
        """
        try:
            # 添加到Set
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            self.redis_service.redis_client.sadd(seen_key, question_id)
            
            # 设置过期时间（30天）
            self.redis_service.redis_client.expire(
                seen_key,
                self.DEFAULT_TIME_WINDOW_DAYS * 24 * 60 * 60
            )
            
            # 同时添加到带时间戳的ZSet（用于滑动窗口）
            if with_timestamp:
                time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
                timestamp = datetime.now().timestamp()
                self.redis_service.redis_client.zadd(time_key, {question_id: timestamp})
                
                # 只保留最近100题（滑动窗口）
                self._maintain_sliding_window(user_id, self.DEFAULT_WINDOW_SIZE)
            
            logger.debug(f"标记已做题目: 用户={user_id}, 题目={question_id}")
            return True
            
        except Exception as e:
            logger.error(f"标记已做题目失败: {e}")
            return False
    
    def mark_questions_as_seen(
        self,
        user_id: int,
        question_ids: List[str]
    ) -> bool:
        """批量标记题目为已做"""
        try:
            if not question_ids:
                return True
            
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
            
            # 批量添加到Set
            self.redis_service.redis_client.sadd(seen_key, *question_ids)
            self.redis_service.redis_client.expire(
                seen_key,
                self.DEFAULT_TIME_WINDOW_DAYS * 24 * 60 * 60
            )
            
            # 批量添加到ZSet
            timestamp = datetime.now().timestamp()
            zadd_data = {qid: timestamp for qid in question_ids}
            self.redis_service.redis_client.zadd(time_key, zadd_data)
            
            # 维护滑动窗口
            self._maintain_sliding_window(user_id, self.DEFAULT_WINDOW_SIZE)
            
            logger.info(f"批量标记已做题目: 用户={user_id}, 数量={len(question_ids)}")
            return True
            
        except Exception as e:
            logger.error(f"批量标记已做题目失败: {e}")
            return False
    
    def is_question_seen(
        self,
        user_id: int,
        question_id: str
    ) -> bool:
        """
        检查题目是否已做过
        
        对应行号41: 推题前检查是否已做过
        """
        try:
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            return self.redis_service.redis_client.sismember(seen_key, question_id)
            
        except Exception as e:
            logger.error(f"检查已做题目失败: {e}")
            return False
    
    def filter_seen_questions(
        self,
        user_id: int,
        question_ids: List[str]
    ) -> List[str]:
        """
        过滤已做题目
        
        返回未做过的题目列表
        """
        try:
            if not question_ids:
                return []
            
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            
            # 使用pipeline批量检查
            pipe = self.redis_service.redis_client.pipeline()
            for qid in question_ids:
                pipe.sismember(seen_key, qid)
            
            results = pipe.execute()
            
            # 过滤出未做过的题目
            unseen = [
                qid for qid, is_seen in zip(question_ids, results)
                if not is_seen
            ]
            
            return unseen
            
        except Exception as e:
            logger.error(f"过滤已做题目失败: {e}")
            return question_ids  # 出错时返回全部，避免漏题
    
    def get_seen_questions(
        self,
        user_id: int,
        limit: Optional[int] = None
    ) -> Set[str]:
        """获取已做题目列表"""
        try:
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            questions = self.redis_service.redis_client.smembers(seen_key)
            
            if limit and len(questions) > limit:
                # 只返回最近N题
                time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
                recent = self.redis_service.redis_client.zrevrange(
                    time_key, 0, limit - 1
                )
                return set(recent)
            
            return questions
            
        except Exception as e:
            logger.error(f"获取已做题目失败: {e}")
            return set()
    
    def get_seen_question_count(self, user_id: int) -> int:
        """获取已做题目数量"""
        try:
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            return self.redis_service.redis_client.scard(seen_key)
            
        except Exception as e:
            logger.error(f"获取已做题目数量失败: {e}")
            return 0
    
    # ==================== 滑动窗口管理 ====================
    
    def _maintain_sliding_window(self, user_id: int, window_size: int) -> None:
        """维护滑动窗口大小"""
        try:
            time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
            
            # 获取当前数量
            count = self.redis_service.redis_client.zcard(time_key)
            
            # 如果超过窗口大小，删除最旧的
            if count > window_size:
                # 删除排名0到(count - window_size - 1)的元素
                remove_count = count - window_size
                oldest = self.redis_service.redis_client.zrange(
                    time_key, 0, remove_count - 1
                )
                
                # 从ZSet删除
                self.redis_service.redis_client.zrem(time_key, *oldest)
                
                # 从Set删除
                seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
                self.redis_service.redis_client.srem(seen_key, *oldest)
                
                logger.debug(f"维护滑动窗口: 用户={user_id}, 移除{remove_count}个旧题目")
                
        except Exception as e:
            logger.error(f"维护滑动窗口失败: {e}")
    
    def get_recent_seen_questions(
        self,
        user_id: int,
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """获取最近做过的题目（带时间戳）"""
        try:
            time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
            
            # 获取最近N题（按时间倒序）
            recent = self.redis_service.redis_client.zrevrange(
                time_key, 0, count - 1, withscores=True
            )
            
            return [
                {
                    'question_id': qid,
                    'timestamp': timestamp,
                    'datetime': datetime.fromtimestamp(timestamp).isoformat()
                }
                for qid, timestamp in recent
            ]
            
        except Exception as e:
            logger.error(f"获取最近已做题目失败: {e}")
            return []
    
    # ==================== 时间窗口管理 ====================
    
    def clear_old_seen_questions(
        self,
        user_id: int,
        days: int = 30
    ) -> int:
        """清除超过指定天数的已做记录"""
        try:
            time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            
            # 计算截止时间
            cutoff = (datetime.now() - timedelta(days=days)).timestamp()
            
            # 获取需要删除的旧题目
            old_questions = self.redis_service.redis_client.zrangebyscore(
                time_key, 0, cutoff
            )
            
            if old_questions:
                # 从ZSet删除
                self.redis_service.redis_client.zrem(time_key, *old_questions)
                # 从Set删除
                self.redis_service.redis_client.srem(seen_key, *old_questions)
                
                logger.info(f"清除旧已做记录: 用户={user_id}, 数量={len(old_questions)}")
                return len(old_questions)
            
            return 0
            
        except Exception as e:
            logger.error(f"清除旧已做记录失败: {e}")
            return 0
    
    # ==================== 推题过滤集成 ====================
    
    def deduplicate_for_recommendation(
        self,
        user_id: int,
        candidate_questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        为推荐去重
        
        从候选题目中过滤掉已做过的题目
        """
        try:
            if not candidate_questions:
                return []
            
            # 提取题目ID
            question_ids = [q.get('question_id') or q.get('id') for q in candidate_questions]
            
            # 过滤已做题目
            unseen_ids = self.filter_seen_questions(user_id, question_ids)
            
            # 构建ID到题目的映射
            id_to_question = {}
            for q in candidate_questions:
                qid = q.get('question_id') or q.get('id')
                id_to_question[qid] = q
            
            # 返回未做过的题目
            result = [id_to_question[qid] for qid in unseen_ids if qid in id_to_question]
            
            logger.info(f"推荐去重: 用户={user_id}, 候选{len(candidate_questions)}题, 过滤后{len(result)}题")
            
            return result
            
        except Exception as e:
            logger.error(f"推荐去重失败: {e}")
            return candidate_questions  # 出错时返回全部
    
    # ==================== 统计信息 ====================
    
    def get_seen_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取已做题目统计"""
        try:
            seen_key = self.SEEN_QUESTIONS_KEY.format(user_id=user_id)
            time_key = self.SEEN_QUESTIONS_TIME_KEY.format(user_id=user_id)
            
            total_seen = self.redis_service.redis_client.scard(seen_key)
            
            # 获取最近7天的做题数
            week_ago = (datetime.now() - timedelta(days=7)).timestamp()
            recent_count = self.redis_service.redis_client.zcount(
                time_key, week_ago, datetime.now().timestamp()
            )
            
            # 获取最近题目
            recent_questions = self.get_recent_seen_questions(user_id, 5)
            
            return {
                'user_id': user_id,
                'total_seen': total_seen,
                'recent_7_days': recent_count,
                'window_size': self.DEFAULT_WINDOW_SIZE,
                'time_window_days': self.DEFAULT_TIME_WINDOW_DAYS,
                'recent_questions': recent_questions
            }
            
        except Exception as e:
            logger.error(f"获取已做统计失败: {e}")
            return {'total_seen': 0, 'recent_7_days': 0}


# ==================== 便捷函数 ====================

def mark_question_seen(user_id: int, question_id: str) -> bool:
    """便捷函数：标记题目已做"""
    service = SeenQuestionsService()
    return service.mark_question_as_seen(user_id, question_id)


def is_question_seen(user_id: int, question_id: str) -> bool:
    """便捷函数：检查题目是否已做"""
    service = SeenQuestionsService()
    return service.is_question_seen(user_id, question_id)


def filter_unseen_questions(user_id: int, question_ids: List[str]) -> List[str]:
    """便捷函数：过滤未做题目"""
    service = SeenQuestionsService()
    return service.filter_seen_questions(user_id, question_ids)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Redis已做题目标记服务测试")
    print("=" * 60)
    
    service = SeenQuestionsService()
    
    # 测试标记已做
    print("\n标记已做测试：")
    service.mark_question_as_seen(1, "q001")
    service.mark_question_as_seen(1, "q002")
    service.mark_question_as_seen(1, "q003")
    print("  已标记3题为已做")
    
    # 测试检查
    print("\n检查已做测试：")
    print(f"  q001已做: {service.is_question_seen(1, 'q001')}")
    print(f"  q999已做: {service.is_question_seen(1, 'q999')}")
    
    # 测试过滤
    print("\n过滤测试：")
    candidates = ["q001", "q002", "q004", "q005"]
    unseen = service.filter_seen_questions(1, candidates)
    print(f"  候选: {candidates}")
    print(f"  未做: {unseen}")
    
    # 测试统计
    print("\n统计测试：")
    stats = service.get_seen_statistics(1)
    print(f"  总已做: {stats['total_seen']}")
    
    print("\n测试完成")
