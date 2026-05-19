"""
六维能力画像V2服务
支持实时动态渲染的六维能力画像

对应行号8: 多维度展示学生非纯知识性的数学认知与行为特质，构建差异化竞争优势

核心维度（与V1相同，但增强实时性和动态性）：
1. 逻辑推演力 (Logical Reasoning)
2. 计算稳定性 (Calculation Stability)
3. 知识迁移力 (Knowledge Transfer)
4. 提示独立性 (Hint Independence)
5. 错题自愈力 (Error Recovery)
6. 学习抗挫力 (Learning Resilience)

V2增强特性：
- 实时动态计算
- 交互日志实时分析
- Actual Score权重调整
- 动态雷达图渲染支持

实现文件: backend/services/six_dim_v2_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import json

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy.ext.asyncio import AsyncSession

from services.redis_service import RedisService
from services.six_dimensional_ability_service import SixDimensionalAbilityService
from utils.logger import logger


@dataclass
class RealTimeAbilityMetrics:
    """实时能力指标"""
    timestamp: str
    logical_reasoning: float
    calculation_stability: float
    knowledge_transfer: float
    hint_independence: float
    error_recovery: float
    learning_resilience: float
    confidence: float  # 置信度


@dataclass
class DynamicRadarData:
    """动态雷达图数据"""
    user_id: int
    current_scores: Dict[str, float]
    previous_scores: Dict[str, float]
    change_rates: Dict[str, float]  # 变化率
    animation_data: List[Dict[str, Any]]  # 动画帧数据
    update_timestamp: str


@dataclass
class InteractionPattern:
    """交互模式分析"""
    hint_click_rate: float  # 提示点击率
    skip_rate: float  # 跳过率
    avg_time_per_question: float  # 平均每题时间
    consecutive_error_recovery: float  # 连续错误恢复率
    exploration_depth: float  # 探索深度


class SixDimV2Service:
    """
    六维能力画像V2服务
    
    V2增强特性：
    1. 实时动态计算（基于最新交互）
    2. 交互日志实时分析
    3. Actual Score权重调整
    4. 动态雷达图渲染支持
    """
    
    # Redis Key前缀
    REALTIME_ABILITY_KEY = "ai:tutor:sixdim-v2:realtime:{user_id}"
    INTERACTION_PATTERN_KEY = "ai:tutor:sixdim-v2:pattern:{user_id}"
    ANIMATION_FRAMES_KEY = "ai:tutor:sixdim-v2:frames:{user_id}"
    
    # 维度权重（V2调整）
    DIMENSION_WEIGHTS = {
        'logical_reasoning': 1.0,
        'calculation_stability': 1.0,
        'knowledge_transfer': 1.2,  # V2增强
        'hint_independence': 1.1,   # V2增强
        'error_recovery': 1.0,
        'learning_resilience': 1.1  # V2增强
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        self.v1_service = SixDimensionalAbilityService()
        logger.info("六维能力画像V2服务初始化完成")
    
    # ==================== 实时计算（V2核心） ====================
    
    def calculate_realtime_ability(
        self,
        user_id: int,
        recent_interactions: Optional[List[Dict]] = None
    ) -> RealTimeAbilityMetrics:
        """
        实时计算六维能力（V2核心）
        
        基于最近的交互日志实时更新能力值
        """
        try:
            # 获取基础能力值（V1计算）
            base_ability = self.v1_service.get_cached_ability(user_id)
            if not base_ability:
                base_ability = self.v1_service.calculate_six_dimensional_ability(user_id)
            
            # 获取最近交互
            if recent_interactions is None:
                recent_interactions = self._get_recent_interactions(user_id, minutes=30)
            
            # 基于最近交互计算调整因子
            adjustments = self._calculate_adjustments(recent_interactions)
            
            # 应用调整（加权平均：基础70% + 实时30%）
            logical = base_ability.logical_reasoning * 0.7 + adjustments.get('logical', 50) * 0.3
            calculation = base_ability.calculation_stability * 0.7 + adjustments.get('calculation', 50) * 0.3
            transfer = base_ability.knowledge_transfer * 0.7 + adjustments.get('transfer', 50) * 0.3
            independence = base_ability.hint_independence * 0.7 + adjustments.get('independence', 50) * 0.3
            recovery = base_ability.error_recovery * 0.7 + adjustments.get('recovery', 50) * 0.3
            resilience = base_ability.learning_resilience * 0.7 + adjustments.get('resilience', 50) * 0.3
            
            # 计算置信度（基于数据量）
            confidence = min(1.0, len(recent_interactions) / 10) if recent_interactions else 0.5
            
            metrics = RealTimeAbilityMetrics(
                timestamp=datetime.now().isoformat(),
                logical_reasoning=round(logical, 1),
                calculation_stability=round(calculation, 1),
                knowledge_transfer=round(transfer, 1),
                hint_independence=round(independence, 1),
                error_recovery=round(recovery, 1),
                learning_resilience=round(resilience, 1),
                confidence=round(confidence, 2)
            )
            
            # 缓存实时数据
            self._cache_realtime_metrics(user_id, metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"实时计算六维能力失败: {e}")
            return RealTimeAbilityMetrics(
                timestamp=datetime.now().isoformat(),
                logical_reasoning=50.0,
                calculation_stability=50.0,
                knowledge_transfer=50.0,
                hint_independence=50.0,
                error_recovery=50.0,
                learning_resilience=50.0,
                confidence=0.0
            )
    
    def _calculate_adjustments(self, interactions: List[Dict]) -> Dict[str, float]:
        """基于交互计算调整因子"""
        if not interactions:
            return {}
        
        adjustments = {}
        
        # 逻辑推演力调整：基于最近答题正确率
        recent_correct = sum(1 for i in interactions if i.get('is_correct'))
        adjustments['logical'] = (recent_correct / len(interactions)) * 100
        
        # 计算稳定性调整：基于计算错误
        calc_errors = sum(1 for i in interactions if i.get('error_type') == 'calculation')
        adjustments['calculation'] = (1 - calc_errors / len(interactions)) * 100
        
        # 知识迁移力调整：基于跨知识点答题
        topics = set(i.get('knowledge_point') for i in interactions)
        if len(topics) > 1:
            adjustments['transfer'] = 70 + len(topics) * 5  # 跨知识点奖励
        else:
            adjustments['transfer'] = 60
        
        # 提示独立性调整：基于提示使用
        hints_used = sum(i.get('hint_count', 0) for i in interactions)
        avg_hints = hints_used / len(interactions)
        adjustments['independence'] = max(0, 100 - avg_hints * 20)
        
        # 错题自愈力调整：基于错误后改正
        error_recovery_count = 0
        for i in range(1, len(interactions)):
            if not interactions[i-1].get('is_correct') and interactions[i].get('is_correct'):
                error_recovery_count += 1
        adjustments['recovery'] = min(100, 50 + error_recovery_count * 15)
        
        # 学习抗挫力调整：基于连续错误后继续
        consecutive_errors = 0
        max_consecutive = 0
        for i in interactions:
            if not i.get('is_correct'):
                consecutive_errors += 1
                max_consecutive = max(max_consecutive, consecutive_errors)
            else:
                consecutive_errors = 0
        adjustments['resilience'] = min(100, 50 + max_consecutive * 10)
        
        return adjustments
    
    async def _get_recent_interactions(self, db: AsyncSession, user_id: int, minutes: int = 30) -> List[Dict]:
        """从 user_interaction_logs 查询最近交互"""
        from sqlalchemy import select, desc
        from models.learning_analytics import UserInteractionLog
        cutoff = datetime.now() - timedelta(minutes=minutes)
        try:
            stmt = (
                select(UserInteractionLog)
                .where(UserInteractionLog.user_id == user_id)
                .where(UserInteractionLog.created_at >= cutoff)
                .order_by(desc(UserInteractionLog.created_at))
                .limit(50)
            )
            result = await db.execute(stmt)
            records = result.scalars().all()
            return [
                {
                    'interaction_type': r.interaction_type,
                    'knowledge_points': r.knowledge_points,
                    'created_at': r.created_at.isoformat() if r.created_at else '',
                }
                for r in records
            ]
        except Exception:
            return []
    
    def _cache_realtime_metrics(self, user_id: int, metrics: RealTimeAbilityMetrics) -> None:
        """缓存实时指标"""
        try:
            key = self.REALTIME_ABILITY_KEY.format(user_id=user_id)
            data = {
                'timestamp': metrics.timestamp,
                'logical_reasoning': metrics.logical_reasoning,
                'calculation_stability': metrics.calculation_stability,
                'knowledge_transfer': metrics.knowledge_transfer,
                'hint_independence': metrics.hint_independence,
                'error_recovery': metrics.error_recovery,
                'learning_resilience': metrics.learning_resilience,
                'confidence': metrics.confidence
            }
            self.redis_service.redis_client.hset(key, mapping=data)
            self.redis_service.redis_client.expire(key, 3600)  # 1小时TTL
        except Exception as e:
            logger.error(f"缓存实时指标失败: {e}")
    
    # ==================== 交互模式分析（V2增强） ====================
    
    def analyze_interaction_pattern(self, user_id: int) -> InteractionPattern:
        """
        分析用户交互模式（V2增强）
        
        从交互日志中分析行为模式
        """
        try:
            # 获取最近100条交互记录
            interactions = self._get_recent_interactions(user_id, minutes=1440)  # 24小时
            
            if not interactions:
                return InteractionPattern(
                    hint_click_rate=0.5,
                    skip_rate=0.1,
                    avg_time_per_question=60.0,
                    consecutive_error_recovery=0.5,
                    exploration_depth=0.5
                )
            
            # 提示点击率
            hint_clicks = sum(1 for i in interactions if i.get('hint_count', 0) > 0)
            hint_click_rate = hint_clicks / len(interactions)
            
            # 跳过率
            skips = sum(1 for i in interactions if i.get('skipped', False))
            skip_rate = skips / len(interactions)
            
            # 平均每题时间
            avg_time = sum(i.get('time_spent', 60) for i in interactions) / len(interactions)
            
            # 连续错误恢复率
            recovery_count = 0
            error_sequences = 0
            for i in range(1, len(interactions)):
                if not interactions[i-1].get('is_correct'):
                    error_sequences += 1
                    if interactions[i].get('is_correct'):
                        recovery_count += 1
            
            recovery_rate = recovery_count / error_sequences if error_sequences > 0 else 0.5
            
            # 探索深度（不同知识点数量）
            topics = len(set(i.get('knowledge_point') for i in interactions))
            exploration_depth = min(1.0, topics / 10)
            
            pattern = InteractionPattern(
                hint_click_rate=round(hint_click_rate, 2),
                skip_rate=round(skip_rate, 2),
                avg_time_per_question=round(avg_time, 1),
                consecutive_error_recovery=round(recovery_rate, 2),
                exploration_depth=round(exploration_depth, 2)
            )
            
            # 缓存模式
            self._cache_interaction_pattern(user_id, pattern)
            
            return pattern
            
        except Exception as e:
            logger.error(f"分析交互模式失败: {e}")
            return InteractionPattern(
                hint_click_rate=0.5,
                skip_rate=0.1,
                avg_time_per_question=60.0,
                consecutive_error_recovery=0.5,
                exploration_depth=0.5
            )
    
    def _cache_interaction_pattern(self, user_id: int, pattern: InteractionPattern) -> None:
        """缓存交互模式"""
        try:
            key = self.INTERACTION_PATTERN_KEY.format(user_id=user_id)
            data = {
                'hint_click_rate': pattern.hint_click_rate,
                'skip_rate': pattern.skip_rate,
                'avg_time_per_question': pattern.avg_time_per_question,
                'consecutive_error_recovery': pattern.consecutive_error_recovery,
                'exploration_depth': pattern.exploration_depth,
                'updated_at': datetime.now().isoformat()
            }
            self.redis_service.redis_client.hset(key, mapping=data)
            self.redis_service.redis_client.expire(key, 3600)
        except Exception as e:
            logger.error(f"缓存交互模式失败: {e}")
    
    # ==================== 动态雷达图（V2核心） ====================
    
    def generate_dynamic_radar_data(
        self,
        user_id: int,
        animation_frames: int = 10
    ) -> DynamicRadarData:
        """
        生成动态雷达图数据（V2核心）
        
        支持前端实时动态渲染
        """
        try:
            # 获取当前能力值
            current_metrics = self.calculate_realtime_ability(user_id)
            current_scores = {
                'logical_reasoning': current_metrics.logical_reasoning,
                'calculation_stability': current_metrics.calculation_stability,
                'knowledge_transfer': current_metrics.knowledge_transfer,
                'hint_independence': current_metrics.hint_independence,
                'error_recovery': current_metrics.error_recovery,
                'learning_resilience': current_metrics.learning_resilience
            }
            
            # 获取历史数据（用于计算变化率）
            previous_scores = self._get_previous_scores(user_id)
            
            # 计算变化率
            change_rates = {}
            for dim in current_scores:
                if dim in previous_scores and previous_scores[dim] > 0:
                    change = (current_scores[dim] - previous_scores[dim]) / previous_scores[dim]
                    change_rates[dim] = round(change * 100, 1)
                else:
                    change_rates[dim] = 0.0
            
            # 生成动画帧数据
            animation_data = self._generate_animation_frames(
                previous_scores, current_scores, animation_frames
            )
            
            radar_data = DynamicRadarData(
                user_id=user_id,
                current_scores=current_scores,
                previous_scores=previous_scores,
                change_rates=change_rates,
                animation_data=animation_data,
                update_timestamp=datetime.now().isoformat()
            )
            
            # 缓存动画数据
            self._cache_animation_frames(user_id, animation_data)
            
            return radar_data
            
        except Exception as e:
            logger.error(f"生成动态雷达图数据失败: {e}")
            return DynamicRadarData(
                user_id=user_id,
                current_scores={},
                previous_scores={},
                change_rates={},
                animation_data=[],
                update_timestamp=datetime.now().isoformat()
            )
    
    def _get_previous_scores(self, user_id: int) -> Dict[str, float]:
        """获取历史分数"""
        try:
            # 从缓存获取上一次的数据
            key = self.REALTIME_ABILITY_KEY.format(user_id=user_id)
            data = self.redis_service.redis_client.hgetall(key)
            
            if data:
                return {
                    'logical_reasoning': float(data.get('logical_reasoning', 50)),
                    'calculation_stability': float(data.get('calculation_stability', 50)),
                    'knowledge_transfer': float(data.get('knowledge_transfer', 50)),
                    'hint_independence': float(data.get('hint_independence', 50)),
                    'error_recovery': float(data.get('error_recovery', 50)),
                    'learning_resilience': float(data.get('learning_resilience', 50))
                }
            
            return {dim: 50.0 for dim in self.DIMENSION_WEIGHTS.keys()}
            
        except Exception as e:
            logger.error(f"获取历史分数失败: {e}")
            return {dim: 50.0 for dim in self.DIMENSION_WEIGHTS.keys()}
    
    def _generate_animation_frames(
        self,
        start_scores: Dict[str, float],
        end_scores: Dict[str, float],
        frames: int
    ) -> List[Dict[str, Any]]:
        """生成动画帧数据"""
        animation_frames = []
        
        for i in range(frames + 1):
            progress = i / frames
            frame_scores = {}
            
            for dim in end_scores:
                start = start_scores.get(dim, 50)
                end = end_scores[dim]
                # 缓动函数
                eased_progress = self._ease_in_out_cubic(progress)
                frame_scores[dim] = round(start + (end - start) * eased_progress, 1)
            
            animation_frames.append({
                'frame': i,
                'progress': round(progress * 100, 1),
                'scores': frame_scores
            })
        
        return animation_frames
    
    def _ease_in_out_cubic(self, t: float) -> float:
        """缓动函数"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2
    
    def _cache_animation_frames(self, user_id: int, frames: List[Dict]) -> None:
        """缓存动画帧"""
        try:
            key = self.ANIMATION_FRAMES_KEY.format(user_id=user_id)
            self.redis_service.redis_client.setex(
                key,
                3600,  # 1小时TTL
                json.dumps(frames)
            )
        except Exception as e:
            logger.error(f"缓存动画帧失败: {e}")
    
    # ==================== V2增强API ====================
    
    def get_ability_with_confidence(self, user_id: int) -> Dict[str, Any]:
        """获取带置信度的能力值"""
        metrics = self.calculate_realtime_ability(user_id)
        
        return {
            'scores': {
                'logical_reasoning': metrics.logical_reasoning,
                'calculation_stability': metrics.calculation_stability,
                'knowledge_transfer': metrics.knowledge_transfer,
                'hint_independence': metrics.hint_independence,
                'error_recovery': metrics.error_recovery,
                'learning_resilience': metrics.learning_resilience
            },
            'confidence': metrics.confidence,
            'timestamp': metrics.timestamp,
            'reliability': 'high' if metrics.confidence > 0.8 else 'medium' if metrics.confidence > 0.5 else 'low'
        }
    
    async def get_dimension_trend(self, db: AsyncSession, user_id: int, dimension: str, hours: int = 24) -> List[Dict]:
        """从 user_ability_history 查询维度趋势"""
        from sqlalchemy import select
        from models.learning_analytics import UserAbilityHistory
        cutoff = datetime.now() - timedelta(hours=hours)
        try:
            stmt = (
                select(UserAbilityHistory)
                .where(UserAbilityHistory.user_id == user_id)
                .where(UserAbilityHistory.recorded_at >= cutoff)
                .order_by(UserAbilityHistory.recorded_at)
            )
            result = await db.execute(stmt)
            records = result.scalars().all()
            return [
                {
                    'date': r.recorded_at.isoformat() if r.recorded_at else '',
                    'theta': r.theta,
                }
                for r in records
            ]
        except Exception:
            return []


# ==================== 便捷函数 ====================

def get_realtime_six_dim_ability(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取实时六维能力"""
    service = SixDimV2Service()
    return service.get_ability_with_confidence(user_id)


def get_dynamic_radar_chart(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取动态雷达图"""
    service = SixDimV2Service()
    radar_data = service.generate_dynamic_radar_data(user_id)
    
    return {
        'user_id': radar_data.user_id,
        'current_scores': radar_data.current_scores,
        'change_rates': radar_data.change_rates,
        'animation_frames': radar_data.animation_data,
        'update_timestamp': radar_data.update_timestamp
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("六维能力画像V2服务测试")
    print("=" * 60)
    
    service = SixDimV2Service()
    
    # 测试实时计算
    print("\n实时能力计算测试：")
    metrics = service.calculate_realtime_ability(1)
    print(f"  逻辑推演力: {metrics.logical_reasoning}")
    print(f"  置信度: {metrics.confidence}")
    
    # 测试交互模式
    print("\n交互模式分析测试：")
    pattern = service.analyze_interaction_pattern(1)
    print(f"  提示点击率: {pattern.hint_click_rate}")
    print(f"  跳过率: {pattern.skip_rate}")
    
    # 测试动态雷达图
    print("\n动态雷达图测试：")
    radar = service.generate_dynamic_radar_data(1, animation_frames=5)
    print(f"  当前分数: {radar.current_scores}")
    print(f"  变化率: {radar.change_rates}")
    print(f"  动画帧数: {len(radar.animation_data)}")
    
    print("\n测试完成")
