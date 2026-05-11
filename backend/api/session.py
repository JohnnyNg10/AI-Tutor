"""
Session管理API接口
提供Session状态管理的HTTP接口

对应需求27: 在Redis中维护当前Session的临时状态

实现文件：backend/api/session.py
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

from services.session_service import SessionService, get_or_create_session
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/session", tags=["Session管理"])


# ============ 数据模型 ============

class CreateSessionRequest(BaseModel):
    """创建Session请求"""
    question_id: str = Field(..., description="题目ID")
    session_id: Optional[str] = Field(default=None, description="指定Session ID（可选）")


class CreateSessionResponse(BaseModel):
    """创建Session响应"""
    success: bool
    session_id: str
    user_id: int
    question_id: str
    message: str


class SessionStateResponse(BaseModel):
    """Session状态响应"""
    success: bool
    session_id: str
    user_id: int
    question_id: str
    hint_level: int
    conversation_summary: str
    last_message: str
    message_count: int
    created_at: str
    updated_at: str


class UpdateSessionRequest(BaseModel):
    """更新Session请求"""
    hint_level: Optional[int] = Field(default=None, ge=0, le=4, description="提示等级")
    conversation_summary: Optional[str] = Field(default=None, description="对话摘要")
    last_message: Optional[str] = Field(default=None, description="最后消息")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class AddMessageRequest(BaseModel):
    """添加消息请求"""
    role: str = Field(..., description="角色（user/assistant）")
    message: str = Field(..., description="消息内容")


class ConversationContextResponse(BaseModel):
    """对话上下文响应"""
    success: bool
    session_id: str
    context: List[Dict[str, str]]


class UserSessionsResponse(BaseModel):
    """用户Sessions响应"""
    success: bool
    user_id: int
    sessions: List[Dict[str, Any]]


# ============ API端点 ============

@router.post("/create", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    创建新Session
    
    对应需求27: 创建Session，存储题号等基本信息
    """
    try:
        user_id = current_user.id
        
        service = SessionService()
        session_id = service.create_session(
            user_id=user_id,
            question_id=request.question_id,
            session_id=request.session_id
        )
        
        return CreateSessionResponse(
            success=True,
            session_id=session_id,
            user_id=user_id,
            question_id=request.question_id,
            message="Session创建成功"
        )
        
    except Exception as e:
        logger.error(f"创建Session失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionStateResponse)
async def get_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取Session状态
    
    返回Session的完整状态信息
    """
    try:
        user_id = current_user.id
        
        service = SessionService()
        session = service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session不存在或已过期")
        
        # 验证权限
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此Session")
        
        return SessionStateResponse(
            success=True,
            session_id=session.session_id,
            user_id=session.user_id,
            question_id=session.question_id,
            hint_level=session.hint_level,
            conversation_summary=session.conversation_summary,
            last_message=session.last_message,
            message_count=session.message_count,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Session失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/update")
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    更新Session状态
    
    对应需求27: 更新hint_level、对话摘要等
    """
    try:
        user_id = current_user.id
        
        service = SessionService()
        
        # 验证Session存在和权限
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session不存在")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此Session")
        
        success = service.update_session(
            session_id=session_id,
            hint_level=request.hint_level,
            conversation_summary=request.conversation_summary,
            last_message=request.last_message,
            metadata=request.metadata
        )
        
        if success:
            return {'success': True, 'message': 'Session更新成功'}
        else:
            raise HTTPException(status_code=500, detail="更新失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Session失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/message")
async def add_message(
    session_id: str,
    request: AddMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    添加消息到Session
    
    对应需求27: 维护多轮对话上下文
    """
    try:
        user_id = current_user.id
        
        service = SessionService()
        
        # 验证Session存在和权限
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session不存在")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此Session")
        
        success = service.add_message_to_summary(
            session_id=session_id,
            role=request.role,
            message=request.message
        )
        
        if success:
            return {
                'success': True,
                'message': '消息添加成功',
                'session_id': session_id
            }
        else:
            raise HTTPException(status_code=500, detail="添加消息失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/context", response_model=ConversationContextResponse)
async def get_conversation_context(
    session_id: str,
    max_messages: int = 5,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取对话上下文
    
    对应需求27: 获取多轮对话历史，用于Agent生成响应
    """
    try:
        user_id = current_user.id
        
        service = SessionService()
        
        # 验证Session存在和权限
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session不存在")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此Session")
        
        context = service.get_conversation_context(session_id, max_messages)
        
        return ConversationContextResponse(
            success=True,
            session_id=session_id,
            context=context
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话上下文失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/list", response_model=UserSessionsResponse)
async def get_user_sessions(
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取用户的Session列表
    """
    try:
        user_id = current_user.id
        
        service = SessionService()
        sessions = service.get_user_active_sessions(user_id, limit)
        
        return UserSessionsResponse(
            success=True,
            user_id=user_id,
            sessions=sessions
        )
        
    except Exception as e:
        logger.error(f"获取用户Sessions失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """删除Session"""
    try:
        user_id = current_user.id
        
        service = SessionService()
        
        # 验证Session存在和权限
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session不存在")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此Session")
        
        success = service.delete_session(session_id)
        
        if success:
            return {'success': True, 'message': 'Session删除成功'}
        else:
            raise HTTPException(status_code=500, detail="删除失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除Session失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/extend-ttl")
async def extend_session_ttl(
    session_id: str,
    ttl_seconds: int = 7200,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """延长Session TTL"""
    try:
        user_id = current_user.id
        
        service = SessionService()
        
        # 验证Session存在和权限
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session不存在")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此Session")
        
        success = service.extend_session_ttl(session_id, ttl_seconds)
        
        if success:
            return {
                'success': True,
                'message': f'Session TTL延长成功（{ttl_seconds}秒）'
            }
        else:
            raise HTTPException(status_code=500, detail="延长TTL失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"延长Session TTL失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 便捷端点 ============

@router.post("/get-or-create")
async def get_or_create_session_endpoint(
    request: CreateSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取或创建Session（便捷接口）
    
    如果该题目已有活跃Session，返回现有Session；否则创建新Session
    """
    try:
        user_id = current_user.id
        
        session_id = get_or_create_session(
            user_id=user_id,
            question_id=request.question_id,
            session_id=request.session_id
        )
        
        # 判断是新建还是复用
        service = SessionService()
        session = service.get_session(session_id)
        is_new = session.message_count == 0 if session else True
        
        return {
            'success': True,
            'session_id': session_id,
            'is_new': is_new,
            'message': '创建新Session' if is_new else '复用现有Session'
        }
        
    except Exception as e:
        logger.error(f"获取或创建Session失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = SessionService()
        return {
            'status': 'healthy',
            'service': 'session',
            'session_ttl': service.SESSION_TTL
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
