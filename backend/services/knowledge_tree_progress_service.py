"""
知识树节点解锁率进度服务
摒弃传统题量进度条，基于"知识树节点解锁率"来定义学习进度

对应行号22/27: 摒弃传统题量进度条，基于"知识树节点解锁率"来定义学习进度

进度定义：以专题（如：递推数列）为单位，计算该专题下所有 P(L) >= 0.8 的知识点占比
阶段反馈：当某个专题进度突破 50%、100% 时，触发系统级的里程碑庆祝播报

实现文件: backend/services/knowledge_tree_progress_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
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
    
    # Redis Key前缀
    KNOWLEDGE_TREE_KEY = "ai:tutor:knowledge-tree:{user_id}"
    TOPIC_PROGRESS_KEY = "ai:tutor:topic-progress:{user_id}"
    MILESTONE_KEY = "ai:tutor:milestone:{user_id}"
    
    # 掌握度阈值
    MASTERY_THRESHOLD = 0.8  # P(L) >= 0.8 为已掌握
    UNLOCK_THRESHOLD = 0.5   # P(L) >= 0.5 为已解锁
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("知识树进度服务初始化完成")
    
    # ==================== 知识树构建 ====================
    
    def build_knowledge_tree(
        self,
        user_id: int,
        topic: Optional[str] = None
    ) -> KnowledgeTreeData:
        """
        构建知识树
        
        计算所有知识点的解锁和掌握状态
        """
        try:
            # 获取知识点数据
            knowledge_points = self._get_knowledge_points(topic)
            
            # 获取用户掌握度
            mastery_data = self._get_user_mastery(user_id)
            
            # 构建节点
            nodes = []
            for kp in knowledge_points:
                p_known = mastery_data.get(kp['id'], 0.0)
                
                node = KnowledgeNode(
                    node_id=kp['id'],
                    name=kp['name'],
                    topic=kp['topic'],
                    p_known=p_known,
                    is_unlocked=p_known >= self.UNLOCK_THRESHOLD,
                    is_mastered=p_known >= self.MASTERY_THRESHOLD,
                    prerequisites=kp.get('prerequisites', [])
                )
                nodes.append(node)
            
            # 计算解锁顺序（拓扑排序）
            nodes = self._calculate_unlock_order(nodes)
            
            # 按专题分组计算进度
            topics = self._calculate_topic_progress(nodes)
            
            # 计算总体进度
            total_nodes = len(nodes)
            total_unlocked = sum(1 for n in nodes if n.is_unlocked)
            total_mastered = sum(1 for n in nodes if n.is_mastered)
            overall_progress = (total_mastered / total_nodes * 100) if total_nodes > 0 else 0
            
            tree_data = KnowledgeTreeData(
                user_id=user_id,
                topics=topics,
                total_nodes=total_nodes,
                total_unlocked=total_unlocked,
                total_mastered=total_mastered,
                overall_progress=round(overall_progress, 1)
            )
            
            # 缓存数据
            self._cache_tree_data(user_id, tree_data)
            
            return tree_data
            
        except Exception as e:
            logger.error(f"构建知识树失败: {e}")
            return KnowledgeTreeData(
                user_id=user_id,
                topics=[],
                total_nodes=0,
                total_unlocked=0,
                total_mastered=0,
                overall_progress=0.0
            )
    
    def _get_knowledge_points(self, topic: Optional[str] = None) -> List[Dict]:
        """获取知识点列表"""
        # TODO: 从数据库查询
        # 临时返回模拟数据
        all_kps = [
            {'id': 'arith_001', 'name': '数列基础概念', 'topic': '等差数列', 'prerequisites': []},
            {'id': 'arith_002', 'name': '等差数列定义', 'topic': '等差数列', 'prerequisites': ['arith_001']},
            {'id': 'arith_003', 'name': '等差数列通项', 'topic': '等差数列', 'prerequisites': ['arith_002']},
            {'id': 'arith_004', 'name': '等差数列求和', 'topic': '等差数列', 'prerequisites': ['arith_003']},
            {'id': 'geo_001', 'name': '等比数列定义', 'topic': '等比数列', 'prerequisites': ['arith_001']},
            {'id': 'geo_002', 'name': '等比数列通项', 'topic': '等比数列', 'prerequisites': ['geo_001']},
            {'id': 'geo_003', 'name': '等比数列求和', 'topic': '等比数列', 'prerequisites': ['geo_002']},
        ]
        
        if topic:
            return [kp for kp in all_kps if kp['topic'] == topic]
        return all_kps
    
    def _get_user_mastery(self, user_id: int) -> Dict[str, float]:
        """获取用户掌握度"""
        # TODO: 从Redis/数据库查询
        # 临时返回模拟数据
        return {
            'arith_001': 0.9,
            'arith_002': 0.85,
            'arith_003': 0.6,
            'arith_004': 0.3,
            'geo_001': 0.9,
            'geo_002': 0.4,
            'geo_003': 0.2,
        }
    
    def _calculate_unlock_order(self, nodes: List[KnowledgeNode]) -> List[KnowledgeNode]:
        """计算解锁顺序"""
        # 简化的拓扑排序
        unlocked_ids = set()
        order = 0
        
        for node in nodes:
            # 检查前置条件
            prereqs_met = all(
                prereq in unlocked_ids 
                for prereq in node.prerequisites
            )
            
            if prereqs_met or not node.prerequisites:
                node.unlock_order = order
                order += 1
                if node.is_unlocked:
                    unlocked_ids.add(node.node_id)
        
        return nodes
    
    def _calculate_topic_progress(
        self,
        nodes: List[KnowledgeNode]
    ) -> List[TopicProgress]:
        """计算各专题进度"""
        # 按专题分组
        topics_dict = {}
        for node in nodes:
            if node.topic not in topics_dict:
                topics_dict[node.topic] = []
            topics_dict[node.topic].append(node)
        
        topics = []
        for topic_name, topic_nodes in topics_dict.items():
            total = len(topic_nodes)
            unlocked = sum(1 for n in topic_nodes if n.is_unlocked)
            mastered = sum(1 for n in topic_nodes if n.is_mastered)
            
            # 进度 = 已掌握 / 总数
            progress = (mastered / total * 100) if total > 0 else 0
            
            # 确定状态
            if mastered == total:
                status = 'completed'
            elif mastered > 0 or unlocked > 0:
                status = 'in_progress'
            else:
                status = 'not_started'
            
            # 检查里程碑
            milestone_50 = progress >= 50
            milestone_100 = progress >= 100
            
            topics.append(TopicProgress(
                topic=topic_name,
                total_nodes=total,
                unlocked_nodes=unlocked,
                mastered_nodes=mastered,
                progress_percentage=round(progress, 1),
                progress_text=f"{int(progress)}%",
                status=status,
                milestone_50_reached=milestone_50,
                milestone_100_reached=milestone_100
            ))
        
        # 按进度排序
        topics.sort(key=lambda x: x.progress_percentage, reverse=True)
        
        return topics
    
    def _cache_tree_data(self, user_id: int, tree_data: KnowledgeTreeData) -> None:
        """缓存知识树数据"""
        try:
            key = self.KNOWLEDGE_TREE_KEY.format(user_id=user_id)
            
            data = {
                'user_id': tree_data.user_id,
                'total_nodes': tree_data.total_nodes,
                'total_unlocked': tree_data.total_unlocked,
                'total_mastered': tree_data.total_mastered,
                'overall_progress': tree_data.overall_progress,
                'updated_at': datetime.now().isoformat()
            }
            
            self.redis_service.redis_client.hset(key, mapping=data)
            self.redis_service.redis_client.expire(key, 3600)
            
        except Exception as e:
            logger.error(f"缓存知识树数据失败: {e}")
    
    # ==================== 里程碑检测 ====================
    
    def check_milestones(self, user_id: int) -> List[Dict[str, Any]]:
        """
        检测里程碑
        
        当专题进度突破50%、100%时触发
        """
        try:
            tree_data = self.build_knowledge_tree(user_id)
            
            milestones = []
            for topic in tree_data.topics:
                # 检查50%里程碑
                if topic.milestone_50_reached and not self._is_milestone_reached(
                    user_id, topic.topic, '50%'
                ):
                    milestones.append({
                        'type': 'milestone_50',
                        'topic': topic.topic,
                        'progress': topic.progress_percentage,
                        'message': f'恭喜！{topic.topic}专题进度突破50%！',
                        'celebration': True
                    })
                    self._mark_milestone_reached(user_id, topic.topic, '50%')
                
                # 检查100%里程碑
                if topic.milestone_100_reached and not self._is_milestone_reached(
                    user_id, topic.topic, '100%'
                ):
                    milestones.append({
                        'type': 'milestone_100',
                        'topic': topic.topic,
                        'progress': 100,
                        'message': f'太棒了！{topic.topic}专题已完全掌握！',
                        'celebration': True,
                        'reward': 'unlock_next_topic'
                    })
                    self._mark_milestone_reached(user_id, topic.topic, '100%')
            
            return milestones
            
        except Exception as e:
            logger.error(f"检测里程碑失败: {e}")
            return []
    
    def _is_milestone_reached(self, user_id: int, topic: str, level: str) -> bool:
        """检查里程碑是否已达成"""
        try:
            key = self.MILESTONE_KEY.format(user_id=user_id)
            field = f"{topic}_{level}"
            return self.redis_service.redis_client.hexists(key, field)
        except Exception as e:
            logger.error(f"检查里程碑失败: {e}")
            return False
    
    def _mark_milestone_reached(self, user_id: int, topic: str, level: str) -> None:
        """标记里程碑已达成"""
        try:
            key = self.MILESTONE_KEY.format(user_id=user_id)
            field = f"{topic}_{level}"
            self.redis_service.redis_client.hset(key, field, datetime.now().isoformat())
        except Exception as e:
            logger.error(f"标记里程碑失败: {e}")
    
    # ==================== API数据格式 ====================
    
    def get_tree_for_display(self, user_id: int, topic: Optional[str] = None) -> Dict[str, Any]:
        """获取用于前端展示的知识树数据"""
        tree_data = self.build_knowledge_tree(user_id, topic)
        
        return {
            'user_id': tree_data.user_id,
            'overall_progress': tree_data.overall_progress,
            'statistics': {
                'total_nodes': tree_data.total_nodes,
                'unlocked_nodes': tree_data.total_unlocked,
                'mastered_nodes': tree_data.total_mastered,
                'unlock_rate': round(tree_data.total_unlocked / tree_data.total_nodes * 100, 1) if tree_data.total_nodes > 0 else 0
            },
            'topics': [
                {
                    'topic': t.topic,
                    'progress': t.progress_percentage,
                    'progress_text': t.progress_text,
                    'status': t.status,
                    'statistics': {
                        'total': t.total_nodes,
                        'unlocked': t.unlocked_nodes,
                        'mastered': t.mastered_nodes
                    },
                    'milestones': {
                        '50%': t.milestone_50_reached,
                        '100%': t.milestone_100_reached
                    }
                }
                for t in tree_data.topics
            ]
        }


# ==================== 便捷函数 ====================

def get_user_knowledge_tree_progress(user_id: int) -> Dict[str, Any]:
    """便捷函数：获取用户知识树进度"""
    service = KnowledgeTreeProgressService()
    return service.get_tree_for_display(user_id)


def check_topic_milestones(user_id: int) -> List[Dict[str, Any]]:
    """便捷函数：检查专题里程碑"""
    service = KnowledgeTreeProgressService()
    return service.check_milestones(user_id)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("知识树进度服务测试")
    print("=" * 60)
    
    service = KnowledgeTreeProgressService()
    
    # 测试构建知识树
    print("\n知识树构建测试：")
    tree = service.build_knowledge_tree(1)
    print(f"  总节点: {tree.total_nodes}")
    print(f"  已解锁: {tree.total_unlocked}")
    print(f"  已掌握: {tree.total_mastered}")
    print(f"  总体进度: {tree.overall_progress}%")
    
    # 测试专题进度
    print("\n专题进度测试：")
    for topic in tree.topics:
        print(f"  {topic.topic}: {topic.progress_text} ({topic.mastered_nodes}/{topic.total_nodes})")
    
    # 测试里程碑
    print("\n里程碑检测测试：")
    milestones = service.check_milestones(1)
    for m in milestones:
        print(f"  {m['message']}")
    
    print("\n测试完成")
