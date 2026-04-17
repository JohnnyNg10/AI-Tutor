"""
学习习惯成就徽章服务
弱化分数激励，强化对学生优良"学习习惯与抗压行为"的成就认可

对应行号23/28: 弱化分数激励，强化对学生优良"学习习惯与抗压行为"的成就认可

功能：
1. 行为埋点检测（长耗时未跳过、连续不查看答案、复习队列正确率100%等）
2. 勋章系统（坚韧不拔、独立思考者、温故知新等）
3. 虚拟成就徽章展示

实现文件: backend/services/learning_habit_badge_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
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
class Badge:
    """成就徽章"""
    badge_id: str
    name: str
    description: str
    icon: str
    color: str
    category: str  # habit / resilience / persistence
    condition_description: str
    unlocked_at: Optional[str] = None
    is_new: bool = False


@dataclass
class BadgeProgress:
    """徽章进度"""
    badge_id: str
    current_value: int
    target_value: int
    percentage: float
    is_unlocked: bool


class LearningHabitBadgeService:
    """
    学习习惯成就徽章服务
    
    功能：
    1. 检测学习行为（长耗时、不查看答案、复习正确率等）
    2. 颁发成就徽章
    3. 展示在个人主页
    """
    
    # Redis Key前缀
    USER_BADGES_KEY = "ai:tutor:badges:{user_id}"
    BADGE_PROGRESS_KEY = "ai:tutor:badge-progress:{user_id}"
    BEHAVIOR_TRACKING_KEY = "ai:tutor:behavior:{user_id}"
    
    # 徽章定义
    BADGES = {
        # 习惯类
        'persistent_solver': {
            'name': '🔥 坚韧不拔',
            'description': '单题耗时超过10分钟但未跳过，坚持到最后',
            'icon': '🔥',
            'color': '#FF4D4F',
            'category': 'resilience',
            'condition': 'time_spent >= 600 AND NOT skipped'
        },
        'independent_thinker': {
            'name': '🧠 独立思考者',
            'description': '连续5道题不查看完整答案（L4提示）',
            'icon': '🧠',
            'color': '#722ED1',
            'category': 'habit',
            'condition': 'consecutive_no_l4 >= 5'
        },
        'review_master': {
            'name': '📚 温故知新',
            'description': '复习队列正确率达到100%',
            'icon': '📚',
            'color': '#52C41A',
            'category': 'habit',
            'condition': 'review_accuracy == 1.0 AND review_count >= 5'
        },
        'early_bird': {
            'name': '🌅 早起鸟',
            'description': '连续7天在早上8点前完成学习',
            'icon': '🌅',
            'color': '#FAAD14',
            'category': 'habit',
            'condition': 'consecutive_early_morning >= 7'
        },
        'streak_keeper': {
            'name': '🔥 连胜达人',
            'description': '连续答对10道题',
            'icon': '🔥',
            'color': '#FF6B6B',
            'category': 'habit',
            'condition': 'consecutive_correct >= 10'
        },
        'hint_minimalist': {
            'name': '💡 提示极简主义者',
            'description': '连续3道题仅使用L0-L1提示',
            'icon': '💡',
            'color': '#1890FF',
            'category': 'habit',
            'condition': 'consecutive_low_hint >= 3'
        },
        'error_conqueror': {
            'name': '⚔️ 错题征服者',
            'description': '连续3次将错题重做正确',
            'icon': '⚔️',
            'color': '#EB2F96',
            'category': 'resilience',
            'condition': 'consecutive_error_recovery >= 3'
        },
        'deep_thinker': {
            'name': '🤔 深度思考者',
            'description': '单题思考时间超过平均值的2倍但最终答对',
            'icon': '🤔',
            'color': '#13C2C2',
            'category': 'persistence',
            'condition': 'time_spent >= avg_time * 2 AND is_correct'
        },
        'comeback_king': {
            'name': '👑 逆袭王者',
            'description': '连续3题错误后连续3题正确',
            'icon': '👑',
            'color': '#FA8C16',
            'category': 'resilience',
            'condition': 'consecutive_wrong_3 AND consecutive_correct_3'
        },
        'daily_grind': {
            'name': '📅 每日坚持',
            'description': '连续30天每天完成至少5道题',
            'icon': '📅',
            'color': '#52C41A',
            'category': 'habit',
            'condition': 'consecutive_days >= 30 AND daily_questions >= 5'
        }
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("学习习惯徽章服务初始化完成")
    
    # ==================== 行为检测 ====================
    
    def track_behavior(self, user_id: int, behavior_data: Dict[str, Any]) -> None:
        """
        追踪学习行为
        
        记录用户的学习行为用于徽章检测
        """
        try:
            key = self.BEHAVIOR_TRACKING_KEY.format(user_id=user_id)
            
            # 更新行为计数
            for behavior_type, value in behavior_data.items():
                if isinstance(value, (int, float)):
                    self.redis_service.redis_client.hincrbyfloat(key, behavior_type, value)
                else:
                    # 记录最近行为
                    recent_key = f"{key}:{behavior_type}"
                    self.redis_service.redis_client.lpush(recent_key, json.dumps({
                        'value': value,
                        'timestamp': datetime.now().isoformat()
                    }))
                    self.redis_service.redis_client.ltrim(recent_key, 0, 99)  # 保留最近100条
            
            # 设置TTL
            self.redis_service.redis_client.expire(key, 30 * 24 * 60 * 60)
            
        except Exception as e:
            logger.error(f"追踪行为失败: {e}")
    
    def detect_and_award_badges(self, user_id: int) -> List[Badge]:
        """
        检测并颁发徽章
        
        根据用户行为检测是否满足徽章条件
        """
        try:
            # 获取用户行为数据
            behavior = self._get_user_behavior(user_id)
            
            # 获取已获得的徽章
            earned_badges = self._get_earned_badges(user_id)
            
            new_badges = []
            
            for badge_id, badge_info in self.BADGES.items():
                # 检查是否已获得
                if badge_id in earned_badges:
                    continue
                
                # 检查是否满足条件
                if self._check_badge_condition(badge_id, behavior):
                    # 颁发徽章
                    badge = self._award_badge(user_id, badge_id)
                    if badge:
                        new_badges.append(badge)
            
            return new_badges
            
        except Exception as e:
            logger.error(f"检测徽章失败: {e}")
            return []
    
    def _get_user_behavior(self, user_id: int) -> Dict[str, Any]:
        """获取用户行为数据"""
        try:
            key = self.BEHAVIOR_TRACKING_KEY.format(user_id=user_id)
            behavior = self.redis_service.redis_client.hgetall(key)
            
            # 转换数值
            result = {}
            for k, v in behavior.items():
                try:
                    result[k] = float(v)
                except:
                    result[k] = v
            
            return result
            
        except Exception as e:
            logger.error(f"获取用户行为失败: {e}")
            return {}
    
    def _check_badge_condition(self, badge_id: str, behavior: Dict[str, Any]) -> bool:
        """检查徽章条件"""
        # 简化的条件检查
        conditions = {
            'persistent_solver': lambda b: b.get('long_time_no_skip', 0) >= 1,
            'independent_thinker': lambda b: b.get('consecutive_no_l4', 0) >= 5,
            'review_master': lambda b: b.get('review_accuracy', 0) >= 1.0 and b.get('review_count', 0) >= 5,
            'early_bird': lambda b: b.get('consecutive_early_morning', 0) >= 7,
            'streak_keeper': lambda b: b.get('consecutive_correct', 0) >= 10,
            'hint_minimalist': lambda b: b.get('consecutive_low_hint', 0) >= 3,
            'error_conqueror': lambda b: b.get('consecutive_error_recovery', 0) >= 3,
            'deep_thinker': lambda b: b.get('deep_think_count', 0) >= 1,
            'comeback_king': lambda b: b.get('comeback_count', 0) >= 1,
            'daily_grind': lambda b: b.get('consecutive_days', 0) >= 30 and b.get('daily_questions', 0) >= 5
        }
        
        check_func = conditions.get(badge_id)
        if check_func:
            return check_func(behavior)
        
        return False
    
    def _award_badge(self, user_id: int, badge_id: str) -> Optional[Badge]:
        """颁发徽章"""
        try:
            badge_info = self.BADGES.get(badge_id)
            if not badge_info:
                return None
            
            now = datetime.now().isoformat()
            
            # 保存徽章
            key = self.USER_BADGES_KEY.format(user_id=user_id)
            badge_data = {
                'badge_id': badge_id,
                'unlocked_at': now,
                'is_new': True
            }
            self.redis_service.redis_client.hset(key, badge_id, json.dumps(badge_data))
            
            logger.info(f"颁发徽章: 用户={user_id}, 徽章={badge_id}")
            
            return Badge(
                badge_id=badge_id,
                name=badge_info['name'],
                description=badge_info['description'],
                icon=badge_info['icon'],
                color=badge_info['color'],
                category=badge_info['category'],
                condition_description=badge_info['condition'],
                unlocked_at=now,
                is_new=True
            )
            
        except Exception as e:
            logger.error(f"颁发徽章失败: {e}")
            return None
    
    def _get_earned_badges(self, user_id: int) -> Set[str]:
        """获取已获得的徽章ID"""
        try:
            key = self.USER_BADGES_KEY.format(user_id=user_id)
            return set(self.redis_service.redis_client.hkeys(key))
        except Exception as e:
            logger.error(f"获取已获得徽章失败: {e}")
            return set()
    
    # ==================== 徽章查询 ====================
    
    def get_user_badges(self, user_id: int) -> Dict[str, Any]:
        """获取用户所有徽章"""
        try:
            # 已获得徽章
            earned = self._get_earned_badges(user_id)
            
            earned_badges = []
            for badge_id in earned:
                badge_info = self.BADGES.get(badge_id)
                if badge_info:
                    earned_badges.append({
                        'badge_id': badge_id,
                        'name': badge_info['name'],
                        'description': badge_info['description'],
                        'icon': badge_info['icon'],
                        'color': badge_info['color'],
                        'category': badge_info['category']
                    })
            
            # 未获得徽章（进度）
            behavior = self._get_user_behavior(user_id)
            in_progress = []
            
            for badge_id, badge_info in self.BADGES.items():
                if badge_id not in earned:
                    progress = self._calculate_badge_progress(badge_id, behavior)
                    in_progress.append({
                        'badge_id': badge_id,
                        'name': badge_info['name'],
                        'description': badge_info['description'],
                        'icon': badge_info['icon'],
                        'color': '#999999',  # 灰色表示未获得
                        'category': badge_info['category'],
                        'progress': progress
                    })
            
            return {
                'earned_count': len(earned_badges),
                'total_count': len(self.BADGES),
                'earned_badges': earned_badges,
                'in_progress': in_progress
            }
            
        except Exception as e:
            logger.error(f"获取用户徽章失败: {e}")
            return {'earned_count': 0, 'total_count': 0, 'earned_badges': [], 'in_progress': []}
    
    def _calculate_badge_progress(self, badge_id: str, behavior: Dict[str, Any]) -> Dict[str, Any]:
        """计算徽章进度"""
        progress_map = {
            'persistent_solver': {'current': behavior.get('long_time_no_skip', 0), 'target': 1},
            'independent_thinker': {'current': behavior.get('consecutive_no_l4', 0), 'target': 5},
            'review_master': {'current': behavior.get('review_accuracy', 0) * 100, 'target': 100},
            'early_bird': {'current': behavior.get('consecutive_early_morning', 0), 'target': 7},
            'streak_keeper': {'current': behavior.get('consecutive_correct', 0), 'target': 10},
            'hint_minimalist': {'current': behavior.get('consecutive_low_hint', 0), 'target': 3},
            'error_conqueror': {'current': behavior.get('consecutive_error_recovery', 0), 'target': 3},
            'deep_thinker': {'current': behavior.get('deep_think_count', 0), 'target': 1},
            'comeback_king': {'current': behavior.get('comeback_count', 0), 'target': 1},
            'daily_grind': {'current': min(behavior.get('consecutive_days', 0), 30), 'target': 30}
        }
        
        progress = progress_map.get(badge_id, {'current': 0, 'target': 1})
        percentage = min(100, progress['current'] / progress['target'] * 100) if progress['target'] > 0 else 0
        
        return {
            'current': progress['current'],
            'target': progress['target'],
            'percentage': round(percentage, 1)
        }


# ==================== 便捷函数 ====================

def track_learning_behavior(user_id: int, behavior_data: Dict[str, Any]) -> None:
    """便捷函数：追踪学习行为"""
    service = LearningHabitBadgeService()
    service.track_behavior(user_id, behavior_data)


def check_and_award_badges(user_id: int) -> List[Badge]:
    """便捷函数：检查并颁发徽章"""
    service = LearningHabitBadgeService()
    return service.detect_and_award_badges(user_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("学习习惯徽章服务测试")
    print("=" * 60)
    
    service = LearningHabitBadgeService()
    
    # 测试追踪行为
    print("\n行为追踪测试：")
    service.track_behavior(1, {
        'consecutive_correct': 10,
        'consecutive_no_l4': 5
    })
    print("  已追踪行为数据")
    
    # 测试检测徽章
    print("\n徽章检测测试：")
    new_badges = service.detect_and_award_badges(1)
    for badge in new_badges:
        print(f"  获得徽章: {badge.name}")
    
    # 测试获取徽章
    print("\n徽章查询测试：")
    badges = service.get_user_badges(1)
    print(f"  已获得: {badges['earned_count']}/{badges['total_count']}")
    
    print("\n测试完成")
