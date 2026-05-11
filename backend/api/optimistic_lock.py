"""
乐观锁API接口
提供并发冲突控制的HTTP接口

对应行号39: 防止学生快速连续交互导致数据库画像更新冲突（脏读/脏写），保障核心算法数据的绝对准确

实现文件: backend/api/optimistic_lock.py
"""

import sys
import os

# 添加backend目录到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from services.optimistic_lock_service import (
    OptimisticLockService,
    safe_update_user_profile,
    safe_update_mastery
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/optimistic-lock", tags=["并发冲突乐观锁"])


# ============ 数据模型 ============

class CASUpdateRequest(BaseModel):
    """CAS更新请求"""
    entity_type: str = Field(..., description="实体类型")
    entity_id: str = Field(..., description="实体ID")
    expected_version: int = Field(..., description="期望版本号")
    new_data: Dict[str, Any] = Field(..., description="新数据")


class CASUpdateResponse(BaseModel):
    """CAS更新响应"""
    success: bool
    new_version: Optional[int] = None
    retry_count: int = 0
    error_message: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """更新画像请求"""
    updates: Dict[str, Any] = Field(..., description="更新数据")


class UpdateMasteryRequest(BaseModel):
    """更新掌握度请求"""
    knowledge_point_id: str = Field(..., description="知识点ID")
    updates: Dict[str, Any] = Field(..., description="更新数据")


# ============ API端点 ============

@router.post("/cas-update", response_model=CASUpdateResponse)
async def cas_update(
    request: CASUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    CAS（Compare-And-Swap）更新
    
    对应行号39: 乐观锁核心，防止并发冲突
    """
    try:
        user_id = current_user.id
        
        service = OptimisticLockService()
        result = service.cas_update(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            expected_version=request.expected_version,
            new_data=request.new_data,
            updated_by=user_id
        )
        
        return CASUpdateResponse(
            success=result.success,
            new_version=result.new_version,
            retry_count=result.retry_count,
            error_message=result.error_message
        )
        
    except Exception as e:
        logger.error(f"CAS更新失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-profile")
async def update_profile_safe(
    request: UpdateProfileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    安全更新用户画像
    
    防止快速连续交互导致的更新冲突
    """
    try:
        user_id = current_user.id
        
        service = OptimisticLockService()
        result = service.update_user_profile_safe(user_id, request.updates)
        
        return {
            'success': result.success,
            'user_id': user_id,
            'new_version': result.new_version,
            'retry_count': result.retry_count,
            'error': result.error_message
        }
        
    except Exception as e:
        logger.error(f"安全更新画像失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-mastery")
async def update_mastery_safe(
    request: UpdateMasteryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """安全更新掌握度"""
    try:
        user_id = current_user.id
        
        service = OptimisticLockService()
        result = service.update_mastery_safe(
            user_id,
            request.knowledge_point_id,
            request.updates
        )
        
        return {
            'success': result.success,
            'user_id': user_id,
            'knowledge_point_id': request.knowledge_point_id,
            'new_version': result.new_version,
            'retry_count': result.retry_count,
            'error': result.error_message
        }
        
    except Exception as e:
        logger.error(f"安全更新掌握度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version/{entity_type}/{entity_id}")
async def get_version(
    entity_type: str,
    entity_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取当前版本号"""
    try:
        service = OptimisticLockService()
        version = service.get_current_version(entity_type, entity_id)
        
        return {
            'success': True,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'version': version
        }
        
    except Exception as e:
        logger.error(f"获取版本号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{entity_type}/{entity_id}")
async def get_versioned_data(
    entity_type: str,
    entity_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取带版本号的数据"""
    try:
        service = OptimisticLockService()
        data = service.get_versioned_data(entity_type, entity_id)
        
        if data:
            return {
                'success': True,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'data': data.data,
                'version': data.version,
                'updated_at': data.updated_at
            }
        else:
            return {
                'success': True,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'data': None,
                'version': 1
            }
        
    except Exception as e:
        logger.error(f"获取版本化数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conflict-stats")
async def get_conflict_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取冲突统计"""
    try:
        user_id = current_user.id
        
        service = OptimisticLockService()
        stats = service.get_conflict_statistics(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'conflicts': stats['conflicts']
        }
        
    except Exception as e:
        logger.error(f"获取冲突统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = OptimisticLockService()
        return {
            'status': 'healthy',
            'service': 'optimistic_lock',
            'max_retries': service.MAX_RETRIES,
            'retry_delay': service.RETRY_DELAY,
            'features': ['cas_update', 'version_management', 'conflict_detection']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
