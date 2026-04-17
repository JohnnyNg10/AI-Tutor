"""
学习习惯成就徽章API接口
提供徽章检测和查询的HTTP接口

对应行号23/28: 弱化分数激励，强化对学生优良"学习习惯与抗压行为"的成就认可

实现文件: backend/api/learning_habit_badges.py
"""

import sys
import os

# 添加backend目录到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from services.learning_habit_badge_service import (
    LearningHabitBadgeService,
    track_learning_behavior,
    check_and_award_badges
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/learning-badges", tags=["学习习惯成就徽章"])


# ============ 数据模型 ============

class TrackBehaviorRequest(BaseModel):
    """追踪行为请求"""
    behavior_data: Dict[str, Any] = Field(..., description="行为数据")


class BadgeResponse(BaseModel):
    """徽章响应"""
    badge_id: str
    name: str
    description: str
    icon: str
    color: str
    category: str
    unlocked_at: str
    is_new: bool


class UserBadgesResponse(BaseModel):
    """用户徽章响应"""
    success: bool
    user_id: int
    earned_count: int
    total_count: int
    earned_badges: List[Dict[str, Any]]
    in_progress: List[Dict[str, Any]]


class NewBadgesResponse(BaseModel):
    """新徽章响应"""
    success: bool
    user_id: int
    new_badges_count: int
    new_badges: List[BadgeResponse]


# ============ API端点 ============

@router.post("/track-behavior")
async def track_behavior(
    request: TrackBehaviorRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    追踪学习行为
    
    记录用户的学习行为用于徽章检测
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = LearningHabitBadgeService()
        service.track_behavior(user_id, request.behavior_data)
        
        return {
            'success': True,
            'user_id': user_id,
            'message': '行为已记录'
        }
        
    except Exception as e:
        logger.error(f"追踪行为失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-new")
async def check_new_badges(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查并颁发新徽章
    
    根据用户行为检测是否满足徽章条件
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = LearningHabitBadgeService()
        new_badges = service.detect_and_award_badges(user_id)
        
        return NewBadgesResponse(
            success=True,
            user_id=user_id,
            new_badges_count=len(new_badges),
            new_badges=[
                BadgeResponse(
                    badge_id=b.badge_id,
                    name=b.name,
                    description=b.description,
                    icon=b.icon,
                    color=b.color,
                    category=b.category,
                    unlocked_at=b.unlocked_at,
                    is_new=b.is_new
                )
                for b in new_badges
            ]
        )
        
    except Exception as e:
        logger.error(f"检查徽章失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-badges", response_model=UserBadgesResponse)
async def get_my_badges(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取我的徽章
    
    返回已获得和进行中的徽章
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = LearningHabitBadgeService()
        badges = service.get_user_badges(user_id)
        
        return UserBadgesResponse(
            success=True,
            user_id=user_id,
            earned_count=badges['earned_count'],
            total_count=badges['total_count'],
            earned_badges=badges['earned_badges'],
            in_progress=badges['in_progress']
        )
        
    except Exception as e:
        logger.error(f"获取徽章失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions")
async def get_badge_definitions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取所有徽章定义"""
    try:
        service = LearningHabitBadgeService()
        
        return {
            'success': True,
            'total_count': len(service.BADGES),
            'badges': [
                {
                    'badge_id': bid,
                    'name': b['name'],
                    'description': b['description'],
                    'icon': b['icon'],
                    'color': b['color'],
                    'category': b['category'],
                    'condition': b['condition']
                }
                for bid, b in service.BADGES.items()
            ]
        }
        
    except Exception as e:
        logger.error(f"获取徽章定义失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_badges_summary(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取徽章摘要"""
    try:
        user_id = current_user.get('id', 0)
        
        service = LearningHabitBadgeService()
        badges = service.get_user_badges(user_id)
        
        # 按类别统计
        categories = {}
        for badge in badges['earned_badges']:
            cat = badge['category']
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1
        
        return {
            'success': True,
            'user_id': user_id,
            'summary': {
                'earned': badges['earned_count'],
                'total': badges['total_count'],
                'completion_rate': round(badges['earned_count'] / badges['total_count'] * 100, 1) if badges['total_count'] > 0 else 0,
                'by_category': categories
            },
            'motivation': f"你已经获得了{badges['earned_count']}个徽章，继续保持良好的学习习惯！"
        }
        
    except Exception as e:
        logger.error(f"获取徽章摘要失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = LearningHabitBadgeService()
        return {
            'status': 'healthy',
            'service': 'learning_habit_badges',
            'total_badges': len(service.BADGES),
            'categories': list(set(b['category'] for b in service.BADGES.values())),
            'features': ['behavior_tracking', 'badge_detection', 'progress_tracking']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
