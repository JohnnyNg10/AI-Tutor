"""
4 种答题行为轨迹

每种轨迹定义了 30 题的答题行为模式，包括：
- 何时答对/答错
- 何时求助 (以及求助到哪一级)
- 何时跳题
- 每题耗时
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import random


@dataclass
class AnswerAction:
    """单题答题行为"""
    question_index: int        # 第几题 (0-29)
    is_correct: bool           # 是否正确
    hint_count: int = 0        # 使用提示次数
    hint_levels: List[int] = field(default_factory=list)  # 逐次提示等级
    time_spent: int = 60       # 耗时(秒)
    skip_reason: Optional[str] = None  # 跳过原因
    attempts: int = 1          # 尝试次数


class TrajectoryGenerator:
    """答题轨迹生成器 - 基于画像生成符合行为模式的答题序列"""

    def __init__(self, profile, seed: int = 42):
        self.profile = profile
        self.rng = random.Random(seed)

    def _correct_prob(self, question_difficulty: int) -> float:
        """根据 IRT 模型估算正确概率 (简化版)"""
        theta = self.profile.theta_initial
        # IRT 2PL 简化: P(correct) = 1 / (1 + exp(-a * (theta - b)))
        a = 1.0  # 区分度
        b = question_difficulty - 2.0  # 难度映射到 θ 尺度
        import math
        try:
            return 1.0 / (1.0 + math.exp(-a * (theta - b)))
        except OverflowError:
            return 0.0 if theta < b else 1.0

    def generate_normal(self, difficulties: List[int]) -> List[AnswerAction]:
        """T1 正常规律轨迹 - 答对率 ~65%，渐进式求助，认真看解析"""
        actions = []
        for i, diff in enumerate(difficulties):
            p = self._correct_prob(diff)
            correct = self.rng.random() < p

            # 渐进式求助：先尝试，不行再 L0→L1→L2
            hint_count = 0
            hint_levels = []
            if self.rng.random() < 0.4:  # 40% 题目会用提示
                hint_count = self.rng.randint(1, 3)
                hint_levels = list(range(min(hint_count, 5)))

            time_spent = self.profile.avg_time_per_question + self.rng.randint(-20, 40)

            actions.append(AnswerAction(
                question_index=i,
                is_correct=correct,
                hint_count=hint_count,
                hint_levels=hint_levels,
                time_spent=max(10, time_spent),
                attempts=1 if correct else self.rng.randint(1, 3),
            ))
        return actions

    def generate_anxious(self, difficulties: List[int]) -> List[AnswerAction]:
        """T2 焦虑模式 - 答对率 ~40%，频繁 L3/L4 求助，快速跳过"""
        actions = []
        for i, diff in enumerate(difficulties):
            p = self._correct_prob(diff) * 0.6  # 焦虑降低正确率
            correct = self.rng.random() < p

            # 焦虑型：跳过中间层级，直接要 L3/L4
            hint_count = 0
            hint_levels = []
            if self.rng.random() < 0.7:  # 70% 会用提示
                hint_count = self.rng.randint(1, 2)
                hint_levels = [self.rng.choice([2, 3, 4]) for _ in range(hint_count)]

            time_spent = self.rng.randint(10, 40)  # 快速答题

            skip_reason = None
            if self.rng.random() < self.profile.skip_tendency:
                skip_reason = self.rng.choice(["too_hard", "too_hard", "tired"])

            actions.append(AnswerAction(
                question_index=i,
                is_correct=correct,
                hint_count=hint_count,
                hint_levels=hint_levels,
                time_spent=max(5, time_spent),
                skip_reason=skip_reason,
                attempts=1,
            ))
        return actions

    def generate_overperform(self, difficulties: List[int]) -> List[AnswerAction]:
        """T3 超常发挥 - 答对率 ~85%，几乎不求助，仔细读解析"""
        actions = []
        for i, diff in enumerate(difficulties):
            p = self._correct_prob(diff) * 1.3  # 超常发挥提升正确率
            correct = self.rng.random() < min(p, 0.95)

            hint_count = 0
            hint_levels = []
            if self.rng.random() < 0.1:  # 仅 10% 用提示
                hint_count = 1
                hint_levels = [self.rng.randint(0, 1)]  # 只用 L0/L1

            time_spent = self.profile.avg_time_per_question + self.rng.randint(30, 90)

            actions.append(AnswerAction(
                question_index=i,
                is_correct=correct,
                hint_count=hint_count,
                hint_levels=hint_levels,
                time_spent=max(30, time_spent),
                attempts=1 if correct else 2,
            ))
        return actions

    def generate_volatile(self, difficulties: List[int]) -> List[AnswerAction]:
        """T4 波动模式 - 正确率剧烈波动，求助层级跳跃"""
        actions = []
        phase = 0  # 0=低谷, 1=高峰, 2=波动
        for i, diff in enumerate(difficulties):
            # 每 7-8 题切换一次状态
            if i % 8 == 0:
                phase = (phase + 1) % 3

            p = self._correct_prob(diff)
            if phase == 0:
                p *= 0.4  # 低谷
            elif phase == 1:
                p = min(p * 1.5, 0.95)  # 高峰
            # phase 2 保持原样

            correct = self.rng.random() < p

            # 波动型求助：跳跃式
            hint_count = 0
            hint_levels = []
            if self.rng.random() < 0.5:
                hint_count = self.rng.randint(1, 4)
                hint_levels = sorted([self.rng.randint(0, 4) for _ in range(hint_count)])

            time_spent = self.rng.randint(20, 150)

            skip_reason = None
            if phase == 0 and self.rng.random() < 0.3:
                skip_reason = "too_hard"

            actions.append(AnswerAction(
                question_index=i,
                is_correct=correct,
                hint_count=hint_count,
                hint_levels=hint_levels,
                time_spent=max(5, time_spent),
                skip_reason=skip_reason,
                attempts=1 if correct else self.rng.randint(1, 4),
            ))
        return actions

    def generate(self, trajectory_type: str, difficulties: List[int]) -> List[AnswerAction]:
        """根据轨迹类型生成答题序列"""
        generators = {
            "normal": self.generate_normal,
            "anxious": self.generate_anxious,
            "overperform": self.generate_overperform,
            "volatile": self.generate_volatile,
        }
        gen = generators.get(trajectory_type, self.generate_normal)
        return gen(difficulties)


# 轨迹类型元数据
TRAJECTORIES = {
    "T1": {"name": "正常规律", "type": "normal", "description": "答对率~65%，渐进式求助"},
    "T2": {"name": "焦虑模式", "type": "anxious", "description": "答对率~40%，频繁L3/L4，快速跳过"},
    "T3": {"name": "超常发挥", "type": "overperform", "description": "答对率~85%，极少求助"},
    "T4": {"name": "波动模式", "type": "volatile", "description": "正确率剧烈波动，求助跳跃"},
}
