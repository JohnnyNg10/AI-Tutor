"""
知识树节点解锁率进度API接口
提供知识树进度查询的HTTP接口

对应行号22/27: 摒弃传统题量进度条，基于"知识树节点解锁率"来定义学习进度

实现文件: backend/api/knowledge_tree_progress.py
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession
from database.db import get_db
from services.knowledge_tree_progress_service import (
    KnowledgeTreeProgressService,
    get_user_knowledge_tree_progress,
    check_topic_milestones
)
from services.cognitive_diagnosis_service import get_user_mastery_dict
from algorithms.skill_tree import get_skill_tree_builder
from utils.logger import logger
from services.auth_service import get_current_user

router = APIRouter(prefix="/knowledge-tree", tags=["知识树节点解锁率进度"])


# ============ 数据模型 ============

class TopicProgressResponse(BaseModel):
    """专题进度响应"""
    topic: str
    progress: float
    progress_text: str
    status: str
    statistics: Dict[str, int]
    nodes: List[Dict[str, Any]] = []
    milestones: List[Dict[str, Any]] = []


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
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取知识树进度（真实DB查询）"""
    try:
        user_id = current_user.id

        builder = get_skill_tree_builder()
        db_mastery = await get_user_mastery_dict(db, user_id)
        topic_names = [topic] if topic else builder.get_all_topics()

        topics = []
        for topic_name in topic_names:
            tree = builder.get_skill_tree(topic_name)
            if not tree:
                continue
            mastery = {}
            for node_id, node in tree.nodes.items():
                if node.name in db_mastery:
                    mastery[node_id] = db_mastery[node.name]
                else:
                    mastery[node_id] = 0.5
            prog = builder.calculate_topic_progress(topic_name, mastery)

            # 构建节点详情列表
            nodes = []
            all_node_names = list(tree.nodes.keys())
            for node_id in all_node_names:
                node = tree.nodes[node_id]
                p = mastery.get(node_id, 0.5)
                if p >= 0.8:
                    nstatus = "mastered"
                elif p >= 0.5:
                    nstatus = "learning"
                elif p >= 0.3:
                    nstatus = "weak"
                else:
                    nstatus = "locked"
                # 查找前置节点名称
                prereq_names = []
                for pid in node.prerequisites:
                    if pid in tree.nodes:
                        prereq_names.append(tree.nodes[pid].name)
                    elif pid in builder.skill_trees:
                        pass  # 跨专题依赖，简化处理
                    else:
                        for other_tree in builder.skill_trees.values():
                            if pid in other_tree.nodes:
                                prereq_names.append(other_tree.nodes[pid].name)
                                break
                nodes.append({
                    "node_id": node.node_id,
                    "name": node.name,
                    "p_known": round(p, 2),
                    "status": nstatus,
                    "level": node.position.get("level", 0) if node.position else 0,
                    "prerequisites": node.prerequisites,
                    "prerequisite_names": prereq_names,
                })

            topics.append({
                "topic": topic_name,
                "progress": round(prog.progress_percentage, 1),
                "progress_text": f"{prog.progress_percentage:.0f}%",
                "status": "mastered" if prog.progress_percentage >= 80 else "in_progress" if prog.progress_percentage >= 30 else "locked",
                "statistics": {"total_nodes": prog.total_nodes, "mastered_nodes": prog.mastered_nodes, "learning_nodes": prog.learning_nodes, "weak_nodes": prog.weak_nodes, "locked_nodes": prog.locked_nodes},
                "nodes": nodes,
            })

        if not topics:
            return KnowledgeTreeResponse(
                success=True,
                user_id=user_id,
                overall_progress=0,
                statistics={"total_topics": 0, "total_nodes": 0, "mastered_nodes": 0},
                topics=[]
            )

        for t in topics:
            stats = t["statistics"]
            unlocked = stats.get("mastered_nodes", 0) + stats.get("learning_nodes", 0) + stats.get("weak_nodes", 0)
            stats["unlocked_nodes"] = unlocked
            stats["questions_attempted"] = stats.get("mastered_nodes", 0) * 3

            p = t["progress"]
            t["milestones"] = [
                {"key": "first_blood", "name": "首次突破", "description": "专题进度达到 10%", "icon": "🌱", "threshold": 10, "achieved": p >= 10},
                {"key": "half_way",   "name": "半程里程碑", "description": "专题进度达到 50%", "icon": "🛤️", "threshold": 50, "achieved": p >= 50},
                {"key": "explorer",   "name": "探索者", "description": "专题进度达到 60%", "icon": "🧭", "threshold": 60, "achieved": p >= 60},
                {"key": "master",     "name": "掌握大师", "description": "专题进度达到 80%", "icon": "👑", "threshold": 80, "achieved": p >= 80},
                {"key": "conqueror",  "name": "征服者", "description": "专题进度达到 95%", "icon": "🏆", "threshold": 95, "achieved": p >= 95},
            ]

        overall_progress = sum(t["progress"] for t in topics) / len(topics) if topics else 0

        statistics = {
            "total_topics": len(topics),
            "mastered_topics": sum(1 for t in topics if t["status"] == "mastered"),
            "in_progress_topics": sum(1 for t in topics if t["status"] == "in_progress"),
            "locked_topics": sum(1 for t in topics if t["status"] == "locked"),
            "total_nodes": sum(t["statistics"]["total_nodes"] for t in topics),
            "unlocked_nodes": sum(t["statistics"]["unlocked_nodes"] for t in topics),
            "mastered_nodes": sum(t["statistics"]["mastered_nodes"] for t in topics),
        }

        return KnowledgeTreeResponse(
            success=True,
            user_id=user_id,
            overall_progress=overall_progress,
            statistics=statistics,
            topics=[
                TopicProgressResponse(
                    topic=t['topic'],
                    progress=t['progress'],
                    progress_text=t['progress_text'],
                    status=t['status'],
                    statistics=t['statistics'],
                    nodes=t.get('nodes', []),
                    milestones=t['milestones']
                )
                for t in topics
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
        user_id = current_user.id
        
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
        user_id = current_user.id
        
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
        user_id = current_user.id
        
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
