"""
跳过处理API接口
提供题目跳过处理的HTTP接口

实现文件：backend/api/skip.py
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

from algorithms.skip_handler import (
    SkipHandler, 
    SkipReason, 
    handle_question_skip
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/skip", tags=["跳过处理"])


# ============ 数据模型 ============

class SkipQuestionRequest(BaseModel):
    """跳过题目请求"""
    question_id: str = Field(..., description="题目ID")
    skip_reason: str = Field(..., description="跳过原因: too_easy / too_hard / other")
    current_theta: float = Field(..., ge=-3, le=3, description="当前能力值")
    knowledge_points: List[str] = Field(default=[], description="知识点列表")


class SkipQuestionResponse(BaseModel):
    """跳过题目响应"""
    success: bool
    skip_reason: str
    actual_score: float
    theta_delta: float
    new_theta: float
    advisor_message: str
    next_recommendation: Dict[str, Any]


class SkipStatisticsResponse(BaseModel):
    """跳过统计响应"""
    success: bool
    total_skips: int
    too_easy_count: int
    too_hard_count: int
    other_count: int
    too_easy_ratio: float
    too_hard_ratio: float


class CalibrationSuggestionResponse(BaseModel):
    """校准建议响应"""
    success: bool
    should_adjust: bool
    suggestion: str
    theta_adjustment: float
    difficulty_bias: str


class SkipHistoryResponse(BaseModel):
    """跳过历史响应"""
    success: bool
    history: List[Dict[str, Any]]


# ============ API端点 ============

@router.post("/handle", response_model=SkipQuestionResponse)
async def handle_skip(
    request: SkipQuestionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    处理题目跳过
    
    根据跳过原因（太简单/太难了）进行相应的算法处理和Advisor介入
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"跳过题目：用户={user_id}, 题目={request.question_id}, 原因={request.skip_reason}")
        
        # 验证跳过原因
        if request.skip_reason not in ['too_easy', 'too_hard', 'other']:
            raise HTTPException(status_code=400, detail="无效的跳过原因")
        
        # 处理跳过
        result = handle_question_skip(
            user_id=user_id,
            question_id=request.question_id,
            skip_reason=request.skip_reason,
            current_theta=request.current_theta,
            knowledge_points=request.knowledge_points
        )
        
        # 计算新的能力值
        new_theta = request.current_theta + result['theta_delta']
        new_theta = max(-3.0, min(3.0, new_theta))  # 限制在[-3, 3]
        
        return SkipQuestionResponse(
            success=True,
            skip_reason=result['skip_reason'],
            actual_score=result['actual_score'],
            theta_delta=result['theta_delta'],
            new_theta=new_theta,
            advisor_message=result['advisor_message'],
            next_recommendation=result['next_recommendation']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理跳过失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/too-easy", response_model=SkipQuestionResponse)
async def skip_too_easy(
    request: SkipQuestionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    处理"太简单"跳过
    
    算法处理：
    - Actual = 1.0
    - θ += 0.1
    - BKT掌握度提升
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"太简单跳过：用户={user_id}, 题目={request.question_id}")
        
        handler = SkipHandler()
        result = handler.handle_too_easy(
            user_id=user_id,
            question_id=request.question_id,
            current_theta=request.current_theta,
            knowledge_points=request.knowledge_points
        )
        
        new_theta = request.current_theta + result.theta_delta
        new_theta = max(-3.0, min(3.0, new_theta))
        
        return SkipQuestionResponse(
            success=True,
            skip_reason=result.skip_reason.value,
            actual_score=result.actual_score,
            theta_delta=result.theta_delta,
            new_theta=new_theta,
            advisor_message=result.advisor_message,
            next_recommendation=result.next_recommendation
        )
        
    except Exception as e:
        logger.error(f"处理太简单跳过失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/too-hard", response_model=SkipQuestionResponse)
async def skip_too_hard(
    request: SkipQuestionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    处理"太难了"跳过
    
    算法处理：
    - Actual = 0.0
    - θ -= 0.05
    - U（不确定性）增加
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"太难了跳过：用户={user_id}, 题目={request.question_id}")
        
        handler = SkipHandler()
        result = handler.handle_too_hard(
            user_id=user_id,
            question_id=request.question_id,
            current_theta=request.current_theta,
            knowledge_points=request.knowledge_points
        )
        
        new_theta = request.current_theta + result.theta_delta
        new_theta = max(-3.0, min(3.0, new_theta))
        
        return SkipQuestionResponse(
            success=True,
            skip_reason=result.skip_reason.value,
            actual_score=result.actual_score,
            theta_delta=result.theta_delta,
            new_theta=new_theta,
            advisor_message=result.advisor_message,
            next_recommendation=result.next_recommendation
        )
        
    except Exception as e:
        logger.error(f"处理太难了跳过失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=SkipStatisticsResponse)
async def get_skip_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取跳过统计信息
    
    统计用户的跳过历史，用于分析学习模式
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"获取跳过统计：用户={user_id}")
        
        handler = SkipHandler()
        stats = handler.get_skip_statistics(user_id)
        
        return SkipStatisticsResponse(
            success=True,
            total_skips=stats['total_skips'],
            too_easy_count=stats['too_easy_count'],
            too_hard_count=stats['too_hard_count'],
            other_count=stats['other_count'],
            too_easy_ratio=stats['too_easy_ratio'],
            too_hard_ratio=stats['too_hard_ratio']
        )
        
    except Exception as e:
        logger.error(f"获取跳过统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=SkipHistoryResponse)
async def get_skip_history(
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取跳过历史
    
    获取用户最近的跳过记录
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"获取跳过历史：用户={user_id}, 限制={limit}")
        
        handler = SkipHandler()
        history = handler.get_skip_history(user_id, limit=limit)
        
        history_list = [
            {
                'question_id': record.question_id,
                'skip_reason': record.skip_reason.value,
                'timestamp': record.timestamp
            }
            for record in history
        ]
        
        return SkipHistoryResponse(
            success=True,
            history=history_list
        )
        
    except Exception as e:
        logger.error(f"获取跳过历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration-suggestion", response_model=CalibrationSuggestionResponse)
async def get_calibration_suggestion(
    current_theta: float,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取系统校准建议
    
    根据跳过历史，建议调整推荐算法参数
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"获取校准建议：用户={user_id}")
        
        handler = SkipHandler()
        suggestion = handler.generate_calibration_suggestion(user_id, current_theta)
        
        return CalibrationSuggestionResponse(
            success=True,
            should_adjust=suggestion['should_adjust'],
            suggestion=suggestion['suggestion'],
            theta_adjustment=suggestion['theta_adjustment'],
            difficulty_bias=suggestion['difficulty_bias']
        )
        
    except Exception as e:
        logger.error(f"获取校准建议失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pattern")
async def detect_skip_pattern(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检测跳过模式
    
    识别学生是否频繁跳过某类题目
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"检测跳过模式：用户={user_id}")
        
        handler = SkipHandler()
        pattern = handler.detect_skip_pattern(user_id)
        
        return {
            'success': True,
            'pattern': pattern,
            'description': {
                'frequent_easy_skip': '频繁跳过简单题（系统可能低估学生能力）',
                'frequent_hard_skip': '频繁跳过难题（系统可能高估学生能力）',
                None: '跳过模式正常'
            }.get(pattern, '未知模式')
        }
        
    except Exception as e:
        logger.error(f"检测跳过模式失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        handler = SkipHandler()
        return {
            'status': 'healthy',
            'handler_initialized': True
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
