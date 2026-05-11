"""
IRT段位API接口
提供段位查询和趋势图的HTTP接口

对应需求9: 将底层枯燥的IRT θ值转化为学生易懂的游戏化成长段位趋势图

实现文件：backend/api/ranking.py
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
from services.irt_ranking_service import IRTRankingService, get_user_ranking_info
from algorithms.question_deduplication import QuestionDeduplicationService, diversify_question_queue
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/ranking", tags=["IRT段位"])


# ============ 数据模型 ============

class RankInfoResponse(BaseModel):
    """段位信息响应"""
    tier: str
    name: str
    name_cn: str
    color: str
    icon: str
    description: str


class RankingDataResponse(BaseModel):
    """段位数据响应"""
    success: bool
    user_id: int
    current_theta: float
    current_rank: RankInfoResponse
    progress_to_next: float
    next_rank: Optional[Dict[str, str]]
    total_study_days: int


class RankTrendResponse(BaseModel):
    """段位趋势响应"""
    success: bool
    user_id: int
    days: int
    data: List[Dict[str, Any]]


class RankChangeResponse(BaseModel):
    """段位变化响应"""
    has_changed: bool
    change_type: str
    from_rank: Optional[Dict[str, str]]
    to_rank: Optional[Dict[str, str]]
    message: Optional[str]
    should_animate: bool


class AllRanksResponse(BaseModel):
    """所有段位响应"""
    success: bool
    ranks: List[Dict[str, Any]]


class DiversifyQueueRequest(BaseModel):
    """队列多样化请求"""
    questions: List[Dict[str, Any]] = Field(..., description="题目列表")
    recent_history: Optional[List[str]] = Field(default=None, description="最近知识点历史")


class DiversifyQueueResponse(BaseModel):
    """队列多样化响应"""
    success: bool
    original_count: int
    diversified_count: int
    questions: List[Dict[str, Any]]
    violations_fixed: int


# ============ API端点 - IRT段位 (需求9) ============

@router.get("/current", response_model=RankingDataResponse)
async def get_current_ranking(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取当前段位信息"""
    try:
        user_id = current_user.id
        logger.info(f"获取当前段位: 用户={user_id}")

        data = await get_user_ranking_info(db, user_id)

        return RankingDataResponse(
            success=True,
            **data
        )

    except Exception as e:
        logger.error(f"获取段位信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trend", response_model=RankTrendResponse)
async def get_rank_trend(
    days: int = Query(30, ge=7, le=90, description="天数范围"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取段位趋势"""
    try:
        user_id = current_user.id
        logger.info(f"获取段位趋势: 用户={user_id}, 天数={days}")

        service = IRTRankingService()
        trend_data = await service.get_rank_trend(db, user_id, days)

        return RankTrendResponse(
            success=True,
            user_id=user_id,
            days=days,
            data=trend_data
        )

    except Exception as e:
        logger.error(f"获取段位趋势失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-change")
async def check_rank_change(
    old_theta: float,
    new_theta: float,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查段位变化
    
    用于答题后检测是否升级/降级，触发动画
    """
    try:
        user_id = current_user.id
        logger.info(f"检查段位变化: 用户={user_id}, θ {old_theta} → {new_theta}")
        
        service = IRTRankingService()
        result = service.check_rank_change(old_theta, new_theta)
        
        # 转换段位信息为可序列化格式
        response = {
            'has_changed': result['has_changed'],
            'change_type': result['change_type'],
            'message': result['message'],
            'should_animate': result['should_animate']
        }
        
        if result['from_rank']:
            response['from_rank'] = {
                'name_cn': result['from_rank'].name_cn,
                'icon': result['from_rank'].icon
            }
        
        if result['to_rank']:
            response['to_rank'] = {
                'name_cn': result['to_rank'].name_cn,
                'icon': result['to_rank'].icon
            }
        
        return response
        
    except Exception as e:
        logger.error(f"检查段位变化失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=AllRanksResponse)
async def get_all_ranks():
    """
    获取所有段位信息
    
    返回完整的段位体系，供前端展示
    """
    try:
        service = IRTRankingService()
        ranks = service.get_all_ranks()
        
        return AllRanksResponse(
            success=True,
            ranks=ranks
        )
        
    except Exception as e:
        logger.error(f"获取所有段位失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ API端点 - 题目多样化 (需求32) ============

@router.post("/diversify-queue", response_model=DiversifyQueueResponse)
async def diversify_queue(
    request: DiversifyQueueRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    对题目队列进行多样化处理
    
    对应需求32: 防止算法陷入局部最优，避免连续推送相同考点
    
    算法：
    1. 滑动窗口检查（窗口大小=2）
    2. 相同知识点惩罚逻辑
    3. 队列重排
    """
    try:
        user_id = current_user.id
        logger.info(f"题目队列多样化: 用户={user_id}, 原队列{len(request.questions)}题")
        
        # 检查原队列违规情况
        service = QuestionDeduplicationService()
        question_objects = [
            service.Question(
                question_id=q.get('question_id', ''),
                knowledge_points=q.get('knowledge_points', []),
                difficulty=q.get('difficulty', 0.0),
                content=q.get('content', ''),
                metadata=q.get('metadata', {})
            )
            for q in request.questions
        ]
        
        original_violations = service.check_sliding_window(question_objects)
        
        # 多样化处理
        diversified = diversify_question_queue(
            request.questions,
            request.recent_history
        )
        
        return DiversifyQueueResponse(
            success=True,
            original_count=len(request.questions),
            diversified_count=len(diversified),
            questions=diversified,
            violations_fixed=len(original_violations)
        )
        
    except Exception as e:
        logger.error(f"队列多样化失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-diversity")
async def check_diversity(
    request: DiversifyQueueRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查题目队列多样性
    
    返回违规情况，不修改队列
    """
    try:
        service = QuestionDeduplicationService()
        
        question_objects = [
            service.Question(
                question_id=q.get('question_id', ''),
                knowledge_points=q.get('knowledge_points', []),
                difficulty=q.get('difficulty', 0.0),
                content=q.get('content', ''),
                metadata=q.get('metadata', {})
            )
            for q in request.questions
        ]
        
        violations = service.check_sliding_window(question_objects)
        
        has_violations = len(violations) > 0
        
        return {
            'success': True,
            'has_violations': has_violations,
            'violation_count': len(violations),
            'violations': violations,
            'message': f'发现{len(violations)}处连续相同考点' if has_violations else '队列多样性良好'
        }
        
    except Exception as e:
        logger.error(f"检查多样性失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        ranking_service = IRTRankingService()
        dedup_service = QuestionDeduplicationService()
        
        return {
            'status': 'healthy',
            'ranking_service': True,
            'deduplication_service': True,
            'sliding_window_size': dedup_service.SLIDING_WINDOW_SIZE
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
