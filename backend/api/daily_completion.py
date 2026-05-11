"""
每日完课结算API接口
提供完课进度追踪和结算的HTTP接口

对应行号23: 以极低的开发成本，实现V3.1规划中的"激励机制"体验雏形

实现文件: backend/api/daily_completion.py
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

from services.daily_completion_service import (
    DailyCompletionService,
    get_daily_progress,
    record_answer,
    get_completion_summary
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/daily-completion", tags=["每日完课结算"])


# ============ 数据模型 ============

class RecordAnswerRequest(BaseModel):
    """记录答题请求"""
    question_id: str = Field(..., description="题目ID")
    is_correct: bool = Field(..., description="是否答对")
    actual_score: float = Field(..., ge=0, le=1, description="Actual Score")
    knowledge_point: str = Field(..., description="知识点")


class RecordAnswerResponse(BaseModel):
    """记录答题响应"""
    success: bool
    completed_questions: int
    total_questions: int
    correct_count: int
    accuracy_rate: float
    total_actual_score: float
    is_completed: bool
    is_just_completed: bool
    remaining: int
    progress_percentage: float


class CompletionStatusResponse(BaseModel):
    """完成状态响应"""
    is_completed: bool
    completed_questions: int
    total_questions: int
    remaining: int
    progress_percentage: float


class MasteryImprovementData(BaseModel):
    """掌握度提升数据"""
    knowledge_point: str
    kp_name: str
    before: float
    after: float
    gain: float


class AnimationStageData(BaseModel):
    """动效阶段数据"""
    stage: int
    name: str
    effect: str
    duration_ms: int
    text: Optional[str] = None


class AnimationData(BaseModel):
    """动效数据"""
    type: str
    duration_ms: int
    stages: List[AnimationStageData]


class CompletionSummaryResponse(BaseModel):
    """完课结算响应"""
    success: bool
    user_id: int
    date: str
    is_completed: bool
    
    # 答题统计
    total_questions: int
    completed_questions: int
    correct_count: int
    accuracy_rate: float
    
    # Actual Score统计
    total_actual_score: float
    avg_actual_score: float
    max_actual_score: float
    
    # θ经验值提升
    theta_before: float
    theta_after: float
    theta_gain: float
    theta_gain_percentage: float
    
    # 掌握度提升
    mastery_improvements: List[MasteryImprovementData]
    total_mastery_gain: float
    
    # 结算文案
    celebration_title: str
    celebration_message: str
    
    # 微动效数据
    animation_data: AnimationData


# ============ API端点 ============

@router.post("/record-answer", response_model=RecordAnswerResponse)
async def record_question_answer(
    request: RecordAnswerRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    记录答题结果
    
    每答完一题调用此接口，系统会自动追踪每日5题进度
    """
    try:
        service = DailyCompletionService()
        result = service.record_question_answer(
            user_id=current_user.id,
            question_id=request.question_id,
            is_correct=request.is_correct,
            actual_score=request.actual_score,
            knowledge_point=request.knowledge_point
        )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', '记录失败'))
        
        progress = result['progress']
        return RecordAnswerResponse(
            success=True,
            completed_questions=progress['completed_questions'],
            total_questions=progress['total_questions'],
            correct_count=progress['correct_count'],
            accuracy_rate=progress['accuracy_rate'],
            total_actual_score=progress['total_actual_score'],
            is_completed=progress['is_completed'],
            is_just_completed=result.get('is_just_completed', False),
            remaining=progress['remaining'],
            progress_percentage=progress['accuracy_rate']
        )
        
    except Exception as e:
        logger.error(f"记录答题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=CompletionStatusResponse)
async def get_completion_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取今日完成状态
    
    返回当前用户今日5题的完成进度
    """
    try:
        service = DailyCompletionService()
        status = service.check_completion_status(current_user.id)
        
        return CompletionStatusResponse(
            is_completed=status['is_completed'],
            completed_questions=status['completed_questions'],
            total_questions=status['total_questions'],
            remaining=status['remaining'],
            progress_percentage=status['progress_percentage']
        )
        
    except Exception as e:
        logger.error(f"获取完成状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=CompletionSummaryResponse)
async def get_completion_summary_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取完课结算数据
    
    完成每日5题后，调用此接口获取结算弹窗数据
    包含：答题统计、Actual Score、θ经验值提升、掌握度提升、动效数据
    """
    try:
        service = DailyCompletionService()
        summary = service.generate_completion_summary(current_user.id)
        
        if not summary:
            raise HTTPException(
                status_code=400,
                detail="今日5题尚未完成，无法生成结算数据"
            )
        
        # 转换掌握度提升数据
        mastery_data = [
            MasteryImprovementData(
                knowledge_point=m['knowledge_point'],
                kp_name=m['kp_name'],
                before=m['before'],
                after=m['after'],
                gain=m['gain']
            )
            for m in summary.mastery_improvements
        ]
        
        # 转换动效数据
        animation_stages = [
            AnimationStageData(
                stage=s['stage'],
                name=s['name'],
                effect=s['effect'],
                duration_ms=s['duration_ms'],
                text=s.get('text')
            )
            for s in summary.animation_data.get('stages', [])
        ]
        
        animation_data = AnimationData(
            type=summary.animation_data.get('type', 'completion_celebration'),
            duration_ms=summary.animation_data.get('duration_ms', 3000),
            stages=animation_stages
        )
        
        return CompletionSummaryResponse(
            success=True,
            user_id=summary.user_id,
            date=summary.date,
            is_completed=summary.is_completed,
            total_questions=summary.total_questions,
            completed_questions=summary.completed_questions,
            correct_count=summary.correct_count,
            accuracy_rate=summary.accuracy_rate,
            total_actual_score=summary.total_actual_score,
            avg_actual_score=summary.avg_actual_score,
            max_actual_score=summary.max_actual_score,
            theta_before=summary.theta_before,
            theta_after=summary.theta_after,
            theta_gain=summary.theta_gain,
            theta_gain_percentage=summary.theta_gain_percentage,
            mastery_improvements=mastery_data,
            total_mastery_gain=summary.total_mastery_gain,
            celebration_title=summary.celebration_title,
            celebration_message=summary.celebration_message,
            animation_data=animation_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取结算数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress")
async def get_daily_progress_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取详细进度
    
    返回今日答题详细进度，包括每道题的记录
    """
    try:
        service = DailyCompletionService()
        progress = service.get_daily_progress(current_user.id)
        
        return {
            'success': True,
            'user_id': progress.user_id,
            'date': progress.date,
            'total_questions': progress.total_questions,
            'completed_questions': progress.completed_questions,
            'correct_count': progress.correct_count,
            'accuracy_rate': round(progress.correct_count / progress.completed_questions * 100, 1) if progress.completed_questions > 0 else 0,
            'total_actual_score': round(progress.total_actual_score, 2),
            'is_completed': progress.is_completed,
            'completed_at': progress.completed_at,
            'questions': progress.questions
        }
        
    except Exception as e:
        logger.error(f"获取进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = DailyCompletionService()
        return {
            'status': 'healthy',
            'service': 'daily_completion',
            'daily_question_count': service.DAILY_QUESTION_COUNT,
            'theta_gain_factor': service.THETA_GAIN_FACTOR,
            'features': [
                'progress_tracking',
                'completion_summary',
                'theta_calculation',
                'mastery_improvement',
                'celebration_animation'
            ]
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
