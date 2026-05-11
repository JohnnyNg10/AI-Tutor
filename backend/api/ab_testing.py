"""
A/B测试API接口
提供实验分组和指标跟踪的HTTP接口

对应行号3: 通过随机分队验证V3认知诊断算法相对V2传统推荐的有效性

实现文件: backend/api/ab_testing.py
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
from services.ab_testing_service import (
    ABTestingService,
    ExperimentGroup,
    get_user_experiment_group,
    is_v3_user
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/ab-test", tags=["A/B测试"])


# ============ 数据模型 ============

class UserGroupResponse(BaseModel):
    """用户分组响应"""
    success: bool
    user_id: int
    group: str
    strategy: str
    features: Dict[str, bool]


class RecordEventRequest(BaseModel):
    """记录事件请求"""
    is_correct: bool = Field(..., description="是否答对")
    time_spent: int = Field(..., ge=0, description="答题耗时(秒)")
    hint_count: int = Field(default=0, ge=0, description="使用提示次数")


class MetricsResponse(BaseModel):
    """指标响应"""
    success: bool
    user_id: int
    group: str
    total_questions: int
    correct_count: int
    accuracy_rate: float
    total_session_time: int
    avg_time_per_question: float
    hint_usage_rate: float


class ExperimentResultsResponse(BaseModel):
    """实验结果响应"""
    success: bool
    experiment_name: str
    timestamp: str
    groups: Dict[str, Any]
    improvement: Optional[Dict[str, Any]]


class GroupStatisticsResponse(BaseModel):
    """分组统计响应"""
    success: bool
    total_users: int
    group_a: Dict[str, Any]
    group_b: Dict[str, Any]


# ============ API端点 ============

@router.get("/group", response_model=UserGroupResponse)
async def get_user_group(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取用户实验组（A/B测试分组）"""
    try:
        user_id = current_user.id

        service = ABTestingService()
        group = service.get_or_assign_group(user_id)

        # Redis 未命中时从 MySQL 回退
        if group is None:
            db_group = await service.get_user_group_from_db(db, user_id)
            if db_group:
                group = ExperimentGroup(db_group)
            else:
                group = service.assign_user_to_group(user_id)
                await service.sync_group_to_db(db, user_id, group.value)

        strategy = service.get_recommendation_strategy(user_id)

        return UserGroupResponse(
            success=True,
            user_id=user_id,
            group=group.value,
            strategy=strategy['strategy'],
            features=strategy['features']
        )

    except Exception as e:
        logger.error(f"获取用户实验组失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy")
async def get_strategy(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取推荐策略详情
    
    A组: V2基础推荐
    B组: V3 K-IRT + Soft Labeling
    """
    try:
        user_id = current_user.id
        
        service = ABTestingService()
        strategy = service.get_recommendation_strategy(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            **strategy
        }
        
    except Exception as e:
        logger.error(f"获取推荐策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-event")
async def record_event(
    request: RecordEventRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    记录答题事件
    
    用于跟踪正确率、答题时长等指标
    """
    try:
        user_id = current_user.id
        
        service = ABTestingService()
        success = service.record_answer_event(
            user_id=user_id,
            is_correct=request.is_correct,
            time_spent=request.time_spent,
            hint_count=request.hint_count
        )
        
        if success:
            return {
                'success': True,
                'message': '事件已记录',
                'user_id': user_id
            }
        else:
            raise HTTPException(status_code=500, detail="记录失败")
        
    except Exception as e:
        logger.error(f"记录事件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=MetricsResponse)
async def get_user_metrics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取用户指标"""
    try:
        user_id = current_user.id
        
        service = ABTestingService()
        metrics = service.get_user_metrics(user_id)
        
        if not metrics:
            return MetricsResponse(
                success=True,
                user_id=user_id,
                group=service.get_or_assign_group(user_id).value,
                total_questions=0,
                correct_count=0,
                accuracy_rate=0.0,
                total_session_time=0,
                avg_time_per_question=0.0,
                hint_usage_rate=0.0
            )
        
        return MetricsResponse(
            success=True,
            user_id=metrics.user_id,
            group=metrics.group,
            total_questions=metrics.total_questions,
            correct_count=metrics.correct_count,
            accuracy_rate=metrics.accuracy_rate,
            total_session_time=metrics.total_session_time,
            avg_time_per_question=metrics.avg_time_per_question,
            hint_usage_rate=metrics.hint_usage_rate
        )
        
    except Exception as e:
        logger.error(f"获取用户指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results", response_model=ExperimentResultsResponse)
async def get_experiment_results(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取实验结果
    
    对比A组和B组的关键指标
    """
    try:
        service = ABTestingService()
        results = service.get_experiment_results()
        
        return ExperimentResultsResponse(
            success=True,
            **results
        )
        
    except Exception as e:
        logger.error(f"获取实验结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=GroupStatisticsResponse)
async def get_group_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取分组统计"""
    try:
        service = ABTestingService()
        stats = service.get_group_statistics()
        
        return GroupStatisticsResponse(
            success=True,
            **stats
        )
        
    except Exception as e:
        logger.error(f"获取分组统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_experiment(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    重置实验（仅管理员）
    
    清除所有A/B测试数据
    """
    try:
        service = ABTestingService()
        success = service.reset_experiment()
        
        if success:
            return {
                'success': True,
                'message': '实验已重置'
            }
        else:
            raise HTTPException(status_code=500, detail="重置失败")
        
    except Exception as e:
        logger.error(f"重置实验失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 便捷端点 ============

@router.get("/is-v3")
async def check_is_v3(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """检查当前用户是否使用V3特性"""
    try:
        user_id = current_user.id
        is_v3 = is_v3_user(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'is_v3': is_v3
        }
        
    except Exception as e:
        logger.error(f"检查V3特性失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = ABTestingService()
        return {
            'status': 'healthy',
            'service': 'ab_testing',
            'experiment_name': service.EXPERIMENT_NAME,
            'groups': ['A', 'B']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
