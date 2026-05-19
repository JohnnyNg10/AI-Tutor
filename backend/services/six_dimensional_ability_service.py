"""
六维能力画像服务
多维度展示学生数学思维深度与认知特质

对应行号4: 多维度展示学生数学思维深度与认知特质，而非单纯知识点

六维定义：
1. 逻辑推演力 (Logical Reasoning)
2. 计算稳定性 (Calculation Stability)
3. 知识迁移力 (Knowledge Transfer)
4. 提示独立性 (Hint Independence)
5. 错题自愈力 (Error Recovery)
6. 学习抗挫力 (Learning Resilience)

实现文件: backend/services/six_dimensional_ability_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy.ext.asyncio import AsyncSession

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class SixDimensionalAbility:
    """六维能力数据"""
    user_id: int
    
    # 六维能力分数 (0-100)
    logical_reasoning: float = 0.0        # 逻辑推演力
    calculation_stability: float = 0.0    # 计算稳定性
    knowledge_transfer: float = 0.0       # 知识迁移力
    hint_independence: float = 0.0        # 提示独立性
    error_recovery: float = 0.0           # 错题自愈力
    learning_resilience: float = 0.0      # 学习抗挫力
    
    # 综合评分
    overall_score: float = 0.0
    dominant_dimension: str = ""  # 主导维度
    
    # 元数据
    calculated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    data_sources: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AbilityDimensionDetail:
    """能力维度详情"""
    dimension_name: str
    dimension_name_cn: str
    score: float
    level: str  # weak/average/strong/excellent
    description: str
    suggestions: List[str]
    trend: str  # up/down/stable


class SixDimensionalAbilityService:
    """
    六维能力画像服务
    
    功能：
    1. 从交互日志和答题记录中聚合计算六维能力
    2. 生成雷达图数据
    3. 提供能力分析和建议
    """
    
    # Redis Key前缀
    SIX_DIM_ABILITY_KEY = "ai:tutor:six-dim:{user_id}"
    SIX_DIM_HISTORY_KEY = "ai:tutor:six-dim-history:{user_id}"
    
    # 能力等级阈值
    LEVEL_THRESHOLDS = {
        'weak': 40,
        'average': 60,
        'strong': 80,
        'excellent': 90
    }
    
    # 维度配置
    DIMENSIONS = {
        'logical_reasoning': {
            'name_cn': '逻辑推演力',
            'description': '分析数学问题、推导解题思路的能力',
            'indicators': ['多步骤推理正确率', '复杂题目完成率', '解题思路清晰度']
        },
        'calculation_stability': {
            'name_cn': '计算稳定性',
            'description': '准确执行数学计算、避免粗心错误的能力',
            'indicators': ['计算错误率', '数值运算准确率', '符号处理正确率']
        },
        'knowledge_transfer': {
            'name_cn': '知识迁移力',
            'description': '将已学知识应用到新情境的能力',
            'indicators': ['变式题正确率', '跨知识点应用', '新题型适应能力']
        },
        'hint_independence': {
            'name_cn': '提示独立性',
            'description': '独立解决问题、减少对外部提示依赖的能力',
            'indicators': ['提示使用率', 'L0自主完成率', '首次尝试成功率']
        },
        'error_recovery': {
            'name_cn': '错题自愈力',
            'description': '从错误中学习、改正并掌握的能力',
            'indicators': ['错题重做正确率', '复习队列完成率', '同类型错误减少率']
        },
        'learning_resilience': {
            'name_cn': '学习抗挫力',
            'description': '面对困难坚持学习、不轻易放弃的能力',
            'indicators': ['连续错误后继续率', '难题停留时间', '跳过率']
        }
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("六维能力画像服务初始化完成")
    
    # ==================== 六维能力计算 ====================
    
    def calculate_six_dimensional_ability(
        self,
        user_id: int,
        interaction_logs: Optional[List[Dict]] = None,
        ability_history: Optional[List[Dict]] = None
    ) -> SixDimensionalAbility:
        """
        计算六维能力画像
        
        从交互日志和能力历史数据中聚合计算
        """
        try:
            # 如果没有提供数据，尝试从Redis/数据库获取
            if interaction_logs is None:
                interaction_logs = self._get_user_interaction_logs(user_id)
            if ability_history is None:
                ability_history = self._get_user_ability_history(user_id)
            
            # 计算各维度能力
            logical_reasoning = self._calculate_logical_reasoning(
                interaction_logs, ability_history
            )
            calculation_stability = self._calculate_calculation_stability(
                interaction_logs, ability_history
            )
            knowledge_transfer = self._calculate_knowledge_transfer(
                interaction_logs, ability_history
            )
            hint_independence = self._calculate_hint_independence(
                interaction_logs, ability_history
            )
            error_recovery = self._calculate_error_recovery(
                interaction_logs, ability_history
            )
            learning_resilience = self._calculate_learning_resilience(
                interaction_logs, ability_history
            )
            
            # 计算综合评分
            overall_score = (
                logical_reasoning +
                calculation_stability +
                knowledge_transfer +
                hint_independence +
                error_recovery +
                learning_resilience
            ) / 6
            
            # 确定主导维度
            scores = {
                'logical_reasoning': logical_reasoning,
                'calculation_stability': calculation_stability,
                'knowledge_transfer': knowledge_transfer,
                'hint_independence': hint_independence,
                'error_recovery': error_recovery,
                'learning_resilience': learning_resilience
            }
            dominant_dimension = max(scores, key=scores.get)
            
            ability = SixDimensionalAbility(
                user_id=user_id,
                logical_reasoning=round(logical_reasoning, 1),
                calculation_stability=round(calculation_stability, 1),
                knowledge_transfer=round(knowledge_transfer, 1),
                hint_independence=round(hint_independence, 1),
                error_recovery=round(error_recovery, 1),
                learning_resilience=round(learning_resilience, 1),
                overall_score=round(overall_score, 1),
                dominant_dimension=dominant_dimension,
                data_sources={
                    'interaction_logs_count': len(interaction_logs) if interaction_logs else 0,
                    'ability_history_count': len(ability_history) if ability_history else 0
                }
            )
            
            # 缓存结果
            self._cache_ability(user_id, ability)
            
            return ability
            
        except Exception as e:
            logger.error(f"计算六维能力失败: {e}")
            return SixDimensionalAbility(user_id=user_id)
    
    def _calculate_logical_reasoning(
        self,
        interaction_logs: List[Dict],
        ability_history: List[Dict]
    ) -> float:
        """计算逻辑推演力"""
        # 基于多步骤推理正确率和复杂题目完成率
        # 简化实现：基于答题正确率和平均步数
        
        if not ability_history:
            return 50.0  # 默认值
        
        correct_rate = sum(1 for h in ability_history if h.get('is_correct', False)) / len(ability_history)
        
        # 基于正确率计算，最高100分
        score = correct_rate * 100
        
        # 如果有交互日志，考虑解题步数
        if interaction_logs:
            avg_steps = sum(log.get('steps', 3) for log in interaction_logs) / len(interaction_logs)
            # 步数越多且正确，逻辑力越强
            if avg_steps > 3 and correct_rate > 0.7:
                score = min(100, score * 1.1)
        
        return min(100, max(0, score))
    
    def _calculate_calculation_stability(
        self,
        interaction_logs: List[Dict],
        ability_history: List[Dict]
    ) -> float:
        """计算计算稳定性"""
        # 基于计算错误率
        
        if not interaction_logs:
            return 50.0
        
        # 统计计算错误
        calc_errors = sum(1 for log in interaction_logs 
                         if log.get('error_type') == 'calculation')
        total = len(interaction_logs)
        
        error_rate = calc_errors / total if total > 0 else 0
        
        # 错误率越低，稳定性越高
        score = (1 - error_rate) * 100
        
        return min(100, max(0, score))
    
    def _calculate_knowledge_transfer(
        self,
        interaction_logs: List[Dict],
        ability_history: List[Dict]
    ) -> float:
        """计算知识迁移力"""
        # 基于变式题正确率和跨知识点应用
        
        if not ability_history:
            return 50.0
        
        # 简化：基于不同知识点的答题正确率方差
        # 方差小说明迁移能力强
        
        topic_correct_rates = {}
        for h in ability_history:
            topic = h.get('knowledge_point', 'unknown')
            if topic not in topic_correct_rates:
                topic_correct_rates[topic] = []
            topic_correct_rates[topic].append(1 if h.get('is_correct') else 0)
        
        if not topic_correct_rates:
            return 50.0
        
        # 计算各主题平均正确率
        avg_rates = [sum(rates) / len(rates) for rates in topic_correct_rates.values()]
        
        # 迁移力 = 平均正确率 * (1 - 方差系数)
        if len(avg_rates) > 1:
            mean_rate = sum(avg_rates) / len(avg_rates)
            variance = sum((r - mean_rate) ** 2 for r in avg_rates) / len(avg_rates)
            std_dev = math.sqrt(variance)
            cv = std_dev / mean_rate if mean_rate > 0 else 0  # 变异系数
            
            score = mean_rate * 100 * (1 - min(cv, 0.5))
        else:
            score = avg_rates[0] * 100 if avg_rates else 50.0
        
        return min(100, max(0, score))
    
    def _calculate_hint_independence(
        self,
        interaction_logs: List[Dict],
        ability_history: List[Dict]
    ) -> float:
        """计算提示独立性"""
        # 基于提示使用率和L0自主完成率
        
        if not interaction_logs:
            return 50.0
        
        # 统计提示使用
        total_hints = sum(log.get('hint_count', 0) for log in interaction_logs)
        total_questions = len(interaction_logs)
        
        avg_hints = total_hints / total_questions if total_questions > 0 else 0
        
        # L0完成（无提示）的比例
        l0_completions = sum(1 for log in interaction_logs if log.get('hint_count', 0) == 0)
        l0_rate = l0_completions / total_questions if total_questions > 0 else 0
        
        # 独立性 = L0率 * 100 - 平均提示数惩罚
        score = l0_rate * 100 - avg_hints * 5
        
        return min(100, max(0, score))
    
    def _calculate_error_recovery(
        self,
        interaction_logs: List[Dict],
        ability_history: List[Dict]
    ) -> float:
        """计算错题自愈力"""
        # 基于错题重做正确率和复习队列完成率
        
        # 简化：基于错误后改进的比例
        if not ability_history or len(ability_history) < 2:
            return 50.0
        
        # 找出连续答题中错误后改正的情况
        recovery_count = 0
        error_count = 0
        
        for i in range(1, len(ability_history)):
            prev = ability_history[i-1]
            curr = ability_history[i]
            
            # 如果前一次错误且同一知识点
            if not prev.get('is_correct') and curr.get('knowledge_point') == prev.get('knowledge_point'):
                error_count += 1
                if curr.get('is_correct'):
                    recovery_count += 1
        
        if error_count == 0:
            return 70.0  # 没有错误，默认较高
        
        recovery_rate = recovery_count / error_count
        score = recovery_rate * 100
        
        return min(100, max(0, score))
    
    def _calculate_learning_resilience(
        self,
        interaction_logs: List[Dict],
        ability_history: List[Dict]
    ) -> float:
        """计算学习抗挫力"""
        # 基于连续错误后继续率、难题停留时间
        
        if not ability_history:
            return 50.0
        
        # 统计连续错误后的继续答题
        consecutive_errors = 0
        max_consecutive = 0
        continued_after_errors = 0
        
        for h in ability_history:
            if not h.get('is_correct'):
                consecutive_errors += 1
                max_consecutive = max(max_consecutive, consecutive_errors)
            else:
                if consecutive_errors >= 2:
                    continued_after_errors += 1
                consecutive_errors = 0
        
        # 抗挫力 = 基于最大连续错误和继续率
        if max_consecutive == 0:
            score = 80.0  # 没有连续错误，默认较高
        else:
            # 连续错误越多但能继续，抗挫力越强
            base_score = 50
            continuation_bonus = continued_after_errors * 10
            persistence_bonus = min(max_consecutive * 5, 30)  # 连续错误奖励，最高30分
            
            score = base_score + continuation_bonus + persistence_bonus
        
        return min(100, max(0, score))
    
    # ==================== 数据获取 ====================

    async def _get_user_interaction_logs(self, db: AsyncSession, user_id: int) -> List[Dict]:
        """从 user_interaction_logs 表查询交互日志"""
        from sqlalchemy import select, desc
        from models.learning_analytics import UserInteractionLog
        try:
            stmt = (
                select(UserInteractionLog)
                .where(UserInteractionLog.user_id == user_id)
                .order_by(desc(UserInteractionLog.created_at))
                .limit(100)
            )
            result = await db.execute(stmt)
            records = result.scalars().all()
            return [
                {
                    'interaction_type': r.interaction_type,
                    'knowledge_points': r.knowledge_points,
                    'sentiment_tag': r.sentiment_tag,
                    'created_at': r.created_at.isoformat() if r.created_at else '',
                }
                for r in records
            ]
        except Exception:
            return []

    async def _get_user_ability_history(self, db: AsyncSession, user_id: int) -> List[Dict]:
        """从 user_ability_history 表查询能力历史"""
        from sqlalchemy import select
        from models.learning_analytics import UserAbilityHistory
        try:
            stmt = (
                select(UserAbilityHistory)
                .where(UserAbilityHistory.user_id == user_id)
                .order_by(UserAbilityHistory.recorded_at.desc())
                .limit(30)
            )
            result = await db.execute(stmt)
            records = result.scalars().all()
            return [
                {
                    'theta': r.theta,
                    'recorded_at': r.recorded_at.isoformat() if r.recorded_at else '',
                }
                for r in records
            ]
        except Exception:
            return []
    
    def _cache_ability(self, user_id: int, ability: SixDimensionalAbility) -> None:
        """缓存能力数据"""
        try:
            key = self.SIX_DIM_ABILITY_KEY.format(user_id=user_id)
            
            data = {
                'user_id': ability.user_id,
                'logical_reasoning': ability.logical_reasoning,
                'calculation_stability': ability.calculation_stability,
                'knowledge_transfer': ability.knowledge_transfer,
                'hint_independence': ability.hint_independence,
                'error_recovery': ability.error_recovery,
                'learning_resilience': ability.learning_resilience,
                'overall_score': ability.overall_score,
                'dominant_dimension': ability.dominant_dimension,
                'calculated_at': ability.calculated_at
            }
            
            self.redis_service.redis_client.hset(key, mapping=data)
            self.redis_service.redis_client.expire(key, 7 * 24 * 60 * 60)  # 7天TTL
            
            # 记录历史
            history_key = self.SIX_DIM_HISTORY_KEY.format(user_id=user_id)
            self.redis_service.redis_client.zadd(
                history_key,
                {json.dumps(data): datetime.now().timestamp()}
            )
            
        except Exception as e:
            logger.error(f"缓存能力数据失败: {e}")
    
    # ==================== 能力分析 ====================
    
    def get_ability_detail(
        self,
        user_id: int,
        dimension: str
    ) -> Optional[AbilityDimensionDetail]:
        """获取单个维度的详细分析"""
        try:
            ability = self.get_cached_ability(user_id)
            if not ability:
                return None
            
            score = getattr(ability, dimension, 0)
            config = self.DIMENSIONS.get(dimension, {})
            
            # 确定等级
            level = self._score_to_level(score)
            
            # 生成描述和建议
            description = self._generate_dimension_description(dimension, score, level)
            suggestions = self._generate_suggestions(dimension, score, level)
            
            return AbilityDimensionDetail(
                dimension_name=dimension,
                dimension_name_cn=config.get('name_cn', dimension),
                score=score,
                level=level,
                description=description,
                suggestions=suggestions,
                trend=('improving' if history and len(history) >= 2 and history[-1].get('theta', 0) > history[0].get('theta', 0) else 'stable')
            )
            
        except Exception as e:
            logger.error(f"获取能力详情失败: {e}")
            return None
    
    def _score_to_level(self, score: float) -> str:
        """分数转等级"""
        if score >= self.LEVEL_THRESHOLDS['excellent']:
            return 'excellent'
        elif score >= self.LEVEL_THRESHOLDS['strong']:
            return 'strong'
        elif score >= self.LEVEL_THRESHOLDS['average']:
            return 'average'
        else:
            return 'weak'
    
    def _generate_dimension_description(
        self,
        dimension: str,
        score: float,
        level: str
    ) -> str:
        """生成维度描述"""
        descriptions = {
            'excellent': '表现优异，这是你的核心优势',
            'strong': '表现良好，继续保持',
            'average': '表现一般，有提升空间',
            'weak': '需要加强训练，建议重点关注'
        }
        return descriptions.get(level, '')
    
    def _generate_suggestions(
        self,
        dimension: str,
        score: float,
        level: str
    ) -> List[str]:
        """生成提升建议"""
        suggestions_map = {
            'logical_reasoning': [
                '多做需要多步推理的复杂题目',
                '练习拆解问题，分步解决',
                '学习常见的数学证明方法'
            ],
            'calculation_stability': [
                '加强基础计算练习',
                '养成检查计算结果的习惯',
                '注意符号和数值的准确性'
            ],
            'knowledge_transfer': [
                '尝试用不同方法解决同一问题',
                '练习跨知识点的综合题',
                '总结解题方法的通用性'
            ],
            'hint_independence': [
                '先独立思考再寻求帮助',
                '尝试自己推导公式',
                '减少对外部提示的依赖'
            ],
            'error_recovery': [
                '认真分析错题原因',
                '定期复习错题',
                '总结易错点，避免重复犯错'
            ],
            'learning_resilience': [
                '遇到困难不轻易放弃',
                '给自己设定挑战目标',
                '保持积极的学习心态'
            ]
        }
        
        return suggestions_map.get(dimension, ['继续练习，提升能力'])
    
    def get_cached_ability(self, user_id: int) -> Optional[SixDimensionalAbility]:
        """获取缓存的能力数据"""
        try:
            key = self.SIX_DIM_ABILITY_KEY.format(user_id=user_id)
            data = self.redis_service.redis_client.hgetall(key)
            
            if not data:
                return None
            
            return SixDimensionalAbility(
                user_id=int(data.get('user_id', user_id)),
                logical_reasoning=float(data.get('logical_reasoning', 0)),
                calculation_stability=float(data.get('calculation_stability', 0)),
                knowledge_transfer=float(data.get('knowledge_transfer', 0)),
                hint_independence=float(data.get('hint_independence', 0)),
                error_recovery=float(data.get('error_recovery', 0)),
                learning_resilience=float(data.get('learning_resilience', 0)),
                overall_score=float(data.get('overall_score', 0)),
                dominant_dimension=data.get('dominant_dimension', ''),
                calculated_at=data.get('calculated_at', datetime.now().isoformat())
            )
            
        except Exception as e:
            logger.error(f"获取缓存能力失败: {e}")
            return None
    
    def get_ability_history(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict]:
        """获取能力历史变化"""
        try:
            key = self.SIX_DIM_HISTORY_KEY.format(user_id=user_id)
            
            # 获取最近N天的记录
            since = datetime.now() - timedelta(days=days)
            records = self.redis_service.redis_client.zrangebyscore(
                key, since.timestamp(), datetime.now().timestamp()
            )
            
            return [json.loads(r) for r in records]
            
        except Exception as e:
            logger.error(f"获取能力历史失败: {e}")
            return []


# 导入json用于缓存
import json

# ==================== 便捷函数 ====================

def get_user_six_dimensional_ability(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取用户六维能力"""
    service = SixDimensionalAbilityService()
    
    # 先尝试获取缓存
    ability = service.get_cached_ability(user_id)
    
    if not ability:
        # 重新计算
        ability = service.calculate_six_dimensional_ability(user_id)
    
    return {
        'user_id': ability.user_id,
        'logical_reasoning': ability.logical_reasoning,
        'calculation_stability': ability.calculation_stability,
        'knowledge_transfer': ability.knowledge_transfer,
        'hint_independence': ability.hint_independence,
        'error_recovery': ability.error_recovery,
        'learning_resilience': ability.learning_resilience,
        'overall_score': ability.overall_score,
        'dominant_dimension': ability.dominant_dimension,
        'dimensions': service.DIMENSIONS
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("六维能力画像服务测试")
    print("=" * 60)
    
    service = SixDimensionalAbilityService()
    
    # 测试能力计算
    print("\n能力计算测试：")
    ability = service.calculate_six_dimensional_ability(1)
    print(f"  用户ID: {ability.user_id}")
    print(f"  逻辑推演力: {ability.logical_reasoning}")
    print(f"  计算稳定性: {ability.calculation_stability}")
    print(f"  知识迁移力: {ability.knowledge_transfer}")
    print(f"  提示独立性: {ability.hint_independence}")
    print(f"  错题自愈力: {ability.error_recovery}")
    print(f"  学习抗挫力: {ability.learning_resilience}")
    print(f"  综合评分: {ability.overall_score}")
    print(f"  主导维度: {ability.dominant_dimension}")
    
    # 测试维度详情
    print("\n维度详情测试：")
    detail = service.get_ability_detail(1, 'logical_reasoning')
    if detail:
        print(f"  {detail.dimension_name_cn}: {detail.score}分 ({detail.level})")
        print(f"  描述: {detail.description}")
        print(f"  建议: {detail.suggestions[:2]}")
    
    print("\n测试完成")
