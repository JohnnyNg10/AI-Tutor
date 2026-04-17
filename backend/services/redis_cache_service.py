"""
Redis缓存服务
提供错题复习队列和知识点掌握度缓存的统一管理

对应需求:
- 需求40: Redis错题复习队列 (ai:tutor:review-q:{uid})
- 需求41: Redis知识点掌握度缓存 (ai:tutor:mastery:{uid})

实现文件: backend/services/redis_cache_service.py
"""

import sys
import os
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class ReviewQueueItem:
    """复习队列项"""
    question_id: str
    next_review_at: datetime
    review_stage: int  # 0-4, 对应1/2/4/7/14天
    mastery_level: float  # 掌握度
    added_at: datetime


@dataclass
class MasteryCacheItem:
    """掌握度缓存项"""
    knowledge_point_id: str
    score: float  # 0-100
    p_known: float  # 0-1
    last_updated: datetime


class RedisCacheService:
    """
    Redis缓存服务
    
    功能:
    1. 错题复习队列管理 (ZSet结构)
    2. 知识点掌握度缓存 (Hash结构)
    3. 缓存预热与淘汰
    """
    
    # Redis Key前缀
    REVIEW_QUEUE_KEY = "ai:tutor:review-q:{user_id}"
    MASTERY_KEY = "ai:tutor:mastery:{user_id}"
    
    # 复习间隔 (天数) - 艾宾浩斯遗忘曲线
    REVIEW_INTERVALS = [1, 2, 4, 7, 14]
    
    # 掌握度缓存TTL (7天)
    MASTERY_TTL = 7 * 24 * 60 * 60  # 秒
    
    # 复习队列TTL (30天)
    REVIEW_QUEUE_TTL = 30 * 24 * 60 * 60  # 秒
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("Redis缓存服务初始化完成")
    
    # ==================== 错题复习队列 (需求40) ====================
    
    def add_to_review_queue(
        self,
        user_id: int,
        question_id: str,
        mastery_level: float = 0.3,
        review_stage: int = 0
    ) -> bool:
        """
        添加题目到复习队列
        
        对应需求40: 将错题加入Redis ZSet复习队列
        
        Args:
            user_id: 用户ID
            question_id: 题目ID
            mastery_level: 当前掌握度 (0-1)
            review_stage: 复习阶段 (0-4)
        
        Returns:
            bool: 是否成功
        """
        try:
            queue_key = self.REVIEW_QUEUE_KEY.format(user_id=user_id)
            
            # 计算下次复习时间
            days = self.REVIEW_INTERVALS[min(review_stage, len(self.REVIEW_INTERVALS) - 1)]
            next_review_at = datetime.now() + timedelta(days=days)
            timestamp = next_review_at.timestamp()
            
            # 存储题目信息
            item_data = {
                'question_id': question_id,
                'review_stage': review_stage,
                'mastery_level': mastery_level,
                'added_at': datetime.now().isoformat(),
                'next_review_at': next_review_at.isoformat()
            }
            
            # ZSet: score为下次复习时间戳
            self.redis_service.redis_client.zadd(queue_key, {question_id: timestamp})
            
            # Hash: 存储详细信息
            detail_key = f"{queue_key}:detail:{question_id}"
            self.redis_service.redis_client.hset(detail_key, mapping={
                'data': json.dumps(item_data)
            })
            
            # 设置TTL
            self.redis_service.redis_client.expire(queue_key, self.REVIEW_QUEUE_TTL)
            self.redis_service.redis_client.expire(detail_key, self.REVIEW_QUEUE_TTL)
            
            logger.info(f"添加复习队列: 用户={user_id}, 题目={question_id}, 阶段={review_stage}, 下次复习={next_review_at.strftime('%Y-%m-%d')}")
            
            return True
            
        except Exception as e:
            logger.error(f"添加复习队列失败: {e}")
            return False
    
    def get_due_reviews(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取到期的复习题目
        
        对应需求40: 使用ZRANGEBYSCORE拉取已到期题目
        
        Args:
            user_id: 用户ID
            limit: 最大返回数量
        
        Returns:
            List[Dict]: 到期题目列表
        """
        try:
            queue_key = self.REVIEW_QUEUE_KEY.format(user_id=user_id)
            current_timestamp = datetime.now().timestamp()
            
            # ZRANGEBYSCORE: 获取score <= 当前时间的题目
            question_ids = self.redis_service.redis_client.zrangebyscore(
                queue_key, 0, current_timestamp, start=0, num=limit
            )
            
            results = []
            for qid in question_ids:
                detail_key = f"{queue_key}:detail:{qid}"
                data = self.redis_service.redis_client.hget(detail_key, 'data')
                
                if data:
                    item = json.loads(data)
                    results.append(item)
            
            logger.debug(f"获取到期复习: 用户={user_id}, 数量={len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"获取到期复习失败: {e}")
            return []
    
    def update_review_stage(
        self,
        user_id: int,
        question_id: str,
        answered_correctly: bool
    ) -> Dict[str, Any]:
        """
        更新复习阶段
        
        答对: 进入下一阶段
        答错: 重置为阶段0
        
        Args:
            user_id: 用户ID
            question_id: 题目ID
            answered_correctly: 是否答对
        
        Returns:
            Dict: 更新后的状态
        """
        try:
            queue_key = self.REVIEW_QUEUE_KEY.format(user_id=user_id)
            detail_key = f"{queue_key}:detail:{question_id}"
            
            # 获取当前状态
            data = self.redis_service.redis_client.hget(detail_key, 'data')
            if not data:
                return {'success': False, 'error': '题目不在复习队列中'}
            
            item = json.loads(data)
            current_stage = item.get('review_stage', 0)
            
            if answered_correctly:
                # 答对: 进入下一阶段
                new_stage = min(current_stage + 1, len(self.REVIEW_INTERVALS) - 1)
                
                if new_stage >= len(self.REVIEW_INTERVALS) - 1:
                    # 已完成所有复习阶段，从队列中移除
                    self.redis_service.redis_client.zrem(queue_key, question_id)
                    self.redis_service.redis_client.delete(detail_key)
                    
                    logger.info(f"复习完成: 用户={user_id}, 题目={question_id}")
                    return {
                        'success': True,
                        'status': 'completed',
                        'message': '恭喜！该题目已完成全部复习阶段'
                    }
                else:
                    # 更新到下一阶段
                    days = self.REVIEW_INTERVALS[new_stage]
                    next_review_at = datetime.now() + timedelta(days=days)
                    timestamp = next_review_at.timestamp()
                    
                    item['review_stage'] = new_stage
                    item['next_review_at'] = next_review_at.isoformat()
                    
                    # 更新ZSet score
                    self.redis_service.redis_client.zadd(queue_key, {question_id: timestamp})
                    self.redis_service.redis_client.hset(detail_key, mapping={
                        'data': json.dumps(item)
                    })
                    
                    logger.info(f"复习阶段更新: 用户={user_id}, 题目={question_id}, 新阶段={new_stage}")
                    return {
                        'success': True,
                        'status': 'progressed',
                        'new_stage': new_stage,
                        'next_review_at': next_review_at.isoformat()
                    }
            else:
                # 答错: 重置为阶段0
                days = self.REVIEW_INTERVALS[0]
                next_review_at = datetime.now() + timedelta(days=days)
                timestamp = next_review_at.timestamp()
                
                item['review_stage'] = 0
                item['next_review_at'] = next_review_at.isoformat()
                
                self.redis_service.redis_client.zadd(queue_key, {question_id: timestamp})
                self.redis_service.redis_client.hset(detail_key, mapping={
                    'data': json.dumps(item)
                })
                
                logger.info(f"复习重置: 用户={user_id}, 题目={question_id}, 答错重置为阶段0")
                return {
                    'success': True,
                    'status': 'reset',
                    'new_stage': 0,
                    'message': '答错了，1天后将再次复习'
                }
                
        except Exception as e:
            logger.error(f"更新复习阶段失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_review_queue_stats(self, user_id: int) -> Dict[str, Any]:
        """获取复习队列统计"""
        try:
            queue_key = self.REVIEW_QUEUE_KEY.format(user_id=user_id)
            current_timestamp = datetime.now().timestamp()
            
            # 总数量
            total = self.redis_service.redis_client.zcard(queue_key)
            
            # 到期数量
            due_count = self.redis_service.redis_client.zcount(
                queue_key, 0, current_timestamp
            )
            
            # 各阶段数量
            stage_counts = {}
            all_items = self.redis_service.redis_client.zrange(queue_key, 0, -1)
            for qid in all_items:
                detail_key = f"{queue_key}:detail:{qid}"
                data = self.redis_service.redis_client.hget(detail_key, 'data')
                if data:
                    item = json.loads(data)
                    stage = item.get('review_stage', 0)
                    stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            return {
                'total': total,
                'due_now': due_count,
                'upcoming': total - due_count,
                'stage_distribution': stage_counts
            }
            
        except Exception as e:
            logger.error(f"获取复习队列统计失败: {e}")
            return {'total': 0, 'due_now': 0, 'upcoming': 0, 'stage_distribution': {}}
    
    def remove_from_review_queue(self, user_id: int, question_id: str) -> bool:
        """从复习队列中移除题目"""
        try:
            queue_key = self.REVIEW_QUEUE_KEY.format(user_id=user_id)
            detail_key = f"{queue_key}:detail:{question_id}"
            
            self.redis_service.redis_client.zrem(queue_key, question_id)
            self.redis_service.redis_client.delete(detail_key)
            
            logger.info(f"移除复习队列: 用户={user_id}, 题目={question_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除复习队列失败: {e}")
            return False
    
    # ==================== 知识点掌握度缓存 (需求41) ====================
    
    def cache_mastery(
        self,
        user_id: int,
        knowledge_point_id: str,
        score: float,
        p_known: float
    ) -> bool:
        """
        缓存知识点掌握度
        
        对应需求41: 将掌握度存入Redis Hash
        
        Args:
            user_id: 用户ID
            knowledge_point_id: 知识点ID
            score: 掌握度分数 (0-100)
            p_known: BKT掌握度概率 (0-1)
        
        Returns:
            bool: 是否成功
        """
        try:
            mastery_key = self.MASTERY_KEY.format(user_id=user_id)
            
            # 存储到Hash
            data = {
                'score': score,
                'p_known': p_known,
                'updated_at': datetime.now().isoformat()
            }
            
            self.redis_service.redis_client.hset(
                mastery_key,
                knowledge_point_id,
                json.dumps(data)
            )
            
            # 设置TTL
            self.redis_service.redis_client.expire(mastery_key, self.MASTERY_TTL)
            
            logger.debug(f"缓存掌握度: 用户={user_id}, 知识点={knowledge_point_id}, P(L)={p_known:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"缓存掌握度失败: {e}")
            return False
    
    def get_mastery(
        self,
        user_id: int,
        knowledge_point_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取知识点掌握度
        
        对应需求41: 从Redis Hash获取掌握度
        
        Args:
            user_id: 用户ID
            knowledge_point_id: 知识点ID
        
        Returns:
            Dict: 掌握度数据，不存在返回None
        """
        try:
            mastery_key = self.MASTERY_KEY.format(user_id=user_id)
            
            data = self.redis_service.redis_client.hget(
                mastery_key,
                knowledge_point_id
            )
            
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"获取掌握度失败: {e}")
            return None
    
    def get_all_mastery(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """
        获取用户所有知识点掌握度
        
        Args:
            user_id: 用户ID
        
        Returns:
            Dict: {knowledge_point_id: mastery_data}
        """
        try:
            mastery_key = self.MASTERY_KEY.format(user_id=user_id)
            
            all_data = self.redis_service.redis_client.hgetall(mastery_key)
            
            result = {}
            for kp_id, data in all_data.items():
                result[kp_id] = json.loads(data)
            
            return result
            
        except Exception as e:
            logger.error(f"获取所有掌握度失败: {e}")
            return {}
    
    def batch_cache_mastery(
        self,
        user_id: int,
        mastery_data: Dict[str, Dict[str, float]]
    ) -> bool:
        """
        批量缓存掌握度
        
        用于缓存预热
        
        Args:
            user_id: 用户ID
            mastery_data: {knowledge_point_id: {'score': x, 'p_known': y}}
        
        Returns:
            bool: 是否成功
        """
        try:
            mastery_key = self.MASTERY_KEY.format(user_id=user_id)
            
            pipe = self.redis_service.redis_client.pipeline()
            
            for kp_id, data in mastery_data.items():
                cache_data = {
                    'score': data.get('score', 0),
                    'p_known': data.get('p_known', 0),
                    'updated_at': datetime.now().isoformat()
                }
                pipe.hset(mastery_key, kp_id, json.dumps(cache_data))
            
            pipe.expire(mastery_key, self.MASTERY_TTL)
            pipe.execute()
            
            logger.info(f"批量缓存掌握度: 用户={user_id}, 数量={len(mastery_data)}")
            
            return True
            
        except Exception as e:
            logger.error(f"批量缓存掌握度失败: {e}")
            return False
    
    def invalidate_mastery_cache(self, user_id: int) -> bool:
        """使掌握度缓存失效"""
        try:
            mastery_key = self.MASTERY_KEY.format(user_id=user_id)
            self.redis_service.redis_client.delete(mastery_key)
            
            logger.info(f"掌握度缓存失效: 用户={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"使掌握度缓存失效失败: {e}")
            return False
    
    # ==================== 缓存预热与工具 ====================
    
    def warm_up_cache(
        self,
        user_id: int,
        mastery_data: Optional[Dict[str, Dict[str, float]]] = None
    ) -> bool:
        """
        缓存预热
        
        用户登录时从MySQL加载数据到Redis
        
        Args:
            user_id: 用户ID
            mastery_data: 掌握度数据（如果为None则从数据库加载）
        
        Returns:
            bool: 是否成功
        """
        try:
            if mastery_data is None:
                # TODO: 从MySQL加载数据
                logger.warning(f"缓存预热: 未提供数据，跳过用户={user_id}")
                return False
            
            # 批量缓存掌握度
            self.batch_cache_mastery(user_id, mastery_data)
            
            logger.info(f"缓存预热完成: 用户={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            return False
    
    def get_cache_stats(self, user_id: int) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            review_key = self.REVIEW_QUEUE_KEY.format(user_id=user_id)
            mastery_key = self.MASTERY_KEY.format(user_id=user_id)
            
            review_ttl = self.redis_service.redis_client.ttl(review_key)
            mastery_ttl = self.redis_service.redis_client.ttl(mastery_key)
            
            review_count = self.redis_service.redis_client.zcard(review_key)
            mastery_count = len(self.redis_service.redis_client.hgetall(mastery_key))
            
            return {
                'review_queue': {
                    'count': review_count,
                    'ttl_seconds': review_ttl,
                    'ttl_days': review_ttl / 86400 if review_ttl > 0 else 0
                },
                'mastery_cache': {
                    'count': mastery_count,
                    'ttl_seconds': mastery_ttl,
                    'ttl_days': mastery_ttl / 86400 if mastery_ttl > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}


# ==================== 便捷函数 ====================

def get_due_review_count(user_id: int) -> int:
    """便捷函数：获取到期复习题目数量"""
    service = RedisCacheService()
    stats = service.get_review_queue_stats(user_id)
    return stats.get('due_now', 0)


def get_mastery_for_recommendation(user_id: int, knowledge_point_ids: List[str]) -> Dict[str, float]:
    """
    便捷函数：获取推荐所需的掌握度数据
    
    用于推题引擎快速获取掌握度
    """
    service = RedisCacheService()
    
    mastery = {}
    for kp_id in knowledge_point_ids:
        data = service.get_mastery(user_id, kp_id)
        if data:
            mastery[kp_id] = data.get('p_known', 0)
        else:
            mastery[kp_id] = 0.5  # 默认值
    
    return mastery


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Redis缓存服务测试")
    print("=" * 60)
    
    service = RedisCacheService()
    
    # 测试复习队列
    print("\n复习队列测试：")
    service.add_to_review_queue(1, "q001", mastery_level=0.3, review_stage=0)
    service.add_to_review_queue(1, "q002", mastery_level=0.4, review_stage=1)
    
    due = service.get_due_reviews(1)
    print(f"  到期复习: {len(due)}题")
    
    stats = service.get_review_queue_stats(1)
    print(f"  队列统计: 总计{stats['total']}, 到期{stats['due_now']}")
    
    # 测试掌握度缓存
    print("\n掌握度缓存测试：")
    service.cache_mastery(1, "kp001", score=75.0, p_known=0.75)
    service.cache_mastery(1, "kp002", score=60.0, p_known=0.60)
    
    mastery = service.get_mastery(1, "kp001")
    print(f"  掌握度 kp001: score={mastery['score']}, P(L)={mastery['p_known']}")
    
    all_mastery = service.get_all_mastery(1)
    print(f"  所有掌握度: {len(all_mastery)}个知识点")
    
    # 缓存统计
    print("\n缓存统计：")
    cache_stats = service.get_cache_stats(1)
    print(f"  复习队列: {cache_stats['review_queue']}")
    print(f"  掌握度缓存: {cache_stats['mastery_cache']}")
    
    # 清理
    service.redis_service.redis_client.delete(service.REVIEW_QUEUE_KEY.format(user_id=1))
    service.redis_service.redis_client.delete(service.MASTERY_KEY.format(user_id=1))
    print("\n测试数据清理完成")
