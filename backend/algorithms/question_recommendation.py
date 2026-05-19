"""
题目推荐算法模块
整合RAG候选池构建、Redis复习队列和策略权重分配

严格遵循PRD 3.4节和3.5节硬指标实现

功能：
1. 复习队列优先调度（Redis ZSet）
2. 新题探索与旧题复盘策略（70%新题 + 30%复习）
3. 推荐理由生成（LLM适配层）
4. 难度适配与语气调整

实现文件：backend/algorithms/question_recommendation.py
"""

import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from algorithms.rag_candidate_pool import (
    RAGCandidatePoolBuilder, 
    CandidateQuestion, 
    build_rag_candidate_pool
)
from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class RecommendedQuestion:
    """推荐题目数据结构"""
    question_id: str
    content: str
    difficulty: float
    knowledge_points: List[str] = field(default_factory=list)
    is_review: bool = False  # 是否为复习题
    recommendation_reason: str = ""  # 推荐理由
    advisor_tone: str = "neutral"  # Advisor语气类型
    estimated_time: int = 10  # 预估用时（分钟）
    metadata: Dict[str, Any] = field(default_factory=dict)


class QuestionRecommendationEngine:
    """
    题目推荐引擎
    
    整合以下功能：
    1. RAG候选池构建（基于向量检索）
    2. Redis复习队列调度（优先级复习）
    3. 新题/复习策略分配（70%/30%）
    4. 推荐理由生成（LLM适配层）
    """
    
    # 硬指标：策略权重分配
    WEIGHT_NEW_EXPLORATION = 0.7   # 新题探索权重 70%
    WEIGHT_REVIEW = 0.3            # 旧题复盘权重 30%
    
    # 硬指标：推荐数量
    DEFAULT_RECOMMEND_COUNT = 5    # 默认推荐5题
    
    # 硬指标：复习题优先数量（如果有到期复习题）
    REVIEW_PRIORITY_COUNT = 3      # 优先推送3道复习题
    NEW_AFTER_REVIEW_COUNT = 2     # 再推送2道新题
    
    def __init__(self):
        """初始化推荐引擎"""
        self.candidate_builder = RAGCandidatePoolBuilder()
        self.redis_service = RedisService()
        logger.info("题目推荐引擎初始化完成")
    
    # ==================== 复习队列调度 ====================
    
    def get_due_review_questions(
        self, 
        user_id: int, 
        limit: int = 10
    ) -> List[str]:
        """
        获取已到期的复习题目
        
        Redis Key: ai:tutor:review-q:{uid}
        数据结构: ZSet (Score = next_review_timestamp)
        
        返回: 已到期的question_id列表
        """
        try:
            due_reviews = self.redis_service.get_due_reviews(user_id, limit=limit)
            logger.info(f"用户 {user_id} 有 {len(due_reviews)} 道到期复习题")
            return due_reviews
        except Exception as e:
            logger.error(f"获取到期复习题失败: {e}")
            return []
    
    async def fetch_review_question_details(
        self,
        db,
        question_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        从数据库获取复习题目的详细信息
        """
        return await self._fetch_questions_from_db(db, question_ids)

    async def _fetch_questions_from_db(self, db, question_ids: List[str]) -> List[Dict[str, Any]]:
        """异步从 questions 表查询题目详情"""
        from sqlalchemy import select
        from models.question import Question
        try:
            ids = [int(qid) for qid in question_ids if str(qid).isdigit()]
            if not ids:
                return [{'question_id': qid, 'content': f'复习题 {qid}', 'difficulty': 0, 'knowledge_points': [], 'is_review': True} for qid in question_ids]
            stmt = select(Question).where(Question.id.in_(ids))
            result = await db.execute(stmt)
            questions = {q.id: q for q in result.scalars().all()}
            review_questions = []
            for qid in question_ids:
                qid_int = int(qid) if str(qid).isdigit() else None
                if qid_int and qid_int in questions:
                    q = questions[qid_int]
                    review_questions.append({
                        'question_id': str(q.id), 'content': q.content,
                        'difficulty': q.difficulty or 0,
                        'knowledge_points': q.knowledge_points or [],
                        'is_review': True
                    })
                else:
                    review_questions.append({
                        'question_id': qid, 'content': f'复习题 {qid}',
                        'difficulty': 0, 'knowledge_points': [], 'is_review': True
                    })
            return review_questions
        except Exception:
            return [{'question_id': qid, 'content': f'复习题 {qid}', 'difficulty': 0, 'knowledge_points': [], 'is_review': True} for qid in question_ids]
    
    # ==================== 推荐策略分配 ====================
    
    def allocate_recommendation_slots(
        self, 
        total_count: int,
        due_review_count: int
    ) -> Tuple[int, int]:
        """
        分配新题和复习题的推荐名额
        
        策略：
        1. 如果有到期复习题，优先推送复习题（最多3道）
        2. 剩余名额按 70%新题 : 30%复习 分配
        
        返回: (new_count, review_count)
        """
        if due_review_count > 0:
            # 有到期复习题，优先推送
            review_count = min(due_review_count, self.REVIEW_PRIORITY_COUNT)
            new_count = min(total_count - review_count, self.NEW_AFTER_REVIEW_COUNT)
            
            # 如果还有名额，继续分配
            remaining = total_count - review_count - new_count
            if remaining > 0:
                # 按 70:30 分配剩余名额
                new_count += int(remaining * self.WEIGHT_NEW_EXPLORATION)
                review_count += int(remaining * self.WEIGHT_REVIEW)
        else:
            # 无到期复习题，全部推送新题
            new_count = total_count
            review_count = 0
        
        return new_count, review_count
    
    # ==================== 推荐理由生成 ====================
    
    def generate_recommendation_reason(
        self,
        question: CandidateQuestion,
        user_theta: float,
        weak_kps: List[str],
        is_review: bool = False
    ) -> str:
        """
        生成推荐理由（自然语言）
        
        PRD 3.5.1 理由合成模板：
        "根据你的学习记录，你在【{weak_kp}】方面还需要加强。
        这道题难度为{difficulty}，正好匹配你当前的能力水平。
        建议用时{estimated_time}分钟，完成后我会为你详细讲解。"
        """
        if is_review:
            # 复习题推荐理由
            return (
                f"这是你之前做错的题目，涉及【{', '.join(question.knowledge_points[:2])}】。"
                f"根据艾宾浩斯遗忘曲线，现在正是复习的最佳时机，"
                f"建议用时{self._estimate_time(question.difficulty)}分钟巩固一下。"
            )
        
        # 新题推荐理由
        # 找出最相关的薄弱知识点
        relevant_kps = [kp for kp in question.knowledge_points if kp in weak_kps]
        if not relevant_kps:
            relevant_kps = question.knowledge_points[:2]
        
        # 难度适配描述
        diff_desc = self._get_difficulty_description(question.difficulty, user_theta)
        
        reason = (
            f"根据你的学习记录，你在【{', '.join(relevant_kps)}】方面还需要加强。"
            f"这道题难度为{question.difficulty:.1f}，{diff_desc}"
            f"建议用时{self._estimate_time(question.difficulty)}分钟，完成后我会为你详细讲解。"
        )
        
        return reason
    
    def _get_difficulty_description(self, difficulty: float, theta: float) -> str:
        """获取难度适配描述"""
        diff_gap = difficulty - theta
        
        if abs(diff_gap) <= 0.3:
            return "正好匹配你当前的能力水平。"
        elif diff_gap > 0.3:
            return "略高于你当前水平，是不错的挑战机会。"
        else:
            return "适合你巩固基础，建立信心。"
    
    def _estimate_time(self, difficulty: float) -> int:
        """预估答题用时（分钟）"""
        # 基础时间5分钟，难度越高时间越长
        base_time = 5
        additional_time = max(0, int(difficulty * 2))
        return min(base_time + additional_time, 20)  # 上限20分钟
    
    def determine_advisor_tone(
        self,
        question: CandidateQuestion,
        user_theta: float,
        is_review: bool = False
    ) -> str:
        """
        确定Advisor语气和推荐类型
        
        PRD 3.5.2 难度适配与语气调整：
        - 降级推荐(太难了→简单): 鼓励型
        - 同级推荐: 中性
        - 升级推荐(太简单→挑战): 激励型
        """
        if is_review:
            return "encouraging"  # 复习题使用鼓励型
        
        diff_gap = question.difficulty - user_theta
        
        if diff_gap > 0.5:
            # 升级推荐（挑战题）
            return "motivating"  # 激励型
        elif diff_gap < -0.5:
            # 降级推荐（简单题）
            return "encouraging"  # 鼓励型
        else:
            # 同级推荐
            return "neutral"  # 中性
    
    def get_advisor_message(self, tone: str, question_difficulty: float) -> str:
        """
        获取Advisor介入话术
        
        PRD 3.5.2 示例话术
        """
        messages = {
            "encouraging": [
                "这道题确实有些挑战，我们先从基础练起，打好基础再回来攻克它！",
                "别灰心，这道题是帮你巩固基础的，做完后你会更有信心！",
                "学习就像爬楼梯，这道题是帮你垫高基础的台阶。"
            ],
            "neutral": [
                "这道题的考点和你刚做的类似，试试看能不能举一反三？",
                "这道题正好适合你当前的水平，试试看吧！",
                "来，试试这道题，检验一下你的掌握程度。"
            ],
            "motivating": [
                "上一题你完成得很棒！这道进阶题能帮你更上一层楼，敢不敢挑战一下？",
                "你已经掌握了基础，这道挑战题会让你更有成就感！",
                "勇者无畏！这道挑战题等着你来征服！"
            ]
        }
        
        import random
        return random.choice(messages.get(tone, messages["neutral"]))
    
    # ==================== 完整推荐流程 ====================
    
    def recommend_questions(
        self,
        user_id: int,
        weak_kps: List[str],
        theta: float,
        recent_context: Optional[str] = None,
        count: int = DEFAULT_RECOMMEND_COUNT
    ) -> List[RecommendedQuestion]:
        """
        完整的题目推荐流程
        
        流程：
        1. 检查Redis复习队列，获取到期复习题
        2. 构建RAG候选池（新题）
        3. 按策略分配新题/复习题名额
        4. 生成推荐理由和Advisor语气
        5. 返回最终推荐列表
        
        参数:
            user_id: 用户ID
            weak_kps: 薄弱知识点列表
            theta: 学生当前能力值
            recent_context: 最近学习上下文
            count: 推荐题目数量
        
        返回:
            推荐题目列表
        """
        logger.info(f"开始推荐题目：用户={user_id}, θ={theta}, 数量={count}")
        
        recommendations = []
        
        # Step 1: 获取到期复习题
        due_reviews = self.get_due_review_questions(user_id, limit=10)
        
        # Step 2: 分配名额
        new_count, review_count = self.allocate_recommendation_slots(count, len(due_reviews))
        logger.info(f"名额分配：新题={new_count}, 复习题={review_count}")
        
        # Step 3: 添加复习题
        if review_count > 0 and due_reviews:
            review_ids = due_reviews[:review_count]
            for qid in review_ids:
                rq = RecommendedQuestion(
                    question_id=qid,
                    content=f"复习题 {qid}",  # 临时数据
                    difficulty=theta,  # 复习题难度与用户当前水平匹配
                    is_review=True,
                    recommendation_reason=f"这是你之前做错的题目，现在需要复习巩固。",
                    advisor_tone="encouraging",
                    estimated_time=8
                )
                recommendations.append(rq)
        
        # Step 4: 构建RAG候选池（新题）
        if new_count > 0:
            candidates = self.candidate_builder.build_candidate_pool(
                user_id=user_id,
                weak_kps=weak_kps,
                theta=theta,
                recent_context=recent_context,
                top_k=new_count * 2  # 多召回一些，防止过滤后不足
            )
            
            # Step 5: 生成推荐理由
            for candidate in candidates[:new_count]:
                reason = self.generate_recommendation_reason(
                    candidate, theta, weak_kps, is_review=False
                )
                tone = self.determine_advisor_tone(candidate, theta, is_review=False)
                
                rq = RecommendedQuestion(
                    question_id=candidate.question_id,
                    content=candidate.content,
                    difficulty=candidate.difficulty,
                    knowledge_points=candidate.knowledge_points,
                    is_review=False,
                    recommendation_reason=reason,
                    advisor_tone=tone,
                    estimated_time=self._estimate_time(candidate.difficulty),
                    metadata={
                        'kp_relevance': candidate.kp_relevance,
                        'difficulty_match': candidate.difficulty_match,
                        'context_similarity': candidate.context_similarity,
                        'final_score': candidate.final_score
                    }
                )
                recommendations.append(rq)
        
        # Step 6: 打乱顺序（避免复习题都在前面）
        import random
        random.shuffle(recommendations)
        
        logger.info(f"推荐完成：共 {len(recommendations)} 道题目")
        return recommendations[:count]

    async def recommend_questions_async(
        self,
        db,
        user_id: int,
        weak_kps: List[str],
        theta: float,
        recent_context: Optional[str] = None,
        count: int = DEFAULT_RECOMMEND_COUNT
    ) -> List[RecommendedQuestion]:
        """异步版本 - 从数据库获取复习题详情"""
        logger.info(f"开始推荐题目（异步）：用户={user_id}, θ={theta}, 数量={count}")

        recommendations = []
        due_reviews = self.get_due_review_questions(user_id, limit=10)
        new_count, review_count = self.allocate_recommendation_slots(count, len(due_reviews))
        logger.info(f"名额分配：新题={new_count}, 复习题={review_count}")

        if review_count > 0 and due_reviews:
            review_ids = due_reviews[:review_count]
            review_details = await self.fetch_review_question_details(db, review_ids)
            for detail in review_details:
                rq = RecommendedQuestion(
                    question_id=detail['question_id'],
                    content=detail['content'],
                    difficulty=detail.get('difficulty', theta),
                    knowledge_points=detail.get('knowledge_points', []),
                    is_review=True,
                    recommendation_reason="这是你之前做错的题目，现在需要复习巩固。",
                    advisor_tone="encouraging",
                    estimated_time=8
                )
                recommendations.append(rq)

        if new_count > 0:
            candidates = self.candidate_builder.build_candidate_pool(
                user_id=user_id, weak_kps=weak_kps, theta=theta,
                recent_context=recent_context, top_k=new_count * 2
            )
            for candidate in candidates[:new_count]:
                reason = self.generate_recommendation_reason(candidate, theta, weak_kps, is_review=False)
                tone = self.determine_advisor_tone(candidate, theta, is_review=False)
                rq = RecommendedQuestion(
                    question_id=candidate.question_id, content=candidate.content,
                    difficulty=candidate.difficulty, knowledge_points=candidate.knowledge_points,
                    is_review=False, recommendation_reason=reason, advisor_tone=tone,
                    estimated_time=self._estimate_time(candidate.difficulty),
                    metadata={'kp_relevance': candidate.kp_relevance, 'difficulty_match': candidate.difficulty_match,
                              'context_similarity': candidate.context_similarity, 'final_score': candidate.final_score}
                )
                recommendations.append(rq)

        import random
        random.shuffle(recommendations)
        logger.info(f"推荐完成（异步）：共 {len(recommendations)} 道题目")
        return recommendations[:count]
    
    def format_recommendation_response(
        self, 
        recommendations: List[RecommendedQuestion]
    ) -> Dict[str, Any]:
        """
        格式化推荐结果（用于API返回）
        """
        return {
            'success': True,
            'total': len(recommendations),
            'new_count': sum(1 for r in recommendations if not r.is_review),
            'review_count': sum(1 for r in recommendations if r.is_review),
            'questions': [
                {
                    'question_id': q.question_id,
                    'content': q.content,
                    'difficulty': q.difficulty,
                    'knowledge_points': q.knowledge_points,
                    'is_review': q.is_review,
                    'recommendation_reason': q.recommendation_reason,
                    'advisor_tone': q.advisor_tone,
                    'advisor_message': self.get_advisor_message(q.advisor_tone, q.difficulty),
                    'estimated_time': q.estimated_time,
                    'metadata': q.metadata
                }
                for q in recommendations
            ]
        }


# ==================== 便捷函数 ====================

def recommend_questions_for_user(
    user_id: int,
    weak_kps: List[str],
    theta: float,
    recent_context: Optional[str] = None,
    count: int = 5
) -> Dict[str, Any]:
    """
    便捷函数：为用户推荐题目
    
    使用示例:
        result = recommend_questions_for_user(
            user_id=1,
            weak_kps=["等比数列", "递推公式"],
            theta=0.5,
            recent_context="最近在学习数列相关知识",
            count=5
        )
    """
    engine = QuestionRecommendationEngine()
    recommendations = engine.recommend_questions(
        user_id=user_id,
        weak_kps=weak_kps,
        theta=theta,
        recent_context=recent_context,
        count=count
    )
    return engine.format_recommendation_response(recommendations)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("题目推荐引擎测试")
    print("=" * 60)
    
    # 测试推荐
    result = recommend_questions_for_user(
        user_id=1,
        weak_kps=["等差数列", "等比数列"],
        theta=0.5,
        recent_context="等差数列求和公式的应用",
        count=5
    )
    
    print(f"\n推荐结果：")
    print(f"总计：{result['total']} 道题目")
    print(f"新题：{result['new_count']} 道")
    print(f"复习题：{result['review_count']} 道")
    print("-" * 60)
    
    for i, q in enumerate(result['questions'], 1):
        print(f"\n[{i}] {'[复习]' if q['is_review'] else '[新题]'} 题目ID: {q['question_id']}")
        print(f"    难度: {q['difficulty']}")
        print(f"    知识点: {q['knowledge_points']}")
        print(f"    预估用时: {q['estimated_time']}分钟")
        print(f"    语气: {q['advisor_tone']}")
        print(f"    推荐理由: {q['recommendation_reason']}")
        print(f"    Advisor话术: {q['advisor_message']}")
