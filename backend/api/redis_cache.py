"""
Redis缓存API接口
提供错题复习队列和知识点掌握度缓存的HTTP接口

对应需求:
- 需求40: Redis错题复习队列
- 需求41: Redis知识点掌握度缓存

实现文件: backend/api/redis_cache.py
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
from datetime import datetime

from services.redis_cache_service import RedisCacheService
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/redis-cache", tags=["Redis缓存"])


# ============ 数据模型 ============

class AddToReviewRequest(BaseModel):
    """添加到复习队列请求"""
    question_id: str = Field(..., description="题目ID")
    mastery_level: float = Field(default=0.3, ge=0, le=1, description="当前掌握度")
    review_stage: int = Field(default=0, ge=0, le=4, description="复习阶段")


class UpdateReviewRequest(BaseModel):
    """更新复习状态请求"""
    question_id: str = Field(..., description="题目ID")
    answered_correctly: bool = Field(..., description="是否答对")


class CacheMasteryRequest(BaseModel):
    """缓存掌握度请求"""
    knowledge_point_id: str = Field(..., description="知识点ID")
    score: float = Field(..., ge=0, le=100, description="掌握度分数(0-100)")
    p_known: float = Field(..., ge=0, le=1, description="BKT掌握度概率(0-1)")


class BatchCacheMasteryRequest(BaseModel):
    """批量缓存掌握度请求"""
    mastery_data: Dict[str, Dict[str, float]] = Field(
        ...,
        description="掌握度数据 {kp_id: {score: x, p_known: y}}"
    )


class WarmUpRequest(BaseModel):
    """缓存预热请求"""
    mastery_data: Optional[Dict[str, Dict[str, float]]] = Field(
        default=None,
        description="掌握度数据（可选，不提供则从数据库加载）"
    )


# ============ 复习队列API (需求40) ============

@router.post("/review-queue/add")
async def add_to_review_queue(
    request: AddToReviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    添加题目到复习队列
    
    对应需求40: 将错题加入Redis ZSet复习队列
    """
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        success = service.add_to_review_queue(
            user_id=user_id,
            question_id=request.question_id,
            mastery_level=request.mastery_level,
            review_stage=request.review_stage
        )
        
        if success:
            # 计算下次复习时间
            intervals = [1, 2, 4, 7, 14]
            days = intervals[min(request.review_stage, len(intervals) - 1)]
            next_review = datetime.now().timestamp() + (days * 86400)
            
            return {
                'success': True,
                'message': '已添加到复习队列',
                'question_id': request.question_id,
                'review_stage': request.review_stage,
                'next_review_in_days': days,
                'next_review_at': datetime.fromtimestamp(next_review).isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="添加到复习队列失败")
        
    except Exception as e:
        logger.error(f"添加复习队列失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-queue/due")
async def get_due_reviews(
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取到期的复习题目
    
    对应需求40: 使用ZRANGEBYSCORE拉取已到期题目
    """
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        due_items = service.get_due_reviews(user_id, limit)
        
        return {
            'success': True,
            'user_id': user_id,
            'due_count': len(due_items),
            'items': due_items
        }
        
    except Exception as e:
        logger.error(f"获取到期复习失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review-queue/update")
async def update_review_stage(
    request: UpdateReviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    更新复习阶段
    
    答对进入下一阶段，答错重置为阶段0
    """
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        result = service.update_review_stage(
            user_id=user_id,
            question_id=request.question_id,
            answered_correctly=request.answered_correctly
        )
        
        if result.get('success'):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', '更新失败'))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新复习阶段失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-queue/stats")
async def get_review_queue_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取复习队列统计"""
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        stats = service.get_review_queue_stats(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"获取复习队列统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/review-queue/{question_id}")
async def remove_from_review_queue(
    question_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """从复习队列中移除题目"""
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        success = service.remove_from_review_queue(user_id, question_id)
        
        if success:
            return {
                'success': True,
                'message': '已从复习队列移除',
                'question_id': question_id
            }
        else:
            raise HTTPException(status_code=500, detail="移除失败")
        
    except Exception as e:
        logger.error(f"移除复习队列失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 掌握度缓存API (需求41) ============

@router.post("/mastery/cache")
async def cache_mastery(
    request: CacheMasteryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    缓存知识点掌握度
    
    对应需求41: 将掌握度存入Redis Hash
    """
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        success = service.cache_mastery(
            user_id=user_id,
            knowledge_point_id=request.knowledge_point_id,
            score=request.score,
            p_known=request.p_known
        )
        
        if success:
            return {
                'success': True,
                'message': '掌握度已缓存',
                'knowledge_point_id': request.knowledge_point_id,
                'score': request.score,
                'p_known': request.p_known
            }
        else:
            raise HTTPException(status_code=500, detail="缓存失败")
        
    except Exception as e:
        logger.error(f"缓存掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mastery/{knowledge_point_id}")
async def get_mastery(
    knowledge_point_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取知识点掌握度
    
    对应需求41: 从Redis Hash获取掌握度
    """
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        data = service.get_mastery(user_id, knowledge_point_id)
        
        if data:
            return {
                'success': True,
                'user_id': user_id,
                'knowledge_point_id': knowledge_point_id,
                'mastery': data
            }
        else:
            return {
                'success': True,
                'user_id': user_id,
                'knowledge_point_id': knowledge_point_id,
                'mastery': None,
                'message': '缓存中不存在该知识点掌握度'
            }
        
    except Exception as e:
        logger.error(f"获取掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mastery")
async def get_all_mastery(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取用户所有知识点掌握度"""
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        all_mastery = service.get_all_mastery(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'count': len(all_mastery),
            'mastery_data': all_mastery
        }
        
    except Exception as e:
        logger.error(f"获取所有掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mastery/batch-cache")
async def batch_cache_mastery(
    request: BatchCacheMasteryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """批量缓存掌握度"""
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        success = service.batch_cache_mastery(user_id, request.mastery_data)
        
        if success:
            return {
                'success': True,
                'message': f'已批量缓存{len(request.mastery_data)}个知识点掌握度',
                'count': len(request.mastery_data)
            }
        else:
            raise HTTPException(status_code=500, detail="批量缓存失败")
        
    except Exception as e:
        logger.error(f"批量缓存掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mastery/cache")
async def invalidate_mastery_cache(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """使掌握度缓存失效"""
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        success = service.invalidate_mastery_cache(user_id)
        
        if success:
            return {
                'success': True,
                'message': '掌握度缓存已失效',
                'user_id': user_id
            }
        else:
            raise HTTPException(status_code=500, detail="失效失败")
        
    except Exception as e:
        logger.error(f"使掌握度缓存失效失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 缓存管理API ============

@router.post("/warm-up")
async def warm_up_cache(
    request: WarmUpRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    缓存预热
    
    用户登录时从MySQL加载数据到Redis
    """
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        
        # 如果提供了数据，直接缓存；否则返回提示
        if request.mastery_data:
            success = service.warm_up_cache(user_id, request.mastery_data)
            if success:
                return {
                    'success': True,
                    'message': f'缓存预热完成，已加载{len(request.mastery_data)}个知识点',
                    'count': len(request.mastery_data)
                }
            else:
                raise HTTPException(status_code=500, detail="预热失败")
        else:
            return {
                'success': False,
                'message': '未提供数据，请从数据库加载后调用批量缓存接口',
                'alternative_endpoint': '/redis-cache/mastery/batch-cache'
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"缓存预热失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_cache_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取缓存统计信息"""
    try:
        user_id = current_user.id
        
        service = RedisCacheService()
        stats = service.get_cache_stats(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 便捷端点 ============

@router.get("/review-queue/due-count")
async def get_due_review_count(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取到期复习题目数量（便捷接口）"""
    try:
        user_id = current_user.id
        
        from services.redis_cache_service import get_due_review_count
        count = get_due_review_count(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'due_count': count
        }
        
    except Exception as e:
        logger.error(f"获取到期复习数量失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mastery/for-recommendation")
async def get_mastery_for_recommendation(
    knowledge_point_ids: List[str],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取推荐所需的掌握度数据
    
    用于推题引擎快速获取掌握度
    """
    try:
        user_id = current_user.id
        
        from services.redis_cache_service import get_mastery_for_recommendation
        mastery = get_mastery_for_recommendation(user_id, knowledge_point_ids)
        
        return {
            'success': True,
            'user_id': user_id,
            'count': len(mastery),
            'mastery': mastery
        }
        
    except Exception as e:
        logger.error(f"获取推荐掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = RedisCacheService()
        return {
            'status': 'healthy',
            'service': 'redis_cache',
            'review_intervals': service.REVIEW_INTERVALS,
            'mastery_ttl_days': service.MASTERY_TTL / 86400,
            'review_queue_ttl_days': service.REVIEW_QUEUE_TTL / 86400
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
