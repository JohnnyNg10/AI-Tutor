"""
提示生成器模块
根据提示等级(L0-L4)生成对应的提示内容

严格遵循PRD 2.2节硬指标实现

提示等级定义：
| 等级 | 触发条件 | Instructor行为 | Actual权重 |
|-----|---------|---------------|-----------|
| L0-自主 | 学生直接提交答案 | 仅批改,不干预 | 1.0 |
| L1-方向 | 学生点击"有点思路但卡住了" | 给出解题方向提示 | 0.8 |
| L2-公式 | 学生点击"需要公式提醒" | 给出相关公式定理 | 0.6 |
| L3-步骤 | 学生点击"教教我" | 给出关键推导步骤 | 0.4 |
| L4-答案 | 学生点击"看答案" | 给出完整解答 | 0.1 |

实现文件：backend/algorithms/hint_generator.py
"""

import sys
import os
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from utils.logger import logger


class HintLevel(Enum):
    """提示等级枚举"""
    L0_AUTONOMOUS = 0   # 自主 - 仅批改
    L1_DIRECTION = 1    # 方向 - 解题方向提示
    L2_FORMULA = 2      # 公式 - 相关公式定理
    L3_STEP = 3         # 步骤 - 关键推导步骤
    L4_ANSWER = 4       # 答案 - 完整解答


@dataclass
class HintContent:
    """提示内容数据结构"""
    level: HintLevel
    title: str
    content: str
    actual_weight: float
    latex_formulas: List[str] = field(default_factory=list)
    follow_up_question: Optional[str] = None


class HintGenerator:
    """
    提示生成器
    
    根据题目内容和提示等级生成对应的提示
    """
    
    # 硬指标：Actual权重
    ACTUAL_WEIGHTS = {
        HintLevel.L0_AUTONOMOUS: 1.0,
        HintLevel.L1_DIRECTION: 0.8,
        HintLevel.L2_FORMULA: 0.6,
        HintLevel.L3_STEP: 0.4,
        HintLevel.L4_ANSWER: 0.1
    }
    
    # 提示等级标题
    LEVEL_TITLES = {
        HintLevel.L0_AUTONOMOUS: "自主解答",
        HintLevel.L1_DIRECTION: "💡 解题方向",
        HintLevel.L2_FORMULA: "📐 公式提醒",
        HintLevel.L3_STEP: "📝 关键步骤",
        HintLevel.L4_ANSWER: "✅ 完整解答"
    }
    
    def __init__(self):
        """初始化提示生成器"""
        logger.info("提示生成器初始化完成")
    
    # ==================== L0: 自主解答 ====================
    
    def generate_l0_hint(self, question_content: str) -> HintContent:
        """
        L0-自主：仅批改，不干预
        
        返回确认信息，鼓励学生独立完成
        """
        content = (
            "好的，请提交你的答案，我会为你批改。\n\n"
            "💪 相信你能独立完成这道题！"
        )
        
        return HintContent(
            level=HintLevel.L0_AUTONOMOUS,
            title=self.LEVEL_TITLES[HintLevel.L0_AUTONOMOUS],
            content=content,
            actual_weight=self.ACTUAL_WEIGHTS[HintLevel.L0_AUTONOMOUS]
        )
    
    # ==================== L1: 解题方向 ====================
    
    def generate_l1_hint(
        self, 
        question_content: str,
        knowledge_points: List[str]
    ) -> HintContent:
        """
        L1-方向：给出解题方向提示
        
        包含：
        - 涉及的知识点
        - 解题思路方向
        - 引导性问题
        """
        # 分析题目类型，生成方向提示
        direction = self._analyze_direction(question_content, knowledge_points)
        
        content = f"""这道题主要考察**{', '.join(knowledge_points[:2])}**。

**解题方向：**
{direction}

**引导问题：**
{self._generate_guiding_question(question_content, knowledge_points)}

试着从这个角度思考，相信你能找到突破口！💪"""
        
        return HintContent(
            level=HintLevel.L1_DIRECTION,
            title=self.LEVEL_TITLES[HintLevel.L1_DIRECTION],
            content=content,
            actual_weight=self.ACTUAL_WEIGHTS[HintLevel.L1_DIRECTION],
            follow_up_question=self._generate_guiding_question(question_content, knowledge_points)
        )
    
    def _analyze_direction(
        self, 
        question_content: str,
        knowledge_points: List[str]
    ) -> str:
        """分析题目，生成解题方向"""
        # 根据知识点生成方向提示
        direction_hints = []
        
        for kp in knowledge_points:
            if "等差数列" in kp:
                direction_hints.append("- 考虑等差数列的通项公式或求和公式")
            elif "等比数列" in kp:
                direction_hints.append("- 考虑等比数列的通项公式或求和公式")
            elif "递推" in kp:
                direction_hints.append("- 尝试找出递推关系，可能需要构造新数列")
            elif "求和" in kp:
                direction_hints.append("- 考虑分组求和、错位相减或裂项相消等方法")
            elif "通项" in kp:
                direction_hints.append("- 尝试通过递推公式推导通项公式")
            elif "不等式" in kp:
                direction_hints.append("- 考虑放缩法或数学归纳法")
            elif "函数" in kp:
                direction_hints.append("- 分析函数性质，考虑单调性或极值")
            elif "导数" in kp:
                direction_hints.append("- 考虑求导分析函数的单调性和极值")
            else:
                direction_hints.append(f"- 重点理解**{kp}**的核心概念")
        
        if not direction_hints:
            direction_hints.append("- 仔细阅读题目，提取关键信息")
            direction_hints.append("- 尝试将已知条件与所求建立联系")
        
        return '\n'.join(direction_hints[:3])  # 最多3条方向提示
    
    def _generate_guiding_question(
        self,
        question_content: str,
        knowledge_points: List[str]
    ) -> str:
        """生成引导性问题"""
        # 根据知识点生成苏格拉底式提问
        if "等差数列" in knowledge_points or "等比数列" in knowledge_points:
            return "这道题的已知条件中，哪些信息可以用来确定数列的首项和公差（或公比）？"
        elif "递推" in knowledge_points:
            return "递推公式告诉我们什么？能否通过变形得到更简单的形式？"
        elif "求和" in knowledge_points:
            return "这个求和式有什么特点？是否可以用我们学过的某种求和方法？"
        elif "不等式" in knowledge_points:
            return "不等式两边有什么特征？能否通过某种变形简化？"
        else:
            return "题目中给出的条件，如何与我们所学的知识建立联系？"
    
    # ==================== L2: 公式提醒 ====================
    
    def generate_l2_hint(
        self,
        question_content: str,
        knowledge_points: List[str]
    ) -> HintContent:
        """
        L2-公式：给出相关公式定理
        
        包含：
        - 核心公式（LaTeX格式）
        - 公式适用条件
        - 如何应用
        """
        formulas = self._get_formulas(knowledge_points)
        
        content = f""**这道题可能用到的公式：**

{self._format_formulas(formulas)}

**使用提示：**
{self._get_formula_usage_tips(knowledge_points)}

试着将这些公式应用到题目中，看看能找到什么突破口！🔍"""
        
        return HintContent(
            level=HintLevel.L2_FORMULA,
            title=self.LEVEL_TITLES[HintLevel.L2_FORMULA],
            content=content,
            actual_weight=self.ACTUAL_WEIGHTS[HintLevel.L2_FORMULA],
            latex_formulas=[f["latex"] for f in formulas]
        )
    
    def _get_formulas(self, knowledge_points: List[str]) -> List[Dict[str, str]]:
        """获取相关公式"""
        formulas = []
        
        formula_db = {
            "等差数列": [
                {"name": "通项公式", "latex": r"a_n = a_1 + (n-1)d"},
                {"name": "求和公式", "latex": r"S_n = \frac{n(a_1 + a_n)}{2} = na_1 + \frac{n(n-1)}{2}d"}
            ],
            "等比数列": [
                {"name": "通项公式", "latex": r"a_n = a_1 \cdot q^{n-1}"},
                {"name": "求和公式", "latex": r"S_n = \frac{a_1(1-q^n)}{1-q} \quad (q \neq 1)"}
            ],
            "递推公式": [
                {"name": "一阶线性递推", "latex": r"a_{n+1} = pa_n + q \Rightarrow a_n + \frac{q}{p-1} = p(a_{n-1} + \frac{q}{p-1})"}
            ],
            "求和": [
                {"name": "裂项相消", "latex": r"\frac{1}{n(n+1)} = \frac{1}{n} - \frac{1}{n+1}"},
                {"name": "错位相减", "latex": r"S_n = a_1b_1 + a_2b_2 + \cdots + a_nb_n \text{（等差×等比）}"}
            ],
            "不等式": [
                {"name": "均值不等式", "latex": r"\frac{a+b}{2} \geq \sqrt{ab} \quad (a,b > 0)"},
                {"name": "柯西不等式", "latex": r"(a^2+b^2)(c^2+d^2) \geq (ac+bd)^2"}
            ],
            "导数": [
                {"name": "基本求导", "latex": r"(x^n)' = nx^{n-1}"},
                {"name": "极值条件", "latex": r"f'(x_0) = 0 \text{ 且 } f''(x_0) \neq 0"}
            ]
        }
        
        for kp in knowledge_points:
            for key, formula_list in formula_db.items():
                if key in kp:
                    formulas.extend(formula_list)
        
        # 去重
        seen = set()
        unique_formulas = []
        for f in formulas:
            if f["latex"] not in seen:
                seen.add(f["latex"])
                unique_formulas.append(f)
        
        return unique_formulas[:4]  # 最多4个公式
    
    def _format_formulas(self, formulas: List[Dict[str, str]]) -> str:
        """格式化公式输出"""
        if not formulas:
            return "（暂无特定公式，请回顾相关知识点）"
        
        lines = []
        for i, f in enumerate(formulas, 1):
            lines.append(f"{i}. **{f['name']}**：${f['latex']}$")
        
        return '\n'.join(lines)
    
    def _get_formula_usage_tips(self, knowledge_points: List[str]) -> str:
        """获取公式使用提示"""
        if "等差数列" in str(knowledge_points):
            return "确定首项 $a_1$ 和公差 $d$，然后代入公式计算。"
        elif "等比数列" in str(knowledge_points):
            return "确定首项 $a_1$ 和公比 $q$，注意 $q=1$ 和 $q \neq 1$ 的情况。"
        elif "递推" in str(knowledge_points):
            return "观察递推关系，尝试构造等差或等比数列。"
        else:
            return "仔细分析题目条件，选择合适的公式代入。"
    
    # ==================== L3: 关键步骤 ====================
    
    def generate_l3_hint(
        self,
        question_content: str,
        knowledge_points: List[str],
        solution_steps: Optional[List[str]] = None
    ) -> HintContent:
        """
        L3-步骤：给出关键推导步骤
        
        包含：
        - 关键步骤分解
        - 每步的核心思路
        - 下一步的提示
        """
        if solution_steps:
            steps = solution_steps[:3]  # 最多显示前3步
        else:
            steps = self._generate_key_steps(question_content, knowledge_points)
        
        content = f"""**关键推导步骤：**

{self._format_steps(steps)}

**下一步提示：**
按照上述步骤继续推导，如果某一步卡住了，可以再问我。加油！💪"""
        
        return HintContent(
            level=HintLevel.L3_STEP,
            title=self.LEVEL_TITLES[HintLevel.L3_STEP],
            content=content,
            actual_weight=self.ACTUAL_WEIGHTS[HintLevel.L3_STEP]
        )
    
    def _generate_key_steps(
        self,
        question_content: str,
        knowledge_points: List[str]
    ) -> List[str]:
        """生成关键步骤"""
        steps = []
        
        if "等差数列" in str(knowledge_points):
            steps = [
                "根据已知条件，设首项为 $a_1$，公差为 $d$",
                "利用通项公式 $a_n = a_1 + (n-1)d$ 建立方程",
                "解方程求出 $a_1$ 和 $d$，再计算所求"
            ]
        elif "等比数列" in str(knowledge_points):
            steps = [
                "根据已知条件，设首项为 $a_1$，公比为 $q$",
                "利用通项公式 $a_n = a_1 \\cdot q^{n-1}$ 建立方程",
                "解方程求出 $a_1$ 和 $q$，再计算所求"
            ]
        elif "递推" in str(knowledge_points):
            steps = [
                "分析递推关系 $a_{n+1}$ 与 $a_n$ 的关系",
                "尝试构造新数列 $b_n = a_n + c$ 使其成为等差或等比数列",
                "求出新数列的通项，再反推原数列"
            ]
        elif "求和" in str(knowledge_points):
            steps = [
                "分析通项 $a_n$ 的结构特征",
                "选择合适的求和方法（分组、错位相减、裂项等）",
                "代入求和公式计算"
            ]
        else:
            steps = [
                "仔细阅读题目，提取已知条件和所求",
                "分析涉及的知识点，建立知识联系",
                "尝试从已知条件出发，逐步推导"
            ]
        
        return steps
    
    def _format_steps(self, steps: List[str]) -> str:
        """格式化步骤输出"""
        lines = []
        for i, step in enumerate(steps, 1):
            lines.append(f"**第{i}步：** {step}")
        return '\n\n'.join(lines)
    
    # ==================== L4: 完整解答 ====================
    
    def generate_l4_hint(
        self,
        question_content: str,
        knowledge_points: List[str],
        full_solution: Optional[str] = None
    ) -> HintContent:
        """
        L4-答案：给出完整解答
        
        包含：
        - 完整解题过程
        - 关键步骤详解
        - 同类题建议
        """
        if full_solution:
            solution = full_solution
        else:
            solution = self._generate_full_solution(question_content, knowledge_points)
        
        content = f"""**完整解答：**

{solution}

---

💡 **学习建议：**
建议仔细理解上述解答的每一步，然后尝试独立完成一遍。如果还有疑问，可以继续提问！

📚 **同类练习：**
掌握这道题后，建议再练习几道同类题目巩固一下。"""
        
        return HintContent(
            level=HintLevel.L4_ANSWER,
            title=self.LEVEL_TITLES[HintLevel.L4_ANSWER],
            content=content,
            actual_weight=self.ACTUAL_WEIGHTS[HintLevel.L4_ANSWER]
        )
    
    def _generate_full_solution(
        self,
        question_content: str,
        knowledge_points: List[str]
    ) -> str:
        """生成完整解答（简化版）"""
        # 实际项目中应该从数据库或LLM获取完整解答
        steps = self._generate_key_steps(question_content, knowledge_points)
        
        solution = "**解：**\n\n"
        for i, step in enumerate(steps, 1):
            solution += f"({i}) {step}\n\n"
        
        solution += "**综上所述，** [答案占位符，实际应从数据库获取]"
        
        return solution
    
    # ==================== 主入口 ====================
    
    def generate_hint(
        self,
        level: HintLevel,
        question_content: str,
        knowledge_points: List[str] = None,
        solution_steps: Optional[List[str]] = None,
        full_solution: Optional[str] = None
    ) -> HintContent:
        """
        生成提示的主入口
        
        参数:
            level: 提示等级
            question_content: 题目内容
            knowledge_points: 知识点列表
            solution_steps: 解题步骤（L3使用）
            full_solution: 完整解答（L4使用）
        
        返回:
            HintContent对象
        """
        knowledge_points = knowledge_points or []
        
        logger.info(f"生成提示：level={level.name}, 知识点={knowledge_points}")
        
        if level == HintLevel.L0_AUTONOMOUS:
            return self.generate_l0_hint(question_content)
        elif level == HintLevel.L1_DIRECTION:
            return self.generate_l1_hint(question_content, knowledge_points)
        elif level == HintLevel.L2_FORMULA:
            return self.generate_l2_hint(question_content, knowledge_points)
        elif level == HintLevel.L3_STEP:
            return self.generate_l3_hint(question_content, knowledge_points, solution_steps)
        elif level == HintLevel.L4_ANSWER:
            return self.generate_l4_hint(question_content, knowledge_points, full_solution)
        else:
            raise ValueError(f"未知的提示等级: {level}")


# ==================== 便捷函数 ====================

def generate_hint_by_level(
    level: int,
    question_content: str,
    knowledge_points: List[str] = None
) -> Dict[str, Any]:
    """
    便捷函数：根据等级生成提示
    
    使用示例:
        hint = generate_hint_by_level(
            level=1,
            question_content="已知等差数列...",
            knowledge_points=["等差数列"]
        )
    """
    generator = HintGenerator()
    hint_level = HintLevel(level)
    hint = generator.generate_hint(hint_level, question_content, knowledge_points)
    
    return {
        "level": hint.level.value,
        "title": hint.title,
        "content": hint.content,
        "actual_weight": hint.actual_weight,
        "latex_formulas": hint.latex_formulas,
        "follow_up_question": hint.follow_up_question
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("提示生成器测试")
    print("=" * 60)
    
    generator = HintGenerator()
    
    question = "已知等差数列{a_n}中，a_3 = 5，a_7 = 13，求通项公式"
    kps = ["等差数列", "通项公式"]
    
    for level in HintLevel:
        print(f"\n{'='*60}")
        print(f"【{level.name}】")
        print(f"{'='*60}")
        
        hint = generator.generate_hint(level, question, kps)
        print(f"标题: {hint.title}")
        print(f"Actual权重: {hint.actual_weight}")
        print(f"内容:\n{hint.content}")
        print(f"公式: {hint.latex_formulas}")
