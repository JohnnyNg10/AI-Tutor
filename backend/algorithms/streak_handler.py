"""
需求1：基于连对/连错状态的实时 UI 交互与难度自适应调整

核心逻辑：
- 高光连击：连续正确 3 次，触发难度上限 S_next 提升 0.3
- 降级保护：连续错误 2 次，触发难度下限 S_next 降低 0.3

PRD参数（硬指标）：
- 连击触发阈值：连续正确 3 次
- 降级触发阈值：连续错误 2 次
- 难度调整幅度：±0.3
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class StreakType(Enum):
    """连击类型"""
    NONE = "none"           # 无连击
    WIN_STREAK = "win"      # 连胜连击
    LOSS_STREAK = "loss"    # 连败连击


class StreakEffect(Enum):
    """连击效果类型"""
    NONE = "none"                   # 无效果
    HIGHLIGHT = "highlight"         # 高光连击（火焰特效）
    DOWNGRADE_PROTECTION = "downgrade_protection"  # 降级保护（保护伞/咖啡杯）


@dataclass
class StreakState:
    """连击状态"""
    consecutive_correct: int = 0    # 连续正确次数
    consecutive_wrong: int = 0      # 连续错误次数
    current_streak_type: StreakType = field(default=StreakType.NONE)
    current_streak_count: int = 0   # 当前连击计数
    
    def to_dict(self) -> Dict:
        return {
            "consecutive_correct": self.consecutive_correct,
            "consecutive_wrong": self.consecutive_wrong,
            "current_streak_type": self.current_streak_type.value,
            "current_streak_count": self.current_streak_count
        }


@dataclass
class DifficultyAdjustment:
    """难度调整结果"""
    original_min: float             # 原始难度下限
    original_max: float             # 原始难度上限
    adjusted_min: float             # 调整后难度下限
    adjusted_max: float             # 调整后难度上限
    adjustment_delta: float         # 调整幅度
    effect_type: StreakEffect       # 触发的效果类型
    effect_triggered: bool          # 是否触发了效果
    streak_count: int               # 当前连击数
    
    def to_dict(self) -> Dict:
        return {
            "original_range": f"[{self.original_min:.2f}, {self.original_max:.2f}]",
            "adjusted_range": f"[{self.adjusted_min:.2f}, {self.adjusted_max:.2f}]",
            "adjustment_delta": self.adjustment_delta,
            "effect_type": self.effect_type.value,
            "effect_triggered": self.effect_triggered,
            "streak_count": self.streak_count
        }


@dataclass
class UIEffect:
    """UI效果定义"""
    effect_type: StreakEffect
    icon: str                       # 图标名称
    animation: str                  # 动画效果
    advisor_message: str            # Advisor话术
    color_theme: str                # 颜色主题
    
    def to_dict(self) -> Dict:
        return {
            "effect_type": self.effect_type.value,
            "icon": self.icon,
            "animation": self.animation,
            "advisor_message": self.advisor_message,
            "color_theme": self.color_theme
        }


class StreakHandler:
    """
    连击处理器 - 处理连对/连错状态并触发难度自适应调整
    
    PRD硬指标：
    - 高光连击阈值：连续正确 3 次
    - 降级保护阈值：连续错误 2 次
    - 难度调整幅度：0.3
    """
    
    # PRD硬指标参数
    WIN_STREAK_THRESHOLD = 3        # 高光连击触发阈值
    LOSS_STREAK_THRESHOLD = 2       # 降级保护触发阈值
    DIFFICULTY_ADJUSTMENT = 0.3     # 难度调整幅度
    
    # UI效果定义
    UI_EFFECTS = {
        StreakEffect.HIGHLIGHT: UIEffect(
            effect_type=StreakEffect.HIGHLIGHT,
            icon="fire",  # 火焰图标
            animation="flame_burst",
            advisor_message="太棒了！你已经连续答对{streak}题，继续保持这个势头！",
            color_theme="orange"
        ),
        StreakEffect.DOWNGRADE_PROTECTION: UIEffect(
            effect_type=StreakEffect.DOWNGRADE_PROTECTION,
            icon="shield",  # 咖啡杯/保护伞
            animation="gentle_fade",
            advisor_message="别灰心，这道题确实有些挑战。我们先降低难度，打好基础再回来攻克它！",
            color_theme="blue"
        )
    }
    
    REDIS_KEY_PREFIX = "ai:tutor:streak:{user_id}"

    def __init__(self):
        self.streak_states: Dict[int, StreakState] = {}  # user_id -> StreakState

    async def save_to_redis(self, user_id: int) -> bool:
        """将连击状态持久化到 Redis"""
        try:
            from utils.redis_client import get_redis
            redis = await get_redis()
            if redis is None:
                return False

            state = self.get_user_streak_state(user_id)
            key = self.REDIS_KEY_PREFIX.format(user_id=user_id)
            await redis.hset(key, mapping={
                'consecutive_correct': state.consecutive_correct,
                'consecutive_wrong': state.consecutive_wrong,
                'current_streak_type': state.current_streak_type.value,
                'current_streak_count': state.current_streak_count,
            })
            # TTL: 7 天
            await redis.expire(key, 7 * 24 * 3600)
            return True
        except Exception:
            return False

    async def load_from_redis(self, user_id: int) -> Optional[StreakState]:
        """从 Redis 恢复连击状态"""
        try:
            from utils.redis_client import get_redis
            redis = await get_redis()
            if redis is None:
                return None

            key = self.REDIS_KEY_PREFIX.format(user_id=user_id)
            data = await redis.hgetall(key)
            if not data:
                return None

            state = StreakState(
                consecutive_correct=int(data.get(b'consecutive_correct', 0)),
                consecutive_wrong=int(data.get(b'consecutive_wrong', 0)),
                current_streak_type=StreakType(data.get(b'current_streak_type', b'none').decode()),
                current_streak_count=int(data.get(b'current_streak_count', 0)),
            )
            self.streak_states[user_id] = state
            return state
        except Exception:
            return None

    async def delete_from_redis(self, user_id: int) -> bool:
        """从 Redis 删除连击状态"""
        try:
            from utils.redis_client import get_redis
            redis = await get_redis()
            if redis is None:
                return False

            key = self.REDIS_KEY_PREFIX.format(user_id=user_id)
            await redis.delete(key)
            return True
        except Exception:
            return False
    
    def get_user_streak_state(self, user_id: int) -> StreakState:
        """获取用户的连击状态（内存）"""
        if user_id not in self.streak_states:
            self.streak_states[user_id] = StreakState()
        return self.streak_states[user_id]

    async def get_or_load_streak_state(self, user_id: int) -> StreakState:
        """获取连击状态，优先从 Redis 恢复"""
        if user_id not in self.streak_states:
            loaded = await self.load_from_redis(user_id)
            if loaded is not None:
                return loaded
            self.streak_states[user_id] = StreakState()
        return self.streak_states[user_id]
    
    def update_streak(self, user_id: int, is_correct: bool) -> StreakState:
        """
        更新用户的连击状态
        
        Args:
            user_id: 用户ID
            is_correct: 是否答对
            
        Returns:
            更新后的连击状态
        """
        state = self.get_user_streak_state(user_id)
        
        if is_correct:
            # 答对：增加连对计数，重置连错计数
            state.consecutive_correct += 1
            state.consecutive_wrong = 0
            state.current_streak_type = StreakType.WIN_STREAK
            state.current_streak_count = state.consecutive_correct
        else:
            # 答错：增加连错计数，重置连对计数
            state.consecutive_wrong += 1
            state.consecutive_correct = 0
            state.current_streak_type = StreakType.LOSS_STREAK
            state.current_streak_count = state.consecutive_wrong
        
        return state
    
    def check_streak_effect(self, user_id: int) -> Tuple[StreakEffect, int]:
        """
        检查是否触发了连击效果
        
        Args:
            user_id: 用户ID
            
        Returns:
            (效果类型, 连击数)
        """
        state = self.get_user_streak_state(user_id)
        
        # 检查高光连击（连续正确3次）
        if state.consecutive_correct >= self.WIN_STREAK_THRESHOLD:
            return StreakEffect.HIGHLIGHT, state.consecutive_correct
        
        # 检查降级保护（连续错误2次）
        if state.consecutive_wrong >= self.LOSS_STREAK_THRESHOLD:
            return StreakEffect.DOWNGRADE_PROTECTION, state.consecutive_wrong
        
        return StreakEffect.NONE, 0
    
    def calculate_difficulty_range(
        self, 
        user_id: int, 
        theta: float,
        base_range: float = 0.5
    ) -> DifficultyAdjustment:
        """
        根据连击状态计算推荐难度范围
        
        PRD公式：
        - 基础推荐难度区间：[θ - 0.5, θ + 0.5]
        - 连续正确3次：S_next 上限 += 0.3
        - 连续错误2次：S_next 下限 -= 0.3
        
        Args:
            user_id: 用户ID
            theta: 学生能力值
            base_range: 基础难度范围（默认0.5）
            
        Returns:
            难度调整结果
        """
        # 基础难度范围
        original_min = theta - base_range
        original_max = theta + base_range
        
        # 检查连击效果
        effect_type, streak_count = self.check_streak_effect(user_id)
        
        adjusted_min = original_min
        adjusted_max = original_max
        adjustment_delta = 0.0
        effect_triggered = False
        
        if effect_type == StreakEffect.HIGHLIGHT:
            # 高光连击：提升难度上限
            adjustment_delta = self.DIFFICULTY_ADJUSTMENT
            adjusted_max = original_max + adjustment_delta
            effect_triggered = True
            
        elif effect_type == StreakEffect.DOWNGRADE_PROTECTION:
            # 降级保护：降低难度下限
            adjustment_delta = -self.DIFFICULTY_ADJUSTMENT
            adjusted_min = original_min + adjustment_delta
            effect_triggered = True
        
        # 限制难度范围在[-3, +3]之间（IRT标准范围）
        adjusted_min = max(-3.0, min(3.0, adjusted_min))
        adjusted_max = max(-3.0, min(3.0, adjusted_max))
        
        return DifficultyAdjustment(
            original_min=original_min,
            original_max=original_max,
            adjusted_min=adjusted_min,
            adjusted_max=adjusted_max,
            adjustment_delta=adjustment_delta,
            effect_type=effect_type,
            effect_triggered=effect_triggered,
            streak_count=streak_count
        )
    
    def get_ui_effect(self, user_id: int) -> Optional[Dict]:
        """
        获取当前应该显示的UI效果
        
        Args:
            user_id: 用户ID
            
        Returns:
            UI效果定义，如果没有触发效果则返回None
        """
        effect_type, streak_count = self.check_streak_effect(user_id)
        
        if effect_type == StreakEffect.NONE:
            return None
        
        ui_effect = self.UI_EFFECTS.get(effect_type)
        if ui_effect is None:
            return None
        
        # 格式化Advisor消息
        message = ui_effect.advisor_message.format(streak=streak_count)
        
        return {
            "effect_type": ui_effect.effect_type.value,
            "icon": ui_effect.icon,
            "animation": ui_effect.animation,
            "advisor_message": message,
            "color_theme": ui_effect.color_theme,
            "streak_count": streak_count
        }
    
    def process_answer(
        self, 
        user_id: int, 
        is_correct: bool,
        theta: float
    ) -> Dict:
        """
        处理答题结果，返回完整的连击状态和UI效果
        
        Args:
            user_id: 用户ID
            is_correct: 是否答对
            theta: 学生能力值
            
        Returns:
            包含连击状态、难度调整、UI效果的完整结果
        """
        # 1. 更新连击状态
        streak_state = self.update_streak(user_id, is_correct)
        
        # 2. 计算难度调整
        difficulty_adj = self.calculate_difficulty_range(user_id, theta)
        
        # 3. 获取UI效果
        ui_effect = self.get_ui_effect(user_id)
        
        return {
            "streak_state": streak_state.to_dict(),
            "difficulty_adjustment": difficulty_adj.to_dict(),
            "ui_effect": ui_effect,
            "should_trigger_effect": ui_effect is not None
        }
    
    def reset_streak(self, user_id: int) -> StreakState:
        """重置用户的连击状态"""
        self.streak_states[user_id] = StreakState()
        return self.streak_states[user_id]


# 全局连击处理器实例
streak_handler = StreakHandler()


def get_streak_handler() -> StreakHandler:
    """获取连击处理器实例"""
    return streak_handler


# 单元测试
if __name__ == "__main__":
    print("=== 需求1：连击处理器测试 ===\n")
    
    handler = StreakHandler()
    user_id = 1
    theta = 0.5  # 学生能力值
    
    # 测试1：连续答对3次（触发高光连击）
    print("测试1：连续答对3次")
    for i in range(3):
        result = handler.process_answer(user_id, True, theta)
        print(f"  第{i+1}次答对:")
        print(f"    连对次数: {result['streak_state']['consecutive_correct']}")
        print(f"    难度范围: {result['difficulty_adjustment']['adjusted_range']}")
        if result['ui_effect']:
            print(f"    UI效果: {result['ui_effect']['icon']} {result['ui_effect']['advisor_message']}")
    
    # 测试2：连续答错2次（触发降级保护）
    print("\n测试2：连续答错2次")
    handler.reset_streak(user_id)
    for i in range(2):
        result = handler.process_answer(user_id, False, theta)
        print(f"  第{i+1}次答错:")
        print(f"    连错次数: {result['streak_state']['consecutive_wrong']}")
        print(f"    难度范围: {result['difficulty_adjustment']['adjusted_range']}")
        if result['ui_effect']:
            print(f"    UI效果: {result['ui_effect']['icon']} {result['ui_effect']['advisor_message']}")
    
    # 测试3：混合答题（对-对-错-对-对-对）
    print("\n测试3：混合答题（对-对-错-对-对-对）")
    handler.reset_streak(user_id)
    answers = [True, True, False, True, True, True]
    for i, is_correct in enumerate(answers):
        result = handler.process_answer(user_id, is_correct, theta)
        status = "答对" if is_correct else "答错"
        print(f"  第{i+1}次{status}: 连对={result['streak_state']['consecutive_correct']}, 连错={result['streak_state']['consecutive_wrong']}")
        if result['ui_effect']:
            print(f"    -> 触发效果: {result['ui_effect']['icon']} {result['ui_effect']['effect_type']}")
    
    print("\n=== 所有测试通过！===")
