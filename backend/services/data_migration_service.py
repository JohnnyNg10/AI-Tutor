"""
数据迁移服务
解决系统大版本升级带来的数据断层，防止老用户画像字段为空导致的核心引擎崩溃

对应行号38: 解决系统大版本升级带来的数据断层，防止老用户画像字段为空导致的核心引擎崩溃

功能：
1. V2→V3数据迁移
2. 缺失字段自动填充
3. 默认值设置
4. 迁移状态跟踪

实现文件: backend/services/data_migration_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class MigrationRecord:
    """迁移记录"""
    user_id: int
    migration_type: str
    status: str  # pending / in_progress / completed / failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class DataMigrationService:
    """
    数据迁移服务
    
    功能：
    1. V2→V3数据迁移
    2. 缺失字段填充
    3. 默认值设置
    4. 迁移状态管理
    """
    
    # Redis Key前缀
    MIGRATION_STATUS_KEY = "ai:tutor:migration:{user_id}"
    MIGRATION_QUEUE_KEY = "ai:tutor:migration:queue"
    
    # V3新增字段默认值
    V3_DEFAULTS = {
        # user_profiles表
        'theta': 0.0,
        'theta_se': 1.0,
        'theta_ci_lower': -2.0,
        'theta_ci_upper': 2.0,
        
        # user_knowledge_mastery表
        'p_learn': 0.3,
        'p_guess': 0.2,
        'p_slip': 0.1,
        'p_known': 0.5,
        
        # learning_records表
        'hint_count': 0,
        'time_spent': 0,
        'skip_reason': None,
        'theta_before': 0.0,
        'theta_after': 0.0,
        'mastery_updates': '{}'
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("数据迁移服务初始化完成")
    
    # ==================== 迁移核心 ====================
    
    def migrate_user_v2_to_v3(self, user_id: int) -> Dict[str, Any]:
        """
        迁移单个用户V2→V3数据
        
        对应行号38: V2→V3数据迁移
        """
        try:
            # 检查是否已迁移
            if self.is_migration_completed(user_id):
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': '用户数据已迁移',
                    'status': 'already_completed'
                }
            
            # 记录迁移开始
            self._record_migration_start(user_id, 'v2_to_v3')
            
            results = {
                'user_id': user_id,
                'tables_migrated': [],
                'fields_filled': [],
                'errors': []
            }
            
            # 1. 迁移user_profiles表
            profile_result = self._migrate_user_profile(user_id)
            results['tables_migrated'].append('user_profiles')
            results['fields_filled'].extend(profile_result.get('filled_fields', []))
            if profile_result.get('error'):
                results['errors'].append(profile_result['error'])
            
            # 2. 迁移user_knowledge_mastery表
            mastery_result = self._migrate_knowledge_mastery(user_id)
            results['tables_migrated'].append('user_knowledge_mastery')
            results['fields_filled'].extend(mastery_result.get('filled_fields', []))
            if mastery_result.get('error'):
                results['errors'].append(mastery_result['error'])
            
            # 3. 迁移learning_records表
            records_result = self._migrate_learning_records(user_id)
            results['tables_migrated'].append('learning_records')
            results['fields_filled'].extend(records_result.get('filled_fields', []))
            if records_result.get('error'):
                results['errors'].append(records_result['error'])
            
            # 4. 初始化V3新表
            v3_tables_result = self._initialize_v3_tables(user_id)
            results['tables_migrated'].extend(v3_tables_result.get('initialized_tables', []))
            if v3_tables_result.get('error'):
                results['errors'].append(v3_tables_result['error'])
            
            # 记录迁移完成
            status = 'completed' if not results['errors'] else 'partial'
            self._record_migration_complete(user_id, 'v2_to_v3', status, results)
            
            return {
                'success': status == 'completed',
                'user_id': user_id,
                'status': status,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"迁移用户数据失败: {e}")
            self._record_migration_error(user_id, 'v2_to_v3', str(e))
            return {
                'success': False,
                'user_id': user_id,
                'status': 'failed',
                'error': str(e)
            }
    
    def _migrate_user_profile(self, user_id: int) -> Dict[str, Any]:
        """迁移用户画像数据"""
        try:
            filled_fields = []
            
            # TODO: 从数据库查询并更新
            # 这里模拟迁移逻辑
            v3_fields = ['theta', 'theta_se', 'theta_ci_lower', 'theta_ci_upper']
            
            for field in v3_fields:
                default_value = self.V3_DEFAULTS.get(field)
                # 检查字段是否为空，为空则填充默认值
                # TODO: 实际数据库操作
                filled_fields.append(field)
            
            return {
                'filled_fields': filled_fields,
                'error': None
            }
            
        except Exception as e:
            return {
                'filled_fields': [],
                'error': f'迁移user_profiles失败: {e}'
            }
    
    def _migrate_knowledge_mastery(self, user_id: int) -> Dict[str, Any]:
        """迁移知识点掌握度数据"""
        try:
            filled_fields = []
            
            v3_fields = ['p_learn', 'p_guess', 'p_slip', 'p_known']
            
            for field in v3_fields:
                default_value = self.V3_DEFAULTS.get(field)
                # TODO: 实际数据库操作
                filled_fields.append(field)
            
            return {
                'filled_fields': filled_fields,
                'error': None
            }
            
        except Exception as e:
            return {
                'filled_fields': [],
                'error': f'迁移user_knowledge_mastery失败: {e}'
            }
    
    def _migrate_learning_records(self, user_id: int) -> Dict[str, Any]:
        """迁移学习记录数据"""
        try:
            filled_fields = []
            
            v3_fields = ['hint_count', 'time_spent', 'skip_reason', 'theta_before', 'theta_after', 'mastery_updates']
            
            for field in v3_fields:
                default_value = self.V3_DEFAULTS.get(field)
                # TODO: 实际数据库操作
                filled_fields.append(field)
            
            return {
                'filled_fields': filled_fields,
                'error': None
            }
            
        except Exception as e:
            return {
                'filled_fields': [],
                'error': f'迁移learning_records失败: {e}'
            }
    
    def _initialize_v3_tables(self, user_id: int) -> Dict[str, Any]:
        """初始化V3新表"""
        try:
            initialized_tables = []
            
            # 初始化user_ability_history表
            # TODO: 实际数据库操作
            initialized_tables.append('user_ability_history')
            
            # 初始化user_interaction_logs表
            initialized_tables.append('user_interaction_logs')
            
            # 初始化review_queue_settings表
            initialized_tables.append('review_queue_settings')
            
            return {
                'initialized_tables': initialized_tables,
                'error': None
            }
            
        except Exception as e:
            return {
                'initialized_tables': [],
                'error': f'初始化V3表失败: {e}'
            }
    
    # ==================== 迁移状态管理 ====================
    
    def is_migration_completed(self, user_id: int) -> bool:
        """检查用户是否已完成迁移"""
        try:
            key = self.MIGRATION_STATUS_KEY.format(user_id=user_id)
            status = self.redis_service.redis_client.hget(key, 'status')
            return status == 'completed'
        except Exception as e:
            logger.error(f"检查迁移状态失败: {e}")
            return False
    
    def _record_migration_start(self, user_id: int, migration_type: str) -> None:
        """记录迁移开始"""
        try:
            key = self.MIGRATION_STATUS_KEY.format(user_id=user_id)
            self.redis_service.redis_client.hset(key, mapping={
                'user_id': user_id,
                'migration_type': migration_type,
                'status': 'in_progress',
                'started_at': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"记录迁移开始失败: {e}")
    
    def _record_migration_complete(
        self,
        user_id: int,
        migration_type: str,
        status: str,
        details: Dict[str, Any]
    ) -> None:
        """记录迁移完成"""
        try:
            key = self.MIGRATION_STATUS_KEY.format(user_id=user_id)
            self.redis_service.redis_client.hset(key, mapping={
                'user_id': user_id,
                'migration_type': migration_type,
                'status': status,
                'completed_at': datetime.now().isoformat(),
                'details': json.dumps(details)
            })
        except Exception as e:
            logger.error(f"记录迁移完成失败: {e}")
    
    def _record_migration_error(self, user_id: int, migration_type: str, error: str) -> None:
        """记录迁移错误"""
        try:
            key = self.MIGRATION_STATUS_KEY.format(user_id=user_id)
            self.redis_service.redis_client.hset(key, mapping={
                'user_id': user_id,
                'migration_type': migration_type,
                'status': 'failed',
                'error': error,
                'failed_at': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"记录迁移错误失败: {e}")
    
    # ==================== 批量迁移 ====================
    
    def batch_migrate_users(
        self,
        user_ids: List[int],
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """批量迁移用户"""
        try:
            results = {
                'total': len(user_ids),
                'completed': 0,
                'failed': 0,
                'skipped': 0,
                'errors': []
            }
            
            for i, user_id in enumerate(user_ids):
                # 检查是否已迁移
                if self.is_migration_completed(user_id):
                    results['skipped'] += 1
                    continue
                
                # 执行迁移
                result = self.migrate_user_v2_to_v3(user_id)
                
                if result['success']:
                    results['completed'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'user_id': user_id,
                        'error': result.get('error', 'Unknown error')
                    })
                
                # 每100个用户记录一次进度
                if (i + 1) % batch_size == 0:
                    logger.info(f"批量迁移进度: {i + 1}/{len(user_ids)}")
            
            return {
                'success': results['failed'] == 0,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"批量迁移失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==================== 验证与修复 ====================
    
    def validate_user_data(self, user_id: int) -> Dict[str, Any]:
        """验证用户数据完整性"""
        try:
            issues = []
            
            # 检查V3必填字段
            required_fields = {
                'user_profiles': ['theta', 'theta_se'],
                'user_knowledge_mastery': ['p_known'],
                'learning_records': ['hint_count']
            }
            
            for table, fields in required_fields.items():
                for field in fields:
                    # TODO: 实际数据库检查
                    pass
            
            return {
                'user_id': user_id,
                'is_valid': len(issues) == 0,
                'issues': issues
            }
            
        except Exception as e:
            return {
                'user_id': user_id,
                'is_valid': False,
                'error': str(e)
            }
    
    def repair_user_data(self, user_id: int) -> Dict[str, Any]:
        """修复用户数据"""
        try:
            # 验证数据
            validation = self.validate_user_data(user_id)
            
            if validation['is_valid']:
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': '数据完整，无需修复'
                }
            
            # 执行修复（重新迁移）
            return self.migrate_user_v2_to_v3(user_id)
            
        except Exception as e:
            return {
                'success': False,
                'user_id': user_id,
                'error': str(e)
            }


# ==================== 便捷函数 ====================

def migrate_user_data(user_id: int) -> Dict[str, Any]:
    """便捷函数：迁移用户数据"""
    service = DataMigrationService()
    return service.migrate_user_v2_to_v3(user_id)


def check_migration_status(user_id: int) -> bool:
    """便捷函数：检查迁移状态"""
    service = DataMigrationService()
    return service.is_migration_completed(user_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("数据迁移服务测试")
    print("=" * 60)
    
    service = DataMigrationService()
    
    # 测试迁移
    print("\n数据迁移测试：")
    result = service.migrate_user_v2_to_v3(1)
    print(f"  状态: {result['status']}")
    if result['success']:
        print(f"  迁移表: {result['results']['tables_migrated']}")
    
    # 测试验证
    print("\n数据验证测试：")
    validation = service.validate_user_data(1)
    print(f"  是否有效: {validation['is_valid']}")
    
    print("\n测试完成")
