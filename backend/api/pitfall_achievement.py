"""
雷区与成就双列卡片API接口
提供双列卡片数据展示和管理的HTTP接口

对应行号14: 摒弃传统占比饼图，以"雷区"与"成就"双列卡片展示易错陷阱

实现文件: backend/api/pitfall_achievement.py
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
from fastapi import APIRouter, HTTPException, Depends

from services.pitfall_achievement_service import (
    PitfallAchievementService,
    get_user_dual_column_cards
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/pitfall-achievement", tags=["雷区与成就双列卡片"])


# ============ 数据模型 ============

class PitfallCardResponse(BaseModel):
    """雷区卡片响应"""
    id: str
    title: str
    description: str
    icon: str
    color: str
    frequency: int
    suggestion: str
    related_questions: List[str]


class AchievementCardResponse(BaseModel):
    """成就卡片响应"""
    id: str
    title: str
    description: str
    icon: str
    color: str
    achievement_type: str
    conquered_at: str
    previous_errors: int
    current_mastery: float


class DualColumnResponse(BaseModel):
    """双列卡片响应"""
    success: bool
    user_id: int
    updated_at: str
    left_column: Dict[str, Any]
    right_column: Dict[str, Any]


class PitfallListResponse(BaseModel):
    """雷区列表响应"""
    success: bool
    user_id: int
    count: int
    pitfalls: List[PitfallCardResponse]


class AchievementListResponse(BaseModel):
    """成就列表响应"""
    success: bool
    user_id: int
    count: int
    achievements: List[AchievementCardResponse]


class ErrorTypeLabelsResponse(BaseModel):
    """错误类型标签响应"""
    success: bool
    labels: Dict[str, Any]


# ============ API端点 ============

@router.get("/dual-column", response_model=DualColumnResponse)
async def get_dual_column(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取雷区与成就双列卡片
    
    对应行号14: 摒弃传统占比饼图，以双列卡片展示易错陷阱和已攻克的难关
    
    左列（雷区）：高频易错点
    右列（成就）：已攻克的难关
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = PitfallAchievementService()
        data = service.get_dual_column_for_display(user_id)
        
        return DualColumnResponse(
            success=True,
            user_id=user_id,
            updated_at=data['updated_at'],
            left_column=data['left_column'],
            right_column=data['right_column']
        )
        
    except Exception as e:
        logger.error(f"获取双列卡片失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pitfalls", response_model=PitfallListResponse)
async def get_pitfalls(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取高频雷区列表
    
    模块A：结合系统提取的易错点标签，列出学生最常踩坑的具体行为
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = PitfallAchievementService()
        pitfalls = service.identify_pitfalls(user_id)
        
        return PitfallListResponse(
            success=True,
            user_id=user_id,
            count=len(pitfalls),
            pitfalls=[
                PitfallCardResponse(
                    id=p.id,
                    title=p.title,
                    description=p.description,
                    icon=p.icon,
                    color=p.color,
                    frequency=p.frequency,
                    suggestion=p.suggestion,
                    related_questions=p.related_questions
                )
                for p in pitfalls
            ]
        )
        
    except Exception as e:
        logger.error(f"获取雷区列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/achievements", response_model=AchievementListResponse)
async def get_achievements(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取已攻克的难关列表
    
    模块B：展示曾经在复习队列中频繁做错，但近期掌握度已跨越0.8的题目或知识点
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = PitfallAchievementService()
        achievements = service.identify_achievements(user_id)
        
        return AchievementListResponse(
            success=True,
            user_id=user_id,
            count=len(achievements),
            achievements=[
                AchievementCardResponse(
                    id=a.id,
                    title=a.title,
                    description=a.description,
                    icon=a.icon,
                    color=a.color,
                    achievement_type=a.achievement_type,
                    conquered_at=a.conquered_at,
                    previous_errors=a.previous_errors,
                    current_mastery=a.current_mastery
                )
                for a in achievements
            ]
        )
        
    except Exception as e:
        logger.error(f"获取成就列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/error-types")
async def get_error_type_labels(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取错误类型标签定义"""
    try:
        service = PitfallAchievementService()
        
        return ErrorTypeLabelsResponse(
            success=True,
            labels=service.ERROR_TYPE_LABELS
        )
        
    except Exception as e:
        logger.error(f"获取错误类型标签失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/achievement-types")
async def get_achievement_types(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取成就类型定义"""
    try:
        service = PitfallAchievementService()
        
        return {
            'success': True,
            'types': service.ACHIEVEMENT_TYPES
        }
        
    except Exception as e:
        logger.error(f"获取成就类型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_dual_column(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """刷新双列卡片数据"""
    try:
        user_id = current_user.get('id', 0)
        
        service = PitfallAchievementService()
        data = service.generate_dual_column_data(user_id)
        
        return {
            'success': True,
            'message': '双列卡片数据已刷新',
            'user_id': user_id,
            'pitfall_count': data.pitfall_count,
            'achievement_count': data.achievement_count,
            'updated_at': data.updated_at
        }
        
    except Exception as e:
        logger.error(f"刷新双列卡片失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_summary(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取雷区与成就摘要"""
    try:
        user_id = current_user.get('id', 0)
        
        service = PitfallAchievementService()
        pitfalls = service.identify_pitfalls(user_id)
        achievements = service.identify_achievements(user_id)
        
        # 统计信息
        total_errors = sum(p.frequency for p in pitfalls)
        
        return {
            'success': True,
            'user_id': user_id,
            'pitfalls': {
                'count': len(pitfalls),
                'total_errors': total_errors,
                'top_error_type': pitfalls[0].title if pitfalls else None
            },
            'achievements': {
                'count': len(achievements),
                'total_conquered': sum(a.previous_errors for a in achievements),
                'latest': achievements[0].title if achievements else None
            },
            'motivation': f"你已经攻克了{len(achievements)}个难关，继续加油！还有{len(pitfalls)}个雷区需要关注。"
        }
        
    except Exception as e:
        logger.error(f"获取摘要失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = PitfallAchievementService()
        return {
            'status': 'healthy',
            'service': 'pitfall_achievement',
            'error_types': len(service.ERROR_TYPE_LABELS),
            'achievement_types': len(service.ACHIEVEMENT_TYPES),
            'features': ['pitfall_identification', 'achievement_tracking', 'dual_column_display']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
