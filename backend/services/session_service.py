"""
Session状态服务
管理Agent对话的临时状态

对应需求27: 在Redis中维护当前Session的临时状态

实现文件：backend/services/session_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any
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
class SessionState:
    """Session状态"""
    session_id: str
    user_id: int
    question_id: str
    hint_level: int
    conversation_summary: str
    last_message: str
    message_count: int
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionService:
    """
    Session状态服务
    
    功能：
    1. Session Hash结构管理
    2. 题号、hint_level、对话摘要存储
    3. Session生命周期管理
    4. 多轮对话上下文维护
    """
    
    # Redis Key前缀
    SESSION_KEY_PREFIX = "ai:tutor:session:{session_id}"
    USER_SESSIONS_KEY = "ai:tutor:user-sessions:{user_id}"
    
    # Session TTL（2小时）
    SESSION_TTL = 2 * 60 * 60  # 秒
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("Session服务初始化完成")
    
    # ==================== Session创建与管理 ====================
    
    def create_session(
        self,
        user_id: int,
        question_id: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        创建新Session
        
        对应需求27: 创建Session，存储题号等基本信息
        """
        try:
            # 生成Session ID（如果没有提供）
            if not session_id:
                session_id = f"{user_id}_{question_id}_{int(datetime.now().timestamp())}"
            
            session_key = self.SESSION_KEY_PREFIX.format(session_id=session_id)
            
            now = datetime.now().isoformat()
            
            # 存储Session基本信息
            session_data = {
                'session_id': session_id,
                'user_id': str(user_id),
                'question_id': question_id,
                'hint_level': '0',
                'conversation_summary': '',
                'last_message': '',
                'message_count': '0',
                'created_at': now,
                'updated_at': now
            }
            
            self.redis_service.redis_client.hset(session_key, mapping=session_data)
            
            # 设置TTL
            self.redis_service.redis_client.expire(session_key, self.SESSION_TTL)
            
            # 记录用户Session列表
            user_sessions_key = self.USER_SESSIONS_KEY.format(user_id=user_id)
            self.redis_service.redis_client.zadd(
                user_sessions_key,
                {session_id: datetime.now().timestamp()}
            )
            
            logger.info(f"Session创建成功: {session_id}, 用户={user_id}, 题目={question_id}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"创建Session失败: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取Session状态"""
        try:
            session_key = self.SESSION_KEY_PREFIX.format(session_id=session_id)
            data = self.redis_service.redis_client.hgetall(session_key)
            
            if not data:
                return None
            
            return SessionState(
                session_id=data.get('session_id', ''),
                user_id=int(data.get('user_id', 0)),
                question_id=data.get('question_id', ''),
                hint_level=int(data.get('hint_level', 0)),
                conversation_summary=data.get('conversation_summary', ''),
                last_message=data.get('last_message', ''),
                message_count=int(data.get('message_count', 0)),
                created_at=data.get('created_at', ''),
                updated_at=data.get('updated_at', ''),
                metadata=json.loads(data.get('metadata', '{}'))
            )
            
        except Exception as e:
            logger.error(f"获取Session失败: {e}")
            return None
    
    def update_session(
        self,
        session_id: str,
        hint_level: Optional[int] = None,
        conversation_summary: Optional[str] = None,
        last_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新Session状态
        
        对应需求27: 更新hint_level、对话摘要等
        """
        try:
            session_key = self.SESSION_KEY_PREFIX.format(session_id=session_id)
            
            update_data = {'updated_at': datetime.now().isoformat()}
            
            if hint_level is not None:
                update_data['hint_level'] = str(hint_level)
            
            if conversation_summary is not None:
                update_data['conversation_summary'] = conversation_summary
            
            if last_message is not None:
                update_data['last_message'] = last_message
                # 增加消息计数
                current_count = int(
                    self.redis_service.redis_client.hget(session_key, 'message_count') or 0
                )
                update_data['message_count'] = str(current_count + 1)
            
            if metadata is not None:
                update_data['metadata'] = json.dumps(metadata)
            
            self.redis_service.redis_client.hset(session_key, mapping=update_data)
            
            # 刷新TTL
            self.redis_service.redis_client.expire(session_key, self.SESSION_TTL)
            
            logger.debug(f"Session更新成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新Session失败: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """删除Session"""
        try:
            session_key = self.SESSION_KEY_PREFIX.format(session_id=session_id)
            
            # 获取用户ID
            user_id = self.redis_service.redis_client.hget(session_key, 'user_id')
            
            # 删除Session
            self.redis_service.redis_client.delete(session_key)
            
            # 从用户Session列表中移除
            if user_id:
                user_sessions_key = self.USER_SESSIONS_KEY.format(user_id=user_id)
                self.redis_service.redis_client.zrem(user_sessions_key, session_id)
            
            logger.info(f"Session删除成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除Session失败: {e}")
            return False
    
    # ==================== 对话上下文管理 ====================
    
    def add_message_to_summary(
        self,
        session_id: str,
        role: str,  # 'user' or 'assistant'
        message: str,
        max_summary_length: int = 500
    ) -> bool:
        """
        添加消息到对话摘要
        
        对应需求27: 维护多轮对话上下文
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return False
            
            # 简化消息（取前100字符）
            simplified_message = message[:100] + "..." if len(message) > 100 else message
            
            # 构建消息记录
            message_entry = f"{role}: {simplified_message}\n"
            
            # 更新对话摘要
            current_summary = session.conversation_summary
            new_summary = current_summary + message_entry
            
            # 限制摘要长度
            if len(new_summary) > max_summary_length:
                # 保留最近的部分
                new_summary = "..." + new_summary[-(max_summary_length-3):]
            
            return self.update_session(
                session_id=session_id,
                conversation_summary=new_summary,
                last_message=simplified_message
            )
            
        except Exception as e:
            logger.error(f"添加消息到摘要失败: {e}")
            return False
    
    def get_conversation_context(
        self,
        session_id: str,
        max_messages: int = 5
    ) -> List[Dict[str, str]]:
        """
        获取对话上下文
        
        用于Agent生成响应时参考历史对话
        """
        try:
            session = self.get_session(session_id)
            if not session or not session.conversation_summary:
                return []
            
            # 解析对话摘要
            lines = session.conversation_summary.strip().split('\n')
            
            context = []
            for line in lines[-max_messages:]:
                if ': ' in line:
                    role, message = line.split(': ', 1)
                    context.append({'role': role, 'message': message})
            
            return context
            
        except Exception as e:
            logger.error(f"获取对话上下文失败: {e}")
            return []
    
    # ==================== Session查询 ====================
    
    def get_user_active_sessions(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取用户的活跃Session列表"""
        try:
            user_sessions_key = self.USER_SESSIONS_KEY.format(user_id=user_id)
            
            # 获取最近的Session ID
            session_ids = self.redis_service.redis_client.zrevrange(
                user_sessions_key, 0, limit - 1
            )
            
            sessions = []
            for sid in session_ids:
                session = self.get_session(sid)
                if session:
                    sessions.append({
                        'session_id': session.session_id,
                        'question_id': session.question_id,
                        'hint_level': session.hint_level,
                        'message_count': session.message_count,
                        'updated_at': session.updated_at
                    })
            
            return sessions
            
        except Exception as e:
            logger.error(f"获取用户Session列表失败: {e}")
            return []
    
    def get_session_by_question(
        self,
        user_id: int,
        question_id: str
    ) -> Optional[str]:
        """根据题目ID查找Session"""
        try:
            sessions = self.get_user_active_sessions(user_id, limit=50)
            
            for session in sessions:
                if session['question_id'] == question_id:
                    return session['session_id']
            
            return None
            
        except Exception as e:
            logger.error(f"查找Session失败: {e}")
            return None
    
    # ==================== Session生命周期管理 ====================
    
    def extend_session_ttl(self, session_id: str, ttl_seconds: int = None) -> bool:
        """延长Session TTL"""
        try:
            session_key = self.SESSION_KEY_PREFIX.format(session_id=session_id)
            ttl = ttl_seconds or self.SESSION_TTL
            
            self.redis_service.redis_client.expire(session_key, ttl)
            return True
            
        except Exception as e:
            logger.error(f"延长Session TTL失败: {e}")
            return False
    
    def cleanup_expired_sessions(self, user_id: int = None) -> int:
        """
        清理过期Session
        
        从用户Session列表中移除已不存在的Session
        """
        try:
            if user_id:
                # 清理指定用户的过期Session
                user_sessions_key = self.USER_SESSIONS_KEY.format(user_id=user_id)
                session_ids = self.redis_service.redis_client.zrange(user_sessions_key, 0, -1)
                
                removed = 0
                for sid in session_ids:
                    session_key = self.SESSION_KEY_PREFIX.format(session_id=sid)
                    if not self.redis_service.redis_client.exists(session_key):
                        self.redis_service.redis_client.zrem(user_sessions_key, sid)
                        removed += 1
                
                return removed
            else:
                # TODO: 全局清理（需要扫描所有用户）
                return 0
                
        except Exception as e:
            logger.error(f"清理过期Session失败: {e}")
            return 0


# ==================== 便捷函数 ====================

def get_or_create_session(
    user_id: int,
    question_id: str,
    session_id: Optional[str] = None
) -> str:
    """
    便捷函数：获取或创建Session
    
    使用示例:
        session_id = get_or_create_session(1, "q001")
    """
    service = SessionService()
    
    # 尝试查找现有Session
    if not session_id:
        existing = service.get_session_by_question(user_id, question_id)
        if existing:
            return existing
    
    # 创建新Session
    return service.create_session(user_id, question_id, session_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Session服务测试")
    print("=" * 60)
    
    service = SessionService()
    
    # 测试创建Session
    print("\n创建Session测试：")
    session_id = service.create_session(1, "q001")
    print(f"  Session ID: {session_id}")
    
    # 测试获取Session
    print("\n获取Session测试：")
    session = service.get_session(session_id)
    if session:
        print(f"  用户ID: {session.user_id}")
        print(f"  题目ID: {session.question_id}")
        print(f"  hint_level: {session.hint_level}")
    
    # 测试更新Session
    print("\n更新Session测试：")
    service.update_session(session_id, hint_level=2)
    session = service.get_session(session_id)
    print(f"  更新后hint_level: {session.hint_level}")
    
    # 测试添加消息
    print("\n添加消息测试：")
    service.add_message_to_summary(session_id, 'user', '这道题怎么做？')
    service.add_message_to_summary(session_id, 'assistant', '让我来帮你分析...')
    
    context = service.get_conversation_context(session_id)
    print(f"  对话上下文: {len(context)}条消息")
    for msg in context:
        print(f"    {msg['role']}: {msg['message'][:30]}...")
    
    # 清理
    service.delete_session(session_id)
    print("\nSession清理完成")
