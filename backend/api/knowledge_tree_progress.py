"""
知识树节点解锁率进度API接口
提供知识树进度查询的HTTP接口

数据源：backend/algorithms/skill_tree.py（84节点/9专题硬编码知识图谱）
匹配方式：关联标签匹配 → 节点名称匹配 → node_id匹配（三级fallback）

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
    """
    获取知识树进度

    数据源：skill_tree.py 84节点知识图谱
    掌握度匹配：关联标签 → 节点名称 → node_id（三级fallback）
    """
    try:
        user_id = current_user.id
        builder = get_skill_tree_builder()

        # 获取用户掌握度 {kp_name: p_known}
        db_mastery = await get_user_mastery_dict(db, user_id)

        # 通过关联标签匹配为 {node_id: p_known}
        node_mastery = builder.match_user_mastery_by_tags(db_mastery)

        topics_out = []
        all_topic_progress = []

        for topic_name in builder.get_all_topics():
            tree = builder.get_skill_tree(topic_name)
            if tree is None:
                continue

            user_tree = builder.build_user_skill_tree(topic_name, node_mastery)

            # 节点详情
            nodes_out = []
            for node_id, node in sorted(user_tree.nodes.items(),
                                         key=lambda x: x[1].position.get("level", 0)):
                prereq_names = []
                for pid in node.prerequisites:
                    pn = builder.get_node(pid)
                    prereq_names.append(pn.name if pn else pid)

                nodes_out.append({
                    "node_id": node.node_id,
                    "name": node.name,
                    "p_known": round(node.p_known, 4),
                    "status": node.status.value,
                    "cognitive_level": node.cognitive_level,
                    "diagnostic_description": node.diagnostic_description,
                    "prerequisites": node.prerequisites,
                    "prerequisite_names": prereq_names,
                    "position": node.position,
                })

            # 统计
            total = len(user_tree.nodes)
            mastered = sum(1 for n in user_tree.nodes.values() if n.status.value == "mastered")
            learning = sum(1 for n in user_tree.nodes.values() if n.status.value == "learning")
            weak = sum(1 for n in user_tree.nodes.values() if n.status.value == "weak")
            locked = sum(1 for n in user_tree.nodes.values() if n.status.value == "locked")
            progress = (mastered / total * 100) if total > 0 else 0

            # 专题状态
            if progress >= 80:
                topic_status = "mastered"
            elif mastered > 0 or learning > 0:
                topic_status = "in_progress"
            else:
                topic_status = "locked"

            # 里程碑
            milestones = [
                {"key": "first_blood", "name": "首次突破", "description": "专题进度达到10%",
                 "icon": "🌱", "threshold": 10, "achieved": progress >= 10},
                {"key": "half_way", "name": "半程里程碑", "description": "专题进度达到50%",
                 "icon": "🛤️", "threshold": 50, "achieved": progress >= 50},
                {"key": "explorer", "name": "探索者", "description": "专题进度达到60%",
                 "icon": "🧭", "threshold": 60, "achieved": progress >= 60},
                {"key": "master", "name": "掌握大师", "description": "专题进度达到80%",
                 "icon": "👑", "threshold": 80, "achieved": progress >= 80},
                {"key": "conqueror", "name": "征服者", "description": "专题进度达到95%",
                 "icon": "🏆", "threshold": 95, "achieved": progress >= 95},
            ]

            all_topic_progress.append(progress)

            topics_out.append({
                "topic": topic_name,
                "progress": round(progress, 1),
                "progress_text": f"{progress:.0f}%",
                "status": topic_status,
                "statistics": {
                    "total_nodes": total,
                    "mastered_nodes": mastered,
                    "learning_nodes": learning,
                    "weak_nodes": weak,
                    "locked_nodes": locked,
                },
                "nodes": nodes_out,
                "milestones": milestones,
            })

        overall = round(sum(all_topic_progress) / len(all_topic_progress), 1) if all_topic_progress else 0

        total_nodes_all = sum(t["statistics"]["total_nodes"] for t in topics_out)
        mastered_nodes_all = sum(t["statistics"]["mastered_nodes"] for t in topics_out)

        statistics = {
            "total_categories": len(topics_out),
            "total_topics": len(topics_out),
            "total_knowledge_nodes": total_nodes_all,
            "mastered_nodes": mastered_nodes_all,
            "mastered_categories": sum(1 for t in topics_out if t["status"] == "mastered"),
            "in_progress_categories": sum(1 for t in topics_out if t["status"] == "in_progress"),
            "locked_categories": sum(1 for t in topics_out if t["status"] == "locked"),
        }

        return KnowledgeTreeResponse(
            success=True,
            user_id=user_id,
            overall_progress=overall,
            statistics=statistics,
            topics=[
                TopicProgressResponse(
                    topic=t["topic"],
                    progress=t["progress"],
                    progress_text=t["progress_text"],
                    status=t["status"],
                    statistics=t["statistics"],
                    nodes=t["nodes"],
                    milestones=t["milestones"]
                )
                for t in topics_out
            ]
        )

    except Exception as e:
        logger.error(f"获取知识树进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topic/{topic_name}")
async def get_topic_detail(
    topic_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取专题详情（含节点列表和诊断说明）"""
    try:
        user_id = current_user.id
        builder = get_skill_tree_builder()

        tree = builder.get_skill_tree(topic_name)
        if tree is None:
            raise HTTPException(status_code=404, detail=f"专题不存在: {topic_name}")

        db_mastery = await get_user_mastery_dict(db, user_id)
        node_mastery = builder.match_user_mastery_by_tags(db_mastery)
        user_tree = builder.build_user_skill_tree(topic_name, node_mastery)

        nodes_out = []
        for node_id, node in sorted(user_tree.nodes.items(),
                                     key=lambda x: x[1].position.get("level", 0)):
            prereq_names = []
            for pid in node.prerequisites:
                pn = builder.get_node(pid)
                prereq_names.append(pn.name if pn else pid)

            nodes_out.append({
                "node_id": node.node_id,
                "name": node.name,
                "p_known": round(node.p_known, 4),
                "status": node.status.value,
                "cognitive_level": node.cognitive_level,
                "diagnostic_description": node.diagnostic_description,
                "prerequisites": node.prerequisites,
                "prerequisite_names": prereq_names,
                "position": node.position,
            })

        total = len(user_tree.nodes)
        mastered = sum(1 for n in user_tree.nodes.values() if n.status.value == "mastered")
        progress = (mastered / total * 100) if total > 0 else 0

        return {
            "success": True,
            "topic": topic_name,
            "progress": round(progress, 1),
            "status": "mastered" if progress >= 80 else ("in_progress" if progress > 0 else "locked"),
            "statistics": {
                "total_nodes": total,
                "mastered_nodes": mastered,
                "learning_nodes": sum(1 for n in user_tree.nodes.values() if n.status.value == "learning"),
                "weak_nodes": sum(1 for n in user_tree.nodes.values() if n.status.value == "weak"),
                "locked_nodes": sum(1 for n in user_tree.nodes.values() if n.status.value == "locked"),
            },
            "nodes": nodes_out,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取专题详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/{node_id}")
async def get_node_detail(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取单个知识节点详情（含诊断说明、学习建议）"""
    try:
        user_id = current_user.id
        builder = get_skill_tree_builder()

        node = builder.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"节点不存在: {node_id}")

        db_mastery = await get_user_mastery_dict(db, user_id)
        node_mastery = builder.match_user_mastery_by_tags(db_mastery)
        p_known = node_mastery.get(node_id, 0.0)

        prereq_nodes = []
        for pid in node.prerequisites:
            pn = builder.get_node(pid)
            if pn:
                prereq_nodes.append({
                    "node_id": pn.node_id,
                    "name": pn.name,
                    "p_known": round(node_mastery.get(pid, 0.0), 4),
                    "status": "mastered" if node_mastery.get(pid, 0.0) >= 0.8 else "not_mastered",
                })

        # 依赖此节点的后续节点
        dependents = []
        for nid, n in builder.get_all_nodes().items():
            if node_id in n.prerequisites:
                dependents.append({"node_id": n.node_id, "name": n.name, "topic": n.topic})

        return {
            "success": True,
            "node": {
                "node_id": node.node_id,
                "name": node.name,
                "topic": node.topic,
                "cognitive_level": node.cognitive_level,
                "diagnostic_description": node.diagnostic_description,
                "p_known": round(p_known, 4),
                "prerequisites": prereq_nodes,
                "dependents": dependents,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取节点详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-milestones", response_model=MilestonesCheckResponse)
async def check_milestones(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """检查里程碑"""
    try:
        user_id = current_user.id
        service = KnowledgeTreeProgressService()
        milestones = service.check_milestones(user_id)
        return MilestonesCheckResponse(
            success=True,
            user_id=user_id,
            new_milestones=[
                MilestoneResponse(
                    type=m["type"], topic=m["topic"],
                    progress=m["progress"], message=m["message"],
                    celebration=m["celebration"]
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
        in_progress = [t for t in tree_data["topics"] if t["status"] == "in_progress"]
        completed = [t for t in tree_data["topics"] if t["status"] == "completed"]
        return {
            "success": True,
            "user_id": user_id,
            "overall_progress": tree_data["overall_progress"],
            "summary": {
                "total_topics": len(tree_data["topics"]),
                "completed_topics": len(completed),
                "in_progress_topics": len(in_progress),
                "not_started_topics": len(tree_data["topics"]) - len(completed) - len(in_progress)
            },
            "current_focus": in_progress[0] if in_progress else None,
            "recent_completed": completed[:3] if completed else []
        }
    except Exception as e:
        logger.error(f"获取总体进度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        builder = get_skill_tree_builder()
        return {
            "status": "healthy",
            "service": "knowledge_tree_progress",
            "data_source": "skill_tree.py (84 nodes / 9 topics)",
            "total_nodes": len(builder.get_all_nodes()),
            "total_topics": len(builder.get_all_topics()),
            "features": ["tree_building", "progress_calculation", "milestone_detection",
                         "tag_matching", "cross_topic_deps", "node_detail"],
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {"status": "unhealthy", "error": str(e)}
