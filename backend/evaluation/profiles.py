"""
5 类标准化用户画像

基于 IRT θ 值构建，覆盖从新手到学霸的全能力区间。
每个画像定义了用户的初始状态和行为特征参数。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UserProfile:
    """标准化用户画像"""
    id: str                     # P1-P5
    name: str                   # 画像名称
    theta_initial: float        # 初始 IRT 能力值 [-3, +3]
    mastered_kp_count: int      # 已掌握知识点数 (0-83)
    weak_kp_count: int          # 薄弱知识点数
    learning_style: str         # 学习风格
    hint_preference: str        # 求助偏好: "independent" / "normal" / "dependent"
    skip_tendency: float        # 跳题倾向 0-1
    persistence: float          # 坚持度 0-1 (越高越不容易放弃)
    reflection_depth: float     # 反思深度 0-1
    avg_time_per_question: int  # 平均每题耗时(秒)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.id,
            "name": self.name,
            "theta_initial": self.theta_initial,
            "mastered_kp_count": self.mastered_kp_count,
            "weak_kp_count": self.weak_kp_count,
            "learning_style": self.learning_style,
        }


# 5 类标准画像
PROFILES = {
    "P1": UserProfile(
        id="P1",
        name="数列新手",
        theta_initial=-2.0,
        mastered_kp_count=0,
        weak_kp_count=15,
        learning_style="frequent_help",
        hint_preference="dependent",
        skip_tendency=0.2,
        persistence=0.4,
        reflection_depth=0.2,
        avg_time_per_question=45,
    ),
    "P2": UserProfile(
        id="P2",
        name="基础薄弱",
        theta_initial=-0.5,
        mastered_kp_count=15,
        weak_kp_count=8,
        learning_style="skip_prone",
        hint_preference="normal",
        skip_tendency=0.6,
        persistence=0.35,
        reflection_depth=0.3,
        avg_time_per_question=60,
    ),
    "P3": UserProfile(
        id="P3",
        name="中等水平",
        theta_initial=0.5,
        mastered_kp_count=40,
        weak_kp_count=4,
        learning_style="balanced",
        hint_preference="normal",
        skip_tendency=0.15,
        persistence=0.65,
        reflection_depth=0.55,
        avg_time_per_question=90,
    ),
    "P4": UserProfile(
        id="P4",
        name="进阶高手",
        theta_initial=1.5,
        mastered_kp_count=65,
        weak_kp_count=2,
        learning_style="independent",
        hint_preference="independent",
        skip_tendency=0.05,
        persistence=0.85,
        reflection_depth=0.75,
        avg_time_per_question=120,
    ),
    "P5": UserProfile(
        id="P5",
        name="学霸选手",
        theta_initial=2.5,
        mastered_kp_count=78,
        weak_kp_count=0,
        learning_style="fast_solver",
        hint_preference="independent",
        skip_tendency=0.02,
        persistence=0.95,
        reflection_depth=0.9,
        avg_time_per_question=30,
    ),
}
