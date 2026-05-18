"""
BKT (Bayesian Knowledge Tracing) 贝叶斯知识追踪算法
严格遵循PRD文档参数：P(T)=0.3, P(G)=0.2, P(S)=0.1, P(L0)=0.5
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class BKTParams:
    """BKT算法参数 - 硬指标"""
    p_learn: float = 0.3      # P(T) - 学习率
    p_guess: float = 0.2      # P(G) - 猜测率
    p_slip: float = 0.1       # P(S) - 失误率
    p_known_initial: float = 0.5  # P(L0) - 初始掌握度
    
    def __post_init__(self):
        """验证参数范围"""
        assert 0 <= self.p_learn <= 1, "P(T)必须在[0,1]之间"
        assert 0 <= self.p_guess <= 1, "P(G)必须在[0,1]之间"
        assert 0 <= self.p_slip <= 1, "P(S)必须在[0,1]之间"
        assert 0 <= self.p_known_initial <= 1, "P(L0)必须在[0,1]之间"


class BKTModel:
    """
    BKT模型 - 追踪学生对单一知识点的掌握概率
    
    核心公式：
    1. P(Correct) = P(L) * (1 - P(S)) + (1 - P(L)) * P(G)
    2. P(L|Correct) = P(L) * (1 - P(S)) / P(Correct)
    3. P(L|Wrong) = P(L) * P(S) / P(Wrong)
    4. P(L_new) = P(L|observation) + (1 - P(L|observation)) * P(T)
    """
    
    def __init__(self, params: Optional[BKTParams] = None):
        self.params = params or BKTParams()
    
    def update(self, p_known: float, is_correct: bool) -> float:
        """
        根据答题结果更新掌握度

        Args:
            p_known: 当前掌握度 P(L)
            is_correct: 是否答对

        Returns:
            更新后的掌握度 P(L_new)
        """
        p_learn = self.params.p_learn
        p_guess = self.params.p_guess
        p_slip = self.params.p_slip

        # 步骤1：计算后验概率 P(L|obs)
        p_known_given_obs = self._bayesian_update(p_known, is_correct, p_guess, p_slip)

        # 步骤2：学习转移 P(L_new) = P(L|obs) + (1 - P(L|obs)) * P(T)
        p_known_new = p_known_given_obs + (1 - p_known_given_obs) * p_learn

        return max(0.0, min(1.0, p_known_new))

    def update_continuous(self, p_known: float, actual_score: float) -> float:
        """
        根据连续得分更新掌握度（支持 Actual Score 融合）

        将 actual_score ∈ [0, 1] 视为"有效正确程度"，
        在正确和错误两条贝叶斯更新路径之间插值，再应用学习转移。

        Args:
            p_known: 当前掌握度 P(L)
            actual_score: 实际得分 [0, 1]，来自 ActualScoreCalculator

        Returns:
            更新后的掌握度 P(L_new)
        """
        p_learn = self.params.p_learn
        p_guess = self.params.p_guess
        p_slip = self.params.p_slip

        # 正确路径的后验
        p_known_given_correct = self._bayesian_update(p_known, True, p_guess, p_slip)
        # 错误路径的后验
        p_known_given_wrong = self._bayesian_update(p_known, False, p_guess, p_slip)

        # 按 actual_score 插值
        s = max(0.0, min(1.0, actual_score))
        p_known_given_obs = s * p_known_given_correct + (1 - s) * p_known_given_wrong

        # 学习转移
        p_known_new = p_known_given_obs + (1 - p_known_given_obs) * p_learn

        return max(0.0, min(1.0, p_known_new))

    def _bayesian_update(self, p_known: float, is_correct: bool,
                         p_guess: float, p_slip: float) -> float:
        """计算贝叶斯后验 P(L|obs)，不包含学习转移"""
        if is_correct:
            p_obs = p_known * (1 - p_slip) + (1 - p_known) * p_guess
            numerator = p_known * (1 - p_slip)
        else:
            p_obs = p_known * p_slip + (1 - p_known) * (1 - p_guess)
            numerator = p_known * p_slip

        if p_obs <= 0:
            return p_known
        return numerator / p_obs
    
    def predict_correct_probability(self, p_known: float) -> float:
        """
        预测答对概率
        
        Args:
            p_known: 当前掌握度
            
        Returns:
            答对概率
        """
        p_guess = self.params.p_guess
        p_slip = self.params.p_slip
        
        # P(Correct) = P(L) * (1 - P(S)) + (1 - P(L)) * P(G)
        p_correct = p_known * (1 - p_slip) + (1 - p_known) * p_guess
        return p_correct
    
    def update_sequence(self, answers: List[bool]) -> List[float]:
        """
        根据答题序列更新掌握度
        
        Args:
            answers: 答题结果列表，True表示答对，False表示答错
            
        Returns:
            每次答题后的掌握度列表
        """
        p_known = self.params.p_known_initial
        mastery_history = [p_known]
        
        for is_correct in answers:
            p_known = self.update(p_known, is_correct)
            mastery_history.append(p_known)
        
        return mastery_history
    
    def get_mastery_level(self, p_known: float) -> str:
        """
        四级掌握度分级

        - 精通 (mastered):  P(L) >= 0.85 — 绿色 #10B981，可进入下一专题
        - 良好 (proficient): 0.65 <= P(L) < 0.85 — 蓝色 #3B82F6，需拓展拔高
        - 合格 (qualified):  0.4 <= P(L) < 0.65 — 橙色 #F97316，需针对性刷题
        - 薄弱 (weak):       P(L) < 0.4 — 红色 #EF4444，需重新学习
        """
        if p_known >= 0.85:
            return "mastered"
        elif p_known >= 0.65:
            return "proficient"
        elif p_known >= 0.4:
            return "qualified"
        else:
            return "weak"


def batch_update_bkt(
    user_answers: Dict[int, List[bool]],
    params: Optional[BKTParams] = None
) -> Dict[int, float]:
    """
    批量更新多个知识点的掌握度
    
    Args:
        user_answers: {knowledge_point_id: [answers]}
        params: BKT参数
        
    Returns:
        {knowledge_point_id: final_mastery}
    """
    model = BKTModel(params)
    results = {}
    
    for kp_id, answers in user_answers.items():
        if not answers:
            results[kp_id] = model.params.p_known_initial
        else:
            mastery_history = model.update_sequence(answers)
            results[kp_id] = mastery_history[-1]
    
    return results


# 单元测试
if __name__ == "__main__":
    # 测试用例1：连续答对
    print("=== 测试1：连续答对3次 ===")
    model = BKTModel()
    p = model.params.p_known_initial
    print(f"初始掌握度: {p:.4f}")

    for i in range(3):
        p = model.update(p, True)
        print(f"第{i+1}次答对后: {p:.4f}")

    # 测试用例2：连续答错
    print("\n=== 测试2：连续答错2次 ===")
    model2 = BKTModel()
    p = model2.params.p_known_initial
    print(f"初始掌握度: {p:.4f}")

    for i in range(2):
        p = model2.update(p, False)
        print(f"第{i+1}次答错后: {p:.4f}")

    # 测试用例3：混合答题
    print("\n=== 测试3：对-错-对-对 ===")
    model3 = BKTModel()
    answers = [True, False, True, True]
    history = model3.update_sequence(answers)
    print("掌握度变化:", [f"{h:.4f}" for h in history])

    # 测试用例4：四级掌握度
    print("\n=== 测试4：四级掌握度 ===")
    test_values = [0.2, 0.5, 0.75, 0.9]
    for v in test_values:
        level = model.get_mastery_level(v)
        print(f"P(L)={v:.2f} -> {level}")

    # 测试用例5：连续得分更新 update_continuous
    print("\n=== 测试5：连续得分 update_continuous ===")
    model5 = BKTModel()
    p = model5.params.p_known_initial
    print(f"初始掌握度: {p:.4f}")
    # 模拟实际得分场景：做对了但用了L2提示 (actual_score ≈ 0.75)
    p = model5.update_continuous(p, 0.75)
    print(f"actual_score=0.75 (对+L2提示)后: {p:.4f}")
    # 做错了但只差一点 (actual_score ≈ 0.35)
    p = model5.update_continuous(p, 0.35)
    print(f"actual_score=0.35 (接近但错)后: {p:.4f}")
    # 完全自主做对 (actual_score = 1.0)
    p = model5.update_continuous(p, 1.0)
    print(f"actual_score=1.0 (完全自主)后: {p:.4f}")
    # 完全不会 (actual_score = 0.0)
    p = model5.update_continuous(p, 0.0)
    print(f"actual_score=0.0 (完全不会)后: {p:.4f}")

    # 测试用例6：对比 update vs update_continuous 在边界情况
    print("\n=== 测试6：边界一致性 ===")
    model6 = BKTModel()
    p_binary = model6.params.p_known_initial
    p_cont = model6.params.p_known_initial
    p_binary = model6.update(p_binary, True)
    p_cont = model6.update_continuous(p_cont, 1.0)
    print(f"答对-二元: {p_binary:.6f}, 连续(score=1.0): {p_cont:.6f}, 一致: {abs(p_binary-p_cont)<1e-9}")
    p_binary = model6.update(p_binary, False)
    p_cont = model6.update_continuous(p_cont, 0.0)
    print(f"答错-二元: {p_binary:.6f}, 连续(score=0.0): {p_cont:.6f}, 一致: {abs(p_binary-p_cont)<1e-9}")
