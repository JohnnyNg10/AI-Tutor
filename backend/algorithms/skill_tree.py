"""
需求10：游戏技能树展示知识点依赖关系

核心功能：
1. 知识点依赖关系图构建
2. 基于P(L)掌握度的节点状态计算
3. 前置依赖检查（锁定/解锁状态）
4. 专题进度计算

PRD标准：
- 绿色：P(L) >= 0.8（已掌握）
- 黄色：0.5 <= P(L) < 0.8（学习中）
- 红色：P(L) < 0.5（薄弱点）
- 灰色：前置知识点未掌握（锁定）
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class NodeStatus(Enum):
    """技能树节点状态"""
    MASTERED = "mastered"       # 绿色：已掌握
    LEARNING = "learning"       # 黄色：学习中
    WEAK = "weak"               # 红色：薄弱点
    LOCKED = "locked"           # 灰色：锁定（前置未达标）


@dataclass
class KnowledgeNode:
    """知识节点"""
    node_id: str                    # 节点ID（如：sequence_001）
    name: str                       # 节点名称（如：等差数列通项公式）
    topic: str                      # 所属专题（如：等差数列）
    p_known: float = 0.0            # 掌握度 P(L)
    status: NodeStatus = field(default=NodeStatus.LOCKED)
    prerequisites: List[str] = field(default_factory=list)  # 前置节点ID列表
    is_root: bool = False           # 是否为根节点（无前置）
    position: Dict[str, int] = field(default_factory=dict)  # 在技能树中的位置 {x, y, level}
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "topic": self.topic,
            "p_known": round(self.p_known, 4),
            "status": self.status.value,
            "prerequisites": self.prerequisites,
            "is_root": self.is_root,
            "position": self.position
        }


@dataclass
class TopicProgress:
    """专题进度"""
    topic: str                      # 专题名称
    total_nodes: int                # 总节点数
    mastered_nodes: int             # 已掌握节点数
    learning_nodes: int             # 学习中节点数
    weak_nodes: int                 # 薄弱节点数
    locked_nodes: int               # 锁定节点数
    progress_percentage: float      # 进度百分比
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "total_nodes": self.total_nodes,
            "mastered_nodes": self.mastered_nodes,
            "learning_nodes": self.learning_nodes,
            "weak_nodes": self.weak_nodes,
            "locked_nodes": self.locked_nodes,
            "progress_percentage": round(self.progress_percentage, 2),
            "progress_text": f"{self.progress_percentage:.0f}%"
        }


@dataclass
class SkillTree:
    """技能树"""
    topic: str
    nodes: Dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)  # (from, to)
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": self.edges,
            "total_nodes": len(self.nodes)
        }


class SkillTreeBuilder:
    """
    技能树构建器
    
    负责：
    1. 构建知识点依赖关系图
    2. 计算节点状态（基于P(L)和前置依赖）
    3. 计算专题进度
    """
    
    # PRD标准：掌握度阈值
    MASTERED_THRESHOLD = 0.8        # 已掌握阈值
    LEARNING_THRESHOLD = 0.5        # 学习中阈值
    
    def __init__(self):
        self.skill_trees: Dict[str, SkillTree] = {}  # topic -> SkillTree
        self._init_default_trees()
    
    def _init_default_trees(self):
        """初始化默认技能树（数列专题全覆盖）"""
        # ===== 1. 数列基础（公共根） =====
        base_tree = SkillTree(topic="数列基础")
        base_nodes = [
            KnowledgeNode(node_id="base_001", name="数列的概念与分类", topic="数列基础", prerequisites=[], is_root=True, position={"x": 400, "y": 50, "level": 0}),
            KnowledgeNode(node_id="base_002", name="数列的通项", topic="数列基础", prerequisites=["base_001"], position={"x": 200, "y": 150, "level": 1}),
            KnowledgeNode(node_id="base_003", name="数列的前n项和", topic="数列基础", prerequisites=["base_001"], position={"x": 600, "y": 150, "level": 1}),
            KnowledgeNode(node_id="base_004", name="数列的递推关系", topic="数列基础", prerequisites=["base_002"], position={"x": 300, "y": 250, "level": 2}),
            KnowledgeNode(node_id="base_005", name="数列的函数特性", topic="数列基础", prerequisites=["base_003"], position={"x": 500, "y": 250, "level": 2}),
        ]
        for node in base_nodes:
            base_tree.nodes[node.node_id] = node
            for p in node.prerequisites:
                base_tree.edges.append((p, node.node_id))
        self.skill_trees["数列基础"] = base_tree

        # ===== 2. 等差数列 =====
        arith = SkillTree(topic="等差数列")
        arith_nodes = [
            KnowledgeNode(node_id="ap_001", name="等差数列定义", topic="等差数列", prerequisites=["base_002"], position={"x": 100, "y": 180, "level": 1}),
            KnowledgeNode(node_id="ap_002", name="公差与公差范围判定", topic="等差数列", prerequisites=["ap_001"], position={"x": 50, "y": 280, "level": 2}),
            KnowledgeNode(node_id="ap_003", name="通项公式推导与应用", topic="等差数列", prerequisites=["ap_001"], position={"x": 180, "y": 280, "level": 2}),
            KnowledgeNode(node_id="ap_004", name="前n项和公式", topic="等差数列", prerequisites=["ap_003"], position={"x": 80, "y": 380, "level": 3}),
            KnowledgeNode(node_id="ap_005", name="等差数列性质", topic="等差数列", prerequisites=["ap_003"], position={"x": 220, "y": 380, "level": 3}),
            KnowledgeNode(node_id="ap_006", name="等差中项", topic="等差数列", prerequisites=["ap_005"], position={"x": 150, "y": 480, "level": 4}),
        ]
        for node in arith_nodes:
            arith.nodes[node.node_id] = node
            for p in node.prerequisites:
                arith.edges.append((p, node.node_id))
        self.skill_trees["等差数列"] = arith

        # ===== 3. 等比数列 =====
        geo = SkillTree(topic="等比数列")
        geo_nodes = [
            KnowledgeNode(node_id="gp_001", name="等比数列定义", topic="等比数列", prerequisites=["base_002"], position={"x": 350, "y": 180, "level": 1}),
            KnowledgeNode(node_id="gp_002", name="公比与收敛发散判定", topic="等比数列", prerequisites=["gp_001"], position={"x": 300, "y": 280, "level": 2}),
            KnowledgeNode(node_id="gp_003", name="通项公式推导与应用", topic="等比数列", prerequisites=["gp_001"], position={"x": 430, "y": 280, "level": 2}),
            KnowledgeNode(node_id="gp_004", name="前n项和公式", topic="等比数列", prerequisites=["gp_003"], position={"x": 330, "y": 380, "level": 3}),
            KnowledgeNode(node_id="gp_005", name="等比数列性质", topic="等比数列", prerequisites=["gp_003"], position={"x": 470, "y": 380, "level": 3}),
            KnowledgeNode(node_id="gp_006", name="等比中项", topic="等比数列", prerequisites=["gp_005"], position={"x": 400, "y": 480, "level": 4}),
        ]
        for node in geo_nodes:
            geo.nodes[node.node_id] = node
            for p in node.prerequisites:
                geo.edges.append((p, node.node_id))
        self.skill_trees["等比数列"] = geo

        # ===== 4. 数列求和 =====
        sum_tree = SkillTree(topic="数列求和")
        sum_nodes = [
            KnowledgeNode(node_id="sum_001", name="公式求和法", topic="数列求和", prerequisites=["base_003"], position={"x": 580, "y": 180, "level": 1}),
            KnowledgeNode(node_id="sum_002", name="分组求和法", topic="数列求和", prerequisites=["sum_001"], position={"x": 530, "y": 280, "level": 2}),
            KnowledgeNode(node_id="sum_003", name="裂项相消法", topic="数列求和", prerequisites=["sum_001"], position={"x": 630, "y": 280, "level": 2}),
            KnowledgeNode(node_id="sum_004", name="错位相减法", topic="数列求和", prerequisites=["sum_001"], position={"x": 730, "y": 280, "level": 2}),
            KnowledgeNode(node_id="sum_005", name="倒序相加法", topic="数列求和", prerequisites=["sum_002"], position={"x": 580, "y": 380, "level": 3}),
            KnowledgeNode(node_id="sum_006", name="数学归纳法求和应用", topic="数列求和", prerequisites=["sum_003", "sum_004"], position={"x": 680, "y": 380, "level": 3}),
        ]
        for node in sum_nodes:
            sum_tree.nodes[node.node_id] = node
            for p in node.prerequisites:
                sum_tree.edges.append((p, node.node_id))
        self.skill_trees["数列求和"] = sum_tree

        # ===== 5. 递推数列 =====
        recur = SkillTree(topic="递推数列")
        recur_nodes = [
            KnowledgeNode(node_id="rec_001", name="递推公式基本类型", topic="递推数列", prerequisites=["base_004"], position={"x": 800, "y": 130, "level": 1}),
            KnowledgeNode(node_id="rec_002", name="待定系数法求通项", topic="递推数列", prerequisites=["rec_001"], position={"x": 760, "y": 240, "level": 2}),
            KnowledgeNode(node_id="rec_003", name="累加/累乘求通项", topic="递推数列", prerequisites=["rec_001"], position={"x": 870, "y": 240, "level": 2}),
            KnowledgeNode(node_id="rec_004", name="不动点法", topic="递推数列", prerequisites=["rec_002"], position={"x": 810, "y": 350, "level": 3}),
            KnowledgeNode(node_id="rec_005", name="特征方程法", topic="递推数列", prerequisites=["rec_004"], position={"x": 810, "y": 440, "level": 4}),
        ]
        for node in recur_nodes:
            recur.nodes[node.node_id] = node
            for p in node.prerequisites:
                recur.edges.append((p, node.node_id))
        self.skill_trees["递推数列"] = recur

        # ===== 6. 数学归纳法 =====
        ind = SkillTree(topic="数学归纳法")
        ind_nodes = [
            KnowledgeNode(node_id="ind_001", name="数学归纳法原理", topic="数学归纳法", prerequisites=["base_002"], position={"x": 940, "y": 100, "level": 1}),
            KnowledgeNode(node_id="ind_002", name="第一数学归纳法", topic="数学归纳法", prerequisites=["ind_001"], position={"x": 900, "y": 210, "level": 2}),
            KnowledgeNode(node_id="ind_003", name="第二数学归纳法", topic="数学归纳法", prerequisites=["ind_001"], position={"x": 990, "y": 210, "level": 2}),
            KnowledgeNode(node_id="ind_004", name="归纳-猜想-证明", topic="数学归纳法", prerequisites=["ind_002"], position={"x": 940, "y": 320, "level": 3}),
            KnowledgeNode(node_id="ind_005", name="数列不等式归纳证明", topic="数学归纳法", prerequisites=["ind_004", "gp_004"], position={"x": 940, "y": 410, "level": 4}),
        ]
        for node in ind_nodes:
            ind.nodes[node.node_id] = node
            for p in node.prerequisites:
                ind.edges.append((p, node.node_id))
        self.skill_trees["数学归纳法"] = ind
    
    def get_skill_tree(self, topic: str) -> Optional[SkillTree]:
        """获取技能树"""
        return self.skill_trees.get(topic)
    
    def update_node_mastery(
        self, 
        topic: str, 
        node_id: str, 
        p_known: float
    ) -> KnowledgeNode:
        """
        更新节点掌握度
        
        Args:
            topic: 专题名称
            node_id: 节点ID
            p_known: 掌握度 P(L)
            
        Returns:
            更新后的节点
        """
        tree = self.get_skill_tree(topic)
        if tree is None or node_id not in tree.nodes:
            raise ValueError(f"节点不存在: {topic}/{node_id}")
        
        node = tree.nodes[node_id]
        node.p_known = p_known
        return node
    
    def calculate_node_status(
        self, 
        node: KnowledgeNode, 
        all_nodes: Dict[str, KnowledgeNode]
    ) -> NodeStatus:
        """
        计算节点状态
        
        PRD逻辑：
        1. 检查前置节点是否都达标（P(L) >= 0.8）
        2. 如果前置未达标 → 锁定（灰色）
        3. 如果前置达标 → 根据P(L)判断状态
        """
        # 检查前置依赖
        if not node.is_root and node.prerequisites:
            for prereq_id in node.prerequisites:
                if prereq_id in all_nodes:
                    prereq = all_nodes[prereq_id]
                    # 前置节点未掌握（P(L) < 0.8）→ 锁定
                    if prereq.p_known < self.MASTERED_THRESHOLD:
                        return NodeStatus.LOCKED
        
        # 前置已达标，根据P(L)判断状态
        if node.p_known >= self.MASTERED_THRESHOLD:
            return NodeStatus.MASTERED
        elif node.p_known >= self.LEARNING_THRESHOLD:
            return NodeStatus.LEARNING
        else:
            return NodeStatus.WEAK
    
    def build_user_skill_tree(
        self, 
        topic: str, 
        user_mastery: Dict[str, float]
    ) -> SkillTree:
        """
        构建用户的技能树（带状态）
        
        Args:
            topic: 专题名称
            user_mastery: {node_id: p_known}
            
        Returns:
            带状态的技能树
        """
        tree = self.get_skill_tree(topic)
        if tree is None:
            raise ValueError(f"专题不存在: {topic}")
        
        # 创建副本
        user_tree = SkillTree(topic=topic)
        
        # 复制节点并更新掌握度
        for node_id, node in tree.nodes.items():
            new_node = KnowledgeNode(
                node_id=node.node_id,
                name=node.name,
                topic=node.topic,
                p_known=user_mastery.get(node_id, 0.0),
                prerequisites=node.prerequisites.copy(),
                is_root=node.is_root,
                position=node.position.copy()
            )
            user_tree.nodes[node_id] = new_node
        
        # 复制边
        user_tree.edges = tree.edges.copy()
        
        # 计算每个节点的状态（需要考虑依赖关系）
        # 按层级排序，从根节点开始计算
        sorted_nodes = sorted(
            user_tree.nodes.values(),
            key=lambda n: n.position.get("level", 0)
        )
        
        for node in sorted_nodes:
            node.status = self.calculate_node_status(node, user_tree.nodes)
        
        return user_tree
    
    def calculate_topic_progress(
        self, 
        topic: str, 
        user_mastery: Dict[str, float]
    ) -> TopicProgress:
        """
        计算专题进度
        
        PRD公式：
        进度百分比 = (P(L) >= 0.8 的知识点数量) / (该专题总知识点数量)
        
        Args:
            topic: 专题名称
            user_mastery: {node_id: p_known}
            
        Returns:
            专题进度
        """
        tree = self.get_skill_tree(topic)
        if tree is None:
            raise ValueError(f"专题不存在: {topic}")
        
        total = len(tree.nodes)
        mastered = 0
        learning = 0
        weak = 0
        locked = 0
        
        # 构建用户技能树以计算状态
        user_tree = self.build_user_skill_tree(topic, user_mastery)
        
        for node in user_tree.nodes.values():
            if node.status == NodeStatus.MASTERED:
                mastered += 1
            elif node.status == NodeStatus.LEARNING:
                learning += 1
            elif node.status == NodeStatus.WEAK:
                weak += 1
            else:  # LOCKED
                locked += 1
        
        # PRD公式：进度 = 已掌握 / 总数
        progress = (mastered / total * 100) if total > 0 else 0
        
        return TopicProgress(
            topic=topic,
            total_nodes=total,
            mastered_nodes=mastered,
            learning_nodes=learning,
            weak_nodes=weak,
            locked_nodes=locked,
            progress_percentage=progress
        )
    
    def get_unlocked_nodes(
        self, 
        topic: str, 
        user_mastery: Dict[str, float]
    ) -> List[KnowledgeNode]:
        """
        获取已解锁的节点（可用于"一键特训"）
        
        Args:
            topic: 专题名称
            user_mastery: {node_id: p_known}
            
        Returns:
            已解锁但未掌握的节点列表
        """
        user_tree = self.build_user_skill_tree(topic, user_mastery)
        
        unlocked = []
        for node in user_tree.nodes.values():
            # 已解锁但未掌握（红色或黄色）
            if node.status in [NodeStatus.WEAK, NodeStatus.LEARNING]:
                unlocked.append(node)
        
        # 按掌握度排序（优先推荐薄弱点）
        unlocked.sort(key=lambda n: n.p_known)
        return unlocked
    
    def get_recommended_training(
        self, 
        topic: str, 
        user_mastery: Dict[str, float],
        limit: int = 3
    ) -> List[Dict]:
        """
        获取推荐训练节点（一键特训）
        
        推荐策略：
        1. 优先推荐薄弱点（红色）
        2. 其次推荐学习中（黄色）
        3. 排除已掌握（绿色）和锁定（灰色）
        
        Args:
            topic: 专题名称
            user_mastery: {node_id: p_known}
            limit: 推荐数量
            
        Returns:
            推荐节点列表
        """
        unlocked = self.get_unlocked_nodes(topic, user_mastery)
        
        recommendations = []
        for node in unlocked[:limit]:
            recommendations.append({
                "node_id": node.node_id,
                "name": node.name,
                "p_known": round(node.p_known, 4),
                "status": node.status.value,
                "topic": node.topic
            })
        
        return recommendations
    
    def get_all_topics(self) -> List[str]:
        """获取所有专题列表"""
        return list(self.skill_trees.keys())


# 全局技能树构建器实例
skill_tree_builder = SkillTreeBuilder()


def get_skill_tree_builder() -> SkillTreeBuilder:
    """获取技能树构建器实例"""
    return skill_tree_builder


# 单元测试
if __name__ == "__main__":
    print("=== 需求10：技能树测试 ===\n")
    
    builder = SkillTreeBuilder()
    
    # 测试1：获取技能树结构
    print("测试1：等差数列技能树结构")
    tree = builder.get_skill_tree("等差数列")
    print(f"  专题: {tree.topic}")
    print(f"  节点数: {len(tree.nodes)}")
    print(f"  边数: {len(tree.edges)}")
    print("  节点列表:")
    for node_id, node in tree.nodes.items():
        print(f"    - {node.name} (ID: {node_id})")
    
    # 测试2：构建用户技能树
    print("\n测试2：构建用户技能树")
    user_mastery = {
        "arith_001": 0.9,   # 已掌握
        "arith_002": 0.85,  # 已掌握
        "arith_003": 0.6,   # 学习中
        "arith_004": 0.3,   # 薄弱
        "arith_005": 0.4,   # 薄弱
        "arith_006": 0.0,   # 未学习（依赖前置）
    }
    
    user_tree = builder.build_user_skill_tree("等差数列", user_mastery)
    print("  节点状态:")
    for node_id, node in user_tree.nodes.items():
        status_emoji = {
            "mastered": "[G]",
            "learning": "[Y]",
            "weak": "[R]",
            "locked": "[-]"
        }.get(node.status.value, "[-]")
        print(f"    {status_emoji} {node.name}: P(L)={node.p_known:.2f} -> {node.status.value}")
    
    # 测试3：计算专题进度
    print("\n测试3：专题进度计算")
    progress = builder.calculate_topic_progress("等差数列", user_mastery)
    print(f"  专题: {progress.topic}")
    print(f"  总节点: {progress.total_nodes}")
    print(f"  已掌握: {progress.mastered_nodes}")
    print(f"  学习中: {progress.learning_nodes}")
    print(f"  薄弱点: {progress.weak_nodes}")
    print(f"  锁定: {progress.locked_nodes}")
    print(f"  进度: {progress.progress_percentage:.1f}%")
    
    # 测试4：推荐训练
    print("\n测试4：推荐训练节点")
    recommendations = builder.get_recommended_training("等差数列", user_mastery, limit=3)
    print(f"  推荐节点数: {len(recommendations)}")
    for rec in recommendations:
        print(f"    - {rec['name']} ({rec['status']}, P(L)={rec['p_known']})")
    
    print("\n=== 所有测试通过！===")
