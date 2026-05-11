"""
六维能力画像V2 API接口
提供实时动态六维能力的HTTP接口

对应行号8: 多维度展示学生非纯知识性的数学认知与行为特质，构建差异化竞争优势

实现文件: backend/api/six_dim_v2.py
"""

import sys
import os

# 添加backend目录到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Query

from services.six_dim_v2_service import (
    SixDimV2Service,
    get_realtime_six_dim_ability,
    get_dynamic_radar_chart
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/six-dim-v2", tags=["六维能力画像V2"])


# ============ 数据模型 ============

class RealtimeAbilityResponse(BaseModel):
    """实时能力响应"""
    success: bool
    user_id: int
    scores: Dict[str, float]
    confidence: float
    timestamp: str
    reliability: str


class DynamicRadarResponse(BaseModel):
    """动态雷达图响应"""
    success: bool
    user_id: int
    current_scores: Dict[str, float]
    previous_scores: Dict[str, float]
    change_rates: Dict[str, float]
    animation_data: List[Dict[str, Any]]
    update_timestamp: str


class InteractionPatternResponse(BaseModel):
    """交互模式响应"""
    success: bool
    user_id: int
    hint_click_rate: float
    skip_rate: float
    avg_time_per_question: float
    consecutive_error_recovery: float
    exploration_depth: float


class DimensionTrendResponse(BaseModel):
    """维度趋势响应"""
    success: bool
    user_id: int
    dimension: str
    hours: int
    trend_data: List[Dict[str, Any]]


# ============ API端点 ============

@router.get("/realtime", response_model=RealtimeAbilityResponse)
async def get_realtime_ability(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取实时六维能力
    
    基于最近交互实时计算的能力值，包含置信度
    """
    try:
        user_id = current_user.id
        
        service = SixDimV2Service()
        ability = service.get_ability_with_confidence(user_id)
        
        return RealtimeAbilityResponse(
            success=True,
            user_id=user_id,
            scores=ability['scores'],
            confidence=ability['confidence'],
            timestamp=ability['timestamp'],
            reliability=ability['reliability']
        )
        
    except Exception as e:
        logger.error(f"获取实时能力失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recalculate")
async def recalculate_ability(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    重新计算实时能力
    
    强制基于最新交互重新计算六维能力
    """
    try:
        user_id = current_user.id
        
        service = SixDimV2Service()
        metrics = service.calculate_realtime_ability(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'message': '实时能力已重新计算',
            'scores': {
                'logical_reasoning': metrics.logical_reasoning,
                'calculation_stability': metrics.calculation_stability,
                'knowledge_transfer': metrics.knowledge_transfer,
                'hint_independence': metrics.hint_independence,
                'error_recovery': metrics.error_recovery,
                'learning_resilience': metrics.learning_resilience
            },
            'confidence': metrics.confidence,
            'timestamp': metrics.timestamp
        }
        
    except Exception as e:
        logger.error(f"重新计算能力失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dynamic-radar", response_model=DynamicRadarResponse)
async def get_dynamic_radar(
    animation_frames: int = Query(10, ge=5, le=30, description="动画帧数"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取动态雷达图数据
    
    支持前端实时动态渲染，包含动画帧数据
    """
    try:
        user_id = current_user.id
        
        service = SixDimV2Service()
        radar_data = service.generate_dynamic_radar_data(user_id, animation_frames)
        
        return DynamicRadarResponse(
            success=True,
            user_id=user_id,
            current_scores=radar_data.current_scores,
            previous_scores=radar_data.previous_scores,
            change_rates=radar_data.change_rates,
            animation_data=radar_data.animation_data,
            update_timestamp=radar_data.update_timestamp
        )
        
    except Exception as e:
        logger.error(f"获取动态雷达图失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interaction-pattern", response_model=InteractionPatternResponse)
async def get_interaction_pattern(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取交互模式分析
    
    分析用户的提示点击率、跳过率等行为模式
    """
    try:
        user_id = current_user.id
        
        service = SixDimV2Service()
        pattern = service.analyze_interaction_pattern(user_id)
        
        return InteractionPatternResponse(
            success=True,
            user_id=user_id,
            hint_click_rate=pattern.hint_click_rate,
            skip_rate=pattern.skip_rate,
            avg_time_per_question=pattern.avg_time_per_question,
            consecutive_error_recovery=pattern.consecutive_error_recovery,
            exploration_depth=pattern.exploration_depth
        )
        
    except Exception as e:
        logger.error(f"获取交互模式失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimension/{dimension}/trend")
async def get_dimension_trend(
    dimension: str,
    hours: int = Query(24, ge=1, le=168, description="小时范围"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取维度趋势
    
    返回指定维度在指定时间范围内的变化趋势
    """
    try:
        user_id = current_user.id
        
        service = SixDimV2Service()
        trend = service.get_dimension_trend(user_id, dimension, hours)
        
        return DimensionTrendResponse(
            success=True,
            user_id=user_id,
            dimension=dimension,
            hours=hours,
            trend_data=trend
        )
        
    except Exception as e:
        logger.error(f"获取维度趋势失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/v1-v2")
async def compare_v1_v2(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    对比V1和V2能力值
    
    展示V1（基础计算）和V2（实时动态）的差异
    """
    try:
        user_id = current_user.id
        
        from services.six_dimensional_ability_service import SixDimensionalAbilityService
        
        # V1能力值
        v1_service = SixDimensionalAbilityService()
        v1_ability = v1_service.get_cached_ability(user_id)
        if not v1_ability:
            v1_ability = v1_service.calculate_six_dimensional_ability(user_id)
        
        # V2能力值
        v2_service = SixDimV2Service()
        v2_metrics = v2_service.calculate_realtime_ability(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'v1_scores': {
                'logical_reasoning': v1_ability.logical_reasoning,
                'calculation_stability': v1_ability.calculation_stability,
                'knowledge_transfer': v1_ability.knowledge_transfer,
                'hint_independence': v1_ability.hint_independence,
                'error_recovery': v1_ability.error_recovery,
                'learning_resilience': v1_ability.learning_resilience
            },
            'v2_scores': {
                'logical_reasoning': v2_metrics.logical_reasoning,
                'calculation_stability': v2_metrics.calculation_stability,
                'knowledge_transfer': v2_metrics.knowledge_transfer,
                'hint_independence': v2_metrics.hint_independence,
                'error_recovery': v2_metrics.error_recovery,
                'learning_resilience': v2_metrics.learning_resilience
            },
            'v2_confidence': v2_metrics.confidence,
            'differences': {
                'logical_reasoning': round(v2_metrics.logical_reasoning - v1_ability.logical_reasoning, 1),
                'calculation_stability': round(v2_metrics.calculation_stability - v1_ability.calculation_stability, 1),
                'knowledge_transfer': round(v2_metrics.knowledge_transfer - v1_ability.knowledge_transfer, 1),
                'hint_independence': round(v2_metrics.hint_independence - v1_ability.hint_independence, 1),
                'error_recovery': round(v2_metrics.error_recovery - v1_ability.error_recovery, 1),
                'learning_resilience': round(v2_metrics.learning_resilience - v1_ability.learning_resilience, 1)
            }
        }
        
    except Exception as e:
        logger.error(f"对比V1V2失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = SixDimV2Service()
        return {
            'status': 'healthy',
            'service': 'six_dim_v2',
            'dimensions': list(service.DIMENSION_WEIGHTS.keys()),
            'features': ['realtime_calculation', 'dynamic_radar', 'interaction_pattern']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
