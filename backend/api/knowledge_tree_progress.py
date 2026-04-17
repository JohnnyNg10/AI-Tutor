"""
知识树节点解锁率进度API接口
提供知识树进度查询的HTTP接口

对应行号22/27: 摒弃传统题量进度条，基于"知识树节点解锁率"来定义学习进度

实现文件: backend/api/knowledge_tree_progress.py
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
from fastapi import APIRouter, HTTPException, Depends, Query

from services.knowledge_tree_progress_service import (
    KnowledgeTreeProgressService,
    get_user_knowledge_tree_progress,
    check_topic_milestones
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/knowledge-tree", tags=["知识树节点解锁率进度"])


# ============ 数据模型 ============

class TopicProgressResponse(BaseModel):
    """专题进度响应"""
    topic: str
    progress: float
    progress_text: str
    status: str
    statistics: Dict[str, int]
    milestones: Dict[str, bool]


class KnowledgeTreeResponse(BaseModel):
    """知识树响应"""
    success: bool
    user_id: int
    overall_progress: float
    statistics: Dict[str, Any]
    topics: List[TopicProgressResponse]


class MilestoneResponse(BaseModel):
    """里程碑响应"""
    type: str
    topic: str
    progress: float
    message: str
    celebration: bool


class MilestonesCheckResponse(BaseModel):
    """里程碑检查响应"""
    success: bool
    user_id: int
    new_milestones: List[MilestoneResponse]


# ============ API端点 ============

@router.get("/progress", response_model=KnowledgeTreeResponse)
async def get_knowledge_tree_progress(
    topic: Optional[str] = Query(None, description="指定专题"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取知识树进度
    
    对应行号22/27: 基于知识树节点解锁率定义学习进度
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = KnowledgeTreeProgressService()
        tree_data = service.get_tree_for_display(user_id, topic)
        
        return KnowledgeTreeResponse(
            success=True,
            user_id=user_id,
            overall_progress=tree_data['overall_progress'],
            statistics=tree_data['statistics'],
            topics=[
                TopicProgressResponse(
                    topic=t['topic'],
                    progress=t['progress'],
                    progress_text=t['progress_text'],
                    status=t['status'],
                    statistics=t['statistics'],
                    milestones=t['milestones']
                )
                for t in tree_data['topics']
            ]
        )
        
    except Exception as e:
        logger.error(f"获取知识树进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topic/{topic}")
async def get_topic_detail(
    topic: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取专题详情"""
    try:
        user_id = current_user.get('id', 0)
        
        service = KnowledgeTreeProgressService()
        tree_data = service.build_knowledge_tree(user_id, topic)
        
        topic_data = next(
            (t for t in tree_data.topics if t.topic == topic),
            None
        )
        
        if not topic_data:
            raise HTTPException(status_code=404, detail="专题不存在")
        
        return {
            'success': True,
            'topic': topic,
            'progress': topic_data.progress_percentage,
            'status': topic_data.status,
            'statistics': {
                'total_nodes': topic_data.total_nodes,
                'unlocked_nodes': topic_data.unlocked_nodes,
                'mastered_nodes': topic_data.mastered_nodes
            },
            'milestones': {
                '50%_reached': topic_data.milestone_50_reached,
                '100%_reached': topic_data.milestone_100_reached
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取专题详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-milestones", response_model=MilestonesCheckResponse)
async def check_milestones(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    检查里程碑
    
    检测专题进度是否突破50%、100%，触发庆祝播报
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = KnowledgeTreeProgressService()
        milestones = service.check_milestones(user_id)
        
        return MilestonesCheckResponse(
            success=True,
            user_id=user_id,
            new_milestones=[
                MilestoneResponse(
                    type=m['type'],
                    topic=m['topic'],
                    progress=m['progress'],
                    message=m['message'],
                    celebration=m['celebration']
                )
                for m in milestones
            ]
        )
        
    except Exception as e:
        logger.error(f"检查里程碑失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overall")
async def get_overall_progress(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取总体进度摘要"""
    try:
        user_id = current_user.get('id', 0)
        
        service = KnowledgeTreeProgressService()
        tree_data = service.get_tree_for_display(user_id)
        
        # 找出进行中的专题
        in_progress = [t for t in tree_data['topics'] if t['status'] == 'in_progress']
        completed = [t for t in tree_data['topics'] if t['status'] == 'completed']
        
        return {
            'success': True,
            'user_id': user_id,
            'overall_progress': tree_data['overall_progress'],
            'summary': {
                'total_topics': len(tree_data['topics']),
                'completed_topics': len(completed),
                'in_progress_topics': len(in_progress),
                'not_started_topics': len(tree_data['topics']) - len(completed) - len(in_progress)
            },
            'current_focus': in_progress[0] if in_progress else None,
            'recent_completed': completed[:3] if completed else []
        }
        
    except Exception as e:
        logger.error(f"获取总体进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = KnowledgeTreeProgressService()
        return {
            'status': 'healthy',
            'service': 'knowledge_tree_progress',
            'mastery_threshold': service.MASTERY_THRESHOLD,
            'unlock_threshold': service.UNLOCK_THRESHOLD,
            'features': ['tree_building', 'progress_calculation', 'milestone_detection']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
