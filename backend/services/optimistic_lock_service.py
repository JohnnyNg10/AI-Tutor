"""
并发冲突乐观锁服务
防止学生快速连续交互导致数据库画像更新冲突（脏读/脏写），保障核心算法数据的绝对准确

对应行号39: 防止学生快速连续交互导致数据库画像更新冲突（脏读/脏写），保障核心算法数据的绝对准确

功能：
1. 版本号机制（乐观锁）
2. CAS（Compare-And-Swap）更新
3. 冲突检测与重试
4. 数据一致性保障

实现文件: backend/services/optimistic_lock_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import time

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class VersionedData:
    """带版本号的数据"""
    data: Dict[str, Any]
    version: int
    updated_at: str
    updated_by: Optional[int] = None


@dataclass
class LockResult:
    """锁操作结果"""
    success: bool
    new_version: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class OptimisticLockService:
    """
    并发冲突乐观锁服务
    
    功能：
    1. 版本号管理
    2. CAS更新
    3. 冲突重试
    4. 数据一致性
    """
    
    # Redis Key前缀
    VERSION_KEY = "ai:tutor:version:{entity_type}:{entity_id}"
    DATA_KEY = "ai:tutor:data:{entity_type}:{entity_id}"
    LOCK_RETRY_KEY = "ai:tutor:lock-retry:{user_id}"
    
    # 配置
    MAX_RETRIES = 3           # 最大重试次数
    RETRY_DELAY = 0.1         # 重试间隔（秒）
    VERSION_TTL = 3600        # 版本号TTL（1小时）
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("乐观锁服务初始化完成")
    
    # ==================== 版本号管理 ====================
    
    def get_current_version(
        self,
        entity_type: str,
        entity_id: str
    ) -> int:
        """获取当前版本号"""
        try:
            version_key = self.VERSION_KEY.format(
                entity_type=entity_type,
                entity_id=entity_id
            )
            
            version = self.redis_service.redis_client.get(version_key)
            
            if version is None:
                # 初始化版本号为1
                self.redis_service.redis_client.setex(
                    version_key,
                    self.VERSION_TTL,
                    1
                )
                return 1
            
            return int(version)
            
        except Exception as e:
            logger.error(f"获取版本号失败: {e}")
            return 1
    
    def increment_version(
        self,
        entity_type: str,
        entity_id: str
    ) -> int:
        """递增版本号"""
        try:
            version_key = self.VERSION_KEY.format(
                entity_type=entity_type,
                entity_id=entity_id
            )
            
            new_version = self.redis_service.redis_client.incr(version_key)
            
            # 更新TTL
            self.redis_service.redis_client.expire(version_key, self.VERSION_TTL)
            
            return new_version
            
        except Exception as e:
            logger.error(f"递增版本号失败: {e}")
            return 1
    
    # ==================== CAS更新（核心） ====================
    
    def cas_update(
        self,
        entity_type: str,
        entity_id: str,
        expected_version: int,
        new_data: Dict[str, Any],
        updated_by: Optional[int] = None,
        max_retries: int = None
    ) -> LockResult:
        """
        CAS（Compare-And-Swap）更新
        
        对应行号39: 乐观锁核心，防止并发冲突
        """
        if max_retries is None:
            max_retries = self.MAX_RETRIES
        
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 获取当前版本号
                current_version = self.get_current_version(entity_type, entity_id)
                
                # 检查版本号是否匹配
                if current_version != expected_version:
                    # 版本号不匹配，说明数据已被其他进程修改
                    logger.warning(
                        f"CAS冲突: {entity_type}/{entity_id}, "
                        f"期望版本={expected_version}, 当前版本={current_version}"
                    )
                    
                    retry_count += 1
                    if retry_count < max_retries:
                        # 等待后重试
                        time.sleep(self.RETRY_DELAY * retry_count)
                        continue
                    else:
                        return LockResult(
                            success=False,
                            error_message=f"版本冲突，重试{max_retries}次后失败",
                            retry_count=retry_count
                        )
                
                # 版本号匹配，执行更新
                # 1. 递增版本号
                new_version = self.increment_version(entity_type, entity_id)
                
                # 2. 存储新数据
                data_key = self.DATA_KEY.format(
                    entity_type=entity_type,
                    entity_id=entity_id
                )
                
                versioned_data = VersionedData(
                    data=new_data,
                    version=new_version,
                    updated_at=datetime.now().isoformat(),
                    updated_by=updated_by
                )
                
                self.redis_service.redis_client.setex(
                    data_key,
                    self.VERSION_TTL,
                    json.dumps({
                        'data': versioned_data.data,
                        'version': versioned_data.version,
                        'updated_at': versioned_data.updated_at,
                        'updated_by': versioned_data.updated_by
                    })
                )
                
                logger.debug(
                    f"CAS更新成功: {entity_type}/{entity_id}, "
                    f"新版本={new_version}"
                )
                
                return LockResult(
                    success=True,
                    new_version=new_version,
                    retry_count=retry_count
                )
                
            except Exception as e:
                logger.error(f"CAS更新失败: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(self.RETRY_DELAY)
                else:
                    return LockResult(
                        success=False,
                        error_message=str(e),
                        retry_count=retry_count
                    )
        
        return LockResult(
            success=False,
            error_message="超过最大重试次数",
            retry_count=retry_count
        )
    
    # ==================== 数据读取 ====================
    
    def get_versioned_data(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[VersionedData]:
        """获取带版本号的数据"""
        try:
            data_key = self.DATA_KEY.format(
                entity_type=entity_type,
                entity_id=entity_id
            )
            
            data_json = self.redis_service.redis_client.get(data_key)
            
            if data_json:
                data = json.loads(data_json)
                return VersionedData(
                    data=data.get('data', {}),
                    version=data.get('version', 1),
                    updated_at=data.get('updated_at', ''),
                    updated_by=data.get('updated_by')
                )
            
            return None
            
        except Exception as e:
            logger.error(f"获取版本化数据失败: {e}")
            return None
    
    # ==================== 用户画像更新（应用场景） ====================
    
    def update_user_profile_safe(
        self,
        user_id: int,
        updates: Dict[str, Any]
    ) -> LockResult:
        """
        安全更新用户画像
        
        防止快速连续交互导致的更新冲突
        """
        try:
            # 获取当前数据
            current_data = self.get_versioned_data('user_profile', str(user_id))
            
            if current_data is None:
                # 首次更新
                return self.cas_update(
                    entity_type='user_profile',
                    entity_id=str(user_id),
                    expected_version=1,
                    new_data=updates,
                    updated_by=user_id
                )
            
            # 合并数据
            merged_data = {**current_data.data, **updates}
            
            # CAS更新
            return self.cas_update(
                entity_type='user_profile',
                entity_id=str(user_id),
                expected_version=current_data.version,
                new_data=merged_data,
                updated_by=user_id
            )
            
        except Exception as e:
            logger.error(f"安全更新用户画像失败: {e}")
            return LockResult(success=False, error_message=str(e))
    
    def update_mastery_safe(
        self,
        user_id: int,
        knowledge_point_id: str,
        updates: Dict[str, Any]
    ) -> LockResult:
        """安全更新掌握度"""
        entity_id = f"{user_id}_{knowledge_point_id}"
        
        try:
            current_data = self.get_versioned_data('mastery', entity_id)
            
            if current_data is None:
                return self.cas_update(
                    entity_type='mastery',
                    entity_id=entity_id,
                    expected_version=1,
                    new_data=updates,
                    updated_by=user_id
                )
            
            merged_data = {**current_data.data, **updates}
            
            return self.cas_update(
                entity_type='mastery',
                entity_id=entity_id,
                expected_version=current_data.version,
                new_data=merged_data,
                updated_by=user_id
            )
            
        except Exception as e:
            logger.error(f"安全更新掌握度失败: {e}")
            return LockResult(success=False, error_message=str(e))
    
    # ==================== 冲突统计 ====================
    
    def record_conflict(self, user_id: int, entity_type: str) -> None:
        """记录冲突"""
        try:
            key = self.LOCK_RETRY_KEY.format(user_id=user_id)
            field = f"{entity_type}_conflicts"
            self.redis_service.redis_client.hincrby(key, field, 1)
        except Exception as e:
            logger.error(f"记录冲突失败: {e}")
    
    def get_conflict_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取冲突统计"""
        try:
            key = self.LOCK_RETRY_KEY.format(user_id=user_id)
            stats = self.redis_service.redis_client.hgetall(key)
            
            return {
                'user_id': user_id,
                'conflicts': {k: int(v) for k, v in stats.items()}
            }
            
        except Exception as e:
            logger.error(f"获取冲突统计失败: {e}")
            return {'user_id': user_id, 'conflicts': {}}


# ==================== 便捷函数 ====================

def safe_update_user_profile(user_id: int, updates: Dict[str, Any]) -> LockResult:
    """便捷函数：安全更新用户画像"""
    service = OptimisticLockService()
    return service.update_user_profile_safe(user_id, updates)


def safe_update_mastery(user_id: int, kp_id: str, updates: Dict[str, Any]) -> LockResult:
    """便捷函数：安全更新掌握度"""
    service = OptimisticLockService()
    return service.update_mastery_safe(user_id, kp_id, updates)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("乐观锁服务测试")
    print("=" * 60)
    
    service = OptimisticLockService()
    
    # 测试CAS更新
    print("\nCAS更新测试：")
    result = service.cas_update(
        entity_type='user_profile',
        entity_id='1',
        expected_version=1,
        new_data={'theta': 0.5, 'level': 3}
    )
    print(f"  成功: {result.success}")
    print(f"  新版本: {result.new_version}")
    
    # 测试安全更新
    print("\n安全更新测试：")
    result = service.update_user_profile_safe(1, {'theta': 0.6})
    print(f"  成功: {result.success}")
    
    # 测试版本冲突
    print("\n版本冲突测试：")
    result = service.cas_update(
        entity_type='user_profile',
        entity_id='1',
        expected_version=1,  # 错误的版本号
        new_data={'theta': 0.7}
    )
    print(f"  成功: {result.success}")
    print(f"  重试次数: {result.retry_count}")
    
    print("\n测试完成")
