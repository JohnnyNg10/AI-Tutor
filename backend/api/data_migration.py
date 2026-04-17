"""
数据迁移API接口
提供V2→V3数据迁移的HTTP接口

对应行号38: 解决系统大版本升级带来的数据断层，防止老用户画像字段为空导致的核心引擎崩溃

实现文件: backend/api/data_migration.py
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

from services.data_migration_service import (
    DataMigrationService,
    migrate_user_data,
    check_migration_status
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/data-migration", tags=["数据迁移"])


# ============ 数据模型 ============

class MigrateUserRequest(BaseModel):
    """迁移用户请求"""
    user_id: int = Field(..., description="用户ID")


class MigrateUserResponse(BaseModel):
    """迁移用户响应"""
    success: bool
    user_id: int
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BatchMigrateRequest(BaseModel):
    """批量迁移请求"""
    user_ids: List[int] = Field(..., description="用户ID列表")
    batch_size: int = Field(default=100, ge=10, le=500)


class ValidationResponse(BaseModel):
    """验证响应"""
    success: bool
    user_id: int
    is_valid: bool
    issues: List[str]


# ============ API端点 ============

@router.post("/migrate", response_model=MigrateUserResponse)
async def migrate_user(
    request: MigrateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    迁移单个用户数据
    
    对应行号38: V2→V3数据迁移
    """
    try:
        service = DataMigrationService()
        result = service.migrate_user_v2_to_v3(request.user_id)
        
        return MigrateUserResponse(
            success=result['success'],
            user_id=result['user_id'],
            status=result['status'],
            results=result.get('results'),
            error=result.get('error')
        )
        
    except Exception as e:
        logger.error(f"迁移用户失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migrate-batch")
async def migrate_batch(
    request: BatchMigrateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """批量迁移用户数据"""
    try:
        service = DataMigrationService()
        result = service.batch_migrate_users(
            request.user_ids,
            request.batch_size
        )
        
        return {
            'success': result['success'],
            'results': result['results']
        }
        
    except Exception as e:
        logger.error(f"批量迁移失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{user_id}")
async def get_migration_status(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取用户迁移状态"""
    try:
        service = DataMigrationService()
        is_completed = service.is_migration_completed(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'is_migrated': is_completed,
            'status': 'completed' if is_completed else 'pending'
        }
        
    except Exception as e:
        logger.error(f"获取迁移状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate/{user_id}", response_model=ValidationResponse)
async def validate_user_data(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """验证用户数据完整性"""
    try:
        service = DataMigrationService()
        validation = service.validate_user_data(user_id)
        
        return ValidationResponse(
            success=True,
            user_id=user_id,
            is_valid=validation['is_valid'],
            issues=validation.get('issues', [])
        )
        
    except Exception as e:
        logger.error(f"验证用户数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repair/{user_id}")
async def repair_user_data(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """修复用户数据"""
    try:
        service = DataMigrationService()
        result = service.repair_user_data(user_id)
        
        return result
        
    except Exception as e:
        logger.error(f"修复用户数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v3-defaults")
async def get_v3_defaults(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取V3字段默认值"""
    try:
        service = DataMigrationService()
        
        return {
            'success': True,
            'defaults': service.V3_DEFAULTS
        }
        
    except Exception as e:
        logger.error(f"获取默认值失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = DataMigrationService()
        return {
            'status': 'healthy',
            'service': 'data_migration',
            'v3_defaults_count': len(service.V3_DEFAULTS),
            'features': ['single_migration', 'batch_migration', 'validation', 'repair']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
