"""
跳过处理机制模块
处理学生跳过题目的场景

严格遵循PRD 2.4节硬指标实现

跳过类型：
| 跳过类型 | 用户心理 | 算法处理 | Advisor介入话术 |
|---------|---------|---------|----------------|
| 太简单 | 系统看低我了 | Actual=1.0, θ+=0.1, BKT提升 | "看来这些基础难不倒你!..." |
| 太难了 | 系统高估我了 | Actual=0.0, θ-=0.05, U增加 | "这道题涉及的放缩法确实超前..." |

实现文件：backend/algorithms/skip_handler.py
"""

import sys
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from utils.logger import logger


class SkipReason(Enum):
    """跳过原因枚举"""
    TOO_EASY = "too_easy"       # 太简单
    TOO_HARD = "too_hard"       # 太难了
    OTHER = "other"             # 其他原因


class SkipImpact(Enum):
    """跳过影响级别"""
    POSITIVE = "positive"       # 积极影响（太简单）
    NEGATIVE = "negative"       # 消极影响（太难了）
    NEUTRAL = "neutral"         # 中性影响


@dataclass
class SkipResult:
    """跳过处理结果"""
    skip_reason: SkipReason
    actual_score: float
    theta_delta: float
    bkt_impact: Dict[str, Any]
    advisor_message: str
    next_recommendation: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SkipRecord:
    """跳过记录"""
    user_id: int
    question_id: str
    skip_reason: SkipReason
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkipHandler:
    """
    跳过处理器
    
    处理学生跳过题目的逻辑：
    1. 根据跳过类型计算Actual Score
    2. 调整能力值θ
    3. 更新BKT掌握度
    4. 生成Advisor介入话术
    5. 决定下一题推荐策略
    """
    
    # 硬指标：跳过处理参数
    TOO_EASY_ACTUAL = 1.0       # 太简单：Actual=1.0
    TOO_EASY_THETA_DELTA = 0.1  # 太简单：θ+=0.1
    TOO_HARD_ACTUAL = 0.0       # 太难了：Actual=0.0
    TOO_HARD_THETA_DELTA = -0.05  # 太难了：θ-=0.05
    
    # Advisor话术模板
    ADVISOR_MESSAGES = {
        SkipReason.TOO_EASY: [
            "看来这些基础难不倒你！我们直接跳过这一阶，挑战更深的内容。💪",
            "太棒了！这道题对你来说太轻松了，让我们直接挑战更高难度的！🚀",
            "你的基础很扎实！这种题目已经不适合你了，我们直接进阶！⭐",
            "不错不错！这种基础题对你来说就是小菜一碟，让我们看看更有挑战的！🔥"
        ],
        SkipReason.TOO_HARD: [
            "这道题涉及的{kp}确实超前，别灰心，我先为你降低难度。🤗",
            "没关系！这道题的难度确实有点高，我们先打好基础再回来攻克它。💪",
            "别气馁！学习就像爬楼梯，这道题暂时跳过，我们先巩固基础。🌟",
            "理解！这道题确实需要更多前置知识，我们先从简单的开始。📚"
        ],
        SkipReason.OTHER: [
            "好的，已记录你的选择。让我们继续下一题吧！",
            "收到！我们看看其他题目。"
        ]
    }
    
    def __init__(self):
        """初始化跳过处理器"""
        self.skip_history: Dict[int, List[SkipRecord]] = {}  # 用户跳过历史
        logger.info("跳过处理器初始化完成")
    
    # ==================== 核心处理方法 ====================
    
    def handle_skip(
        self,
        user_id: int,
        question_id: str,
        skip_reason: SkipReason,
        current_theta: float,
        knowledge_points: List[str],
        bkt_params: Optional[Dict[str, Any]] = None
    ) -> SkipResult:
        """
        处理跳过题目
        
        参数:
            user_id: 用户ID
            question_id: 题目ID
            skip_reason: 跳过原因
            current_theta: 当前能力值
            knowledge_points: 知识点列表
            bkt_params: BKT参数（可选）
        
        返回:
            SkipResult对象
        """
        logger.info(f"处理跳过：用户={user_id}, 题目={question_id}, 原因={skip_reason.value}")
        
        # Step 1: 计算Actual Score
        actual_score = self._calculate_actual_score(skip_reason)
        
        # Step 2: 计算能力值调整
        theta_delta = self._calculate_theta_delta(skip_reason)
        new_theta = max(-3.0, min(3.0, current_theta + theta_delta))  # 限制在[-3, 3]
        
        # Step 3: 计算BKT影响
        bkt_impact = self._calculate_bkt_impact(skip_reason, bkt_params)
        
        # Step 4: 生成Advisor话术
        advisor_message = self._generate_advisor_message(skip_reason, knowledge_points)
        
        # Step 5: 决定下一题推荐策略
        next_recommendation = self._determine_next_recommendation(
            skip_reason, new_theta, knowledge_points
        )
        
        # Step 6: 记录跳过历史
        self._record_skip(user_id, question_id, skip_reason)
        
        result = SkipResult(
            skip_reason=skip_reason,
            actual_score=actual_score,
            theta_delta=theta_delta,
            bkt_impact=bkt_impact,
            advisor_message=advisor_message,
            next_recommendation=next_recommendation
        )
        
        logger.info(f"跳过处理完成：Actual={actual_score}, θ变化={theta_delta:.2f}")
        
        return result
    
    def handle_too_easy(
        self,
        user_id: int,
        question_id: str,
        current_theta: float,
        knowledge_points: List[str]
    ) -> SkipResult:
        """
        处理"太简单"跳过
        
        算法处理：
        - Actual = 1.0
        - θ += 0.1
        - BKT掌握度提升
        """
        return self.handle_skip(
            user_id=user_id,
            question_id=question_id,
            skip_reason=SkipReason.TOO_EASY,
            current_theta=current_theta,
            knowledge_points=knowledge_points
        )
    
    def handle_too_hard(
        self,
        user_id: int,
        question_id: str,
        current_theta: float,
        knowledge_points: List[str]
    ) -> SkipResult:
        """
        处理"太难了"跳过
        
        算法处理：
        - Actual = 0.0
        - θ -= 0.05
        - U（不确定性）增加
        """
        return self.handle_skip(
            user_id=user_id,
            question_id=question_id,
            skip_reason=SkipReason.TOO_HARD,
            current_theta=current_theta,
            knowledge_points=knowledge_points
        )
    
    # ==================== 计算方法 ====================
    
    def _calculate_actual_score(self, skip_reason: SkipReason) -> float:
        """计算Actual Score"""
        if skip_reason == SkipReason.TOO_EASY:
            return self.TOO_EASY_ACTUAL
        elif skip_reason == SkipReason.TOO_HARD:
            return self.TOO_HARD_ACTUAL
        else:
            return 0.0
    
    def _calculate_theta_delta(self, skip_reason: SkipReason) -> float:
        """计算能力值调整量"""
        if skip_reason == SkipReason.TOO_EASY:
            return self.TOO_EASY_THETA_DELTA
        elif skip_reason == SkipReason.TOO_HARD:
            return self.TOO_HARD_THETA_DELTA
        else:
            return 0.0
    
    def _calculate_bkt_impact(
        self,
        skip_reason: SkipReason,
        bkt_params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        计算BKT影响
        
        太简单：提升掌握度 P(L)
        太难了：增加不确定性
        """
        impact = {
            'p_known_delta': 0.0,
            'uncertainty_delta': 0.0,
            'description': ''
        }
        
        if skip_reason == SkipReason.TOO_EASY:
            # 太简单：提升掌握度
            impact['p_known_delta'] = 0.1
            impact['description'] = '跳过简单题目，提升掌握度'
        elif skip_reason == SkipReason.TOO_HARD:
            # 太难了：增加不确定性
            impact['uncertainty_delta'] = 0.05
            impact['description'] = '跳过难题，增加不确定性'
        
        return impact
    
    def _generate_advisor_message(
        self,
        skip_reason: SkipReason,
        knowledge_points: List[str]
    ) -> str:
        """生成Advisor介入话术"""
        import random
        
        messages = self.ADVISOR_MESSAGES.get(skip_reason, [""])
        message = random.choice(messages)
        
        # 替换占位符
        if skip_reason == SkipReason.TOO_HARD and knowledge_points:
            kp = knowledge_points[0] if knowledge_points else "知识点"
            message = message.format(kp=kp)
        
        return message
    
    def _determine_next_recommendation(
        self,
        skip_reason: SkipReason,
        new_theta: float,
        knowledge_points: List[str]
    ) -> Dict[str, Any]:
        """
        决定下一题推荐策略
        
        太简单：推荐更高难度的题目
        太难了：推荐更简单的题目或基础题
        """
        if skip_reason == SkipReason.TOO_EASY:
            return {
                'strategy': 'upgrade',
                'difficulty_range': [new_theta, new_theta + 0.5],
                'description': '推荐更高难度的挑战题',
                'tone': 'motivating'
            }
        elif skip_reason == SkipReason.TOO_HARD:
            return {
                'strategy': 'downgrade',
                'difficulty_range': [new_theta - 0.5, new_theta],
                'description': '推荐更简单的巩固题',
                'tone': 'encouraging'
            }
        else:
            return {
                'strategy': 'maintain',
                'difficulty_range': [new_theta - 0.3, new_theta + 0.3],
                'description': '保持当前难度',
                'tone': 'neutral'
            }
    
    # ==================== 历史记录管理 ====================
    
    def _record_skip(
        self,
        user_id: int,
        question_id: str,
        skip_reason: SkipReason
    ):
        """记录跳过历史"""
        record = SkipRecord(
            user_id=user_id,
            question_id=question_id,
            skip_reason=skip_reason,
            timestamp=datetime.now().isoformat()
        )
        
        if user_id not in self.skip_history:
            self.skip_history[user_id] = []
        
        self.skip_history[user_id].append(record)
        
        # 限制历史记录数量（保留最近100条）
        if len(self.skip_history[user_id]) > 100:
            self.skip_history[user_id] = self.skip_history[user_id][-100:]
    
    def get_skip_history(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[SkipRecord]:
        """获取用户跳过历史"""
        history = self.skip_history.get(user_id, [])
        return history[-limit:]
    
    def get_skip_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取跳过统计信息"""
        history = self.skip_history.get(user_id, [])
        
        if not history:
            return {
                'total_skips': 0,
                'too_easy_count': 0,
                'too_hard_count': 0,
                'other_count': 0,
                'too_easy_ratio': 0.0,
                'too_hard_ratio': 0.0
            }
        
        total = len(history)
        too_easy = sum(1 for r in history if r.skip_reason == SkipReason.TOO_EASY)
        too_hard = sum(1 for r in history if r.skip_reason == SkipReason.TOO_HARD)
        other = total - too_easy - too_hard
        
        return {
            'total_skips': total,
            'too_easy_count': too_easy,
            'too_hard_count': too_hard,
            'other_count': other,
            'too_easy_ratio': too_easy / total,
            'too_hard_ratio': too_hard / total
        }
    
    def detect_skip_pattern(self, user_id: int) -> Optional[str]:
        """
        检测跳过模式
        
        用于识别学生是否频繁跳过某类题目
        """
        stats = self.get_skip_statistics(user_id)
        
        if stats['total_skips'] < 5:
            return None  # 数据不足
        
        # 检测频繁跳过简单题（可能是系统低估）
        if stats['too_easy_ratio'] > 0.7:
            return 'frequent_easy_skip'
        
        # 检测频繁跳过难题（可能是系统高估）
        if stats['too_hard_ratio'] > 0.7:
            return 'frequent_hard_skip'
        
        return None
    
    # ==================== 系统校准建议 ====================
    
    def generate_calibration_suggestion(
        self,
        user_id: int,
        current_theta: float
    ) -> Dict[str, Any]:
        """
        生成系统校准建议
        
        根据跳过历史，建议调整推荐算法参数
        """
        pattern = self.detect_skip_pattern(user_id)
        stats = self.get_skip_statistics(user_id)
        
        if pattern == 'frequent_easy_skip':
            return {
                'should_adjust': True,
                'suggestion': '学生频繁跳过简单题，建议提升初始能力估计',
                'theta_adjustment': 0.2,
                'difficulty_bias': 'increase'
            }
        elif pattern == 'frequent_hard_skip':
            return {
                'should_adjust': True,
                'suggestion': '学生频繁跳过难题，建议降低初始能力估计',
                'theta_adjustment': -0.2,
                'difficulty_bias': 'decrease'
            }
        
        return {
            'should_adjust': False,
            'suggestion': '跳过模式正常，无需调整',
            'theta_adjustment': 0.0,
            'difficulty_bias': 'maintain'
        }


# ==================== 便捷函数 ====================

def handle_question_skip(
    user_id: int,
    question_id: str,
    skip_reason: str,
    current_theta: float,
    knowledge_points: List[str] = None
) -> Dict[str, Any]:
    """
    便捷函数：处理题目跳过
    
    使用示例:
        result = handle_question_skip(
            user_id=1,
            question_id="q001",
            skip_reason="too_easy",
            current_theta=0.5,
            knowledge_points=["等差数列"]
        )
    """
    handler = SkipHandler()
    
    reason_map = {
        'too_easy': SkipReason.TOO_EASY,
        'too_hard': SkipReason.TOO_HARD,
        'other': SkipReason.OTHER
    }
    
    reason = reason_map.get(skip_reason, SkipReason.OTHER)
    
    result = handler.handle_skip(
        user_id=user_id,
        question_id=question_id,
        skip_reason=reason,
        current_theta=current_theta,
        knowledge_points=knowledge_points or []
    )
    
    return {
        'skip_reason': result.skip_reason.value,
        'actual_score': result.actual_score,
        'theta_delta': result.theta_delta,
        'advisor_message': result.advisor_message,
        'next_recommendation': result.next_recommendation,
        'timestamp': result.timestamp
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("跳过处理机制测试")
    print("=" * 60)
    
    handler = SkipHandler()
    
    # 测试"太简单"
    print("\n【测试1】太简单跳过")
    print("-" * 60)
    
    result = handler.handle_too_easy(
        user_id=1,
        question_id="q001",
        current_theta=0.5,
        knowledge_points=["等差数列"]
    )
    
    print(f"跳过原因: {result.skip_reason.value}")
    print(f"Actual Score: {result.actual_score}")
    print(f"θ变化: {result.theta_delta:+.2f}")
    print(f"Advisor话术: {result.advisor_message}")
    print(f"下一题策略: {result.next_recommendation['strategy']}")
    print(f"难度范围: {result.next_recommendation['difficulty_range']}")
    
    # 测试"太难了"
    print("\n【测试2】太难了跳过")
    print("-" * 60)
    
    result = handler.handle_too_hard(
        user_id=1,
        question_id="q002",
        current_theta=0.5,
        knowledge_points=["等比数列"]
    )
    
    print(f"跳过原因: {result.skip_reason.value}")
    print(f"Actual Score: {result.actual_score}")
    print(f"θ变化: {result.theta_delta:+.2f}")
    print(f"Advisor话术: {result.advisor_message}")
    print(f"下一题策略: {result.next_recommendation['strategy']}")
    print(f"难度范围: {result.next_recommendation['difficulty_range']}")
    
    # 测试统计
    print("\n【测试3】跳过统计")
    print("-" * 60)
    
    stats = handler.get_skip_statistics(1)
    print(f"总跳过次数: {stats['total_skips']}")
    print(f"太简单: {stats['too_easy_count']} ({stats['too_easy_ratio']:.1%})")
    print(f"太难了: {stats['too_hard_count']} ({stats['too_hard_ratio']:.1%})")
    
    # 测试校准建议
    print("\n【测试4】系统校准建议")
    print("-" * 60)
    
    suggestion = handler.generate_calibration_suggestion(1, 0.5)
    print(f"需要调整: {suggestion['should_adjust']}")
    print(f"建议: {suggestion['suggestion']}")
    print(f"θ调整: {suggestion['theta_adjustment']:+.2f}")
