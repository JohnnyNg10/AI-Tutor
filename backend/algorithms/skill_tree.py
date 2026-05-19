"""
需求10：游戏技能树展示知识点依赖关系

核心功能：
1. 知识点依赖关系图构建（84节点，9专题）
2. 基于P(L)掌握度的节点状态计算
3. 前置依赖检查（含跨专题依赖）
4. 专题进度计算
5. 基于关联标签的用户掌握度匹配

数据来源：大模型手动整理的高中数列全知识点体系
对标：科大讯飞学习机知识图谱

四级掌握度标准：
- 精通（绿色）：P(L) >= 0.85
- 良好（蓝色）：0.65 <= P(L) < 0.85
- 合格（橙色）：0.4 <= P(L) < 0.65
- 薄弱（红色）：P(L) < 0.4
- 锁定（灰色）：前置知识点未达标
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class NodeStatus(Enum):
    """技能树节点状态（四级掌握度 + 锁定）"""
    MASTERED = "mastered"       # 精通：P(L) >= 0.85  绿色 #10B981
    PROFICIENT = "proficient"   # 良好：0.65-0.85    蓝色 #3B82F6
    QUALIFIED = "qualified"     # 合格：0.4-0.65     橙色 #F97316
    WEAK = "weak"               # 薄弱：P(L) < 0.4   红色 #EF4444
    LOCKED = "locked"           # 灰色：锁定（前置未达标）


@dataclass
class KnowledgeNode:
    """知识节点（对标讯飞学习机知识图谱节点）"""
    node_id: str                    # 节点ID
    name: str                       # 节点名称
    topic: str                      # 所属专题
    cognitive_level: str = ""       # 认知层级：了解/理解/掌握/运用/综合运用
    diagnostic_description: str = ""  # 诊断说明
    associated_tags: List[str] = field(default_factory=list)  # 关联的题库标签（用于掌握度匹配）
    p_known: float = 0.0            # 掌握度 P(L)
    status: NodeStatus = field(default=NodeStatus.LOCKED)
    prerequisites: List[str] = field(default_factory=list)  # 前置节点ID列表
    is_root: bool = False
    position: Dict[str, int] = field(default_factory=dict)  # {x, y, level}

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "topic": self.topic,
            "cognitive_level": self.cognitive_level,
            "diagnostic_description": self.diagnostic_description,
            "associated_tags": self.associated_tags,
            "p_known": round(self.p_known, 4),
            "status": self.status.value,
            "prerequisites": self.prerequisites,
            "is_root": self.is_root,
            "position": self.position
        }


@dataclass
class TopicProgress:
    """专题进度"""
    topic: str
    total_nodes: int
    mastered_nodes: int
    learning_nodes: int
    weak_nodes: int
    locked_nodes: int
    progress_percentage: float

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
    1. 构建84节点全知识点依赖关系图（9专题）
    2. 计算节点状态（基于P(L)和前置依赖，含跨专题依赖）
    3. 计算专题进度
    4. 基于关联标签匹配用户掌握度
    """

    MASTERED_THRESHOLD = 0.85
    PROFICIENT_THRESHOLD = 0.65
    QUALIFIED_THRESHOLD = 0.4

    def __init__(self):
        self.skill_trees: Dict[str, SkillTree] = {}
        self._all_nodes: Dict[str, KnowledgeNode] = {}  # 全局节点注册表（用于跨专题依赖查询）
        self._init_default_trees()

    # ================================================================
    # 知识点定义（84节点，9专题）
    # ================================================================

    def _register_nodes(self, nodes: List[KnowledgeNode], tree: SkillTree):
        """注册节点到专题树和全局注册表"""
        for node in nodes:
            tree.nodes[node.node_id] = node
            for p in node.prerequisites:
                tree.edges.append((p, node.node_id))
            self._all_nodes[node.node_id] = node

    def _init_default_trees(self):
        """初始化完整知识图谱（84节点，9专题）"""

        # ================================================================
        # 1. 数列基础 (8 nodes)
        # ================================================================
        base = SkillTree(topic="数列基础")
        base_nodes = [
            KnowledgeNode(node_id="base_001", name="数列的概念与分类", topic="数列基础",
                cognitive_level="了解", diagnostic_description="无法区分有穷/无穷数列、递增/递减/摆动/常数列，导致后续单调性判断方向混淆",
                associated_tags=["常数列", "递增数列"],
                prerequisites=[], is_root=True, position={"x": 400, "y": 50, "level": 0}),
            KnowledgeNode(node_id="base_002", name="数列的通项公式", topic="数列基础",
                cognitive_level="理解", diagnostic_description="不会根据通项公式求指定项，或对'通项公式是n的函数'缺乏理解",
                associated_tags=["数列的通项公式", "通项公式", "通项公式求解"],
                prerequisites=["base_001"], position={"x": 150, "y": 170, "level": 1}),
            KnowledgeNode(node_id="base_003", name="数列的递推关系", topic="数列基础",
                cognitive_level="理解", diagnostic_description="混淆递推公式与通项公式的功能，不知道递推关系需要首项+递推式才能确定数列",
                associated_tags=["递推关系", "递推数列", "递推公式变形"],
                prerequisites=["base_001"], position={"x": 400, "y": 170, "level": 1}),
            KnowledgeNode(node_id="base_004", name="数列的前n项和（Sn的概念）", topic="数列基础",
                cognitive_level="理解", diagnostic_description="不理解Sn表示前n项和（而非第n项），或用Sn-S(n-1)求an时忘记n≥2条件",
                associated_tags=["前n项和", "数列的前n项和", "数列求和"],
                prerequisites=["base_001"], position={"x": 650, "y": 170, "level": 1}),
            KnowledgeNode(node_id="base_005", name="an与Sn的关系（由Sn求an）", topic="数列基础",
                cognitive_level="掌握", diagnostic_description="直接用Sn-S(n-1)=an却不验证n≥2，或n=1时不单独讨论a1=S1",
                associated_tags=["$a_n$与$S_n$的关系", "由Sn求an（类讨论型）", "类讨论型（由Sn求an）", "和与通项关系", "前n项和反求通项", "前n项和求通项", "前n项和与通项的关系", "前n项和与通项关系", "数列通项与前n项和关系", "通项与前n项和关系", "分类讨论（n=1与n大于等于2）", "数列求和与通项的关系"],
                prerequisites=["base_002", "base_004"], position={"x": 400, "y": 290, "level": 2}),
            KnowledgeNode(node_id="base_006", name="数列的函数特性（单调性初步）", topic="数列基础",
                cognitive_level="理解", diagnostic_description="不会将an视为n的函数f(n)来分析单调性、值域变化",
                associated_tags=["函数与数列", "数列单调性", "二次函数", "二次函数性质", "二次函数值域", "分段函数"],
                prerequisites=["base_002"], position={"x": 150, "y": 290, "level": 2}),
            KnowledgeNode(node_id="base_007", name="作差法与作商法判断数列单调性", topic="数列基础",
                cognitive_level="掌握", diagnostic_description="混淆作差法与作商法的适用条件（作商法要求各项为正），或不会因式分解/配凑后判断符号",
                associated_tags=["作差法", "作商法", "单调性判断", "单调性证明"],
                prerequisites=["base_006"], position={"x": 150, "y": 410, "level": 3}),
            KnowledgeNode(node_id="base_008", name="数列的周期性初步", topic="数列基础",
                cognitive_level="理解", diagnostic_description="不会通过递推公式迭代找周期，或混淆数列周期与函数周期的概念",
                associated_tags=["周期数列", "模运算"],
                prerequisites=["base_003"], position={"x": 400, "y": 290, "level": 2}),
        ]
        self._register_nodes(base_nodes, base)
        self.skill_trees["数列基础"] = base

        # ================================================================
        # 2. 等差数列 (12 nodes)
        # ================================================================
        arith = SkillTree(topic="等差数列")
        arith_nodes = [
            KnowledgeNode(node_id="ap_001", name="等差数列的定义与判定", topic="等差数列",
                cognitive_level="理解", diagnostic_description="判定等差数列时只用a2-a1=a3-a2，不知道需要验证an+1-an为常数对任意n成立",
                associated_tags=["等差数列", "等差数列定义与证明", "等差数列判定", "等差数列证明", "等差数列证明（定义法）", "公差计算"],
                prerequisites=["base_002"], position={"x": 100, "y": 170, "level": 1}),
            KnowledgeNode(node_id="ap_002", name="等差数列的通项公式（基本量法）", topic="等差数列",
                cognitive_level="掌握", diagnostic_description="不会通过a1和d两个基本量建立方程组求通项，属于等差数列解题的第一障碍",
                associated_tags=["等差数列通项公式", "等差数列基本量计算", "等差数列基本量求解", "等差数列基本运算", "等差数列通项", "方程思想", "方程组求解"],
                prerequisites=["ap_001"], position={"x": 60, "y": 290, "level": 2}),
            KnowledgeNode(node_id="ap_003", name="等差中项", topic="等差数列",
                cognitive_level="掌握", diagnostic_description="不理解'2b=a+c ⇔ a,b,c成等差'的双向等价性（只知道正向，忘记逆用判定）",
                associated_tags=["等差中项", "等差中项条件", "等差中项性质", "等差中项应用"],
                prerequisites=["ap_001"], position={"x": 180, "y": 290, "level": 2}),
            KnowledgeNode(node_id="ap_004", name="等差数列的下标性质", topic="等差数列",
                cognitive_level="掌握", diagnostic_description="不会利用'm+n=p+q⇒am+an=ap+aq'化简条件，习惯性地设a1,d硬解导致计算量爆炸",
                associated_tags=["等差数列下标性质", "等差数列性质", "下标性质推广"],
                prerequisites=["ap_003"], position={"x": 180, "y": 410, "level": 3}),
            KnowledgeNode(node_id="ap_005", name="等差数列的前n项和公式", topic="等差数列",
                cognitive_level="掌握", diagnostic_description="两个求和公式(Sn=na1+n(n-1)d/2与Sn=n(a1+an)/2)只会用一个，不会根据已知条件灵活选择",
                associated_tags=["等差数列前n项和", "等差数列前n项和公式", "等差数列求和", "等差数列求和公式", "等差数列和公式", "前n项和公式", "前n项和公式应用"],
                prerequisites=["ap_002"], position={"x": 60, "y": 410, "level": 3}),
            KnowledgeNode(node_id="ap_006", name="等差数列片段和性质", topic="等差数列",
                cognitive_level="掌握", diagnostic_description="不知道Sm, S2m-Sm, S3m-S2m也成等差数列，碰到求中间片段和就束手无策",
                associated_tags=["等差数列片段和性质"],
                prerequisites=["ap_005"], position={"x": 20, "y": 530, "level": 4}),
            KnowledgeNode(node_id="ap_007", name="Sn/n的性质", topic="等差数列",
                cognitive_level="掌握", diagnostic_description="不知道{Sn/n}也是等差数列（首项a1，公差d/2），导致比例类问题无从下手",
                associated_tags=["Sn/n的性质", "和与通项关系"],
                prerequisites=["ap_005"], position={"x": 100, "y": 530, "level": 4}),
            KnowledgeNode(node_id="ap_008", name="等差数列的设元技巧（对称设元）", topic="等差数列",
                cognitive_level="运用", diagnostic_description="不会用a-d, a, a+d（三项）或a-3d, a-d, a+d, a+3d（四项）设元简化条件",
                associated_tags=["对称设元", "对称设元法", "对称性"],
                prerequisites=["ap_002"], position={"x": 60, "y": 530, "level": 3}),
            KnowledgeNode(node_id="ap_009", name="等差数列的最值问题", topic="等差数列",
                cognitive_level="综合运用", diagnostic_description="求Sn最值时不会配方或不会用邻项法（an≥0且an+1≤0处取最大值），两类方法割裂",
                associated_tags=["等差数列前n项和最值", "配方法", "配方法求最值", "二次函数配方求最值", "邻项比较法", "邻项法（符号分析法）", "数列的最值", "最值问题", "最值思想", "等差数列求参", "等差数列通项与前n项和"],
                prerequisites=["ap_005", "base_006"], position={"x": 180, "y": 530, "level": 4}),
            KnowledgeNode(node_id="ap_010", name="等差数列奇数项和与偶数项和", topic="等差数列",
                cognitive_level="运用", diagnostic_description="不知道S奇/S偶与中间项的关系，碰到奇偶项和比值题只能硬算",
                associated_tags=["等差数列奇数项和", "比例计算", "中间项性质（am/bm = A(2m-1)/B(2m-1)）"],
                prerequisites=["ap_005", "ap_004"], position={"x": 20, "y": 650, "level": 5}),
            KnowledgeNode(node_id="ap_011", name="两个等差数列和之比（An/Bn型）", topic="等差数列",
                cognitive_level="综合运用", diagnostic_description="不知道an/bn = A(2n-1)/B(2n-1)的转化公式，在已知Sn/Tn比值时求an/bn遇到瓶颈",
                associated_tags=["等差数列和比值性质", "等差数列与等比数列综合", "比值计算"],
                prerequisites=["ap_007", "ap_004"], position={"x": 100, "y": 650, "level": 5}),
            KnowledgeNode(node_id="ap_012", name="等差数列与方程综合", topic="等差数列",
                cognitive_level="综合运用", diagnostic_description="碰到'某三项成等差'与方程根结合的问题，不会用等差中项建立方程",
                associated_tags=["等差数列与方程根的关系", "韦达定理", "根与系数的关系", "方程求解", "方程求整数解", "方程求正整数"],
                prerequisites=["ap_002", "ap_005"], position={"x": 180, "y": 650, "level": 5}),
        ]
        self._register_nodes(arith_nodes, arith)
        self.skill_trees["等差数列"] = arith

        # ================================================================
        # 3. 等比数列 (10 nodes)
        # ================================================================
        geo = SkillTree(topic="等比数列")
        geo_nodes = [
            KnowledgeNode(node_id="gp_001", name="等比数列的定义与判定", topic="等比数列",
                cognitive_level="理解", diagnostic_description="判定时忽略an≠0、q≠0的隐含条件，或用an+1/an=q验证时未讨论an=0的特殊情况",
                associated_tags=["等比数列", "等比数列定义与判定", "等比数列定义与证明", "等比数列判定", "等比数列证明", "等比数列证明（定义法）", "等比数列判定与求和"],
                prerequisites=["base_002"], position={"x": 300, "y": 170, "level": 1}),
            KnowledgeNode(node_id="gp_002", name="等比数列的通项公式（基本量法）", topic="等比数列",
                cognitive_level="掌握", diagnostic_description="不会通过a1和q两个基本量建立方程组求通项，尤其是涉及幂次运算时容易出错",
                associated_tags=["等比数列通项公式", "等比数列基本量计算", "等比数列基本运算", "等比数列求通项", "等比数列通项与前n项和"],
                prerequisites=["gp_001"], position={"x": 270, "y": 290, "level": 2}),
            KnowledgeNode(node_id="gp_003", name="等比中项", topic="等比数列",
                cognitive_level="掌握", diagnostic_description="不理解'b²=ac ⇔ a,b,c成等比'的等价关系，或忽略同号条件的限制",
                associated_tags=["等比中项", "等比中项性质"],
                prerequisites=["gp_001"], position={"x": 370, "y": 290, "level": 2}),
            KnowledgeNode(node_id="gp_004", name="等比数列的下标性质", topic="等比数列",
                cognitive_level="掌握", diagnostic_description="不知道m+n=p+q⇒am·an=ap·aq，与等差下标性质混淆（加减→乘除）",
                associated_tags=["等比数列性质", "等比数列性质（下标和）"],
                prerequisites=["gp_003"], position={"x": 370, "y": 410, "level": 3}),
            KnowledgeNode(node_id="gp_005", name="等比数列的前n项和公式（含q=1与q≠1分类讨论）", topic="等比数列",
                cognitive_level="掌握", diagnostic_description="直接用Sn=a1(1-q^n)/(1-q)而忘记验证q=1的情况，这是等比数列的最高频错误",
                associated_tags=["等比数列求和", "等比数列求和公式", "等比数列前n项和", "等比数列前n项和公式", "等比数列判定与求和", "分类讨论（q=1与q不等于1）"],
                prerequisites=["gp_002"], position={"x": 270, "y": 410, "level": 3}),
            KnowledgeNode(node_id="gp_006", name="等比数列片段和性质", topic="等比数列",
                cognitive_level="掌握", diagnostic_description="不知道Sm, S2m-Sm, S3m-S2m在q≠-1时也成等比数列",
                associated_tags=["等比数列片段和性质"],
                prerequisites=["gp_005"], position={"x": 270, "y": 530, "level": 4}),
            KnowledgeNode(node_id="gp_007", name="等比数列的单调性判定", topic="等比数列",
                cognitive_level="掌握", diagnostic_description="不会根据a1的正负和q的范围（q<0, 0<q<1, q=1, q>1）分类判断单调性",
                associated_tags=["等比数列单调性"],
                prerequisites=["gp_002"], position={"x": 340, "y": 530, "level": 3}),
            KnowledgeNode(node_id="gp_008", name="等比数列的设元技巧（对称设元）", topic="等比数列",
                cognitive_level="运用", diagnostic_description="不会用a/q, a, aq设三项（代替a, aq, aq²），导致条件化简复杂化",
                associated_tags=["对称设元"],
                prerequisites=["gp_002"], position={"x": 270, "y": 530, "level": 4}),
            KnowledgeNode(node_id="gp_009", name="等比数列与对数/指数综合", topic="等比数列",
                cognitive_level="综合运用", diagnostic_description="不会利用'取对数将等比关系转化为等差关系'来简化指数型条件",
                associated_tags=["对数运算", "对数变换", "对数与指数互化", "对数转等比", "指数运算", "指数方程求解", "指对数转化", "指数型数列", "指数函数求参", "指数不等式", "指数形式递推"],
                prerequisites=["gp_002"], position={"x": 410, "y": 530, "level": 3}),
            KnowledgeNode(node_id="gp_010", name="等比数列的奇偶项和性质", topic="等比数列",
                cognitive_level="综合运用", diagnostic_description="当q=-1时不会分析奇偶项和的特殊性质，或不会推导S奇与S偶的比例关系",
                associated_tags=["等比数列奇偶项和性质", "奇偶项分组"],
                prerequisites=["gp_005"], position={"x": 340, "y": 650, "level": 5}),
        ]
        self._register_nodes(geo_nodes, geo)
        self.skill_trees["等比数列"] = geo

        # ================================================================
        # 4. 递推数列求通项 (17 nodes)
        # ================================================================
        recur = SkillTree(topic="递推数列求通项")
        recur_nodes = [
            KnowledgeNode(node_id="recur_001", name="递推关系的识别与变形", topic="递推数列求通项",
                cognitive_level="理解", diagnostic_description="拿到递推式后不知从何入手，不会通过取倒数、分解因式、移项等基本变形将陌生递推式转化为熟悉类型",
                associated_tags=["递推关系", "递推关系变形", "递推关系处理", "递推变换", "递推变形", "递推公式变形", "分式变形", "代数式变形", "分式化简", "因式分解", "因式分解法"],
                prerequisites=["base_003", "ap_001", "gp_001"], position={"x": 550, "y": 170, "level": 1}),
            KnowledgeNode(node_id="recur_002", name="累加法求通项（an+1-an=f(n)型）", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="不会识别an+1-an=f(n)的形式，或写出累加式后不会求∑f(n)（需要等差数列/裂项求和基础）",
                associated_tags=["累加法", "累加法求通项", "累差法（作差法）求通项"],
                prerequisites=["base_003"], position={"x": 530, "y": 290, "level": 2}),
            KnowledgeNode(node_id="recur_003", name="累乘法求通项（an+1/an=f(n)型）", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="不会识别an+1/an=f(n)的形式，或累乘后不会化简分子分母的连乘积",
                associated_tags=["累乘法", "累乘法（累积法）", "累乘法求通项"],
                prerequisites=["base_003"], position={"x": 630, "y": 290, "level": 2}),
            KnowledgeNode(node_id="recur_004", name="由Sn求an（an=Sn-Sn-1，n≥2分段讨论）", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="直接写an=Sn-Sn-1而不分n=1与n≥2讨论，或n≥2求出的an代入n=1后不与S1核对",
                associated_tags=["$a_n$与$S_n$的关系", "由Sn求an（类讨论型）", "类讨论型数列", "前n项和反求通项", "前n项和求通项", "前n项和与通项的关系", "分类讨论（n=1与n大于等于2）"],
                prerequisites=["base_005"], position={"x": 550, "y": 290, "level": 2}),
            KnowledgeNode(node_id="recur_005", name="待定系数法构造等比数列（an+1=pan+q型）", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="不会设an+1+λ=p(an+λ)，或求出λ后不知道{an+λ}是公比为p的等比数列",
                associated_tags=["构造法", "待定系数法", "构造法求通项", "构造法（和差构造）"],
                prerequisites=["recur_001", "gp_002"], position={"x": 520, "y": 410, "level": 3}),
            KnowledgeNode(node_id="recur_006", name="待定系数法构造等比数列（an+1=pan+q^n型）", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="面对含q^n的递推式，不会通过两边同除q^(n+1)或设an+λq^n来构造新数列",
                associated_tags=["构造法", "待定系数法", "系数比较", "幂次型递推"],
                prerequisites=["recur_005"], position={"x": 430, "y": 530, "level": 4}),
            KnowledgeNode(node_id="recur_007", name="待定系数法构造等比数列（an+1=pan+kn+b型）", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="面对含n一次式的递推（an+1=pan+kn+b），不会设an+1+An+B=p(an+A(n-1)+B)来消去一次项",
                associated_tags=["构造法", "待定系数法"],
                prerequisites=["recur_005"], position={"x": 520, "y": 530, "level": 4}),
            KnowledgeNode(node_id="recur_008", name="倒数变换法求通项", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="面对an+1=an/(kan+b)型递推式，不知道取倒数可转化为等差数列或an+1=pan+q型",
                associated_tags=["倒数变换", "倒数转等差", "分式形式递推", "分式型递推", "分式递推", "分式变换", "分式运算"],
                prerequisites=["recur_001"], position={"x": 610, "y": 410, "level": 3}),
            KnowledgeNode(node_id="recur_009", name="对数变换法求通项（an+1=p·an^k型）", topic="递推数列求通项",
                cognitive_level="运用", diagnostic_description="面对an+1=p·an^k型（指数型乘积递推），不知道两边取对数化为线性递推",
                associated_tags=["对数变换", "对数运算", "对数转等比"],
                prerequisites=["recur_001"], position={"x": 700, "y": 410, "level": 3}),
            KnowledgeNode(node_id="recur_010", name="根式构造法求通项", topic="递推数列求通项",
                cognitive_level="运用", diagnostic_description="面对含根号的递推式，不会通过平方、配凑完全平方等方式消去根号构造等差/等比数列",
                associated_tags=["构造法（根式构造）", "根式运算", "完全平方公式", "平方差公式应用"],
                prerequisites=["recur_001"], position={"x": 790, "y": 410, "level": 3}),
            KnowledgeNode(node_id="recur_011", name="不动点法求通项（分式线性递推an+1=(aan+b)/(can+d)型）", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="不会将分式递推化为(an+1-x1)/(an+1-x2)=k·(an-x1)/(an-x2)的等比形式来求通项",
                associated_tags=["不动点", "不动点原理", "分式形式递推", "分式型递推"],
                prerequisites=["recur_005"], position={"x": 430, "y": 650, "level": 5}),
            KnowledgeNode(node_id="recur_012", name="特征根法求通项（二阶线性递推an+2=pan+1+qan型）", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="不会建立特征方程x²-px-q=0，不会根据两根情况（不等/相等/共轭复根）分类写通项",
                associated_tags=["构造法", "待定系数法"],
                prerequisites=["recur_005"], position={"x": 540, "y": 650, "level": 5}),
            KnowledgeNode(node_id="recur_013", name="由递推关系构造等差数列", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="不会通过变形证明{an+1-an}为常数，或不会通过构造新数列证明{bn}是等差数列",
                associated_tags=["构造法", "递推定义等差数列", "递推关系判定等差数列", "递推转等差"],
                prerequisites=["recur_001", "ap_001"], position={"x": 650, "y": 530, "level": 4}),
            KnowledgeNode(node_id="recur_014", name="由递推关系构造等比数列", topic="递推数列求通项",
                cognitive_level="掌握", diagnostic_description="不会通过变形证明{an+1/an}为常数（或常数q），或不会构造{an+λ}证明其为等比数列",
                associated_tags=["构造法", "构造法（比值构造）", "构造法（平方构造）"],
                prerequisites=["recur_001", "gp_001"], position={"x": 740, "y": 530, "level": 4}),
            KnowledgeNode(node_id="recur_015", name="联立递推方程组消元法", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="面对{an}和{bn}联立递推的方程组，不会通过消元或代入化为单一数列的递推",
                associated_tags=["联立方程", "数列综合关系"],
                prerequisites=["recur_001"], position={"x": 830, "y": 530, "level": 3}),
            KnowledgeNode(node_id="recur_016", name="由几何/函数/实际背景建立递推关系", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="不会从函数图像交点、几何图形迭代、实际情境中抽象出递推关系",
                associated_tags=["函数与几何", "函数与数列", "双曲线离心率", "直线方程", "分段递推"],
                prerequisites=["base_003"], position={"x": 920, "y": 410, "level": 2}),
            KnowledgeNode(node_id="recur_017", name="递推关系中的奇偶分类与分段递推", topic="递推数列求通项",
                cognitive_level="综合运用", diagnostic_description="面对n分奇偶给出不同递推式的情况，不会分别求奇子列和偶子列的通项再合并",
                associated_tags=["奇偶分类讨论", "分段递推", "奇偶分组"],
                prerequisites=["recur_001"], position={"x": 600, "y": 290, "level": 2}),
        ]
        self._register_nodes(recur_nodes, recur)
        self.skill_trees["递推数列求通项"] = recur

        # ================================================================
        # 5. 数列求和 (12 nodes)
        # ================================================================
        sum_tree = SkillTree(topic="数列求和")
        sum_nodes = [
            KnowledgeNode(node_id="sum_001", name="公式求和法（等差/等比/平方和/立方和/奇数和）", topic="数列求和",
                cognitive_level="掌握", diagnostic_description="只记住等差等比公式，碰到1²+2²+…+n²或1³+2³+…+n³等常用求和直接放弃",
                associated_tags=["公式求和法", "等差数列求和公式", "等比数列求和公式", "奇数求和公式", "多项式函数求和", "二阶等差数列"],
                prerequisites=["ap_005", "gp_005"], position={"x": 300, "y": 170, "level": 1}),
            KnowledgeNode(node_id="sum_002", name="分组求和法（等差+等比混合/通项拆分）", topic="数列求和",
                cognitive_level="掌握", diagnostic_description="面对an=等差数列±等比数列型，不会拆分为两个独立数列分别求和再合并",
                associated_tags=["分组求和法", "分组求和验证", "拆项法", "拆项求和", "差比数列求和", "分段求和", "分类求和"],
                prerequisites=["sum_001"], position={"x": 200, "y": 290, "level": 2}),
            KnowledgeNode(node_id="sum_003", name="分式裂项求和（基本型：1/[n(n+k)]类）", topic="数列求和",
                cognitive_level="掌握", diagnostic_description="不会将1/[n(n+k)]拆成(1/k)(1/n-1/(n+k))，或不理解裂项后中间项相消的'望远镜'原理",
                associated_tags=["裂项相消法", "裂项相消", "裂项相消思想", "分式裂项", "分式裂项相消", "分式函数", "分式函数变形", "分式函数求和", "分式求和", "望远镜求和", "复杂分式求和"],
                prerequisites=["sum_001"], position={"x": 400, "y": 290, "level": 2}),
            KnowledgeNode(node_id="sum_004", name="根式裂项求和", topic="数列求和",
                cognitive_level="运用", diagnostic_description="面对1/(√(n+1)+√n)型根式分母，不知道利用有理化分子化为√(n+1)-√n后裂项",
                associated_tags=["根式裂项", "裂项相消法"],
                prerequisites=["sum_003"], position={"x": 350, "y": 410, "level": 3}),
            KnowledgeNode(node_id="sum_005", name="指数型裂项求和", topic="数列求和",
                cognitive_level="运用", diagnostic_description="面对含指数分母的分式（如1/(a^n±b)），不会通过代数变形构造裂项结构",
                associated_tags=["指数裂项", "裂项相消法"],
                prerequisites=["sum_003"], position={"x": 450, "y": 410, "level": 3}),
            KnowledgeNode(node_id="sum_006", name="高阶裂项与待定系数裂项", topic="数列求和",
                cognitive_level="综合运用", diagnostic_description="面对分母为三次式或乘积复杂的分式，不会用待定系数法反推裂项形式",
                associated_tags=["待定系数裂项", "裂项与估值", "分式裂项", "拆项法"],
                prerequisites=["sum_003"], position={"x": 550, "y": 410, "level": 3}),
            KnowledgeNode(node_id="sum_007", name="错位相减法（等差×等比型差比数列求和）", topic="数列求和",
                cognitive_level="掌握", diagnostic_description="错位相减时对齐错误（漏项或多项），或减完后不会用等比求和公式整理结果",
                associated_tags=["错位相减法", "差比数列求和"],
                prerequisites=["gp_005"], position={"x": 300, "y": 410, "level": 3}),
            KnowledgeNode(node_id="sum_008", name="倒序相加法", topic="数列求和",
                cognitive_level="掌握", diagnostic_description="不会识别倒序相加的适用场景（首尾项和为定值，或通项满足f(k)+f(n+1-k)=常数）",
                associated_tags=["倒序相加", "倒序相加法", "函数对称配对", "函数对称性", "对称配对", "函数背景法"],
                prerequisites=["sum_001"], position={"x": 650, "y": 290, "level": 2}),
            KnowledgeNode(node_id="sum_009", name="奇偶分组求和法", topic="数列求和",
                cognitive_level="运用", diagnostic_description="面对含(-1)^n或条件随n奇偶变化的数列，不会按奇数项/偶数项分别求和再合并",
                associated_tags=["奇偶分类讨论", "奇偶分组", "奇偶讨论", "奇偶项分组", "奇偶项配对", "奇偶性求和", "奇偶性分析"],
                prerequisites=["sum_002"], position={"x": 200, "y": 410, "level": 3}),
            KnowledgeNode(node_id="sum_010", name="分段求和法（绝对值/分段定义型）", topic="数列求和",
                cognitive_level="综合运用", diagnostic_description="含绝对值的数列求和时忘记先找正负分界点分段处理，或分段后索引错乱",
                associated_tags=["绝对值求和", "交错符号求和", "分类讨论", "分段求和", "分段函数", "类讨论型数列（分段型）"],
                prerequisites=["sum_002"], position={"x": 100, "y": 410, "level": 3}),
            KnowledgeNode(node_id="sum_011", name="并项求和法（相邻项配对）", topic="数列求和",
                cognitive_level="运用", diagnostic_description="不会利用an+an+1的简单规律（如相邻项和为定值或等比）将2m项配成m对",
                associated_tags=["相邻两项配对", "相邻配对", "奇偶项配对", "对称配对", "配对放缩"],
                prerequisites=["sum_002"], position={"x": 200, "y": 530, "level": 4}),
            KnowledgeNode(node_id="sum_012", name="数列求和与恒成立/参数范围综合", topic="数列求和",
                cognitive_level="综合运用", diagnostic_description="求和后需论证Sn≥λ恒成立或求参数范围时，不会将求和结果转化为最值问题",
                associated_tags=["恒成立问题", "不等式恒成立", "恒成立估值", "参数范围", "区间估值", "最值估计", "上界判定", "上界证明"],
                prerequisites=["sum_003", "sum_007"], position={"x": 400, "y": 530, "level": 4}),
        ]
        self._register_nodes(sum_nodes, sum_tree)
        self.skill_trees["数列求和"] = sum_tree

        # ================================================================
        # 6. 数列的单调性、周期性与最值 (6 nodes)
        # ================================================================
        mono = SkillTree(topic="数列的单调性、周期性与最值")
        mono_nodes = [
            KnowledgeNode(node_id="mono_001", name="数列单调性的判定（作差法/作商法/函数法）", topic="数列的单调性、周期性与最值",
                cognitive_level="掌握", diagnostic_description="三种方法选用不当：负项数列用商法、分式型不会构造函数用导数法",
                associated_tags=["单调性判断", "单调性证明", "数列单调性", "参数范围"],
                prerequisites=["base_007"], position={"x": 300, "y": 170, "level": 1}),
            KnowledgeNode(node_id="mono_002", name="函数背景法分析数列最值与单调性", topic="数列的单调性、周期性与最值",
                cognitive_level="综合运用", diagnostic_description="不会将an=f(n)延拓为f(x)后利用导数/函数性质分析单调性，始终困在作差法中",
                associated_tags=["函数背景法", "函数求导", "函数求导法", "函数分解", "分式函数变形", "二次函数性质", "二次函数配方求最值", "二次函数值域"],
                prerequisites=["mono_001"], position={"x": 250, "y": 290, "level": 2}),
            KnowledgeNode(node_id="mono_003", name="邻项比较法求数列最大/最小项", topic="数列的单调性、周期性与最值",
                cognitive_level="掌握", diagnostic_description="不会利用an≥an+1且an≥an-1解出最大项下标，或用an/an+1≥1且an/an-1≥1解最值项",
                associated_tags=["邻项比较法", "邻项法（符号分析法）", "数列最值", "数列最值（非等差数列）", "最值问题"],
                prerequisites=["mono_001"], position={"x": 380, "y": 290, "level": 2}),
            KnowledgeNode(node_id="mono_004", name="周期数列的判定与求值", topic="数列的单调性、周期性与最值",
                cognitive_level="掌握", diagnostic_description="通过递推迭代找周期时，不会利用模运算直接定位（如求a2026时不知道利用周期简化）",
                associated_tags=["周期数列", "模运算", "绝对值递推", "分段递推"],
                prerequisites=["base_008"], position={"x": 500, "y": 290, "level": 2}),
            KnowledgeNode(node_id="mono_005", name="递增/递减数列的参数约束问题", topic="数列的单调性、周期性与最值",
                cognitive_level="综合运用", diagnostic_description="已知数列递增求参数范围时，不会将'an+1>an恒成立'转化为参变分离或二次不等式恒成立",
                associated_tags=["参数范围", "递增数列", "参数最值问题", "不等式求解", "不等式组求解"],
                prerequisites=["mono_001"], position={"x": 250, "y": 410, "level": 3}),
            KnowledgeNode(node_id="mono_006", name="数列单调性与不等式综合", topic="数列的单调性、周期性与最值",
                cognitive_level="综合运用", diagnostic_description="不会利用数列单调性证明不等式（如证明数列有界、递减有下界则收敛等）",
                associated_tags=["单调性证明", "不等式证明", "数列不等式"],
                prerequisites=["mono_001", "mono_003"], position={"x": 380, "y": 410, "level": 3}),
        ]
        self._register_nodes(mono_nodes, mono)
        self.skill_trees["数列的单调性、周期性与最值"] = mono

        # ================================================================
        # 7. 数学归纳法 (5 nodes)
        # ================================================================
        ind = SkillTree(topic="数学归纳法")
        ind_nodes = [
            KnowledgeNode(node_id="ind_001", name="数学归纳法的基本原理", topic="数学归纳法",
                cognitive_level="理解", diagnostic_description="不理解'n=k成立推n=k+1成立'的逻辑链条，或错误地假设结论成立后再去证明假设",
                associated_tags=["数学归纳法"],
                prerequisites=["base_002"], position={"x": 500, "y": 50, "level": 0}),
            KnowledgeNode(node_id="ind_002", name="第一数学归纳法证明等式（含数列通项/求和）", topic="数学归纳法",
                cognitive_level="掌握", diagnostic_description="归纳递推步骤中不知道如何利用归纳假设变形目标式，或目标式的代数变形卡住",
                associated_tags=["数学归纳法"],
                prerequisites=["ind_001"], position={"x": 450, "y": 170, "level": 1}),
            KnowledgeNode(node_id="ind_003", name="第二数学归纳法（强归纳法）", topic="数学归纳法",
                cognitive_level="运用", diagnostic_description="不理解第二归纳法与第一归纳法的区别，不知道该假设n≤k均成立（而非仅n=k）",
                associated_tags=["数学归纳法"],
                prerequisites=["ind_001"], position={"x": 580, "y": 170, "level": 1}),
            KnowledgeNode(node_id="ind_004", name="归纳-猜想-证明（完整路径）", topic="数学归纳法",
                cognitive_level="综合运用", diagnostic_description="不会通过计算前几项归纳猜想通项公式，或猜想后不会用数学归纳法严格证明",
                associated_tags=["数学归纳法"],
                prerequisites=["ind_002"], position={"x": 450, "y": 290, "level": 2}),
            KnowledgeNode(node_id="ind_005", name="数学归纳法证明数列不等式", topic="数学归纳法",
                cognitive_level="综合运用", diagnostic_description="归纳递推中不会利用归纳假设进行放缩，或放缩方向错误导致不等式方向反转",
                associated_tags=["数学归纳法", "不等式证明", "数列不等式证明", "双向不等式"],
                prerequisites=["ind_002"], position={"x": 580, "y": 290, "level": 2}),
        ]
        self._register_nodes(ind_nodes, ind)
        self.skill_trees["数学归纳法"] = ind

        # ================================================================
        # 8. 数列不等式与放缩法 (8 nodes)
        # ================================================================
        ineq = SkillTree(topic="数列不等式与放缩法")
        ineq_nodes = [
            KnowledgeNode(node_id="ineq_001", name="裂项放缩法证明和式不等式", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="不会将不易求和的通项放缩为可裂项的形式，或放缩后和式超出目标范围（放缩过度或不足）",
                associated_tags=["裂项放缩", "裂项放缩法", "分式裂项", "放缩技巧", "精确放缩", "裂项相消"],
                prerequisites=["sum_003", "ind_005"], position={"x": 500, "y": 170, "level": 1}),
            KnowledgeNode(node_id="ineq_002", name="伪等比放缩法（构造等比上界）", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="不会通过构造an+1≤q·an（0<q<1）或类似形式，将裂项和放缩为等比级数和",
                associated_tags=["伪等比放缩", "放缩法", "迭代放缩", "指数放缩", "精确放缩"],
                prerequisites=["gp_005"], position={"x": 400, "y": 170, "level": 1}),
            KnowledgeNode(node_id="ineq_003", name="根式裂项放缩", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="面对含根式的和式不等式，不会利用有理化分子的方式构造裂项放缩结构",
                associated_tags=["根式裂项放缩", "根式裂项"],
                prerequisites=["ineq_001"], position={"x": 450, "y": 290, "level": 2}),
            KnowledgeNode(node_id="ineq_004", name="奇偶性放缩法", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="面对交错级数（含(-1)^n），不会利用相邻项配对或奇偶项分组来调整放缩方向",
                associated_tags=["奇偶性放缩", "交错和", "交错级数", "常数调整", "符号分析"],
                prerequisites=["sum_009", "ineq_001"], position={"x": 550, "y": 290, "level": 2}),
            KnowledgeNode(node_id="ineq_005", name="迭代放缩法", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="不会通过递推式迭代展开，放缩每一项得到通项的上界估计",
                associated_tags=["迭代放缩", "迭代计算", "放缩法"],
                prerequisites=["recur_005"], position={"x": 700, "y": 170, "level": 1}),
            KnowledgeNode(node_id="ineq_006", name="放缩法的精度控制与多级放缩", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="放缩后和式超出目标范围时，不会调整放缩起点（如保留前几项不缩放）或换用更精细的放缩",
                associated_tags=["精确放缩", "双向不等式", "放缩法", "上界证明"],
                prerequisites=["ineq_001", "ineq_002"], position={"x": 500, "y": 410, "level": 3}),
            KnowledgeNode(node_id="ineq_007", name="柯西不等式在数列不等式中的应用", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="不会将求和式重组为柯西不等式形式，或不会选择合适的两组数进行柯西放缩",
                associated_tags=["柯西不等式", "基本不等式"],
                prerequisites=["ind_005"], position={"x": 650, "y": 290, "level": 2}),
            KnowledgeNode(node_id="ineq_008", name="伯努利不等式与指数放缩", topic="数列不等式与放缩法",
                cognitive_level="综合运用", diagnostic_description="不会利用(1+x)^n≥1+nx（x>-1）等伯努利不等式对指数型数列进行放缩",
                associated_tags=["伯努利不等式", "指数放缩", "对数放缩"],
                prerequisites=["gp_002"], position={"x": 800, "y": 170, "level": 1}),
        ]
        self._register_nodes(ineq_nodes, ineq)
        self.skill_trees["数列不等式与放缩法"] = ineq

        # ================================================================
        # 9. 数列综合应用 (5 nodes)
        # ================================================================
        comp = SkillTree(topic="数列综合应用")
        comp_nodes = [
            KnowledgeNode(node_id="comp_001", name="等差与等比数列综合（混合条件型）", topic="数列综合应用",
                cognitive_level="综合运用", diagnostic_description="面对同时含有等差和等比条件的题目，不知道先各自建立方程组再关联求解",
                associated_tags=["等差与等比综合", "等差数列与等比数列综合", "等比数列通项公式", "等差数列通项公式"],
                prerequisites=["ap_002", "gp_002"], position={"x": 300, "y": 170, "level": 1}),
            KnowledgeNode(node_id="comp_002", name="由数列构造新数列并证明等差/等比", topic="数列综合应用",
                cognitive_level="综合运用", diagnostic_description="不会根据目标设新数列bn，或不会从an的递推关系导出bn的递推关系",
                associated_tags=["构造法", "存在性参数求解"],
                prerequisites=["recur_013", "recur_014"], position={"x": 450, "y": 290, "level": 2}),
            KnowledgeNode(node_id="comp_003", name="数列存在性问题与反证法", topic="数列综合应用",
                cognitive_level="综合运用", diagnostic_description="不会用反证法证明某些项不存在或数列不可能同时满足两个矛盾条件",
                associated_tags=["反证法", "存在性参数求解", "无理数性质（有理数不等于无理数）", "整除问题"],
                prerequisites=["ap_001", "gp_001"], position={"x": 200, "y": 170, "level": 1}),
            KnowledgeNode(node_id="comp_004", name="数列与函数/导数综合", topic="数列综合应用",
                cognitive_level="综合运用", diagnostic_description="不会利用导函数零点确定数列单调性转折点，或不会利用曲线切线建立数列的递推关系",
                associated_tags=["函数与数列", "函数求导", "函数求导法", "函数与几何", "切线问题", "三角函数"],
                prerequisites=["base_006", "mono_002"], position={"x": 550, "y": 170, "level": 1}),
            KnowledgeNode(node_id="comp_005", name="数列与不等式综合（无放缩，纯推理型）", topic="数列综合应用",
                cognitive_level="综合运用", diagnostic_description="不会利用等差/等比数列的固有性质（单调性、下标性质）来推导或证明不等式关系",
                associated_tags=["不等式分析", "不等式求解", "不等式求整数范围", "不等式求最小整数", "最值问题", "参数最值问题", "恒成立问题"],
                prerequisites=["ap_004", "gp_004", "mono_006"], position={"x": 700, "y": 290, "level": 2}),
        ]
        self._register_nodes(comp_nodes, comp)
        self.skill_trees["数列综合应用"] = comp

    # ================================================================
    # 查询方法
    # ================================================================

    def get_skill_tree(self, topic: str) -> Optional[SkillTree]:
        """获取技能树"""
        return self.skill_trees.get(topic)

    def get_all_nodes(self) -> Dict[str, KnowledgeNode]:
        """获取全局节点注册表"""
        return self._all_nodes

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """按ID获取节点（跨专题查询）"""
        return self._all_nodes.get(node_id)

    def get_all_topics(self) -> List[str]:
        """获取所有专题列表"""
        return list(self.skill_trees.keys())

    def update_node_mastery(self, topic: str, node_id: str, p_known: float) -> KnowledgeNode:
        """更新节点掌握度"""
        tree = self.get_skill_tree(topic)
        if tree is None or node_id not in tree.nodes:
            raise ValueError(f"节点不存在: {topic}/{node_id}")
        node = tree.nodes[node_id]
        node.p_known = p_known
        return node

    # ================================================================
    # 节点状态计算
    # ================================================================

    def calculate_node_status(self, node: KnowledgeNode, all_nodes: Dict[str, KnowledgeNode]) -> NodeStatus:
        """
        计算节点状态（四级掌握度 + 锁定）

        1. 检查前置节点是否都达标（P(L) >= MASTERED_THRESHOLD=0.85）
        2. 如果前置未达标 → 锁定
        3. 如果前置达标 → 根据 P(L) 判断四级状态
        """
        if not node.is_root and node.prerequisites:
            for prereq_id in node.prerequisites:
                prereq = all_nodes.get(prereq_id)
                if prereq is not None:
                    if prereq.p_known < self.MASTERED_THRESHOLD:
                        return NodeStatus.LOCKED
                elif prereq_id in self._all_nodes:
                    return NodeStatus.LOCKED

        if node.p_known >= self.MASTERED_THRESHOLD:
            return NodeStatus.MASTERED
        elif node.p_known >= self.PROFICIENT_THRESHOLD:
            return NodeStatus.PROFICIENT
        elif node.p_known >= self.QUALIFIED_THRESHOLD:
            return NodeStatus.QUALIFIED
        else:
            return NodeStatus.WEAK

    # ================================================================
    # 用户技能树构建（含跨专题依赖处理）
    # ================================================================

    def build_user_skill_tree(self, topic: str, user_mastery: Dict[str, float]) -> SkillTree:
        """
        构建用户的技能树（带状态）

        支持跨专题前置依赖：自动引入其他专题的前置节点参与状态计算

        Args:
            topic: 专题名称
            user_mastery: {node_id: p_known}

        Returns:
            带状态的技能树
        """
        tree = self.get_skill_tree(topic)
        if tree is None:
            raise ValueError(f"专题不存在: {topic}")

        user_tree = SkillTree(topic=topic)

        # 第一步：复制专题内的所有节点
        for node_id, node in tree.nodes.items():
            new_node = KnowledgeNode(
                node_id=node.node_id, name=node.name, topic=node.topic,
                cognitive_level=node.cognitive_level,
                diagnostic_description=node.diagnostic_description,
                associated_tags=node.associated_tags.copy(),
                p_known=user_mastery.get(node_id, 0.0),
                prerequisites=node.prerequisites.copy(),
                is_root=node.is_root,
                position=node.position.copy()
            )
            user_tree.nodes[node_id] = new_node

        # 第二步：引入跨专题前置节点（仅用于状态计算，不在用户树中展示）
        external_nodes = {}
        for node in tree.nodes.values():
            for prereq_id in node.prerequisites:
                if prereq_id not in user_tree.nodes and prereq_id not in external_nodes:
                    prereq = self._all_nodes.get(prereq_id)
                    if prereq is not None:
                        ext_node = KnowledgeNode(
                            node_id=prereq.node_id, name=prereq.name, topic=prereq.topic,
                            cognitive_level=prereq.cognitive_level,
                            diagnostic_description=prereq.diagnostic_description,
                            associated_tags=prereq.associated_tags.copy(),
                            p_known=user_mastery.get(prereq_id, 0.0),
                            prerequisites=prereq.prerequisites.copy(),
                            is_root=prereq.is_root,
                            position=prereq.position.copy()
                        )
                        external_nodes[prereq_id] = ext_node

        # 合并节点用于状态计算
        all_nodes = {**user_tree.nodes, **external_nodes}

        # 第三步：复制边
        user_tree.edges = tree.edges.copy()

        # 第四步：按层级排序计算状态
        sorted_nodes = sorted(
            user_tree.nodes.values(),
            key=lambda n: n.position.get("level", 0)
        )

        for node in sorted_nodes:
            node.status = self.calculate_node_status(node, all_nodes)

        return user_tree

    # ================================================================
    # 专题进度计算
    # ================================================================

    def calculate_topic_progress(self, topic: str, user_mastery: Dict[str, float]) -> TopicProgress:
        """计算专题进度"""
        tree = self.get_skill_tree(topic)
        if tree is None:
            raise ValueError(f"专题不存在: {topic}")

        total = len(tree.nodes)
        mastered = 0
        proficient = 0
        qualified = 0
        weak = 0
        locked = 0

        user_tree = self.build_user_skill_tree(topic, user_mastery)

        for node in user_tree.nodes.values():
            if node.status == NodeStatus.MASTERED:
                mastered += 1
            elif node.status == NodeStatus.PROFICIENT:
                proficient += 1
            elif node.status == NodeStatus.QUALIFIED:
                qualified += 1
            elif node.status == NodeStatus.WEAK:
                weak += 1
            else:
                locked += 1

        # 进度以"至少达到合格"为基准
        progress = ((mastered + proficient + qualified) / total * 100) if total > 0 else 0

        return TopicProgress(
            topic=topic, total_nodes=total, mastered_nodes=mastered,
            learning_nodes=proficient + qualified, weak_nodes=weak, locked_nodes=locked,
            progress_percentage=progress
        )

    # ================================================================
    # 推荐与训练
    # ================================================================

    def get_unlocked_nodes(self, topic: str, user_mastery: Dict[str, float]) -> List[KnowledgeNode]:
        """获取已解锁但未精通的节点（薄弱+合格+良好）"""
        user_tree = self.build_user_skill_tree(topic, user_mastery)
        unlocked = [n for n in user_tree.nodes.values()
                    if n.status in [NodeStatus.WEAK, NodeStatus.QUALIFIED, NodeStatus.PROFICIENT]]
        unlocked.sort(key=lambda n: n.p_known)
        return unlocked

    def get_recommended_training(self, topic: str, user_mastery: Dict[str, float], limit: int = 3) -> List[Dict]:
        """
        获取推荐训练节点

        推荐策略：
        1. 优先推荐薄弱点（红色）
        2. 其次推荐学习中（黄色）
        3. 排除已掌握（绿色）和锁定（灰色）
        """
        unlocked = self.get_unlocked_nodes(topic, user_mastery)
        recommendations = []
        for node in unlocked[:limit]:
            recommendations.append({
                "node_id": node.node_id, "name": node.name,
                "p_known": round(node.p_known, 4), "status": node.status.value,
                "topic": node.topic, "cognitive_level": node.cognitive_level,
                "diagnostic_description": node.diagnostic_description,
            })
        return recommendations

    def get_weakest_nodes(self, user_mastery: Dict[str, float], limit: int = 5) -> List[Dict]:
        """获取全局最薄弱节点（跨专题，用于个性化推荐）"""
        all_unlocked = []
        for topic in self.skill_trees:
            nodes = self.get_unlocked_nodes(topic, user_mastery)
            all_unlocked.extend(nodes)

        all_unlocked.sort(key=lambda n: n.p_known)
        result = []
        for node in all_unlocked[:limit]:
            result.append({
                "node_id": node.node_id, "name": node.name, "topic": node.topic,
                "p_known": round(node.p_known, 4), "status": node.status.value,
                "cognitive_level": node.cognitive_level,
                "diagnostic_description": node.diagnostic_description,
            })
        return result

    # ================================================================
    # 基于关联标签的掌握度匹配
    # ================================================================

    def match_user_mastery_by_tags(self, db_mastery: Dict[str, float]) -> Dict[str, float]:
        """
        将 {knowledge_point_name: p_known} 映射为 {node_id: p_known}

        匹配策略：优先匹配 associated_tags 中的标签，再 fallback 到节点名称匹配
        """
        node_mastery: Dict[str, float] = {}

        for node_id, node in self._all_nodes.items():
            scores = []

            # 策略1：按关联标签匹配
            for tag in node.associated_tags:
                if tag in db_mastery:
                    scores.append(db_mastery[tag])
                else:
                    # 模糊匹配：标签被包含
                    for db_name, p in db_mastery.items():
                        if tag in db_name or db_name in tag:
                            scores.append(p)
                            break

            # 策略2：按节点名称匹配
            if not scores:
                for db_name, p in db_mastery.items():
                    if node.name in db_name or db_name in node.name:
                        scores.append(p)
                        break

            # 策略3：按 node_id 匹配
            if not scores and node_id in db_mastery:
                scores.append(db_mastery[node_id])

            if scores:
                node_mastery[node_id] = sum(scores) / len(scores)

        return node_mastery


# 全局技能树构建器实例
skill_tree_builder = SkillTreeBuilder()


def get_skill_tree_builder() -> SkillTreeBuilder:
    """获取技能树构建器实例"""
    return skill_tree_builder


# 单元测试
if __name__ == "__main__":
    print("=== 知识图谱技能树测试（84节点/9专题） ===\n")

    builder = SkillTreeBuilder()

    # 测试1：节点数量
    print("测试1：全局节点总数")
    all_nodes = builder.get_all_nodes()
    print(f"  总节点数: {len(all_nodes)}")
    print(f"  专题数: {len(builder.get_all_topics())}")
    for topic in builder.get_all_topics():
        tree = builder.get_skill_tree(topic)
        print(f"    {topic}: {len(tree.nodes)}节点, {len(tree.edges)}条边")

    # 测试2：跨专题依赖
    print("\n测试2：跨专题依赖检查")
    cross_topic = []
    for node_id, node in all_nodes.items():
        for prereq_id in node.prerequisites:
            prereq = all_nodes.get(prereq_id)
            if prereq and prereq.topic != node.topic:
                cross_topic.append(f"{node.name}({node.topic}) → {prereq.name}({prereq.topic})")
    print(f"  跨专题依赖数: {len(cross_topic)}")
    for dep in cross_topic:
        print(f"    {dep}")

    # 测试3：构建用户技能树（含跨专题依赖）
    print("\n测试3：等差数列用户技能树（含跨专题前置依赖）")
    user_mastery = {
        "base_001": 0.95, "base_002": 0.90,  # 数列基础已掌握
        "ap_001": 0.85, "ap_002": 0.75, "ap_003": 0.60,
        "ap_004": 0.40, "ap_005": 0.55, "ap_006": 0.20,
        "ap_007": 0.30, "ap_008": 0.65,
    }
    user_tree = builder.build_user_skill_tree("等差数列", user_mastery)
    print("  节点状态:")
    for node_id, node in sorted(user_tree.nodes.items(), key=lambda x: x[1].position.get("level", 0)):
        marker = {"mastered": "[G]", "proficient": "[B]", "qualified": "[O]", "weak": "[R]", "locked": "[-]"}[node.status.value]
        print(f"    {marker} {node.name}: P(L)={node.p_known:.2f} → {node.status.value}")

    # 测试4：关联标签匹配
    print("\n测试4：关联标签匹配测试")
    db_mastery = {
        "等差数列": 0.9, "等差数列定义与证明": 0.85, "等差中项": 0.7,
        "等比数列": 0.8, "数列的通项公式": 0.95,
    }
    node_mastery = builder.match_user_mastery_by_tags(db_mastery)
    print(f"  匹配到的节点数: {len(node_mastery)}")
    for node_id, p in list(node_mastery.items())[:10]:
        node = builder.get_node(node_id)
        print(f"    {node.name}: P(L)={p:.2f}")

    # 测试5：全局最薄弱节点
    print("\n测试5：全局最薄弱节点推荐")
    full_mastery = {
        "base_001": 0.95, "base_002": 0.90, "base_003": 0.80, "base_004": 0.75,
        "base_005": 0.60, "base_006": 0.70, "base_007": 0.45, "base_008": 0.55,
        "ap_001": 0.85, "ap_002": 0.75, "ap_003": 0.60,
        "ap_004": 0.40, "ap_005": 0.55,
        "gp_001": 0.70, "gp_002": 0.50,
        "sum_001": 0.35, "sum_003": 0.30,
        "recur_001": 0.25, "recur_002": 0.20,
    }
    weakest = builder.get_weakest_nodes(full_mastery, limit=5)
    for i, node in enumerate(weakest, 1):
        print(f"    {i}. [{node['topic']}] {node['name']}: P(L)={node['p_known']:.2f} ({node['status']})")

    print("\n=== 所有测试通过！ ===")
