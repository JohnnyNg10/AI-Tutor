"""
六维能力画像API接口
提供六维能力计算和分析的HTTP接口

对应行号4: 多维度展示学生数学思维深度与认知特质，而非单纯知识点

实现文件: backend/api/six_dimensional_ability.py
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

from services.six_dimensional_ability_service import (
    SixDimensionalAbilityService,
    get_user_six_dimensional_ability
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/six-dim-ability", tags=["六维能力画像"])


# ============ 数据模型 ============

class SixDimensionalAbilityResponse(BaseModel):
    """六维能力响应"""
    success: bool
    user_id: int
    logical_reasoning: float
    calculation_stability: float
    knowledge_transfer: float
    hint_independence: float
    error_recovery: float
    learning_resilience: float
    overall_score: float
    dominant_dimension: str
    dimensions: Dict[str, Any]


class DimensionDetailResponse(BaseModel):
    """维度详情响应"""
    success: bool
    dimension_name: str
    dimension_name_cn: str
    score: float
    level: str
    description: str
    suggestions: List[str]
    trend: str


class RadarChartResponse(BaseModel):
    """雷达图响应"""
    success: bool
    user_id: int
    labels: List[str]
    data: List[float]
    background_color: str
    border_color: str


class AbilityHistoryResponse(BaseModel):
    """能力历史响应"""
    success: bool
    user_id: int
    days: int
    history: List[Dict[str, Any]]


class ComparisonResponse(BaseModel):
    """对比响应"""
    success: bool
    user_id: int
    compare_with: str
    user_scores: Dict[str, float]
    compare_scores: Dict[str, float]
    differences: Dict[str, float]


# ============ API端点 ============

@router.get("/profile", response_model=SixDimensionalAbilityResponse)
async def get_ability_profile(
    force_recalculate: bool = Query(False, description="强制重新计算"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取六维能力画像
    
    返回用户的六维能力分数和综合评估
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SixDimensionalAbilityService()
        
        if force_recalculate:
            ability = service.calculate_six_dimensional_ability(user_id)
        else:
            ability = service.get_cached_ability(user_id)
            if not ability:
                ability = service.calculate_six_dimensional_ability(user_id)
        
        return SixDimensionalAbilityResponse(
            success=True,
            user_id=ability.user_id,
            logical_reasoning=ability.logical_reasoning,
            calculation_stability=ability.calculation_stability,
            knowledge_transfer=ability.knowledge_transfer,
            hint_independence=ability.hint_independence,
            error_recovery=ability.error_recovery,
            learning_resilience=ability.learning_resilience,
            overall_score=ability.overall_score,
            dominant_dimension=ability.dominant_dimension,
            dimensions=service.DIMENSIONS
        )
        
    except Exception as e:
        logger.error(f"获取六维能力画像失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate")
async def calculate_ability(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    计算六维能力
    
    从交互日志和能力历史中重新计算六维能力
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SixDimensionalAbilityService()
        ability = service.calculate_six_dimensional_ability(user_id)
        
        return {
            'success': True,
            'user_id': ability.user_id,
            'message': '六维能力计算完成',
            'logical_reasoning': ability.logical_reasoning,
            'calculation_stability': ability.calculation_stability,
            'knowledge_transfer': ability.knowledge_transfer,
            'hint_independence': ability.hint_independence,
            'error_recovery': ability.error_recovery,
            'learning_resilience': ability.learning_resilience,
            'overall_score': ability.overall_score,
            'dominant_dimension': ability.dominant_dimension
        }
        
    except Exception as e:
        logger.error(f"计算六维能力失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimension/{dimension}", response_model=DimensionDetailResponse)
async def get_dimension_detail(
    dimension: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取单个维度详情
    
    返回指定维度的详细分析、描述和提升建议
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SixDimensionalAbilityService()
        detail = service.get_ability_detail(user_id, dimension)
        
        if not detail:
            raise HTTPException(status_code=404, detail="维度不存在或数据未计算")
        
        return DimensionDetailResponse(
            success=True,
            dimension_name=detail.dimension_name,
            dimension_name_cn=detail.dimension_name_cn,
            score=detail.score,
            level=detail.level,
            description=detail.description,
            suggestions=detail.suggestions,
            trend=detail.trend
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取维度详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar-chart", response_model=RadarChartResponse)
async def get_radar_chart_data(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取雷达图数据
    
    返回前端雷达图组件所需的数据格式
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SixDimensionalAbilityService()
        ability = service.get_cached_ability(user_id)
        
        if not ability:
            ability = service.calculate_six_dimensional_ability(user_id)
        
        # 雷达图数据
        labels = [
            "逻辑推演力",
            "计算稳定性",
            "知识迁移力",
            "提示独立性",
            "错题自愈力",
            "学习抗挫力"
        ]
        
        data = [
            ability.logical_reasoning,
            ability.calculation_stability,
            ability.knowledge_transfer,
            ability.hint_independence,
            ability.error_recovery,
            ability.learning_resilience
        ]
        
        # 根据综合评分确定颜色
        if ability.overall_score >= 80:
            bg_color = "rgba(82, 196, 26, 0.2)"
            border_color = "#52C41A"
        elif ability.overall_score >= 60:
            bg_color = "rgba(250, 173, 20, 0.2)"
            border_color = "#FAAD14"
        else:
            bg_color = "rgba(255, 77, 79, 0.2)"
            border_color = "#FF4D4F"
        
        return RadarChartResponse(
            success=True,
            user_id=user_id,
            labels=labels,
            data=data,
            background_color=bg_color,
            border_color=border_color
        )
        
    except Exception as e:
        logger.error(f"获取雷达图数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=AbilityHistoryResponse)
async def get_ability_history(
    days: int = Query(30, ge=7, le=90, description="天数范围"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取能力历史变化
    
    返回指定天数内的六维能力变化历史
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SixDimensionalAbilityService()
        history = service.get_ability_history(user_id, days)
        
        return AbilityHistoryResponse(
            success=True,
            user_id=user_id,
            days=days,
            history=history
        )
        
    except Exception as e:
        logger.error(f"获取能力历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison")
async def compare_ability(
    compare_with: str = Query("average", description="对比对象: average/peers/excellent"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    能力对比
    
    与平均水平、同龄人或优秀用户对比
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SixDimensionalAbilityService()
        ability = service.get_cached_ability(user_id)
        
        if not ability:
            ability = service.calculate_six_dimensional_ability(user_id)
        
        user_scores = {
            'logical_reasoning': ability.logical_reasoning,
            'calculation_stability': ability.calculation_stability,
            'knowledge_transfer': ability.knowledge_transfer,
            'hint_independence': ability.hint_independence,
            'error_recovery': ability.error_recovery,
            'learning_resilience': ability.learning_resilience
        }
        
        # 模拟对比数据
        if compare_with == "average":
            compare_scores = {
                'logical_reasoning': 60.0,
                'calculation_stability': 65.0,
                'knowledge_transfer': 55.0,
                'hint_independence': 50.0,
                'error_recovery': 58.0,
                'learning_resilience': 62.0
            }
        elif compare_with == "excellent":
            compare_scores = {
                'logical_reasoning': 85.0,
                'calculation_stability': 88.0,
                'knowledge_transfer': 82.0,
                'hint_independence': 80.0,
                'error_recovery': 85.0,
                'learning_resilience': 87.0
            }
        else:
            compare_scores = {
                'logical_reasoning': 65.0,
                'calculation_stability': 68.0,
                'knowledge_transfer': 62.0,
                'hint_independence': 60.0,
                'error_recovery': 64.0,
                'learning_resilience': 66.0
            }
        
        # 计算差异
        differences = {
            k: round(user_scores[k] - compare_scores[k], 1)
            for k in user_scores.keys()
        }
        
        return ComparisonResponse(
            success=True,
            user_id=user_id,
            compare_with=compare_with,
            user_scores=user_scores,
            compare_scores=compare_scores,
            differences=differences
        )
        
    except Exception as e:
        logger.error(f"能力对比失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimensions")
async def get_dimensions_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取六维能力维度说明
    
    返回所有维度的详细说明和指标
    """
    try:
        service = SixDimensionalAbilityService()
        
        return {
            'success': True,
            'dimensions': service.DIMENSIONS,
            'level_thresholds': service.LEVEL_THRESHOLDS
        }
        
    except Exception as e:
        logger.error(f"获取维度信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = SixDimensionalAbilityService()
        return {
            'status': 'healthy',
            'service': 'six_dimensional_ability',
            'dimensions': list(service.DIMENSIONS.keys()),
            'level_thresholds': service.LEVEL_THRESHOLDS
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
