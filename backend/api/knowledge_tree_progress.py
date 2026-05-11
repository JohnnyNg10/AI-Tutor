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
    """获取知识树进度（基于知识图谱 + DB 掌握度数据）"""
    try:
        user_id = current_user.id
        from algorithms.knowledge_graph import (
            SEQUENCE_KNOWLEDGE_GRAPH, get_categories, get_topics_by_category,
            KGGraphNode, KGNodeType
        )

        db_mastery = await get_user_mastery_dict(db, user_id)

        def _tag_mastery(tags):
            """计算一组标签的掌握度。只有有学习记录的标签参与进度计算，无记录的标签进度为 0。"""
            scores = []
            for tag in tags:
                if tag in db_mastery:
                    scores.append(db_mastery[tag])
            if not scores:
                return { "avg": 0, "matched": 0, "total": len(tags), "scores": [],
                         "coverage": 0 }  # 没有任何学习记录 → 进度 0%
            avg_mastery = sum(scores) / len(scores)
            coverage = len(scores) / len(tags)  # 已学习标签占比
            # 综合进度 = 已学习覆盖率 × 平均掌握度
            return { "avg": avg_mastery, "matched": len(scores),
                     "total": len(tags), "scores": scores, "coverage": round(coverage, 2) }

        def _status(p):
            if p >= 0.8: return "mastered"
            if p >= 0.5: return "learning"
            if p >= 0.3: return "weak"
            return "locked"

        def _milestones(p):
            return [
                {"key": "first_blood", "name": "首次突破", "description": "专题进度达到 10%",  "icon": "🌱", "threshold": 10,  "achieved": p >= 10},
                {"key": "half_way",   "name": "半程里程碑", "description": "专题进度达到 50%",  "icon": "🛤️", "threshold": 50,  "achieved": p >= 50},
                {"key": "explorer",   "name": "探索者",     "description": "专题进度达到 60%",  "icon": "🧭", "threshold": 60,  "achieved": p >= 60},
                {"key": "master",     "name": "掌握大师",   "description": "专题进度达到 80%",  "icon": "👑", "threshold": 80,  "achieved": p >= 80},
                {"key": "conqueror",  "name": "征服者",     "description": "专题进度达到 95%",  "icon": "🏆", "threshold": 95,  "achieved": p >= 95},
            ]

        categories_out = []
        all_topic_progress = []
        total_tags_all = 0
        mastered_tags_all = 0

        for cat in get_categories():
            cat_topics = []
            cat_progress_sum = 0
            cat_tags = 0
            cat_mastered = 0

            for tpc in get_topics_by_category(cat.node_id):
                m = _tag_mastery(tpc.tags)
                # 综合进度 = 覆盖率 × 平均掌握度（无记录时 = 0，不会虚高）
                progress = round(m["coverage"] * m["avg"] * 100, 1) if m["matched"] > 0 else 0
                cat_progress_sum += progress
                cat_tags += m["total"]
                cat_mastered += m["matched"]

                # 标签掌握度明细：未匹配的标签 p_known=0，状态 locked
                tag_details = []
                for tag in tpc.tags:
                    if tag in db_mastery:
                        p = db_mastery[tag]
                        matched = True
                    else:
                        p = 0
                        matched = False
                    tag_details.append({
                        "name": tag,
                        "p_known": round(p, 2),
                        "status": _status(p) if matched else "locked",
                        "matched": matched,
                    })

                # 子专题的状态取决于覆盖率（至少学过一半标签才算 in_progress）
                subtopic_status = "locked"
                if m["matched"] > 0:
                    subtopic_status = _status(m["coverage"] * m["avg"])

                cat_topics.append({
                    "topic": tpc.name,
                    "topic_id": tpc.node_id,
                    "description": tpc.description,
                    "progress": progress,
                    "progress_text": f"{progress:.0f}%",
                    "status": subtopic_status,
                    "statistics": {
                        "total_tags": m["total"],
                        "matched_tags": m["matched"],
                        "avg_mastery": round(m["avg"], 2) if m["matched"] > 0 else 0,
                        "coverage": m["coverage"],
                    },
                    "tags": tag_details,
                    "milestones": _milestones(progress),
                })

            cat_progress = round(cat_progress_sum / len(cat_topics), 1) if cat_topics else 0
            if cat_topics:
                all_topic_progress.append(cat_progress)
            total_tags_all += cat_tags
            mastered_tags_all += cat_mastered

            # 主干状态：覆盖率 > 0 才算有进度
            if cat_progress >= 80: cat_status = "mastered"
            elif cat_progress >= 30: cat_status = "in_progress"
            elif cat_mastered > 0: cat_status = "in_progress"
            else: cat_status = "locked"

            categories_out.append({
                "topic": cat.name,
                "topic_id": cat.node_id,
                "description": cat.description,
                "progress": cat_progress,
                "progress_text": f"{cat_progress:.0f}%",
                "status": cat_status,
                "statistics": {
                    "total_tags": cat_tags,
                    "matched_tags": cat_mastered,
                    "topic_count": len(cat_topics),
                },
                "nodes": cat_topics,  # 子专题作为"节点"展开
                "milestones": _milestones(cat_progress),
            })

        overall_progress = round(sum(all_topic_progress) / len(all_topic_progress), 1) if all_topic_progress else 0

        all_nodes = [n for cat in get_categories() for n in get_topics_by_category(cat.node_id)]
        statistics = {
            "total_categories": len(categories_out),
            "total_topics": len(all_nodes),
            "total_knowledge_tags": total_tags_all,
            "mastered_tags": mastered_tags_all,
            "mastered_categories": sum(1 for c in categories_out if c["status"] == "mastered"),
            "in_progress_categories": sum(1 for c in categories_out if c["status"] == "learning"),
            "locked_categories": sum(1 for c in categories_out if c["status"] == "locked"),
        }

        return KnowledgeTreeResponse(
            success=True,
            user_id=user_id,
            overall_progress=overall_progress,
            statistics=statistics,
            topics=[
                TopicProgressResponse(
                    topic=c['topic'],
                    progress=c['progress'],
                    progress_text=c['progress_text'],
                    status=c['status'],
                    statistics=c['statistics'],
                    nodes=c.get('nodes', []),
                    milestones=c['milestones']
                )
                for c in categories_out
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
