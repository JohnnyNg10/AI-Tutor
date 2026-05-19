"""
错因诊断服务 — 基于LLM的逐步错误分析

对标猿辅导"五重错因分析法"，对每道错题输出结构化诊断：
1. 错误类型分类（概念/过程/计算/审题/格式）
2. 错误位置定位（第几步出错）
3. 匹配知识图谱薄弱节点
4. 严重程度权重（用于掌握度衰减）
5. 针对性引导提示（用于重试）
6. 是否需要重试的判断

实现文件: backend/services/error_diagnosis_service.py
"""

import sys
import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from openai import OpenAI
from utils.logger import logger
from utils.config import settings


class ErrorType(Enum):
    """错误类型枚举（对标猿辅导五重错因 + 讯飞3层级标签）"""
    CONCEPT_ERROR = "concept_error"          # 概念错误：不知道/记错了知识点
    PROCESS_ERROR = "process_error"           # 过程错误：思路/方法错了
    CALCULATION_ERROR = "calculation_error"   # 计算错误：算错了
    READING_ERROR = "reading_error"           # 审题错误：读错题了
    FORMAT_ERROR = "format_error"             # 格式错误：会做但表达有误


# 错误类型对掌握度的衰减权重
ERROR_DECAY_WEIGHTS = {
    ErrorType.CONCEPT_ERROR: 1.5,       # 概念不会 = 真正没掌握
    ErrorType.PROCESS_ERROR: 1.2,       # 方法错了 = 半懂不懂
    ErrorType.CALCULATION_ERROR: 0.7,   # 粗心算错 ≠ 不懂
    ErrorType.READING_ERROR: 0.5,       # 看错题 ≠ 不会做
    ErrorType.FORMAT_ERROR: 0.3,        # 格式问题 ≈ 会做
}

# 哪些错误类型需要引导学生重试
SHOULD_RETRY_ERROR_TYPES = {
    ErrorType.CONCEPT_ERROR,
    ErrorType.PROCESS_ERROR,
}


@dataclass
class ErrorDiagnosisResult:
    """错因诊断结果"""
    primary_error_type: ErrorType
    error_location: str = ""             # 出错位置描述
    error_detail: str = ""               # 错误具体描述
    matched_kp_node_id: str = ""         # 匹配的知识图谱节点ID
    matched_kp_name: str = ""            # 匹配的知识点名称
    severity_weight: float = 1.0         # 严重程度权重
    remediation_hint: str = ""           # 针对性引导提示
    should_retry: bool = False           # 是否需要重试
    improvement_suggestion: str = ""     # 改进建议
    raw_llm_response: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "primary_error_type": self.primary_error_type.value,
            "error_location": self.error_location,
            "error_detail": self.error_detail,
            "matched_kp_node_id": self.matched_kp_node_id,
            "matched_kp_name": self.matched_kp_name,
            "severity_weight": self.severity_weight,
            "remediation_hint": self.remediation_hint,
            "should_retry": self.should_retry,
            "improvement_suggestion": self.improvement_suggestion,
        }


class ErrorDiagnosisService:
    """基于LLM的错因诊断服务"""

    DIAGNOSIS_SYSTEM_PROMPT = """你是一位高中数学特级教师，专精于诊断学生的解题错误根因。

你的任务：分析学生的错误答案，从以下五个维度进行诊断：

1. **概念错误**：学生是否缺少某个知识点？是否混淆了相似概念？
   - 例如：分不清等差数列和等比数列、忘记判别式Δ≥0的条件
2. **过程错误**：学生的解题思路/方法是否选错了？
   - 例如：应该用错位相减法却用了裂项、推理步骤跳跃缺少中间环节
3. **计算错误**：学生是否在某个计算步骤上出错了？
   - 例如：移项符号错误、通分计算错误、下标计算错误
4. **审题错误**：学生是否遗漏了题目的关键条件？是否答非所问？
   - 例如：没看到"正整数"限制、忽略了定义域
5. **格式错误**：学生会做但表达不规范？
   - 例如：缺少"解"字、跳步、书写不规范

输出格式（严格遵守JSON）：
{
  "primary_error_type": "concept_error|process_error|calculation_error|reading_error|format_error",
  "error_location": "第X步：具体描述出错位置",
  "error_detail": "详细分析学生错在哪里，为什么错",
  "matched_kp_name": "匹配的知识点名称（如：错位相减法、等差中项）",
  "is_concept_confusion": true,
  "confused_concepts": ["混淆的概念A", "混淆的概念B"],
  "should_retry": true,
  "remediation_hint": "给学生的一两句针对性引导提示（苏格拉底式，不直接给答案）",
  "improvement_suggestion": "给学生的长期改进建议",
  "severity_reason": "为什么给这个严重程度"
}

诊断原则：
- 逐步骤分析，不要只看最终答案
- 区分"不会做"(概念/过程错误)和"粗心"(计算/审题错误)
- 当学生明显是粗心算错时，不要判为概念错误
- 引导提示应该是苏格拉底式的反问，而非直接告诉答案
- 如果错误涉及知识图谱中的具体知识点，请明确指出知识点名称"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base
        )
        self.model = settings.llm_model
        logger.info("错因诊断服务初始化完成")

    async def diagnose(
        self,
        question_text: str,
        standard_answer: str,
        student_answer: str,
        knowledge_points: List[str],
        user_mastery: Dict[str, float],
        hint_levels_used: int = 0
    ) -> ErrorDiagnosisResult:
        """
        诊断学生的错题

        Args:
            question_text: 题目内容
            standard_answer: 标准答案/解析
            student_answer: 学生的答案（经OCR+校对）
            knowledge_points: 题目关联的知识点名称列表
            user_mastery: 学生当前掌握度 {kp_name: p_known}
            hint_levels_used: 使用了多少级提示

        Returns:
            ErrorDiagnosisResult
        """
        # 构建知识点掌握度上下文
        kp_context = ""
        for kp in knowledge_points:
            p = user_mastery.get(kp, 0.5)
            level = "薄弱" if p < 0.4 else ("合格" if p < 0.65 else ("良好" if p < 0.85 else "精通"))
            kp_context += f"  - {kp}: {level} (P(L)={p:.2f})\n"

        user_prompt = f"""请诊断以下学生的错题：

【题目】
{question_text}

【标准答案/解析】
{standard_answer}

【学生答案】
{student_answer}

【题目关联知识点及学生掌握度】
{kp_context if kp_context else '无知识点数据'}

【提示使用】学生使用了 {hint_levels_used} 级提示

请分析学生错误的原因，按JSON格式输出诊断结果。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.DIAGNOSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"}
            )

            raw = json.loads(response.choices[0].message.content)
            logger.info(f"[错因诊断] 主类型={raw.get('primary_error_type')}, "
                        f"位置={raw.get('error_location', '')[:50]}")

            return self._parse_llm_response(raw, knowledge_points)

        except Exception as e:
            logger.error(f"[错因诊断] LLM调用失败: {e}")
            return self._fallback_diagnosis(student_answer, knowledge_points)

    def _parse_llm_response(self, raw: Dict, knowledge_points: List[str]) -> ErrorDiagnosisResult:
        """解析LLM返回的JSON为结构化结果"""
        error_type_str = raw.get("primary_error_type", "process_error")
        try:
            error_type = ErrorType(error_type_str)
        except ValueError:
            error_type = ErrorType.PROCESS_ERROR

        severity = ERROR_DECAY_WEIGHTS.get(error_type, 1.0)

        # 尝试匹配知识图谱节点
        matched_kp_name = raw.get("matched_kp_name", "")
        if not matched_kp_name and knowledge_points:
            matched_kp_name = knowledge_points[0]

        return ErrorDiagnosisResult(
            primary_error_type=error_type,
            error_location=raw.get("error_location", ""),
            error_detail=raw.get("error_detail", ""),
            matched_kp_name=matched_kp_name,
            severity_weight=severity,
            remediation_hint=raw.get("remediation_hint", ""),
            should_retry=error_type in SHOULD_RETRY_ERROR_TYPES,
            improvement_suggestion=raw.get("improvement_suggestion", ""),
            raw_llm_response=raw
        )

    def _fallback_diagnosis(
        self, student_answer: str, knowledge_points: List[str]
    ) -> ErrorDiagnosisResult:
        """LLM不可用时的降级诊断（基于规则）"""
        # 检查是否有计算相关关键词
        calc_keywords = ["算错", "计算", "算成", "得数", "=", "+", "-", "×", "÷"]
        concept_keywords = ["公式", "定理", "定义", "记错", "记混", "混淆"]

        has_calc = any(kw in student_answer for kw in calc_keywords)
        has_concept = any(kw in student_answer for kw in concept_keywords)

        if has_concept:
            error_type = ErrorType.CONCEPT_ERROR
        elif has_calc:
            error_type = ErrorType.CALCULATION_ERROR
        else:
            error_type = ErrorType.PROCESS_ERROR

        return ErrorDiagnosisResult(
            primary_error_type=error_type,
            error_detail="（离线降级诊断）请人工检查学生答案",
            matched_kp_name=knowledge_points[0] if knowledge_points else "",
            severity_weight=ERROR_DECAY_WEIGHTS.get(error_type, 1.0),
            should_retry=error_type in SHOULD_RETRY_ERROR_TYPES,
            improvement_suggestion="建议重新审题后再次尝试"
        )

    def get_severity_weight(self, error_type: ErrorType) -> float:
        """获取错误类型的掌握度衰减权重"""
        return ERROR_DECAY_WEIGHTS.get(error_type, 1.0)


# 全局单例
error_diagnosis_service = ErrorDiagnosisService()
