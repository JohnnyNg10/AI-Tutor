"""
Redis已做题目标记API接口
提供已做题目管理和去重的HTTP接口

对应行号41: 利用 Redis 高速读写特性，拦截已做题目，杜绝学生在短时间内刷到重复题目的糟糕体验

实现文件: backend/api/seen_questions.py
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

from services.seen_questions_service import (
    SeenQuestionsService,
    mark_question_seen,
    is_question_seen,
    filter_unseen_questions
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/seen-questions", tags=["Redis已做题目标记"])


# ============ 数据模型 ============

class MarkSeenRequest(BaseModel):
    """标记已做请求"""
    question_id: str = Field(..., description="题目ID")


class MarkSeenResponse(BaseModel):
    """标记已做响应"""
    success: bool
    user_id: int
    question_id: str
    message: str


class CheckSeenResponse(BaseModel):
    """检查已做响应"""
    success: bool
    user_id: int
    question_id: str
    is_seen: bool


class FilterUnseenRequest(BaseModel):
    """过滤未做请求"""
    question_ids: List[str] = Field(..., description="题目ID列表")


class FilterUnseenResponse(BaseModel):
    """过滤未做响应"""
    success: bool
    user_id: int
    total: int
    seen_count: int
    unseen_count: int
    unseen_ids: List[str]


class SeenStatisticsResponse(BaseModel):
    """已做统计响应"""
    success: bool
    user_id: int
    total_seen: int
    recent_7_days: int
    window_size: int
    time_window_days: int
    recent_questions: List[Dict[str, Any]]


# ============ API端点 ============

@router.post("/mark", response_model=MarkSeenResponse)
async def mark_seen(
    request: MarkSeenRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    标记题目为已做
    
    对应行号41: 将已做题目存入Redis Set
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        success = service.mark_question_as_seen(user_id, request.question_id)
        
        if success:
            return MarkSeenResponse(
                success=True,
                user_id=user_id,
                question_id=request.question_id,
                message="题目已标记为已做"
            )
        else:
            raise HTTPException(status_code=500, detail="标记失败")
        
    except Exception as e:
        logger.error(f"标记已做失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-batch")
async def mark_seen_batch(
    question_ids: List[str],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """批量标记题目为已做"""
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        success = service.mark_questions_as_seen(user_id, question_ids)
        
        if success:
            return {
                'success': True,
                'user_id': user_id,
                'count': len(question_ids),
                'message': f"已批量标记{len(question_ids)}题为已做"
            }
        else:
            raise HTTPException(status_code=500, detail="批量标记失败")
        
    except Exception as e:
        logger.error(f"批量标记失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check/{question_id}", response_model=CheckSeenResponse)
async def check_seen(
    question_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查题目是否已做过
    
    对应行号41: 推题前检查是否已做过
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        is_seen = service.is_question_seen(user_id, question_id)
        
        return CheckSeenResponse(
            success=True,
            user_id=user_id,
            question_id=question_id,
            is_seen=is_seen
        )
        
    except Exception as e:
        logger.error(f"检查已做失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filter-unseen", response_model=FilterUnseenResponse)
async def filter_unseen(
    request: FilterUnseenRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    过滤未做题目
    
    从候选题目中过滤掉已做过的题目
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        unseen_ids = service.filter_seen_questions(user_id, request.question_ids)
        
        return FilterUnseenResponse(
            success=True,
            user_id=user_id,
            total=len(request.question_ids),
            seen_count=len(request.question_ids) - len(unseen_ids),
            unseen_count=len(unseen_ids),
            unseen_ids=unseen_ids
        )
        
    except Exception as e:
        logger.error(f"过滤未做失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def get_seen_list(
    limit: Optional[int] = Query(None, description="限制数量"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取已做题目列表"""
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        seen = service.get_seen_questions(user_id, limit)
        
        return {
            'success': True,
            'user_id': user_id,
            'count': len(seen),
            'question_ids': list(seen)
        }
        
    except Exception as e:
        logger.error(f"获取已做列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
async def get_recent_seen(
    count: int = Query(10, ge=1, le=50, description="最近N题"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取最近做过的题目"""
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        recent = service.get_recent_seen_questions(user_id, count)
        
        return {
            'success': True,
            'user_id': user_id,
            'count': len(recent),
            'questions': recent
        }
        
    except Exception as e:
        logger.error(f"获取最近已做失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=SeenStatisticsResponse)
async def get_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取已做题目统计"""
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        stats = service.get_seen_statistics(user_id)
        
        return SeenStatisticsResponse(
            success=True,
            user_id=user_id,
            total_seen=stats['total_seen'],
            recent_7_days=stats['recent_7_days'],
            window_size=stats['window_size'],
            time_window_days=stats['time_window_days'],
            recent_questions=stats['recent_questions']
        )
        
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-old")
async def clear_old_records(
    days: int = Query(30, ge=7, le=90, description="清除超过N天的记录"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """清除旧的已做记录"""
    try:
        user_id = current_user.get('id', 0)
        
        service = SeenQuestionsService()
        cleared_count = service.clear_old_seen_questions(user_id, days)
        
        return {
            'success': True,
            'user_id': user_id,
            'cleared_count': cleared_count,
            'message': f"已清除{cleared_count}条超过{days}天的记录"
        }
        
    except Exception as e:
        logger.error(f"清除旧记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = SeenQuestionsService()
        return {
            'status': 'healthy',
            'service': 'seen_questions',
            'window_size': service.DEFAULT_WINDOW_SIZE,
            'time_window_days': service.DEFAULT_TIME_WINDOW_DAYS,
            'features': ['seen_tracking', 'deduplication', 'sliding_window']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
