"""
计算失误处理模块
识别纯计算失误，避免错误扣除Actual权重

对应需求17: 复用V2的错误诊断能力，避免在"纯计算失误"时错误扣除学生的Actual权重

实现文件：backend/algorithms/calculation_error_handler.py
"""

import sys
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from utils.logger import logger


class ErrorType(Enum):
    """错误类型"""
    CALCULATION_ERROR = "calculation_error"    # 纯计算失误
    LOGIC_ERROR = "logic_error"                 # 逻辑错误
    FORMULA_ERROR = "formula_error"             # 公式错误
    CONCEPT_ERROR = "concept_error"             # 概念错误
    UNKNOWN_ERROR = "unknown_error"             # 未知错误


@dataclass
class ErrorDiagnosisResult:
    """错误诊断结果"""
    error_type: ErrorType
    is_calculation_error: bool
    confidence: float
    description: str
    suggested_hint: str
    should_preserve_weight: bool  # 是否保护权重不降低


class CalculationErrorHandler:
    """
    计算失误处理器
    
    功能：
    1. 诊断错误类型（粗心算错 vs 逻辑/公式错误）
    2. 纯计算失误检测
    3. Actual Score权重保护
    4. 生成轻提示
    """
    
    # 计算失误关键词模式
    CALCULATION_ERROR_PATTERNS = [
        r'计算错误', r'算错', r'计算失误', r'粗心', r'漏算',
        r'符号错误', r'正负号', r'加减错误', r'乘除错误',
        r'数值计算', r'算术错误', r'计算过程', r'运算错误'
    ]
    
    # 逻辑错误关键词模式
    LOGIC_ERROR_PATTERNS = [
        r'逻辑错误', r'思路错误', r'方法错误', r'方向错误',
        r'理解错误', r'概念混淆', r'思路偏差', r'方法不当'
    ]
    
    # 公式错误关键词模式
    FORMULA_ERROR_PATTERNS = [
        r'公式错误', r'公式记错', r'公式混淆', r'定理错误',
        r'公式应用', r'公式选择', r'公式变形'
    ]
    
    def __init__(self):
        """初始化处理器"""
        self._compile_patterns()
        logger.info("计算失误处理器初始化完成")
    
    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.calc_patterns = [re.compile(p) for p in self.CALCULATION_ERROR_PATTERNS]
        self.logic_patterns = [re.compile(p) for p in self.LOGIC_ERROR_PATTERNS]
        self.formula_patterns = [re.compile(p) for p in self.FORMULA_ERROR_PATTERNS]
    
    # ==================== 核心诊断方法 ====================
    
    def diagnose_error(
        self,
        student_answer: str,
        correct_answer: str,
        solution_steps: List[str],
        error_analysis: str = None
    ) -> ErrorDiagnosisResult:
        """
        诊断错误类型
        
        对应需求17: 识别纯计算失误
        """
        # 如果没有提供错误分析，进行自动分析
        if not error_analysis:
            error_analysis = self._auto_analyze_error(
                student_answer, correct_answer, solution_steps
            )
        
        # 分析错误类型
        error_type, confidence = self._classify_error_type(error_analysis)
        
        # 判断是否为纯计算失误
        is_calculation_error = (error_type == ErrorType.CALCULATION_ERROR)
        
        # 生成建议提示
        suggested_hint = self._generate_light_hint(error_type, error_analysis)
        
        # 确定是否保护权重
        # 纯计算失误：保护权重（不降低）
        # 其他错误：正常扣权重
        should_preserve_weight = is_calculation_error
        
        return ErrorDiagnosisResult(
            error_type=error_type,
            is_calculation_error=is_calculation_error,
            confidence=confidence,
            description=self._get_error_description(error_type),
            suggested_hint=suggested_hint,
            should_preserve_weight=should_preserve_weight
        )
    
    def _auto_analyze_error(
        self,
        student_answer: str,
        correct_answer: str,
        solution_steps: List[str]
    ) -> str:
        """自动分析错误"""
        # 简化分析：比较学生答案和正确答案
        # 实际项目中应该使用LLM进行详细分析
        
        analysis_parts = []
        
        # 检查数值差异
        try:
            student_val = float(student_answer)
            correct_val = float(correct_answer)
            diff = abs(student_val - correct_val)
            
            if diff < 0.01:
                analysis_parts.append("答案数值接近，可能存在精度问题")
            elif diff < 1.0:
                analysis_parts.append("答案数值有小偏差，可能是计算过程中的四舍五入或符号错误")
            else:
                analysis_parts.append("答案数值差异较大")
        except:
            # 非数值答案，进行字符串比较
            if student_answer.strip() == correct_answer.strip():
                analysis_parts.append("答案形式相同")
            else:
                analysis_parts.append("答案形式不同")
        
        # 检查解题步骤（如果有）
        if solution_steps:
            analysis_parts.append(f"解题步骤共{len(solution_steps)}步")
        
        return "；".join(analysis_parts) if analysis_parts else "需要进一步分析错误类型"
    
    def _classify_error_type(self, error_analysis: str) -> Tuple[ErrorType, float]:
        """
        分类错误类型
        
        返回: (错误类型, 置信度)
        """
        error_analysis = error_analysis.lower()
        
        # 统计各类关键词匹配数
        calc_matches = sum(1 for p in self.calc_patterns if p.search(error_analysis))
        logic_matches = sum(1 for p in self.logic_patterns if p.search(error_analysis))
        formula_matches = sum(1 for p in self.formula_patterns if p.search(error_analysis))
        
        # 确定最可能的错误类型
        max_matches = max(calc_matches, logic_matches, formula_matches)
        
        if max_matches == 0:
            return ErrorType.UNKNOWN_ERROR, 0.3
        
        total_matches = calc_matches + logic_matches + formula_matches
        confidence = max_matches / total_matches if total_matches > 0 else 0.5
        
        if calc_matches == max_matches:
            return ErrorType.CALCULATION_ERROR, confidence
        elif logic_matches == max_matches:
            return ErrorType.LOGIC_ERROR, confidence
        elif formula_matches == max_matches:
            return ErrorType.FORMULA_ERROR, confidence
        else:
            return ErrorType.UNKNOWN_ERROR, confidence
    
    def _get_error_description(self, error_type: ErrorType) -> str:
        """获取错误类型描述"""
        descriptions = {
            ErrorType.CALCULATION_ERROR: "纯计算失误，思路和方法正确",
            ErrorType.LOGIC_ERROR: "逻辑错误，解题思路存在问题",
            ErrorType.FORMULA_ERROR: "公式错误，公式记忆或应用不当",
            ErrorType.CONCEPT_ERROR: "概念错误，对知识点的理解有误",
            ErrorType.UNKNOWN_ERROR: "错误类型不明确，需要进一步分析"
        }
        return descriptions.get(error_type, "未知错误类型")
    
    def _generate_light_hint(self, error_type: ErrorType, error_analysis: str) -> str:
        """
        生成轻提示
        
        对应需求17: 纯计算失误时弹出轻提示，不触发L1-L4降权重
        """
        if error_type == ErrorType.CALCULATION_ERROR:
            hints = [
                "你的思路完全正确，但仔细检查一下计算过程哦！",
                "方法是对的，再检查一下数值计算是否有小错误？",
                "解题方向正确，注意一下计算细节！",
                "差点就对了！检查一下符号或数值计算~"
            ]
            import random
            return random.choice(hints)
        
        elif error_type == ErrorType.LOGIC_ERROR:
            return "这道题的思路有点偏差，让我给你一点提示..."
        
        elif error_type == ErrorType.FORMULA_ERROR:
            return "公式使用上有些问题，回忆一下相关的公式定理..."
        
        else:
            return "我们再仔细看看这道题..."
    
    # ==================== Actual Score权重保护 ====================
    
    def calculate_actual_score_with_protection(
        self,
        base_score: float,
        hint_level: int,
        error_diagnosis: ErrorDiagnosisResult
    ) -> Dict[str, Any]:
        """
        计算Actual Score（带权重保护）
        
        对应需求17: 纯计算失误时不降低Actual权重
        """
        # 基础权重计算
        hint_penalty = self._get_hint_penalty(hint_level)
        
        # 如果纯计算失误，保护权重
        if error_diagnosis.is_calculation_error and error_diagnosis.confidence > 0.7:
            # 不应用hint惩罚，或大幅降低惩罚
            effective_hint_penalty = 0.0  # 完全保护
            protection_applied = True
            protection_reason = "检测到纯计算失误，保护Actual权重"
        else:
            effective_hint_penalty = hint_penalty
            protection_applied = False
            protection_reason = None
        
        # 计算最终分数
        final_score = base_score * (1 - effective_hint_penalty)
        final_score = max(0.0, min(1.0, final_score))
        
        return {
            'final_score': round(final_score, 2),
            'base_score': base_score,
            'hint_penalty': hint_penalty,
            'effective_hint_penalty': effective_hint_penalty,
            'protection_applied': protection_applied,
            'protection_reason': protection_reason,
            'error_type': error_diagnosis.error_type.value,
            'is_calculation_error': error_diagnosis.is_calculation_error
        }
    
    def _get_hint_penalty(self, hint_level: int) -> float:
        """获取提示惩罚系数"""
        penalties = {
            0: 0.0,   # L0: 无惩罚
            1: 0.2,   # L1: 20%惩罚
            2: 0.4,   # L2: 40%惩罚
            3: 0.6,   # L3: 60%惩罚
            4: 0.9    # L4: 90%惩罚
        }
        return penalties.get(hint_level, 0.0)
    
    # ==================== 便捷方法 ====================
    
    def is_calculation_error(
        self,
        error_analysis: str,
        confidence_threshold: float = 0.7
    ) -> bool:
        """
        便捷方法：判断是否为纯计算失误
        """
        error_type, confidence = self._classify_error_type(error_analysis)
        return (error_type == ErrorType.CALCULATION_ERROR and 
                confidence >= confidence_threshold)


# ==================== 便捷函数 ====================

def diagnose_and_protect_score(
    student_answer: str,
    correct_answer: str,
    hint_level: int,
    base_score: float = 1.0,
    error_analysis: str = None
) -> Dict[str, Any]:
    """
    便捷函数：诊断错误并计算受保护的Actual Score
    
    使用示例:
        result = diagnose_and_protect_score(
            student_answer="10",
            correct_answer="12",
            hint_level=2,
            base_score=1.0
        )
    """
    handler = CalculationErrorHandler()
    
    # 诊断错误
    diagnosis = handler.diagnose_error(
        student_answer=student_answer,
        correct_answer=correct_answer,
        solution_steps=[],
        error_analysis=error_analysis
    )
    
    # 计算受保护的分数
    score_result = handler.calculate_actual_score_with_protection(
        base_score=base_score,
        hint_level=hint_level,
        error_diagnosis=diagnosis
    )
    
    return {
        'diagnosis': {
            'error_type': diagnosis.error_type.value,
            'is_calculation_error': diagnosis.is_calculation_error,
            'confidence': diagnosis.confidence,
            'description': diagnosis.description,
            'suggested_hint': diagnosis.suggested_hint
        },
        'score_calculation': score_result
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("计算失误处理器测试")
    print("=" * 60)
    
    handler = CalculationErrorHandler()
    
    # 测试错误类型分类
    test_cases = [
        ("学生计算过程中符号错误", "计算失误"),
        ("解题思路完全错误，方法不对", "逻辑错误"),
        ("公式记错了，应该用求和公式", "公式错误"),
        ("粗心算错，把3+5算成了7", "计算失误")
    ]
    
    print("\n错误类型分类测试：")
    for analysis, expected in test_cases:
        error_type, confidence = handler._classify_error_type(analysis)
        is_calc = handler.is_calculation_error(analysis)
        print(f"  分析: {analysis[:20]}...")
        print(f"    → 类型: {error_type.value}, 置信度: {confidence:.0%}, 是否计算失误: {is_calc}")
    
    # 测试权重保护
    print("\n权重保护测试：")
    result = diagnose_and_protect_score(
        student_answer="10",
        correct_answer="12",
        hint_level=2,
        base_score=1.0,
        error_analysis="学生在最后一步计算时出现符号错误，思路和方法完全正确"
    )
    
    print(f"  错误类型: {result['diagnosis']['error_type']}")
    print(f"  是否计算失误: {result['diagnosis']['is_calculation_error']}")
    print(f"  保护是否生效: {result['score_calculation']['protection_applied']}")
    print(f"  最终分数: {result['score_calculation']['final_score']}")
    print(f"  建议提示: {result['diagnosis']['suggested_hint']}")
