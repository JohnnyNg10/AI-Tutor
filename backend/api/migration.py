"""
数据迁移API接口
提供数据库表扩展和数据迁移的HTTP接口

实现文件：backend/api/migration.py
"""

import sys
import os

# 添加backend目录到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from database.migrations.v3_schema_extensions import V3SchemaExtensions, run_v3_migrations
from services.data_migration_service import DataMigrationService, run_data_migration
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/migration", tags=["数据迁移"])


# ============ 数据模型 ============

class SchemaMigrationResponse(BaseModel):
    """表结构迁移响应"""
    success: bool
    message: str
    details: Dict[str, bool]


class DataMigrationResponse(BaseModel):
    """数据迁移响应"""
    success: bool
    message: str
    results: Dict[str, Dict[str, Any]]


class MigrationStatusResponse(BaseModel):
    """迁移状态响应"""
    success: bool
    schema_migrated: bool
    data_migrated: bool
    pending_tables: List[str]
    consistency_issues: List[str]


class TableStatusResponse(BaseModel):
    """表状态响应"""
    success: bool
    tables: Dict[str, Dict[str, Any]]


# ============ API端点 ============

@router.post("/schema", response_model=SchemaMigrationResponse)
async def run_schema_migration(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    执行数据库表结构迁移
    
    对应需求34/35/36:
    - 扩展learning_records表
    - 扩展user_profiles表和user_knowledge_mastery表
    - 创建新表（user_ability_history, user_interaction_logs等）
    """
    try:
        # 检查权限（仅管理员可执行）
        if not current_user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="仅管理员可执行迁移")
        
        logger.info("开始执行数据库表结构迁移")
        
        success = run_v3_migrations()
        
        if success:
            return SchemaMigrationResponse(
                success=True,
                message="数据库表结构迁移完成",
                details={
                    'extend_learning_records': True,
                    'extend_user_profiles': True,
                    'extend_user_knowledge_mastery': True,
                    'create_user_ability_history': True,
                    'create_user_interaction_logs': True,
                    'create_review_queue_settings': True
                }
            )
        else:
            return SchemaMigrationResponse(
                success=False,
                message="部分迁移失败，请检查日志",
                details={}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"表结构迁移失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data", response_model=DataMigrationResponse)
async def run_data_migration_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    执行V2到V3数据迁移
    
    对应需求37: 解决系统大版本升级带来的数据断层
    """
    try:
        # 检查权限
        if not current_user.get('is_admin', False):
            raise HTTPException(status_code=403, detail="仅管理员可执行迁移")
        
        logger.info("开始执行V2到V3数据迁移")
        
        results = run_data_migration()
        
        # 转换结果为可序列化格式
        response_results = {}
        for table_name, result in results.items():
            response_results[table_name] = {
                'total': result.total_records,
                'migrated': result.migrated_records,
                'failed': result.failed_records,
                'errors': result.errors[:5]  # 只返回前5个错误
            }
        
        all_success = all(r.failed_records == 0 for r in results.values())
        
        return DataMigrationResponse(
            success=all_success,
            message="数据迁移完成" if all_success else "部分迁移失败",
            results=response_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=MigrationStatusResponse)
async def get_migration_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取迁移状态
    
    检查哪些表已经迁移，哪些还需要迁移
    """
    try:
        from sqlalchemy import create_engine, inspect
        from utils.config import settings
        
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # 检查表是否存在
        existing_tables = inspector.get_table_names()
        
        # 检查V3新表
        v3_tables = [
            'user_ability_history',
            'user_interaction_logs',
            'review_queue_settings'
        ]
        
        pending_tables = [t for t in v3_tables if t not in existing_tables]
        
        # 检查现有表的V3字段
        schema_migrated = True
        
        if 'learning_records' in existing_tables:
            columns = [c['name'] for c in inspector.get_columns('learning_records')]
            if 'hint_count' not in columns:
                schema_migrated = False
        
        if 'user_profiles' in existing_tables:
            columns = [c['name'] for c in inspector.get_columns('user_profiles')]
            if 'theta' not in columns:
                schema_migrated = False
        
        # 检查数据一致性
        service = DataMigrationService()
        consistency = service.check_data_consistency()
        
        return MigrationStatusResponse(
            success=True,
            schema_migrated=schema_migrated and len(pending_tables) == 0,
            data_migrated=not consistency['has_issues'],
            pending_tables=pending_tables,
            consistency_issues=consistency['issues']
        )
        
    except Exception as e:
        logger.error(f"获取迁移状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table-status", response_model=TableStatusResponse)
async def get_table_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取各表的详细状态
    """
    try:
        from sqlalchemy import create_engine, inspect, text
        from utils.config import settings
        
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        tables = {}
        
        # 检查核心表
        core_tables = [
            'learning_records',
            'user_profiles',
            'user_knowledge_mastery',
            'user_ability_history',
            'user_interaction_logs',
            'review_queue_settings'
        ]
        
        for table_name in core_tables:
            if table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                column_names = [c['name'] for c in columns]
                
                # 获取记录数
                with engine.connect() as conn:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                
                tables[table_name] = {
                    'exists': True,
                    'column_count': len(columns),
                    'record_count': count,
                    'columns': column_names[:10]  # 只显示前10个字段
                }
            else:
                tables[table_name] = {
                    'exists': False,
                    'column_count': 0,
                    'record_count': 0,
                    'columns': []
                }
        
        return TableStatusResponse(
            success=True,
            tables=tables
        )
        
    except Exception as e:
        logger.error(f"获取表状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-consistency")
async def check_data_consistency(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查数据一致性
    
    检查是否存在数据断层问题
    """
    try:
        service = DataMigrationService()
        consistency = service.check_data_consistency()
        
        return {
            'success': True,
            'has_issues': consistency['has_issues'],
            'issues': consistency['issues'],
            'message': '发现数据问题' if consistency['has_issues'] else '数据一致性良好'
        }
        
    except Exception as e:
        logger.error(f"数据一致性检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def migration_health_check():
    """迁移服务健康检查"""
    try:
        from sqlalchemy import create_engine, inspect
        from utils.config import settings
        
        engine = create_engine(settings.database_url)
        inspector = inspect(engine)
        
        # 检查是否能连接数据库
        tables = inspector.get_table_names()
        
        return {
            'status': 'healthy',
            'database_connected': True,
            'total_tables': len(tables)
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'database_connected': False,
            'error': str(e)
        }
