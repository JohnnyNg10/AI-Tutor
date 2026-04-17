"""
IRT段位服务
将IRT θ值转化为游戏化成长段位趋势图

对应需求9: 将底层枯燥的IRT θ值转化为学生易懂的游戏化成长段位趋势图

实现文件：backend/services/irt_ranking_service.py
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

from utils.logger import logger


class RankTier(Enum):
    """段位等级"""
    NOVICE = "novice"           # 见习生
    EXPLORER = "explorer"       # 探索者
    APPRENTICE = "apprentice"   # 学徒
    PRACTITIONER = "practitioner"  # 实践者
    EXPERT = "expert"           # 专家
    MASTER = "master"           # 大师
    GRANDMASTER = "grandmaster" # 宗师


@dataclass
class RankInfo:
    """段位信息"""
    tier: RankTier
    name: str
    name_cn: str
    min_theta: float
    max_theta: float
    color: str
    icon: str
    description: str


@dataclass
class RankingData:
    """段位数据"""
    user_id: int
    current_theta: float
    current_rank: RankInfo
    progress_to_next: float  # 0-100
    next_rank: Optional[RankInfo]
    prev_rank: Optional[RankInfo]
    total_study_days: int
    rank_history: List[Dict[str, Any]]


class IRTRankingService:
    """
    IRT段位服务
    
    功能：
    1. θ值到段位的映射（[-3, +3] → 游戏化段位）
    2. 段位趋势历史数据查询
    3. 升级/降级动画触发
    """
    
    # 段位定义（硬指标）
    RANK_DEFINITIONS = [
        RankInfo(
            tier=RankTier.NOVICE,
            name="Novice",
            name_cn="见习生",
            min_theta=-3.0,
            max_theta=-2.0,
            color="#8C8C8C",
            icon="🌱",
            description="数学之路刚刚起步，充满无限可能"
        ),
        RankInfo(
            tier=RankTier.EXPLORER,
            name="Explorer",
            name_cn="探索者",
            min_theta=-2.0,
            max_theta=-1.0,
            color="#52C41A",
            icon="🔍",
            description="开始探索数学的奥秘，发现规律的魅力"
        ),
        RankInfo(
            tier=RankTier.APPRENTICE,
            name="Apprentice",
            name_cn="学徒",
            min_theta=-1.0,
            max_theta=0.0,
            color="#1890FF",
            icon="📚",
            description="勤奋学习，基础日渐扎实"
        ),
        RankInfo(
            tier=RankTier.PRACTITIONER,
            name="Practitioner",
            name_cn="实践者",
            min_theta=0.0,
            max_theta=1.0,
            color="#722ED1",
            icon="⚔️",
            description="理论与实践结合，解题能力稳步提升"
        ),
        RankInfo(
            tier=RankTier.EXPERT,
            name="Expert",
            name_cn="专家",
            min_theta=1.0,
            max_theta=2.0,
            color="#FA8C16",
            icon="⭐",
            description="数列领域已有深厚造诣，能够解决复杂问题"
        ),
        RankInfo(
            tier=RankTier.MASTER,
            name="Master",
            name_cn="大师",
            min_theta=2.0,
            max_theta=2.5,
            color="#EB2F96",
            icon="🏆",
            description="数列大师，技巧炉火纯青"
        ),
        RankInfo(
            tier=RankTier.GRANDMASTER,
            name="Grandmaster",
            name_cn="宗师",
            min_theta=2.5,
            max_theta=3.0,
            color="#F5222D",
            icon="👑",
            description="数列宗师，登峰造极，罕有敌手"
        )
    ]
    
    def __init__(self):
        """初始化服务"""
        logger.info("IRT段位服务初始化完成")
    
    # ==================== 核心转换方法 ====================
    
    def theta_to_rank(self, theta: float) -> RankInfo:
        """
        将θ值转换为段位
        
        θ范围: [-3, +3]
        """
        # 限制在有效范围内
        theta = max(-3.0, min(3.0, theta))
        
        for rank in self.RANK_DEFINITIONS:
            if rank.min_theta <= theta < rank.max_theta:
                return rank
        
        # 边界情况
        if theta >= 2.5:
            return self.RANK_DEFINITIONS[-1]  # 宗师
        return self.RANK_DEFINITIONS[0]  # 见习生
    
    def calculate_progress_to_next(self, theta: float, current_rank: RankInfo) -> float:
        """
        计算到下一阶段的进度（0-100）
        """
        if current_rank.tier == RankTier.GRANDMASTER:
            return 100.0  # 已是最高段位
        
        rank_range = current_rank.max_theta - current_rank.min_theta
        progress_in_rank = theta - current_rank.min_theta
        
        if rank_range <= 0:
            return 100.0
        
        return min(100.0, max(0.0, (progress_in_rank / rank_range) * 100))
    
    def get_next_rank(self, current_rank: RankInfo) -> Optional[RankInfo]:
        """获取下一段位"""
        current_index = self.RANK_DEFINITIONS.index(current_rank)
        if current_index < len(self.RANK_DEFINITIONS) - 1:
            return self.RANK_DEFINITIONS[current_index + 1]
        return None
    
    def get_prev_rank(self, current_rank: RankInfo) -> Optional[RankInfo]:
        """获取上一段位"""
        current_index = self.RANK_DEFINITIONS.index(current_rank)
        if current_index > 0:
            return self.RANK_DEFINITIONS[current_index - 1]
        return None
    
    def check_rank_change(
        self,
        old_theta: float,
        new_theta: float
    ) -> Dict[str, Any]:
        """
        检查段位变化
        
        返回升级/降级信息，用于触发动画
        """
        old_rank = self.theta_to_rank(old_theta)
        new_rank = self.theta_to_rank(new_theta)
        
        old_index = self.RANK_DEFINITIONS.index(old_rank)
        new_index = self.RANK_DEFINITIONS.index(new_rank)
        
        if new_index > old_index:
            # 升级
            return {
                'has_changed': True,
                'change_type': 'promotion',
                'from_rank': old_rank,
                'to_rank': new_rank,
                'message': f'恭喜！你已从【{old_rank.name_cn}】晋升为【{new_rank.name_cn}】！',
                'should_animate': True
            }
        elif new_index < old_index:
            # 降级
            return {
                'has_changed': True,
                'change_type': 'demotion',
                'from_rank': old_rank,
                'to_rank': new_rank,
                'message': f'别灰心，你当前处于【{new_rank.name_cn}】，继续努力！',
                'should_animate': True
            }
        else:
            # 段位不变
            return {
                'has_changed': False,
                'change_type': 'none',
                'from_rank': old_rank,
                'to_rank': new_rank,
                'message': None,
                'should_animate': False
            }
    
    # ==================== 数据查询方法 ====================
    
    def get_ranking_data(self, user_id: int) -> RankingData:
        """
        获取段位数据
        
        这是前端展示的主入口
        """
        # TODO: 从数据库查询用户当前θ值
        # 临时返回模拟数据
        current_theta = 0.5  # 模拟数据
        
        current_rank = self.theta_to_rank(current_theta)
        progress = self.calculate_progress_to_next(current_theta, current_rank)
        next_rank = self.get_next_rank(current_rank)
        prev_rank = self.get_prev_rank(current_rank)
        
        # TODO: 从数据库查询段位历史
        rank_history = self._get_mock_rank_history()
        
        return RankingData(
            user_id=user_id,
            current_theta=round(current_theta, 2),
            current_rank=current_rank,
            progress_to_next=round(progress, 2),
            next_rank=next_rank,
            prev_rank=prev_rank,
            total_study_days=30,  # 模拟数据
            rank_history=rank_history
        )
    
    def _get_mock_rank_history(self) -> List[Dict[str, Any]]:
        """获取模拟段位历史"""
        history = []
        base_theta = -1.5
        
        for i in range(10):
            date = datetime.now() - timedelta(days=(10-i)*3)
            theta = base_theta + (i / 10) * 2.0
            rank = self.theta_to_rank(theta)
            
            history.append({
                'date': date.strftime('%Y-%m-%d'),
                'theta': round(theta, 2),
                'rank_tier': rank.tier.value,
                'rank_name': rank.name_cn,
                'rank_color': rank.color,
                'rank_icon': rank.icon
            })
        
        return history
    
    def get_rank_trend(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取段位趋势数据
        
        用于绘制段位趋势图
        """
        # TODO: 从user_ability_history表查询
        history = []
        base_theta = 0.0
        
        for i in range(days):
            date = datetime.now() - timedelta(days=days-i-1)
            # 模拟数据：逐渐提升
            theta = base_theta + (i / days) * 0.8
            rank = self.theta_to_rank(theta)
            
            history.append({
                'date': date.strftime('%Y-%m-%d'),
                'theta': round(theta, 2),
                'rank_tier': rank.tier.value,
                'rank_name': rank.name_cn,
                'rank_color': rank.color,
                'rank_icon': rank.icon,
                'progress': self.calculate_progress_to_next(theta, rank)
            })
        
        return history
    
    # ==================== 所有段位信息 ====================
    
    def get_all_ranks(self) -> List[Dict[str, Any]]:
        """获取所有段位信息"""
        return [
            {
                'tier': rank.tier.value,
                'name': rank.name,
                'name_cn': rank.name_cn,
                'min_theta': rank.min_theta,
                'max_theta': rank.max_theta,
                'color': rank.color,
                'icon': rank.icon,
                'description': rank.description
            }
            for rank in self.RANK_DEFINITIONS
        ]


# ==================== 便捷函数 ====================

def get_user_ranking_info(user_id: int) -> Dict[str, Any]:
    """
    便捷函数：获取用户段位信息
    
    使用示例:
        info = get_user_ranking_info(1)
    """
    service = IRTRankingService()
    data = service.get_ranking_data(user_id)
    
    return {
        'user_id': data.user_id,
        'current_theta': data.current_theta,
        'current_rank': {
            'tier': data.current_rank.tier.value,
            'name': data.current_rank.name,
            'name_cn': data.current_rank.name_cn,
            'color': data.current_rank.color,
            'icon': data.current_rank.icon,
            'description': data.current_rank.description
        },
        'progress_to_next': data.progress_to_next,
        'next_rank': {
            'name_cn': data.next_rank.name_cn,
            'icon': data.next_rank.icon
        } if data.next_rank else None,
        'total_study_days': data.total_study_days
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("IRT段位服务测试")
    print("=" * 60)
    
    service = IRTRankingService()
    
    # 测试θ值到段位映射
    print("\nθ值到段位映射测试：")
    test_thetas = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.3, 2.8]
    for theta in test_thetas:
        rank = service.theta_to_rank(theta)
        progress = service.calculate_progress_to_next(theta, rank)
        print(f"  θ={theta:+.1f} → {rank.name_cn} {rank.icon} (进度: {progress:.0f}%)")
    
    # 测试段位变化检测
    print("\n段位变化检测测试：")
    changes = [
        (-1.5, -0.5),  # 升级
        (0.5, -0.5),   # 降级
        (0.5, 0.6)     # 不变
    ]
    for old_theta, new_theta in changes:
        result = service.check_rank_change(old_theta, new_theta)
        print(f"  θ {old_theta:+.1f} → {new_theta:+.1f}: {result['change_type']}")
