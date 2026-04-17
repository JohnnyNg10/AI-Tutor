"""
日志分区归档API接口
提供日志分区管理和归档的HTTP接口

对应行号40: 防止新引入的 user_interaction_logs 表无限制膨胀撑爆数据库磁盘

实现文件: backend/api/log_partitioning.py
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

from services.log_partitioning_service import (
    LogPartitioningService,
    get_current_log_partition,
    write_log_to_current_partition,
    archive_old_logs
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/log-partitioning", tags=["交互日志表分区归档"])


# ============ 数据模型 ============

class WriteLogRequest(BaseModel):
    """写入日志请求"""
    log_data: Dict[str, Any] = Field(..., description="日志数据")


class PartitionStatsResponse(BaseModel):
    """分区统计响应"""
    success: bool
    total_partitions: int
    total_records: int
    total_size_mb: float
    archived_partitions: int
    active_partitions: int


class ArchiveResponse(BaseModel):
    """归档响应"""
    success: bool
    archived_count: int
    archived_partitions: List[str]
    errors: List[Dict[str, Any]]


class DiskSpaceResponse(BaseModel):
    """磁盘空间响应"""
    success: bool
    total_size_mb: float
    total_size_gb: float
    status: str
    warning_threshold_mb: int
    critical_threshold_mb: int
    recommendation: str


# ============ API端点 ============

@router.get("/current-partition")
async def get_current_partition(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取当前分区
    
    返回当前正在使用的日志分区名称
    """
    try:
        service = LogPartitioningService()
        partition = service.get_current_partition()
        
        return {
            'success': True,
            'current_partition': partition,
            'partition_days': service.PARTITION_DAYS
        }
        
    except Exception as e:
        logger.error(f"获取当前分区失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write-log")
async def write_log(
    request: WriteLogRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """写入日志到当前分区"""
    try:
        service = LogPartitioningService()
        result = service.write_log_to_partition(request.log_data)
        
        if result:
            return {
                'success': True,
                'message': '日志已写入分区'
            }
        else:
            raise HTTPException(status_code=500, detail="写入失败")
        
    except Exception as e:
        logger.error(f"写入日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=PartitionStatsResponse)
async def get_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取分区统计
    
    返回所有分区的统计信息
    """
    try:
        service = LogPartitioningService()
        stats = service.get_partition_statistics()
        
        return PartitionStatsResponse(
            success=True,
            total_partitions=stats.total_partitions,
            total_records=stats.total_records,
            total_size_mb=stats.total_size_mb,
            archived_partitions=stats.archived_partitions,
            active_partitions=stats.active_partitions
        )
        
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archive", response_model=ArchiveResponse)
async def archive_partitions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    归档旧分区
    
    对应行号40: 自动归档30天前的分区
    """
    try:
        service = LogPartitioningService()
        result = service.archive_old_partitions()
        
        return ArchiveResponse(
            success=result['success'],
            archived_count=result['archived_count'],
            archived_partitions=result['archived_partitions'],
            errors=result.get('errors', [])
        )
        
    except Exception as e:
        logger.error(f"归档分区失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-expired")
async def delete_expired_partitions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """删除过期分区（90天前）"""
    try:
        service = LogPartitioningService()
        result = service.delete_expired_partitions()
        
        return {
            'success': result['success'],
            'deleted_count': result['deleted_count'],
            'deleted_partitions': result['deleted_partitions'],
            'errors': result.get('errors', [])
        }
        
    except Exception as e:
        logger.error(f"删除过期分区失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/disk-space", response_model=DiskSpaceResponse)
async def check_disk_space(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查磁盘空间
    
    监控日志分区占用的磁盘空间
    """
    try:
        service = LogPartitioningService()
        space = service.check_disk_space()
        
        return DiskSpaceResponse(
            success=True,
            total_size_mb=space['total_size_mb'],
            total_size_gb=space['total_size_gb'],
            status=space['status'],
            warning_threshold_mb=space['warning_threshold_mb'],
            critical_threshold_mb=space['critical_threshold_mb'],
            recommendation=space['recommendation']
        )
        
    except Exception as e:
        logger.error(f"检查磁盘空间失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/partitions")
async def list_partitions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """列出所有分区"""
    try:
        service = LogPartitioningService()
        partitions = service._get_all_partitions()
        
        return {
            'success': True,
            'count': len(partitions),
            'partitions': [
                {
                    'name': p.partition_name,
                    'start_date': p.start_date,
                    'end_date': p.end_date,
                    'record_count': p.record_count,
                    'size_mb': p.size_mb,
                    'is_archived': p.is_archived,
                    'archived_at': p.archived_at
                }
                for p in partitions
            ]
        }
        
    except Exception as e:
        logger.error(f"列出分区失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query/{partition_name}")
async def query_partition(
    partition_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """查询分区日志"""
    try:
        service = LogPartitioningService()
        logs = service.query_logs_from_partition(
            partition_name,
            start_time,
            end_time,
            limit
        )
        
        return {
            'success': True,
            'partition': partition_name,
            'count': len(logs),
            'logs': logs
        }
        
    except Exception as e:
        logger.error(f"查询分区失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = LogPartitioningService()
        stats = service.get_partition_statistics()
        space = service.check_disk_space()
        
        return {
            'status': 'healthy',
            'service': 'log_partitioning',
            'partitions': stats.total_partitions,
            'disk_status': space['status'],
            'partition_days': service.PARTITION_DAYS,
            'archive_after_days': service.ARCHIVE_AFTER_DAYS,
            'features': ['partitioning', 'archiving', 'cleanup', 'monitoring']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
