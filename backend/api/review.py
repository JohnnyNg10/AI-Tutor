"""
错题复习API接口
提供错题复习游戏化和变式题推荐的HTTP接口

对应需求：
- 需求11: 将传统的错题复习清单游戏化
- 需求12: 复习错题时抽取变式题进行能力验证

实现文件：backend/api/review.py
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
from services.review_queue_service import ReviewQueueService, get_due_review_questions
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/review", tags=["错题复习"])


# ============ 数据模型 ============

class ReviewQuestionResponse(BaseModel):
    """复习题目响应"""
    question_id: str
    original_question: Dict[str, Any]
    variation_question: Optional[Dict[str, Any]]
    review_stage: int
    visual_status: str
    color: str
    icon: str
    is_mastered: bool


class ReviewListResponse(BaseModel):
    """复习列表响应"""
    success: bool
    total: int
    questions: List[ReviewQuestionResponse]


class ReviewProgressResponse(BaseModel):
    """复习进度响应"""
    success: bool
    total_questions: int
    mastered_count: int
    in_progress_count: int
    rusty_count: int
    healing_progress: float


class ReviewUpdateRequest(BaseModel):
    """复习状态更新请求"""
    question_id: str = Field(..., description="题目ID")
    is_correct: bool = Field(..., description="是否答对")


class ReviewUpdateResponse(BaseModel):
    """复习状态更新响应"""
    success: bool
    message: str
    is_mastered: bool
    stage: int
    visual_status: str
    color: str
    icon: str


class AddToReviewRequest(BaseModel):
    """加入复习队列请求"""
    question_id: str = Field(..., description="题目ID")
    error_count: int = Field(default=1, description="错误次数")


class VariationQuestionResponse(BaseModel):
    """变式题响应"""
    success: bool
    original_question_id: str
    variation_question: Optional[Dict[str, Any]]
    message: str


# ============ API端点 ============

@router.get("/due", response_model=ReviewListResponse)
async def get_due_reviews(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取已到期的复习题目"""
    try:
        user_id = current_user.id
        logger.info(f"获取到期复习题: 用户={user_id}, 限制={limit}")

        service = ReviewQueueService()

        # 从 Redis 复习队列获取到期题目
        due_ids = service.get_due_review_ids(user_id, limit)

        questions = []
        for qid in due_ids:
            info = await service._get_question_info(db, qid)
            stage = service.get_review_stage(user_id, qid)
            questions.append({
                'question_id': qid,
                'original_question': info,
                'variation_question': None,
                'review_stage': stage,
                'visual_status': 'reviewing',
                'color': '#FF9800',
                'icon': '📝',
                'is_mastered': stage >= 5,
            })

        return ReviewListResponse(
            success=True,
            total=len(questions),
            questions=[ReviewQuestionResponse(**q) for q in questions]
        )

    except Exception as e:
        logger.error(f"获取到期复习题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update", response_model=ReviewUpdateResponse)
async def update_review_status(
    request: ReviewUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    更新复习状态
    
    根据答题结果推进到下一阶段或标记为Mastered
    """
    try:
        user_id = current_user.id
        logger.info(f"更新复习状态: 用户={user_id}, 题目={request.question_id}, 正确={request.is_correct}")
        
        service = ReviewQueueService()
        result = service.update_review_status(
            user_id=user_id,
            question_id=request.question_id,
            is_correct=request.is_correct
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])
        
        return ReviewUpdateResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新复习状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress", response_model=ReviewProgressResponse)
async def get_review_progress(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取复习进度统计
    
    返回错题复习的整体进度和治愈情况
    """
    try:
        user_id = current_user.id
        logger.info(f"获取复习进度: 用户={user_id}")
        
        service = ReviewQueueService()
        progress = service.get_review_progress(user_id)
        
        return ReviewProgressResponse(
            success=True,
            total_questions=progress.total_questions,
            mastered_count=progress.mastered_count,
            in_progress_count=progress.in_progress_count,
            rusty_count=progress.rusty_count,
            healing_progress=progress.healing_progress
        )
        
    except Exception as e:
        logger.error(f"获取复习进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_to_review_queue(
    request: AddToReviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    将错题加入复习队列
    
    初始状态为"生锈"（红色），1天后首次复习
    """
    try:
        user_id = current_user.id
        logger.info(f"加入复习队列: 用户={user_id}, 题目={request.question_id}")
        
        service = ReviewQueueService()
        success = service.add_to_review_queue(
            user_id=user_id,
            question_id=request.question_id,
            error_count=request.error_count
        )
        
        if success:
            return {
                'success': True,
                'message': '已加入复习队列，1天后首次复习',
                'visual_status': 'rusty',
                'color': '#FF4D4F',
                'icon': '🔴'
            }
        else:
            raise HTTPException(status_code=500, detail="加入复习队列失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加入复习队列失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/variation/{question_id}", response_model=VariationQuestionResponse)
async def get_variation_question(
    question_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取变式题
    
    对应需求12: 基于RAG抽取同知识点、难度匹配的变式题
    """
    try:
        user_id = current_user.id
        logger.info(f"获取变式题: 用户={user_id}, 原题={question_id}")
        
        service = ReviewQueueService()
        
        # 获取原题信息
        original = service._get_question_info(question_id)
        
        # 获取变式题
        variation = service._get_variation_question(user_id, question_id, original)
        
        if variation:
            return VariationQuestionResponse(
                success=True,
                original_question_id=question_id,
                variation_question=variation,
                message='成功获取变式题'
            )
        else:
            return VariationQuestionResponse(
                success=False,
                original_question_id=question_id,
                variation_question=None,
                message='未找到合适的变式题'
            )
        
    except Exception as e:
        logger.error(f"获取变式题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visual-status")
async def get_visual_status_mapping():
    """
    获取视觉状态映射配置
    
    返回复习阶段到视觉表现的映射规则
    """
    service = ReviewQueueService()
    
    mapping = {}
    for stage in range(7):
        status, color, icon = service.VISUAL_STATUS_MAP.get(
            stage,
            (service.ReviewVisualStatus.RUSTY, "#FF4D4F", "🔴")
        )
        mapping[stage] = {
            'status': status.value,
            'color': color,
            'icon': icon,
            'description': {
                0: '初始/生锈',
                1: '第1阶段（1天后）',
                2: '第2阶段（2天后）',
                3: '第3阶段（4天后）',
                4: '第4阶段（7天后）',
                5: '第5阶段（14天后）',
                6: '已攻克'
            }.get(stage, '未知')
        }
    
    return {
        'success': True,
        'review_intervals': service.REVIEW_INTERVALS,
        'visual_status_map': mapping
    }


@router.get("/mastered")
async def get_mastered_questions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取已攻克的题目列表
    """
    try:
        user_id = current_user.id
        
        # 从Redis获取已攻克集合
        mastered_key = f"ai:tutor:mastered:{user_id}"
        mastered_ids = ReviewQueueService().redis_service.redis_client.smembers(mastered_key)
        
        return {
            'success': True,
            'count': len(mastered_ids),
            'question_ids': list(mastered_ids)
        }
        
    except Exception as e:
        logger.error(f"获取已攻克题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = ReviewQueueService()
        return {
            'status': 'healthy',
            'service': 'review_queue',
            'review_intervals': service.REVIEW_INTERVALS
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
