"""
题目去重与多样化服务
防止算法陷入局部最优，避免连续推送相同考点

对应需求32: 防止算法陷入局部最优，避免连续向用户推送相同考点的题目导致认知疲劳

实现文件：backend/algorithms/question_deduplication.py
"""

import sys
import os
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import deque

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from utils.logger import logger


@dataclass
class Question:
    """题目数据结构"""
    question_id: str
    knowledge_points: List[str]
    difficulty: float
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class QuestionDeduplicationService:
    """
    题目去重与多样化服务
    
    功能：
    1. 滑动窗口检查（窗口大小=2）
    2. 相同知识点惩罚逻辑
    3. 队列重排算法
    """
    
    # 硬指标：滑动窗口大小
    SLIDING_WINDOW_SIZE = 2
    
    # 知识点相似度阈值
    KNOWLEDGE_OVERLAP_THRESHOLD = 0.5  # 50%知识点重叠视为相同考点
    
    def __init__(self):
        """初始化服务"""
        self.recent_knowledge_points: deque = deque(maxlen=self.SLIDING_WINDOW_SIZE)
        logger.info("题目去重服务初始化完成")
    
    # ==================== 核心去重算法 ====================
    
    def deduplicate_question_queue(
        self,
        questions: List[Question],
        recent_history: Optional[List[str]] = None
    ) -> List[Question]:
        """
        对题目队列进行去重和重排
        
        算法：
        1. 滑动窗口检查（窗口大小=2）
        2. 若第i题与第i+1题知识点重叠>50%，将第i+1题顺延
        3. 插入另一知识点的题目，保证交替感
        """
        if not questions:
            return []
        
        if len(questions) <= 1:
            return questions
        
        # 初始化最近历史
        if recent_history:
            self.recent_knowledge_points = deque(
                recent_history[-self.SLIDING_WINDOW_SIZE:],
                maxlen=self.SLIDING_WINDOW_SIZE
            )
        
        # 分类题目（按主要知识点）
        categorized = self._categorize_by_knowledge_point(questions)
        
        # 重排队列
        reordered = self._reorder_queue(questions, categorized)
        
        logger.info(f"队列重排完成: 原{len(questions)}题 → 重排后{len(reordered)}题")
        
        return reordered
    
    def _categorize_by_knowledge_point(
        self,
        questions: List[Question]
    ) -> Dict[str, List[Question]]:
        """按主要知识点分类题目"""
        categorized: Dict[str, List[Question]] = {}
        
        for q in questions:
            # 取第一个知识点作为主要知识点
            primary_kp = q.knowledge_points[0] if q.knowledge_points else "unknown"
            
            if primary_kp not in categorized:
                categorized[primary_kp] = []
            categorized[primary_kp].append(q)
        
        return categorized
    
    def _reorder_queue(
        self,
        questions: List[Question],
        categorized: Dict[str, List[Question]]
    ) -> List[Question]:
        """
        重排队列，避免连续相同知识点
        
        策略：
        1. 优先选择与最近历史不同的知识点
        2. 如果必须选择相同知识点，顺延到后面
        3. 保持整体难度分布
        """
        reordered = []
        remaining = list(questions)
        
        while remaining:
            # 找到最佳候选（与最近历史不同的知识点）
            best_candidate = None
            best_score = -1
            
            for i, q in enumerate(remaining):
                score = self._calculate_diversity_score(q)
                if score > best_score:
                    best_score = score
                    best_candidate = i
            
            if best_candidate is not None:
                selected = remaining.pop(best_candidate)
                reordered.append(selected)
                
                # 更新最近历史
                primary_kp = selected.knowledge_points[0] if selected.knowledge_points else "unknown"
                self.recent_knowledge_points.append(primary_kp)
            else:
                # 没有更好的选择，取第一个
                reordered.append(remaining.pop(0))
        
        return reordered
    
    def _calculate_diversity_score(self, question: Question) -> float:
        """
        计算题目的多样性得分
        
        得分越高，表示与最近历史差异越大，越应该优先选择
        """
        if not question.knowledge_points:
            return 0.5  # 默认中等得分
        
        # 检查与最近历史的知识点重叠
        max_overlap = 0.0
        for recent_kp in self.recent_knowledge_points:
            overlap = self._calculate_knowledge_overlap(
                question.knowledge_points,
                [recent_kp]
            )
            max_overlap = max(max_overlap, overlap)
        
        # 得分 = 1 - 重叠度（重叠度越低，得分越高）
        diversity_score = 1.0 - max_overlap
        
        return diversity_score
    
    def _calculate_knowledge_overlap(
        self,
        kp1: List[str],
        kp2: List[str]
    ) -> float:
        """
        计算两组知识点的重叠度
        
        返回: 0-1，1表示完全重叠
        """
        if not kp1 or not kp2:
            return 0.0
        
        set1 = set(kp1)
        set2 = set(kp2)
        
        intersection = set1 & set2
        union = set1 | set2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    # ==================== 滑动窗口检查 ====================
    
    def check_sliding_window(
        self,
        questions: List[Question]
    ) -> List[Dict[str, Any]]:
        """
        滑动窗口检查
        
        检查队列中是否存在连续相同考点的题目
        窗口大小 = 2
        """
        violations = []
        
        for i in range(len(questions) - 1):
            q1 = questions[i]
            q2 = questions[i + 1]
            
            overlap = self._calculate_knowledge_overlap(
                q1.knowledge_points,
                q2.knowledge_points
            )
            
            if overlap >= self.KNOWLEDGE_OVERLAP_THRESHOLD:
                violations.append({
                    'index': i,
                    'question_1_id': q1.question_id,
                    'question_2_id': q2.question_id,
                    'knowledge_overlap': overlap,
                    'knowledge_points_1': q1.knowledge_points,
                    'knowledge_points_2': q2.knowledge_points,
                    'severity': 'high' if overlap > 0.8 else 'medium'
                })
        
        return violations
    
    def has_consecutive_same_knowledge(
        self,
        questions: List[Question]
    ) -> bool:
        """检查是否存在连续相同考点的题目"""
        violations = self.check_sliding_window(questions)
        return len(violations) > 0
    
    # ==================== 惩罚逻辑 ====================
    
    def apply_diversity_penalty(
        self,
        questions: List[Question],
        base_scores: List[float]
    ) -> List[float]:
        """
        应用多样性惩罚
        
        对连续相同知识点的题目降低分数
        """
        penalized_scores = base_scores.copy()
        
        for i in range(1, len(questions)):
            q1 = questions[i - 1]
            q2 = questions[i]
            
            overlap = self._calculate_knowledge_overlap(
                q1.knowledge_points,
                q2.knowledge_points
            )
            
            if overlap >= self.KNOWLEDGE_OVERLAP_THRESHOLD:
                # 应用惩罚（降低20%分数）
                penalized_scores[i] *= 0.8
        
        return penalized_scores
    
    # ==================== 便捷方法 ====================
    
    def ensure_diversity(
        self,
        questions: List[Dict[str, Any]],
        recent_question_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        便捷方法：确保题目多样性
        
        输入输出为字典格式，便于API使用
        """
        # 转换为Question对象
        question_objects = [
            Question(
                question_id=q.get('question_id', ''),
                knowledge_points=q.get('knowledge_points', []),
                difficulty=q.get('difficulty', 0.0),
                content=q.get('content', ''),
                metadata=q.get('metadata', {})
            )
            for q in questions
        ]
        
        # 去重重排
        reordered = self.deduplicate_question_queue(question_objects)
        
        # 转换回字典
        return [
            {
                'question_id': q.question_id,
                'knowledge_points': q.knowledge_points,
                'difficulty': q.difficulty,
                'content': q.content,
                'metadata': q.metadata
            }
            for q in reordered
        ]


# ==================== 便捷函数 ====================

def diversify_question_queue(
    questions: List[Dict[str, Any]],
    recent_history: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：对题目队列进行多样化处理
    
    使用示例:
        diversified = diversify_question_queue([
            {'question_id': 'q1', 'knowledge_points': ['等差数列'], 'difficulty': 0.5},
            {'question_id': 'q2', 'knowledge_points': ['等差数列'], 'difficulty': 0.6},
            {'question_id': 'q3', 'knowledge_points': ['等比数列'], 'difficulty': 0.5}
        ])
    """
    service = QuestionDeduplicationService()
    return service.ensure_diversity(questions, recent_history)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("题目去重服务测试")
    print("=" * 60)
    
    service = QuestionDeduplicationService()
    
    # 创建测试数据（有连续相同知识点）
    test_questions = [
        Question('q1', ['等差数列'], 0.5, '题目1'),
        Question('q2', ['等差数列'], 0.6, '题目2'),  # 与q1相同知识点
        Question('q3', ['等比数列'], 0.5, '题目3'),
        Question('q4', ['等比数列'], 0.7, '题目4'),  # 与q3相同知识点
        Question('q5', ['递推数列'], 0.6, '题目5'),
    ]
    
    print("\n原始队列：")
    for i, q in enumerate(test_questions):
        print(f"  [{i}] {q.question_id}: {q.knowledge_points}")
    
    # 检查滑动窗口
    violations = service.check_sliding_window(test_questions)
    print(f"\n滑动窗口检查：发现 {len(violations)} 处违规")
    for v in violations:
        print(f"  位置{v['index']}: {v['question_1_id']} 与 {v['question_2_id']} 知识点重叠 {v['knowledge_overlap']:.0%}")
    
    # 重排队列
    reordered = service.deduplicate_question_queue(test_questions)
    print("\n重排后队列：")
    for i, q in enumerate(reordered):
        print(f"  [{i}] {q.question_id}: {q.knowledge_points}")
    
    # 再次检查
    violations_after = service.check_sliding_window(reordered)
    print(f"\n重排后违规数: {len(violations_after)}")
