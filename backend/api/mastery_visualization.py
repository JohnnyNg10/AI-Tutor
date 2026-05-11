"""
掌握度可视化API接口
提供掌握度可视化组件所需的数据接口

对应需求1: 将BKT算法生成的掌握度P(L)转化为直观的色彩和水位动效

实现文件：backend/api/mastery_visualization.py
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

from sqlalchemy.ext.asyncio import AsyncSession
from database.db import get_db
from services.mastery_visualization_service import (
    MasteryVisualizationService,
    get_user_mastery_visualization
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/mastery", tags=["掌握度可视化"])


# ============ 数据模型 ============

class MasteryLevelResponse(BaseModel):
    """掌握度等级响应"""
    kp_id: str
    kp_name: str
    p_known: float
    level: str
    color: str
    percentage: int


class TopicProgressResponse(BaseModel):
    """专题进度响应"""
    topic: str
    progress: float
    progress_text: str
    status: str
    mastered: int
    total: int


class MasteryVisualizationResponse(BaseModel):
    """掌握度可视化完整响应"""
    success: bool
    user_id: int
    global_mastery: float
    water_level: int
    ring_color: str
    status_text: str
    statistics: Dict[str, int]
    mastery_levels: List[MasteryLevelResponse]
    topic_progress: List[TopicProgressResponse]


class AbilityCurveResponse(BaseModel):
    """能力曲线响应"""
    success: bool
    user_id: int
    days: int
    data: List[Dict[str, Any]]


class ColorMappingResponse(BaseModel):
    """颜色映射响应"""
    success: bool
    thresholds: Dict[str, float]
    colors: Dict[str, str]
    status_texts: Dict[str, str]


class RingComponentResponse(BaseModel):
    """圆环组件响应"""
    success: bool
    user_id: int
    percentage: int  # 0-100
    color: str  # 十六进制颜色
    stroke_color: str  # 圆环描边颜色
    fill_color: str  # 圆环填充颜色
    status_text: str
    animation_duration: int  # 动画时长(ms)


class WaterDropComponentResponse(BaseModel):
    """水滴组件响应"""
    success: bool
    user_id: int
    water_level: int  # 0-100 水位高度
    wave_height: int  # 波浪高度
    color: str  # 水体颜色
    bg_color: str  # 背景颜色
    status_text: str
    animation_enabled: bool


class ComponentConfigResponse(BaseModel):
    """组件配置响应"""
    success: bool
    component_type: str  # ring / water_drop
    config: Dict[str, Any]


# ============ API端点 ============

@router.get("/visualization", response_model=MasteryVisualizationResponse)
async def get_mastery_visualization(
    topics: Optional[List[str]] = Query(None, description="专题列表"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取掌握度可视化数据
    
    将BKT算法生成的掌握度P(L)转化为前端可视化组件所需的数据格式：
    - 水位高度（0-100）
    - 圆环颜色（红/黄/绿）
    - 掌握度等级（weak/learning/mastered）
    - 专题进度
    """
    try:
        user_id = current_user.id
        logger.info(f"获取掌握度可视化数据: 用户={user_id}")
        
        viz_data = get_user_mastery_visualization(user_id, topics)
        
        return MasteryVisualizationResponse(
            success=True,
            **viz_data
        )
        
    except Exception as e:
        logger.error(f"获取掌握度可视化数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/level/{knowledge_point_id}")
async def get_knowledge_point_mastery(
    knowledge_point_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取单个知识点的掌握度详情
    """
    try:
        user_id = current_user.id
        
        service = MasteryVisualizationService()
        mastery_data = service.get_user_mastery_from_redis(user_id)
        
        p_known = mastery_data.get(knowledge_point_id, 0.0)
        
        return {
            'success': True,
            'user_id': user_id,
            'knowledge_point_id': knowledge_point_id,
            'p_known': p_known,
            'level': service.p_known_to_level(p_known),
            'color': service.p_known_to_color(p_known),
            'percentage': service.p_known_to_percentage(p_known),
            'status_text': service.get_status_text(p_known)
        }
        
    except Exception as e:
        logger.error(f"获取知识点掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topic-progress/{topic}")
async def get_topic_progress(
    topic: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取专题进度
    
    计算公式：进度百分比 = (P(L) >= 0.8的知识点数量) / (该专题总知识点数量)
    """
    try:
        user_id = current_user.id
        logger.info(f"获取专题进度: 用户={user_id}, 专题={topic}")
        
        service = MasteryVisualizationService()
        mastery_data = service.get_user_mastery_from_redis(user_id)
        
        progress = service.calculate_topic_progress(user_id, topic, mastery_data)
        
        return {
            'success': True,
            'user_id': user_id,
            'topic': progress.topic,
            'progress_percentage': progress.progress_percentage,
            'progress_text': progress.progress_text,
            'status': progress.status,
            'statistics': {
                'total_nodes': progress.total_nodes,
                'mastered_nodes': progress.mastered_nodes,
                'learning_nodes': progress.learning_nodes,
                'weak_nodes': progress.weak_nodes,
                'locked_nodes': progress.locked_nodes
            }
        }
        
    except Exception as e:
        logger.error(f"获取专题进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ability-curve", response_model=AbilityCurveResponse)
async def get_ability_curve(
    days: int = Query(30, ge=7, le=90, description="天数范围"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取能力曲线数据（真实DB查询）"""
    try:
        user_id = current_user.id
        service = MasteryVisualizationService()
        curve_data = await service.get_ability_curve_data(db, user_id, days)
        return AbilityCurveResponse(success=True, user_id=user_id, days=days, data=curve_data)
    except Exception as e:
        logger.error(f"获取能力曲线失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/color-mapping", response_model=ColorMappingResponse)
async def get_color_mapping():
    """
    获取颜色映射配置
    
    返回掌握度到颜色的映射规则，供前端使用
    """
    service = MasteryVisualizationService()
    
    return ColorMappingResponse(
        success=True,
        thresholds={
            'weak': service.MASTERY_THRESHOLD_WEAK,
            'learning': service.MASTERY_THRESHOLD_LEARNING
        },
        colors=service.COLOR_MAP,
        status_texts=service.STATUS_TEXT_MAP
    )


@router.get("/component/ring", response_model=RingComponentResponse)
async def get_ring_component(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取圆环组件数据
    
    对应行号2: 弃用传统进度条，采用圆环组件展示掌握度
    
    颜色联动硬指标：
    - P(L) < 0.5: 红色（危险区）#FF4D4F
    - 0.5 <= P(L) < 0.8: 黄色（过渡区）#FAAD14
    - P(L) >= 0.8: 绿色（掌握区）#52C41A
    """
    try:
        user_id = current_user.id
        
        service = MasteryVisualizationService()
        mastery_data = service.get_user_mastery_from_redis(user_id)
        
        # 计算全局掌握度
        global_mastery = sum(mastery_data.values()) / len(mastery_data) if mastery_data else 0.0
        percentage = service.p_known_to_percentage(global_mastery)
        color = service.p_known_to_color(global_mastery)
        status_text = service.get_status_text(global_mastery)
        
        return RingComponentResponse(
            success=True,
            user_id=user_id,
            percentage=percentage,
            color=color,
            stroke_color=color,
            fill_color=color + "20",  # 添加透明度
            status_text=status_text,
            animation_duration=1000  # 1秒动画
        )
        
    except Exception as e:
        logger.error(f"获取圆环组件数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/component/water-drop", response_model=WaterDropComponentResponse)
async def get_water_drop_component(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取水滴组件数据
    
    对应行号2: 弃用传统进度条，采用水滴组件展示掌握度
    
    水位动效：
    - 水位高度 = P(L) * 100
    - 波浪高度根据掌握度动态调整
    """
    try:
        user_id = current_user.id
        
        service = MasteryVisualizationService()
        mastery_data = service.get_user_mastery_from_redis(user_id)
        
        # 计算全局掌握度
        global_mastery = sum(mastery_data.values()) / len(mastery_data) if mastery_data else 0.0
        water_level = service.calculate_water_level(global_mastery)
        color = service.p_known_to_color(global_mastery)
        status_text = service.get_status_text(global_mastery)
        
        # 波浪高度：掌握度越高，波浪越平缓
        wave_height = max(5, 20 - int(global_mastery * 15))
        
        return WaterDropComponentResponse(
            success=True,
            user_id=user_id,
            water_level=water_level,
            wave_height=wave_height,
            color=color,
            bg_color="#F0F0F0",
            status_text=status_text,
            animation_enabled=True
        )
        
    except Exception as e:
        logger.error(f"获取水滴组件数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/component/config")
async def get_component_config(
    component_type: str = Query("ring", description="组件类型: ring / water_drop"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取组件配置
    
    返回前端可视化组件的完整配置参数
    """
    try:
        user_id = current_user.id
        
        service = MasteryVisualizationService()
        mastery_data = service.get_user_mastery_from_redis(user_id)
        global_mastery = sum(mastery_data.values()) / len(mastery_data) if mastery_data else 0.0
        
        if component_type == "ring":
            config = {
                "type": "ring",
                "percentage": service.p_known_to_percentage(global_mastery),
                "color": service.p_known_to_color(global_mastery),
                "stroke_width": 10,
                "radius": 60,
                "animation_duration": 1000,
                "show_text": True,
                "text_format": "{percentage}%"
            }
        elif component_type == "water_drop":
            config = {
                "type": "water_drop",
                "water_level": service.calculate_water_level(global_mastery),
                "color": service.p_known_to_color(global_mastery),
                "wave_amplitude": max(5, 20 - int(global_mastery * 15)),
                "wave_frequency": 0.02,
                "animation_speed": 2000,
                "show_bubbles": global_mastery > 0.5
            }
        else:
            raise HTTPException(status_code=400, detail="不支持的组件类型")
        
        return ComponentConfigResponse(
            success=True,
            component_type=component_type,
            config=config
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取组件配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_mastery_summary(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取掌握度摘要（用于首页展示）
    """
    try:
        user_id = current_user.id
        
        viz_data = get_user_mastery_visualization(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'global_mastery': viz_data['global_mastery'],
            'water_level': viz_data['water_level'],
            'ring_color': viz_data['ring_color'],
            'status_text': viz_data['status_text'],
            'quick_stats': {
                'total': viz_data['statistics']['total'],
                'mastered': viz_data['statistics']['mastered'],
                'mastered_percentage': round(
                    viz_data['statistics']['mastered'] / viz_data['statistics']['total'] * 100, 1
                ) if viz_data['statistics']['total'] > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"获取掌握度摘要失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = MasteryVisualizationService()
        return {
            'status': 'healthy',
            'service': 'mastery_visualization',
            'color_map': service.COLOR_MAP
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
