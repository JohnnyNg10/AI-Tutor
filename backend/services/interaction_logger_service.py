"""
全量交互日志记录服务
全量记录用户在学习过程中的每一个微小交互

对应行号37: 全量记录用户在学习过程中的每一个微小交互，作为未来六维雷达图和算法优化的数据金矿

功能：
1. 记录所有用户交互（点击、输入、停留等）
2. 异步批量写入，避免阻塞主流程
3. 支持多种交互类型
4. 为六维雷达图和算法优化提供数据

实现文件: backend/services/interaction_logger_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy.ext.asyncio import AsyncSession

from services.redis_service import RedisService
from utils.logger import logger


class InteractionType(str, Enum):
    """交互类型"""
    PAGE_VIEW = "page_view"           # 页面浏览
    QUESTION_START = "question_start" # 开始答题
    QUESTION_SUBMIT = "question_submit" # 提交答案
    HINT_CLICK = "hint_click"         # 点击提示
    HINT_LEVEL_CHANGE = "hint_level_change" # 提示等级变化
    SKIP_CLICK = "skip_click"         # 点击跳过
    FAVORITE_CLICK = "favorite_click" # 点击收藏
    SCROLL = "scroll"                 # 滚动
    INPUT_FOCUS = "input_focus"       # 输入框聚焦
    INPUT_BLUR = "input_blur"         # 输入框失焦
    BUTTON_CLICK = "button_click"     # 按钮点击
    TAB_SWITCH = "tab_switch"         # 标签切换
    TIME_SPENT = "time_spent"         # 时间统计
    ERROR_OCCUR = "error_occur"       # 错误发生
    RECOVERY_ACTION = "recovery_action" # 恢复操作


@dataclass
class InteractionLog:
    """交互日志条目"""
    # 基础信息
    log_id: str
    user_id: int
    session_id: str
    timestamp: str
    
    # 交互信息
    interaction_type: str
    action: str
    
    # 上下文
    page_url: Optional[str] = None
    question_id: Optional[str] = None
    knowledge_point: Optional[str] = None
    
    # 详细数据
    data: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    device_info: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    
    # 处理状态
    processed: bool = False


class InteractionLoggerService:
    """
    全量交互日志记录服务
    
    功能：
    1. 全量记录用户交互
    2. 异步批量写入
    3. 支持多种交互类型
    4. 为算法优化提供数据
    """
    
    # Redis Key前缀
    INTERACTION_LOG_QUEUE = "ai:tutor:interaction:queue"
    INTERACTION_LOG_BUFFER = "ai:tutor:interaction:buffer:{user_id}"
    
    # 批量写入配置
    BATCH_SIZE = 100      # 每100条写入一次
    FLUSH_INTERVAL = 5    # 每5秒刷新一次
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        self.buffer: List[InteractionLog] = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._log_counter = 0
        logger.info("交互日志服务初始化完成")
    
    # ==================== 核心记录方法 ====================
    
    def log_interaction(
        self,
        user_id: int,
        interaction_type: InteractionType,
        action: str,
        **kwargs
    ) -> str:
        """
        记录交互
        
        对应行号37: 全量记录用户在学习过程中的每一个微小交互
        """
        try:
            # 生成日志ID
            self._log_counter += 1
            log_id = f"log_{user_id}_{datetime.now().timestamp()}_{self._log_counter}"
            
            # 创建日志条目
            log = InteractionLog(
                log_id=log_id,
                user_id=user_id,
                session_id=kwargs.get('session_id', ''),
                timestamp=datetime.now().isoformat(),
                interaction_type=interaction_type.value,
                action=action,
                page_url=kwargs.get('page_url'),
                question_id=kwargs.get('question_id'),
                knowledge_point=kwargs.get('knowledge_point'),
                data=kwargs.get('data', {}),
                device_info=kwargs.get('device_info'),
                ip_address=kwargs.get('ip_address')
            )
            
            # 添加到缓冲区
            self.buffer.append(log)
            
            # 检查是否需要批量写入
            if len(self.buffer) >= self.BATCH_SIZE:
                self._flush_buffer()
            
            return log_id
            
        except Exception as e:
            logger.error(f"记录交互失败: {e}")
            return ""
    
    def log_question_interaction(
        self,
        user_id: int,
        question_id: str,
        interaction_type: InteractionType,
        **kwargs
    ) -> str:
        """记录题目相关交互"""
        return self.log_interaction(
            user_id=user_id,
            interaction_type=interaction_type,
            action=kwargs.get('action', interaction_type.value),
            question_id=question_id,
            **kwargs
        )
    
    def log_hint_interaction(
        self,
        user_id: int,
        question_id: str,
        hint_level: int,
        action: str,
        **kwargs
    ) -> str:
        """记录提示交互"""
        return self.log_interaction(
            user_id=user_id,
            interaction_type=InteractionType.HINT_CLICK,
            action=action,
            question_id=question_id,
            data={'hint_level': hint_level, **kwargs.get('data', {})},
            **kwargs
        )
    
    def log_time_spent(
        self,
        user_id: int,
        question_id: str,
        time_seconds: int,
        **kwargs
    ) -> str:
        """记录停留时间"""
        return self.log_interaction(
            user_id=user_id,
            interaction_type=InteractionType.TIME_SPENT,
            action='time_record',
            question_id=question_id,
            data={'time_seconds': time_seconds, **kwargs.get('data', {})},
            **kwargs
        )
    
    # ==================== 批量写入 ====================
    
    def _flush_buffer(self) -> bool:
        """刷新缓冲区，批量写入"""
        try:
            if not self.buffer:
                return True
            
            # 将缓冲区数据转为JSON
            logs_data = [asdict(log) for log in self.buffer]
            
            # 写入Redis队列（异步处理）
            pipe = self.redis_service.redis_client.pipeline()
            for log_data in logs_data:
                pipe.lpush(self.INTERACTION_LOG_QUEUE, json.dumps(log_data))
            
            pipe.execute()
            
            logger.info(f"批量写入交互日志: {len(self.buffer)}条")
            
            # 清空缓冲区
            self.buffer = []
            
            return True
            
        except Exception as e:
            logger.error(f"批量写入交互日志失败: {e}")
            return False
    
    def flush(self) -> bool:
        """手动刷新缓冲区"""
        return self._flush_buffer()
    
    # ==================== 查询与分析 ====================
    
    async def get_user_interactions_async(
        self, db: AsyncSession, user_id: int,
        interaction_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """从 user_interaction_logs 表查询用户交互记录"""
        from sqlalchemy import select, desc
        from models.learning_analytics import UserInteractionLog
        try:
            stmt = (
                select(UserInteractionLog)
                .where(UserInteractionLog.user_id == user_id)
                .order_by(desc(UserInteractionLog.created_at))
                .limit(limit)
            )
            if interaction_type:
                stmt = stmt.where(UserInteractionLog.interaction_type == interaction_type)
            result = await db.execute(stmt)
            records = result.scalars().all()
            return [
                {'interaction_type': r.interaction_type, 'knowledge_points': r.knowledge_points,
                 'created_at': r.created_at.isoformat() if r.created_at else ''}
                for r in records
            ]
        except Exception:
            return []

    def get_user_interactions(
        self, user_id: int, interaction_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取用户交互记录（Redis 队列回退）"""
        try:
            logs = self.redis_service.redis_client.lrange(self.INTERACTION_LOG_QUEUE, 0, limit * 2)
            result = []
            for log_json in logs:
                try:
                    log_data = json.loads(log_json)
                    if log_data.get('user_id') == user_id:
                        if interaction_type is None or log_data.get('interaction_type') == interaction_type:
                            result.append(log_data)
                            if len(result) >= limit: break
                except: continue
            return result
        except Exception as e:
            logger.error(f"获取用户交互记录失败: {e}")
            return []
    
    def analyze_interaction_patterns(self, user_id: int) -> Dict[str, Any]:
        """
        分析交互模式
        
        为六维雷达图和算法优化提供数据
        """
        try:
            interactions = self.get_user_interactions(user_id, limit=1000)
            
            if not interactions:
                return {}
            
            # 统计各类交互次数
            type_counts = {}
            for interaction in interactions:
                itype = interaction.get('interaction_type', 'unknown')
                type_counts[itype] = type_counts.get(itype, 0) + 1
            
            # 计算平均停留时间
            time_spent_logs = [i for i in interactions if i.get('interaction_type') == 'time_spent']
            avg_time = sum(i.get('data', {}).get('time_seconds', 0) for i in time_spent_logs) / len(time_spent_logs) if time_spent_logs else 0
            
            # 提示使用频率
            hint_logs = [i for i in interactions if i.get('interaction_type') == 'hint_click']
            hint_frequency = len(hint_logs) / len(interactions) if interactions else 0
            
            return {
                'user_id': user_id,
                'total_interactions': len(interactions),
                'type_distribution': type_counts,
                'avg_time_per_question': round(avg_time, 1),
                'hint_usage_rate': round(hint_frequency, 2),
                'engagement_score': min(100, len(interactions) / 10)  # 参与度评分
            }
            
        except Exception as e:
            logger.error(f"分析交互模式失败: {e}")
            return {}
    
    def get_interaction_statistics(self) -> Dict[str, Any]:
        """获取交互统计"""
        try:
            queue_length = self.redis_service.redis_client.llen(self.INTERACTION_LOG_QUEUE)
            
            return {
                'queue_length': queue_length,
                'buffer_size': len(self.buffer),
                'batch_size': self.BATCH_SIZE,
                'flush_interval': self.FLUSH_INTERVAL
            }
            
        except Exception as e:
            logger.error(f"获取交互统计失败: {e}")
            return {}
    
    # ==================== 清理与维护 ====================
    
    async def clear_old_logs(self, db: AsyncSession, days: int = 30) -> int:
        """清理旧日志 - 从MySQL删除指定天数前的记录"""
        from sqlalchemy import delete
        from models.learning_analytics import UserInteractionLog
        from datetime import timedelta
        try:
            cutoff = datetime.now() - timedelta(days=days)
            stmt = delete(UserInteractionLog).where(UserInteractionLog.created_at < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            count = result.rowcount
            logger.info(f"清理{days}天前的交互日志: {count}条")
            return count
        except Exception as e:
            logger.error(f"清理旧日志失败: {e}")
            return 0


# ==================== 便捷函数 ====================

def log_user_interaction(
    user_id: int,
    interaction_type: InteractionType,
    action: str,
    **kwargs
) -> str:
    """便捷函数：记录用户交互"""
    service = InteractionLoggerService()
    return service.log_interaction(user_id, interaction_type, action, **kwargs)


def get_user_interaction_summary(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取用户交互摘要"""
    service = InteractionLoggerService()
    return service.analyze_interaction_patterns(user_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("交互日志服务测试")
    print("=" * 60)
    
    service = InteractionLoggerService()
    
    # 测试记录交互
    print("\n记录交互测试：")
    for i in range(5):
        log_id = service.log_interaction(
            user_id=1,
            interaction_type=InteractionType.BUTTON_CLICK,
            action='click_hint_button',
            question_id=f'q00{i}',
            data={'button': 'hint', 'level': i}
        )
        print(f"  记录{i+1}: {log_id[:20]}...")
    
    # 测试手动刷新
    print("\n刷新缓冲区测试：")
    service.flush()
    print("  缓冲区已刷新")
    
    # 测试分析
    print("\n交互分析测试：")
    analysis = service.analyze_interaction_patterns(1)
    print(f"  总交互数: {analysis.get('total_interactions', 0)}")
    
    print("\n测试完成")
