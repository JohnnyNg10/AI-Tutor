"""
交互日志表分区归档服务
防止新引入的 user_interaction_logs 表无限制膨胀撑爆数据库磁盘

对应行号40: 防止新引入的 user_interaction_logs 表无限制膨胀撑爆数据库磁盘

功能：
1. 按时间分区存储交互日志
2. 自动归档旧数据
3. 分区管理和清理
4. 磁盘空间监控

实现文件: backend/services/log_partitioning_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import hashlib

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class LogPartition:
    """日志分区"""
    partition_name: str
    start_date: str
    end_date: str
    record_count: int
    size_mb: float
    is_archived: bool
    archived_at: Optional[str] = None


@dataclass
class PartitionStats:
    """分区统计"""
    total_partitions: int
    total_records: int
    total_size_mb: float
    archived_partitions: int
    active_partitions: int


class LogPartitioningService:
    """
    交互日志表分区归档服务
    
    功能：
    1. 按时间分区存储
    2. 自动归档旧数据
    3. 分区管理和清理
    4. 磁盘空间监控
    """
    
    # Redis Key前缀
    PARTITION_INDEX_KEY = "ai:tutor:log-partitions:index"
    PARTITION_META_KEY = "ai:tutor:log-partition:{partition_name}"
    CURRENT_PARTITION_KEY = "ai:tutor:log-partition:current"
    ARCHIVE_QUEUE_KEY = "ai:tutor:log-archive:queue"
    
    # 分区配置
    PARTITION_DAYS = 7           # 每个分区7天
    MAX_ACTIVE_PARTITIONS = 4    # 最多4个活跃分区（28天）
    ARCHIVE_AFTER_DAYS = 30      # 30天后归档
    DELETE_AFTER_DAYS = 90       # 90天后删除
    MAX_PARTITION_SIZE_MB = 500  # 单个分区最大500MB
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("日志分区服务初始化完成")
    
    # ==================== 分区管理 ====================
    
    def get_current_partition(self) -> str:
        """获取当前分区名称"""
        try:
            current = self.redis_service.redis_client.get(self.CURRENT_PARTITION_KEY)
            
            if current is None:
                # 创建新分区
                current = self._create_new_partition()
            else:
                # 检查是否需要切换分区
                current = current.decode('utf-8') if isinstance(current, bytes) else current
                if self._should_switch_partition(current):
                    current = self._create_new_partition()
            
            return current
            
        except Exception as e:
            logger.error(f"获取当前分区失败: {e}")
            return self._create_new_partition()
    
    def _create_new_partition(self) -> str:
        """创建新分区"""
        try:
            # 生成分区名：log_YYYY_MM_DD
            today = datetime.now()
            partition_name = f"log_{today.strftime('%Y_%m_%d')}"
            
            # 计算分区时间范围
            start_date = today.strftime('%Y-%m-%d')
            end_date = (today + timedelta(days=self.PARTITION_DAYS)).strftime('%Y-%m-%d')
            
            # 保存分区元数据
            meta_key = self.PARTITION_META_KEY.format(partition_name=partition_name)
            self.redis_service.redis_client.hset(meta_key, mapping={
                'partition_name': partition_name,
                'start_date': start_date,
                'end_date': end_date,
                'record_count': 0,
                'size_mb': 0.0,
                'is_archived': 'false',
                'created_at': datetime.now().isoformat()
            })
            
            # 添加到分区索引
            self.redis_service.redis_client.zadd(
                self.PARTITION_INDEX_KEY,
                {partition_name: today.timestamp()}
            )
            
            # 设置为当前分区
            self.redis_service.redis_client.set(
                self.CURRENT_PARTITION_KEY,
                partition_name
            )
            
            logger.info(f"创建新分区: {partition_name}")
            
            return partition_name
            
        except Exception as e:
            logger.error(f"创建新分区失败: {e}")
            return "log_default"
    
    def _should_switch_partition(self, current_partition: str) -> bool:
        """检查是否需要切换分区"""
        try:
            # 获取当前分区元数据
            meta_key = self.PARTITION_META_KEY.format(partition_name=current_partition)
            meta = self.redis_service.redis_client.hgetall(meta_key)
            
            if not meta:
                return True
            
            # 检查分区是否已满
            record_count = int(meta.get(b'record_count', 0))
            size_mb = float(meta.get(b'size_mb', 0))
            
            if record_count >= 100000 or size_mb >= self.MAX_PARTITION_SIZE_MB:
                logger.info(f"分区 {current_partition} 已满，需要切换")
                return True
            
            # 检查是否超过时间范围
            end_date = meta.get(b'end_date', b'').decode('utf-8') if isinstance(meta.get(b'end_date'), bytes) else meta.get('end_date', '')
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d')
                if datetime.now() >= end:
                    logger.info(f"分区 {current_partition} 时间到期，需要切换")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查分区切换失败: {e}")
            return False
    
    # ==================== 日志写入 ====================
    
    def write_log_to_partition(
        self,
        log_data: Dict[str, Any],
        partition_name: Optional[str] = None
    ) -> bool:
        """写入日志到分区"""
        try:
            if partition_name is None:
                partition_name = self.get_current_partition()
            
            # 生成分区内的key
            log_id = log_data.get('log_id', f"log_{datetime.now().timestamp()}")
            partition_key = f"ai:tutor:logs:{partition_name}"
            
            # 写入日志
            self.redis_service.redis_client.zadd(
                partition_key,
                {json.dumps(log_data): datetime.now().timestamp()}
            )
            
            # 更新分区统计
            self._update_partition_stats(partition_name, len(json.dumps(log_data)))
            
            return True
            
        except Exception as e:
            logger.error(f"写入日志到分区失败: {e}")
            return False
    
    def _update_partition_stats(self, partition_name: str, log_size_bytes: int) -> None:
        """更新分区统计"""
        try:
            meta_key = self.PARTITION_META_KEY.format(partition_name=partition_name)
            
            # 增加记录数
            self.redis_service.redis_client.hincrby(meta_key, 'record_count', 1)
            
            # 增加大小（MB）
            size_mb = log_size_bytes / (1024 * 1024)
            self.redis_service.redis_client.hincrbyfloat(meta_key, 'size_mb', size_mb)
            
        except Exception as e:
            logger.error(f"更新分区统计失败: {e}")
    
    # ==================== 归档管理 ====================
    
    def archive_old_partitions(self) -> Dict[str, Any]:
        """
        归档旧分区
        
        对应行号40: 自动归档旧数据
        """
        try:
            # 获取所有分区
            all_partitions = self._get_all_partitions()
            
            archived = []
            errors = []
            
            cutoff_date = datetime.now() - timedelta(days=self.ARCHIVE_AFTER_DAYS)
            
            for partition in all_partitions:
                # 检查是否需要归档
                end_date = datetime.strptime(partition.end_date, '%Y-%m-%d')
                
                if end_date < cutoff_date and not partition.is_archived:
                    result = self._archive_partition(partition.partition_name)
                    if result['success']:
                        archived.append(partition.partition_name)
                    else:
                        errors.append({
                            'partition': partition.partition_name,
                            'error': result['error']
                        })
            
            return {
                'success': len(errors) == 0,
                'archived_count': len(archived),
                'archived_partitions': archived,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"归档旧分区失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _archive_partition(self, partition_name: str) -> Dict[str, Any]:
        """归档单个分区"""
        try:
            # TODO: 实际归档逻辑（如写入S3、文件等）
            # 这里模拟归档
            
            meta_key = self.PARTITION_META_KEY.format(partition_name=partition_name)
            
            # 标记为已归档
            self.redis_service.redis_client.hset(meta_key, 'is_archived', 'true')
            self.redis_service.redis_client.hset(
                meta_key,
                'archived_at',
                datetime.now().isoformat()
            )
            
            # 添加到归档队列
            self.redis_service.redis_client.lpush(
                self.ARCHIVE_QUEUE_KEY,
                partition_name
            )
            
            logger.info(f"分区归档成功: {partition_name}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"归档分区失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_expired_partitions(self) -> Dict[str, Any]:
        """删除过期分区"""
        try:
            all_partitions = self._get_all_partitions()
            
            deleted = []
            errors = []
            
            cutoff_date = datetime.now() - timedelta(days=self.DELETE_AFTER_DAYS)
            
            for partition in all_partitions:
                # 检查是否已归档且过期
                end_date = datetime.strptime(partition.end_date, '%Y-%m-%d')
                
                if partition.is_archived and end_date < cutoff_date:
                    result = self._delete_partition(partition.partition_name)
                    if result['success']:
                        deleted.append(partition.partition_name)
                    else:
                        errors.append({
                            'partition': partition.partition_name,
                            'error': result['error']
                        })
            
            return {
                'success': len(errors) == 0,
                'deleted_count': len(deleted),
                'deleted_partitions': deleted,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"删除过期分区失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _delete_partition(self, partition_name: str) -> Dict[str, Any]:
        """删除单个分区"""
        try:
            # 删除分区数据
            partition_key = f"ai:tutor:logs:{partition_name}"
            self.redis_service.redis_client.delete(partition_key)
            
            # 删除分区元数据
            meta_key = self.PARTITION_META_KEY.format(partition_name=partition_name)
            self.redis_service.redis_client.delete(meta_key)
            
            # 从索引中移除
            self.redis_service.redis_client.zrem(
                self.PARTITION_INDEX_KEY,
                partition_name
            )
            
            logger.info(f"分区删除成功: {partition_name}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"删除分区失败: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== 查询与统计 ====================
    
    def _get_all_partitions(self) -> List[LogPartition]:
        """获取所有分区"""
        try:
            partition_names = self.redis_service.redis_client.zrange(
                self.PARTITION_INDEX_KEY, 0, -1
            )
            
            partitions = []
            for name in partition_names:
                name = name.decode('utf-8') if isinstance(name, bytes) else name
                
                meta_key = self.PARTITION_META_KEY.format(partition_name=name)
                meta = self.redis_service.redis_client.hgetall(meta_key)
                
                if meta:
                    partitions.append(LogPartition(
                        partition_name=name,
                        start_date=meta.get(b'start_date', b'').decode('utf-8') if isinstance(meta.get(b'start_date'), bytes) else meta.get('start_date', ''),
                        end_date=meta.get(b'end_date', b'').decode('utf-8') if isinstance(meta.get(b'end_date'), bytes) else meta.get('end_date', ''),
                        record_count=int(meta.get(b'record_count', 0)),
                        size_mb=float(meta.get(b'size_mb', 0)),
                        is_archived=meta.get(b'is_archived', b'false') == b'true' or meta.get('is_archived') == 'true',
                        archived_at=meta.get(b'archived_at', b'').decode('utf-8') if isinstance(meta.get(b'archived_at'), bytes) else meta.get('archived_at')
                    ))
            
            return partitions
            
        except Exception as e:
            logger.error(f"获取所有分区失败: {e}")
            return []
    
    def get_partition_statistics(self) -> PartitionStats:
        """获取分区统计"""
        try:
            partitions = self._get_all_partitions()
            
            total_records = sum(p.record_count for p in partitions)
            total_size = sum(p.size_mb for p in partitions)
            archived_count = sum(1 for p in partitions if p.is_archived)
            
            return PartitionStats(
                total_partitions=len(partitions),
                total_records=total_records,
                total_size_mb=round(total_size, 2),
                archived_partitions=archived_count,
                active_partitions=len(partitions) - archived_count
            )
            
        except Exception as e:
            logger.error(f"获取分区统计失败: {e}")
            return PartitionStats(0, 0, 0.0, 0, 0)
    
    def query_logs_from_partition(
        self,
        partition_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """从分区查询日志"""
        try:
            partition_key = f"ai:tutor:logs:{partition_name}"
            
            # 构建时间范围
            start_ts = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp() if start_time else 0
            end_ts = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp() if end_time else datetime.now().timestamp()
            
            # 查询
            logs = self.redis_service.redis_client.zrangebyscore(
                partition_key, start_ts, end_ts, start=0, num=limit
            )
            
            return [json.loads(log) for log in logs]
            
        except Exception as e:
            logger.error(f"查询分区日志失败: {e}")
            return []
    
    # ==================== 磁盘监控 ====================
    
    def check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间"""
        try:
            stats = self.get_partition_statistics()
            
            # 警告阈值
            warning_threshold = 5000  # 5GB
            critical_threshold = 8000  # 8GB
            
            status = 'normal'
            if stats.total_size_mb > critical_threshold:
                status = 'critical'
            elif stats.total_size_mb > warning_threshold:
                status = 'warning'
            
            return {
                'total_size_mb': stats.total_size_mb,
                'total_size_gb': round(stats.total_size_mb / 1024, 2),
                'status': status,
                'warning_threshold_mb': warning_threshold,
                'critical_threshold_mb': critical_threshold,
                'recommendation': self._get_space_recommendation(stats.total_size_mb)
            }
            
        except Exception as e:
            logger.error(f"检查磁盘空间失败: {e}")
            return {'error': str(e)}
    
    def _get_space_recommendation(self, total_size_mb: float) -> str:
        """获取空间建议"""
        if total_size_mb > 8000:
            return "磁盘空间严重不足，建议立即归档或删除旧分区"
        elif total_size_mb > 5000:
            return "磁盘空间紧张，建议归档30天前的分区"
        elif total_size_mb > 3000:
            return "磁盘空间正常，建议定期监控"
        else:
            return "磁盘空间充足"


# ==================== 便捷函数 ====================

def get_current_log_partition() -> str:
    """便捷函数：获取当前日志分区"""
    service = LogPartitioningService()
    return service.get_current_partition()


def write_log_to_current_partition(log_data: Dict[str, Any]) -> bool:
    """便捷函数：写入日志到当前分区"""
    service = LogPartitioningService()
    return service.write_log_to_partition(log_data)


def archive_old_logs() -> Dict[str, Any]:
    """便捷函数：归档旧日志"""
    service = LogPartitioningService()
    return service.archive_old_partitions()


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("日志分区服务测试")
    print("=" * 60)
    
    service = LogPartitioningService()
    
    # 测试获取当前分区
    print("\n获取当前分区测试：")
    partition = service.get_current_partition()
    print(f"  当前分区: {partition}")
    
    # 测试写入日志
    print("\n写入日志测试：")
    for i in range(5):
        result = service.write_log_to_partition({
            'log_id': f'test_{i}',
            'timestamp': datetime.now().isoformat(),
            'data': f'test data {i}'
        })
        print(f"  写入{i+1}: {'成功' if result else '失败'}")
    
    # 测试统计
    print("\n分区统计测试：")
    stats = service.get_partition_statistics()
    print(f"  分区数: {stats.total_partitions}")
    print(f"  总记录: {stats.total_records}")
    print(f"  总大小: {stats.total_size_mb} MB")
    
    # 测试磁盘检查
    print("\n磁盘空间检查：")
    space = service.check_disk_space()
    print(f"  状态: {space['status']}")
    print(f"  大小: {space.get('total_size_gb', 0)} GB")
    
    print("\n测试完成")
