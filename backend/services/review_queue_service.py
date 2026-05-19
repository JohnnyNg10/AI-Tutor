"""
错题复习队列服务
实现错题复习的游戏化和变式题推荐

对应需求：
- 需求11: 将传统的错题复习清单游戏化，基于遗忘曲线体现错题的"治愈"过程
- 需求12: 复习错题时拒绝死记硬背原题，由Advisor抽取变式题进行能力验证

实现文件：backend/services/review_queue_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy.ext.asyncio import AsyncSession

from services.redis_service import RedisService
from services.chroma_service import ChromaService
from algorithms.rag_candidate_pool import RAGCandidatePoolBuilder
from utils.logger import logger


class ReviewStage(Enum):
    """复习阶段"""
    STAGE_1 = 1   # 1天后
    STAGE_2 = 2   # 2天后
    STAGE_3 = 3   # 4天后
    STAGE_4 = 4   # 7天后
    STAGE_5 = 5   # 14天后
    MASTERED = 6  # 已攻克


class ReviewVisualStatus(Enum):
    """复习视觉状态（游戏化表现）"""
    RUSTY = "rusty"           # 生锈（刚加入，红色）
    TARNISHED = "tarnished"  # 暗淡（第1-2阶段，橙红色）
    POLISHING = "polishing"  # 打磨中（第3阶段，黄色）
    SHINY = "shiny"          # 发亮（第4阶段，浅绿色）
    GLEAMING = "gleaming"    # 闪亮（第5阶段，绿色）
    MASTERED = "mastered"    # 已攻克（金色）


@dataclass
class ReviewQuestion:
    """复习题目"""
    question_id: str
    original_question: Dict[str, Any]
    variation_question: Optional[Dict[str, Any]]  # 变式题
    review_stage: int  # 1-5
    next_review_at: datetime
    error_count: int
    visual_status: str
    color: str
    icon: str
    is_mastered: bool = False


@dataclass
class ReviewProgress:
    """复习进度"""
    total_questions: int
    mastered_count: int
    in_progress_count: int
    rusty_count: int
    healing_progress: float  # 治愈进度 0-100


class ReviewQueueService:
    """
    错题复习队列服务
    
    功能：
    1. 错题复习游戏化（5种视觉表现）
    2. 变式题推荐（RAG抽取）
    3. 复习状态流转（1/2/4/7/14天）
    4. Mastered标签管理
    """
    
    # 复习间隔（硬指标 - 艾宾浩斯遗忘曲线）
    REVIEW_INTERVALS = [1, 2, 4, 7, 14]  # 天数
    
    # 视觉状态映射
    VISUAL_STATUS_MAP = {
        0: (ReviewVisualStatus.RUSTY, "#FF4D4F", "🔴"),      # 初始/生锈
        1: (ReviewVisualStatus.RUSTY, "#FF4D4F", "🔴"),      # 第1阶段
        2: (ReviewVisualStatus.TARNISHED, "#FF7875", "🟠"),  # 第2阶段
        3: (ReviewVisualStatus.POLISHING, "#FFC53D", "🟡"),  # 第3阶段
        4: (ReviewVisualStatus.SHINY, "#95DE64", "🟢"),      # 第4阶段
        5: (ReviewVisualStatus.GLEAMING, "#52C41A", "✨"),   # 第5阶段
        6: (ReviewVisualStatus.MASTERED, "#FFD700", "🏆"),   # 已攻克
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        self.chroma_service = ChromaService()
        self.candidate_builder = RAGCandidatePoolBuilder()
        logger.info("错题复习队列服务初始化完成")
    
    # ==================== 错题加入队列 ====================
    
    def add_to_review_queue(
        self,
        user_id: int,
        question_id: str,
        error_count: int = 1
    ) -> bool:
        """
        将错题加入复习队列
        
        对应需求11: 错题加入复习队列，初始状态为"生锈"
        """
        try:
            # 计算下次复习时间（1天后）
            next_review = datetime.now() + timedelta(days=self.REVIEW_INTERVALS[0])
            next_review_timestamp = next_review.timestamp()
            
            # 添加到Redis Review Queue (ZSet)
            self.redis_service.add_to_review_queue(
                user_id=user_id,
                question_id=question_id,
                next_review_at=next_review_timestamp
            )
            
            # 存储复习阶段信息（使用Redis Hash）
            review_key = f"ai:tutor:review-meta:{user_id}:{question_id}"
            self.redis_service.redis_client.hset(review_key, mapping={
                'stage': 0,
                'error_count': error_count,
                'added_at': datetime.now().isoformat(),
                'is_mastered': 0
            })
            
            logger.info(f"错题加入复习队列: 用户={user_id}, 题目={question_id}")
            return True
            
        except Exception as e:
            logger.error(f"加入复习队列失败: {e}")
            return False
    
    # ==================== 获取到期复习题 ====================
    
    def get_due_reviews(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[ReviewQuestion]:
        """
        获取已到期的复习题目
        
        对应需求11: 从Redis Review Queue获取到期题目
        """
        try:
            # 从Redis获取到期题目
            due_question_ids = self.redis_service.get_due_reviews(user_id, limit)
            
            if not due_question_ids:
                return []
            
            review_questions = []
            for qid in due_question_ids:
                review_q = self._build_review_question(user_id, qid)
                if review_q:
                    review_questions.append(review_q)
            
            return review_questions
            
        except Exception as e:
            logger.error(f"获取到期复习题失败: {e}")
            return []
    
    def _build_review_question(
        self,
        user_id: int,
        question_id: str
    ) -> Optional[ReviewQuestion]:
        """构建复习题目对象"""
        try:
            # 获取复习元数据
            review_key = f"ai:tutor:review-meta:{user_id}:{question_id}"
            meta = self.redis_service.redis_client.hgetall(review_key)
            
            if not meta:
                return None
            
            stage = int(meta.get('stage', 0))
            error_count = int(meta.get('error_count', 1))
            is_mastered = int(meta.get('is_mastered', 0)) == 1
            
            # 获取原题信息（从数据库）
            original_question = self._get_question_info(question_id)
            
            # 获取变式题（对应需求12）
            variation_question = self._get_variation_question(
                user_id, question_id, original_question
            )
            
            # 计算下次复习时间
            if stage < len(self.REVIEW_INTERVALS):
                next_review = datetime.now() + timedelta(days=self.REVIEW_INTERVALS[stage])
            else:
                next_review = datetime.now()
            
            # 获取视觉状态
            visual_status, color, icon = self.VISUAL_STATUS_MAP.get(
                stage if not is_mastered else 6,
                (ReviewVisualStatus.RUSTY, "#FF4D4F", "🔴")
            )
            
            return ReviewQuestion(
                question_id=question_id,
                original_question=original_question,
                variation_question=variation_question,
                review_stage=stage,
                next_review_at=next_review,
                error_count=error_count,
                visual_status=visual_status.value,
                color=color,
                icon=icon,
                is_mastered=is_mastered
            )
            
        except Exception as e:
            logger.error(f"构建复习题目失败: {e}")
            return None
    
    async def _get_question_info(self, db: AsyncSession, question_id: str) -> Dict[str, Any]:
        """从 questions 表查询题目信息"""
        from sqlalchemy import select
        from models.question import Question
        try:
            qid = int(question_id) if question_id.isdigit() else 0
            stmt = select(Question).where(Question.id == qid)
            result = await db.execute(stmt)
            q = result.scalar_one_or_none()
            if q:
                return {
                    'id': str(q.id),
                    'content': q.content,
                    'knowledge_points': q.knowledge_points or [],
                    'difficulty': q.difficulty or 0.5,
                }
        except Exception:
            pass
        return {
            'id': question_id,
            'content': f'题目 {question_id}',
            'knowledge_points': [],
            'difficulty': 0.5,
        }
    
    # ==================== 需求12: 变式题推荐 ====================
    
    def _get_variation_question(
        self,
        user_id: int,
        original_question_id: str,
        original_question: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        获取变式题
        
        对应需求12: 通过RAG/向量检索，从题库中抽取知识点相同、难度匹配的同类型变式题
        """
        try:
            # 获取用户当前能力值
            theta = self._get_user_theta(user_id)
            
            # 获取原题知识点
            knowledge_points = original_question.get('knowledge_points', [])
            
            if not knowledge_points:
                return None
            
            # 使用Chroma搜索同知识点题目
            candidates = self.chroma_service.search_by_knowledge_points(
                knowledge_points=knowledge_points,
                top_k=10
            )
            
            # 过滤：排除原题、难度匹配 |S - θ| <= 0.5
            variations = []
            for candidate in candidates:
                if candidate.question_id == original_question_id:
                    continue
                
                diff_gap = abs(candidate.difficulty - theta)
                if diff_gap <= 0.5:
                    variations.append(candidate)
            
            if not variations:
                return None
            
            # 选择最匹配的变式题（按相似度排序）
            best_match = variations[0]
            
            return {
                'question_id': best_match.question_id,
                'content': best_match.content,
                'difficulty': best_match.difficulty,
                'knowledge_points': best_match.knowledge_points,
                'similarity': best_match.similarity,
                'is_variation': True,
                'original_question_id': original_question_id
            }
            
        except Exception as e:
            logger.error(f"获取变式题失败: {e}")
            return None
    
    async def _get_user_theta(self, db: AsyncSession, user_id: int) -> float:
        """从 user_ability_history 查询用户能力值"""
        from sqlalchemy import select, desc
        from models.learning_analytics import UserAbilityHistory
        try:
            stmt = (
                select(UserAbilityHistory.theta)
                .where(UserAbilityHistory.user_id == user_id)
                .order_by(desc(UserAbilityHistory.recorded_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            theta = result.scalar_one_or_none()
            if theta is not None:
                return theta
        except Exception:
            pass
        return 0.0
    
    # ==================== 复习状态更新 ====================
    
    def update_review_status(
        self,
        user_id: int,
        question_id: str,
        is_correct: bool
    ) -> Dict[str, Any]:
        """
        更新复习状态
        
        根据答题结果推进到下一阶段或标记为Mastered
        """
        try:
            # 获取当前状态
            review_key = f"ai:tutor:review-meta:{user_id}:{question_id}"
            meta = self.redis_service.redis_client.hgetall(review_key)
            
            if not meta:
                return {'success': False, 'message': '复习记录不存在'}
            
            current_stage = int(meta.get('stage', 0))
            error_count = int(meta.get('error_count', 1))
            
            if is_correct:
                # 答对：推进到下一阶段
                next_stage = current_stage + 1
                
                if next_stage >= len(self.REVIEW_INTERVALS):
                    # 完成所有阶段，标记为Mastered
                    self._mark_as_mastered(user_id, question_id)
                    return {
                        'success': True,
                        'message': '恭喜！该错题已攻克',
                        'is_mastered': True,
                        'stage': next_stage,
                        'visual_status': 'mastered',
                        'color': '#FFD700',
                        'icon': '🏆'
                    }
                else:
                    # 更新到下一阶段
                    next_review = datetime.now() + timedelta(days=self.REVIEW_INTERVALS[next_stage])
                    self.redis_service.update_review_schedule(
                        user_id=user_id,
                        question_id=question_id,
                        next_review_at=next_review.timestamp()
                    )
                    
                    self.redis_service.redis_client.hset(review_key, 'stage', next_stage)
                    
                    visual_status, color, icon = self.VISUAL_STATUS_MAP.get(
                        next_stage, (ReviewVisualStatus.RUSTY, "#FF4D4F", "🔴")
                    )
                    
                    return {
                        'success': True,
                        'message': f'答对了！下次复习在{self.REVIEW_INTERVALS[next_stage]}天后',
                        'is_mastered': False,
                        'stage': next_stage,
                        'visual_status': visual_status.value,
                        'color': color,
                        'icon': icon
                    }
            else:
                # 答错：重置到第1阶段，增加错误计数
                next_review = datetime.now() + timedelta(days=self.REVIEW_INTERVALS[0])
                self.redis_service.update_review_schedule(
                    user_id=user_id,
                    question_id=question_id,
                    next_review_at=next_review.timestamp()
                )
                
                self.redis_service.redis_client.hset(review_key, mapping={
                    'stage': 0,
                    'error_count': error_count + 1
                })
                
                return {
                    'success': True,
                    'message': '答错了，别灰心！1天后再次复习',
                    'is_mastered': False,
                    'stage': 0,
                    'visual_status': 'rusty',
                    'color': '#FF4D4F',
                    'icon': '🔴'
                }
            
        except Exception as e:
            logger.error(f"更新复习状态失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def _mark_as_mastered(self, user_id: int, question_id: str):
        """标记为已攻克"""
        try:
            # 从Review Queue移除
            self.redis_service.remove_from_review_queue(user_id, question_id)
            
            # 更新元数据
            review_key = f"ai:tutor:review-meta:{user_id}:{question_id}"
            self.redis_service.redis_client.hset(review_key, 'is_mastered', 1)
            
            # 添加到已攻克集合
            mastered_key = f"ai:tutor:mastered:{user_id}"
            self.redis_service.redis_client.sadd(mastered_key, question_id)
            
            logger.info(f"错题已攻克: 用户={user_id}, 题目={question_id}")
            
        except Exception as e:
            logger.error(f"标记已攻克失败: {e}")
    
    # ==================== 复习进度统计 ====================
    
    def get_review_progress(self, user_id: int) -> ReviewProgress:
        """获取复习进度统计"""
        try:
            # 获取所有复习中的题目
            review_key_pattern = f"ai:tutor:review-meta:{user_id}:*"
            review_keys = self.redis_service.redis_client.keys(review_key_pattern)
            
            total = len(review_keys)
            mastered = 0
            rusty = 0
            in_progress = 0
            
            for key in review_keys:
                meta = self.redis_service.redis_client.hgetall(key)
                if not meta:
                    continue
                
                stage = int(meta.get('stage', 0))
                is_mastered = int(meta.get('is_mastered', 0)) == 1
                
                if is_mastered:
                    mastered += 1
                elif stage == 0:
                    rusty += 1
                else:
                    in_progress += 1
            
            # 计算治愈进度
            if total > 0:
                healing_progress = (mastered / total) * 100
            else:
                healing_progress = 0.0
            
            return ReviewProgress(
                total_questions=total,
                mastered_count=mastered,
                in_progress_count=in_progress,
                rusty_count=rusty,
                healing_progress=round(healing_progress, 2)
            )
            
        except Exception as e:
            logger.error(f"获取复习进度失败: {e}")
            return ReviewProgress(0, 0, 0, 0, 0.0)


# ==================== 便捷函数 ====================

def get_due_review_questions(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    便捷函数：获取到期复习题目
    
    使用示例:
        questions = get_due_review_questions(1, limit=5)
    """
    service = ReviewQueueService()
    review_questions = service.get_due_reviews(user_id, limit)
    
    return [
        {
            'question_id': q.question_id,
            'original_question': q.original_question,
            'variation_question': q.variation_question,
            'review_stage': q.review_stage,
            'visual_status': q.visual_status,
            'color': q.color,
            'icon': q.icon,
            'is_mastered': q.is_mastered
        }
        for q in review_questions
    ]


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("错题复习队列服务测试")
    print("=" * 60)
    
    service = ReviewQueueService()
    
    # 测试视觉状态映射
    print("\n视觉状态映射测试：")
    for stage in range(7):
        status, color, icon = service.VISUAL_STATUS_MAP.get(
            stage, (ReviewVisualStatus.RUSTY, "#FF4D4F", "🔴")
        )
        print(f"  阶段{stage}: {status.value} {icon} ({color})")
    
    # 测试复习间隔
    print("\n复习间隔（艾宾浩斯遗忘曲线）：")
    for i, interval in enumerate(service.REVIEW_INTERVALS, 1):
        print(f"  第{i}阶段: {interval}天后")
