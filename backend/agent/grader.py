"""
Grader Agent — AI批改核心引擎

使用 LLM 对学生的解题过程进行步骤级分析，输出结构化批改结果。
"""

import json
from typing import Dict, List, Optional

from openai import OpenAI
from utils.config import settings
from utils.logger import logger

GRADING_SYSTEM_PROMPT = """你是 AI Tutor 的智能阅卷人（Grader Agent）。你的任务是批改高中数学数列题目的学生作答。

## 批改原则
1. 逐步骤检查，不要只看最终答案
2. 对于过程正确但答案错误的情况，给予部分分数（每个正确步骤得分）
3. 区分"不会做"(概念/过程错误)和"粗心"(计算/审题错误)
4. 对每道题标记最可能的1个错误主类型 + 最多2个副标签
5. 描述用中文，具体指出错误位置和原因

## 错误类型
- CONCEPT_ERROR: 概念错误（不知道/记错了知识点）
- PROCESS_ERROR: 过程错误（思路/方法错了）
- CALCULATION_ERROR: 计算错误（算错了）
- READING_ERROR: 审题错误（读错题了）
- FORMAT_ERROR: 格式错误（会做但表达有误）

## 输出格式（严格遵守JSON）
{
  "steps": [
    {
      "step_number": 1,
      "step_content": "学生作答的这一步内容概括",
      "status": "correct|incorrect|partially_correct",
      "analysis": "对这一步的分析",
      "score_ratio": 1.0
    }
  ],
  "final_score": 85,
  "is_correct": false,
  "error": {
    "primary_type": "CALCULATION_ERROR",
    "sub_type": "算术错误",
    "description": "具体错误描述",
    "location": "第3步"
  },
  "knowledge_points": ["等差数列通项公式"],
  "error_tags": ["计算粗心", "代入错误"],
  "improvement_suggestion": "建议的改进方向"
}

如果学生完全正确，error字段为null，is_correct为true。
"""


class GraderAgent:

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
        )
        self.model = settings.llm_model or "gpt-4o"

    async def grade(
        self,
        question_text: str,
        student_answer: str,
        standard_answer: Optional[str] = None,
        knowledge_points: Optional[List[str]] = None,
    ) -> dict:
        """批改单道题"""
        user_prompt = f"""请批改以下学生的作答：

## 题目
{question_text}

## 学生作答
{student_answer}"""

        if standard_answer:
            user_prompt += f"\n\n## 标准答案（参考）\n{standard_answer}"

        if knowledge_points:
            user_prompt += f"\n\n## 题目涉及的知识点\n{', '.join(knowledge_points)}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": GRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content
            return self._parse_response(content)
        except Exception as e:
            logger.error(f"Grader LLM call failed: {e}")
            return self._fallback_grade(question_text, student_answer)

    async def grade_batch(
        self,
        questions: List[dict],
    ) -> List[dict]:
        """批量批改，每道题独立调用LLM"""
        results = []
        for q in questions:
            result = await self.grade(
                question_text=q.get("question_text", ""),
                student_answer=q.get("student_answer", ""),
                standard_answer=q.get("standard_answer"),
                knowledge_points=q.get("knowledge_points"),
            )
            result["question_index"] = q.get("index", 0)
            results.append(result)
        return results

    def _parse_response(self, response: str) -> dict:
        """解析LLM JSON响应"""
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse grader response: {response[:200]}")
            return {
                "steps": [],
                "final_score": 0,
                "is_correct": None,
                "error": None,
                "knowledge_points": [],
                "error_tags": [],
                "improvement_suggestion": "",
                "parse_error": True,
            }

    def _fallback_grade(self, question_text: str, student_answer: str) -> dict:
        """LLM不可用时的降级批改（规则匹配）"""
        return {
            "steps": [{
                "step_number": 1,
                "step_content": student_answer[:100],
                "status": "correct" if len(student_answer) > 10 else "incorrect",
                "analysis": "LLM批改服务暂不可用，此为规则降级结果",
                "score_ratio": 0.5,
            }],
            "final_score": 50,
            "is_correct": None,
            "error": None,
            "knowledge_points": [],
            "error_tags": [],
            "improvement_suggestion": "请稍后重试以获取详细批改分析",
            "fallback": True,
        }


grader_agent = GraderAgent()
