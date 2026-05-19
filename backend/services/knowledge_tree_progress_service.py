"""
知识树节点解锁率进度服务
摒弃传统题量进度条，基于"知识树节点解锁率"来定义学习进度

数据源：backend/algorithms/skill_tree.py（84节点/9专题）

进度定义：以专题为单位，计算该专题下所有 P(L) >= 0.8 的知识点占比
阶段反馈：当某个专题进度突破 50%、100% 时，触发系统级的里程碑庆祝播报

实现文件: backend/services/knowledge_tree_progress_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class KnowledgeNode:
    """知识树节点"""
    node_id: str
    name: str
    topic: str
    p_known: float
    is_unlocked: bool
    is_mastered: bool
    prerequisites: List[str]
    unlock_order: Optional[int] = None


@dataclass
class TopicProgress:
    """专题进度"""
    topic: str
    total_nodes: int
    unlocked_nodes: int
    mastered_nodes: int
    progress_percentage: float
    progress_text: str
    status: str  # not_started / in_progress / completed
    milestone_50_reached: bool = False
    milestone_100_reached: bool = False


@dataclass
class KnowledgeTreeData:
    """知识树完整数据"""
    user_id: int
    topics: List[TopicProgress]
    total_nodes: int
    total_unlocked: int
    total_mastered: int
    overall_progress: float


class KnowledgeTreeProgressService:
    """
    知识树节点解锁率进度服务

    功能：
    1. 知识树节点解锁状态计算
    2. 专题进度计算（P(L) >= 0.8的知识点占比）
    3. 里程碑检测（50%、100%）
    4. 阶段反馈触发
    """

    KNOWLEDGE_TREE_KEY = "ai:tutor:knowledge-tree:{user_id}"
    TOPIC_PROGRESS_KEY = "ai:tutor:topic-progress:{user_id}"
    MILESTONE_KEY = "ai:tutor:milestone:{user_id}"

    MASTERY_THRESHOLD = 0.8
    UNLOCK_THRESHOLD = 0.5

    def __init__(self):
        self.redis_service = RedisService()
        logger.info("知识树进度服务初始化完成")

    def build_knowledge_tree(self, user_id: int, topic: Optional[str] = None) -> KnowledgeTreeData:
        """构建知识树（数据源：skill_tree.py）"""
        from algorithms.skill_tree import get_skill_tree_builder

        builder = get_skill_tree_builder()
        all_nodes = builder.get_all_nodes()

        # 从Redis获取缓存的掌握度数据
        node_mastery: Dict[str, float] = {}
        try:
            key = f"ai:tutor:mastery:{user_id}"
            raw = self.redis_service.redis_client.hgetall(key)
            if raw:
                node_mastery = {k.decode() if isinstance(k, bytes) else k:
                                float(v.decode() if isinstance(v, bytes) else v) / 100
                                for k, v in raw.items()}
        except Exception:
            pass

        nodes = []
        for node_id, node in all_nodes.items():
            if topic and node.topic != topic:
                continue
            p_known = node_mastery.get(node_id, 0.0)
            nodes.append(KnowledgeNode(
                node_id=node_id, name=node.name, topic=node.topic,
                p_known=p_known,
                is_unlocked=p_known >= self.UNLOCK_THRESHOLD,
                is_mastered=p_known >= self.MASTERY_THRESHOLD,
                prerequisites=node.prerequisites.copy()
            ))

        nodes = self._calculate_unlock_order(nodes)
        topics = self._calculate_topic_progress(nodes)

        total_nodes = len(nodes)
        total_unlocked = sum(1 for n in nodes if n.is_unlocked)
        total_mastered = sum(1 for n in nodes if n.is_mastered)
        overall_progress = (total_mastered / total_nodes * 100) if total_nodes > 0 else 0

        tree_data = KnowledgeTreeData(
            user_id=user_id, topics=topics, total_nodes=total_nodes,
            total_unlocked=total_unlocked, total_mastered=total_mastered,
            overall_progress=round(overall_progress, 1)
        )

        self._cache_tree_data(user_id, tree_data)
        return tree_data

    def _calculate_unlock_order(self, nodes: List[KnowledgeNode]) -> List[KnowledgeNode]:
        """计算解锁顺序（拓扑排序）"""
        unlocked_ids = set()
        order = 0
        for node in nodes:
            prereqs_met = all(p in unlocked_ids for p in node.prerequisites)
            if prereqs_met or not node.prerequisites:
                node.unlock_order = order
                order += 1
                if node.is_unlocked:
                    unlocked_ids.add(node.node_id)
        return nodes

    def _calculate_topic_progress(self, nodes: List[KnowledgeNode]) -> List[TopicProgress]:
        """计算各专题进度"""
        topics_dict: Dict[str, List[KnowledgeNode]] = {}
        for node in nodes:
            topics_dict.setdefault(node.topic, []).append(node)

        topics = []
        for topic_name, topic_nodes in topics_dict.items():
            total = len(topic_nodes)
            unlocked = sum(1 for n in topic_nodes if n.is_unlocked)
            mastered = sum(1 for n in topic_nodes if n.is_mastered)
            progress = (mastered / total * 100) if total > 0 else 0

            if mastered == total:
                status = "completed"
            elif mastered > 0 or unlocked > 0:
                status = "in_progress"
            else:
                status = "not_started"

            topics.append(TopicProgress(
                topic=topic_name, total_nodes=total, unlocked_nodes=unlocked,
                mastered_nodes=mastered, progress_percentage=round(progress, 1),
                progress_text=f"{int(progress)}%", status=status,
                milestone_50_reached=progress >= 50,
                milestone_100_reached=progress >= 100
            ))

        topics.sort(key=lambda x: x.progress_percentage, reverse=True)
        return topics

    def _cache_tree_data(self, user_id: int, tree_data: KnowledgeTreeData) -> None:
        """缓存知识树数据到Redis"""
        try:
            key = self.KNOWLEDGE_TREE_KEY.format(user_id=user_id)
            data = {
                "user_id": str(tree_data.user_id),
                "total_nodes": str(tree_data.total_nodes),
                "total_unlocked": str(tree_data.total_unlocked),
                "total_mastered": str(tree_data.total_mastered),
                "overall_progress": str(tree_data.overall_progress),
                "updated_at": datetime.now().isoformat()
            }
            self.redis_service.redis_client.hset(key, mapping=data)
            self.redis_service.redis_client.expire(key, 3600)
        except Exception as e:
            logger.error(f"缓存知识树数据失败: {e}")

    def check_milestones(self, user_id: int) -> List[Dict[str, Any]]:
        """检测里程碑：当专题进度突破50%、100%时触发"""
        try:
            tree_data = self.build_knowledge_tree(user_id)
            milestones = []
            for topic in tree_data.topics:
                if topic.milestone_50_reached and not self._is_milestone_reached(user_id, topic.topic, "50%"):
                    milestones.append({
                        "type": "milestone_50", "topic": topic.topic,
                        "progress": topic.progress_percentage,
                        "message": f"恭喜！{topic.topic}专题进度突破50%！",
                        "celebration": True
                    })
                    self._mark_milestone_reached(user_id, topic.topic, "50%")

                if topic.milestone_100_reached and not self._is_milestone_reached(user_id, topic.topic, "100%"):
                    milestones.append({
                        "type": "milestone_100", "topic": topic.topic,
                        "progress": 100,
                        "message": f"太棒了！{topic.topic}专题已完全掌握！",
                        "celebration": True, "reward": "unlock_next_topic"
                    })
                    self._mark_milestone_reached(user_id, topic.topic, "100%")
            return milestones
        except Exception as e:
            logger.error(f"检测里程碑失败: {e}")
            return []

    def _is_milestone_reached(self, user_id: int, topic: str, level: str) -> bool:
        try:
            key = self.MILESTONE_KEY.format(user_id=user_id)
            return self.redis_service.redis_client.hexists(key, f"{topic}_{level}")
        except Exception:
            return False

    def _mark_milestone_reached(self, user_id: int, topic: str, level: str) -> None:
        try:
            key = self.MILESTONE_KEY.format(user_id=user_id)
            self.redis_service.redis_client.hset(key, f"{topic}_{level}", datetime.now().isoformat())
        except Exception as e:
            logger.error(f"标记里程碑失败: {e}")

    def get_tree_for_display(self, user_id: int, topic: Optional[str] = None) -> Dict[str, Any]:
        """获取用于前端展示的知识树数据"""
        tree_data = self.build_knowledge_tree(user_id, topic)
        return {
            "user_id": tree_data.user_id,
            "overall_progress": tree_data.overall_progress,
            "statistics": {
                "total_nodes": tree_data.total_nodes,
                "unlocked_nodes": tree_data.total_unlocked,
                "mastered_nodes": tree_data.total_mastered,
                "unlock_rate": round(tree_data.total_unlocked / tree_data.total_nodes * 100, 1) if tree_data.total_nodes > 0 else 0
            },
            "topics": [
                {
                    "topic": t.topic, "progress": t.progress_percentage,
                    "progress_text": t.progress_text, "status": t.status,
                    "statistics": {
                        "total": t.total_nodes, "unlocked": t.unlocked_nodes,
                        "mastered": t.mastered_nodes
                    },
                    "milestones": {"50%": t.milestone_50_reached, "100%": t.milestone_100_reached}
                }
                for t in tree_data.topics
            ]
        }


def get_user_knowledge_tree_progress(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取用户知识树进度"""
    service = KnowledgeTreeProgressService()
    return service.get_tree_for_display(user_id)


def check_topic_milestones(user_id: int) -> List[Dict[str, Any]]:
    """便捷函数：检查专题里程碑"""
    service = KnowledgeTreeProgressService()
    return service.check_milestones(user_id)
