"""
题目内容审核服务
在将用户上传的题目存入数据库之前，使用LLM进行审核
确保存储的是真正的数学题目，而非用户的提问词
"""

import json
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI
from utils.config import settings
from utils.logger import logger


class QuestionValidationResult:
    """题目审核结果"""
    
    def __init__(
        self,
        is_valid: bool,
        content: Optional[str] = None,
        reason: Optional[str] = None,
        knowledge_points: Optional[list] = None,
        difficulty: Optional[float] = None,
        question_type: Optional[str] = None
    ):
        self.is_valid = is_valid
        self.content = content  # 审核后的纯净题目内容
        self.reason = reason    # 审核不通过的原因
        self.knowledge_points = knowledge_points or []
        self.difficulty = difficulty
        self.question_type = question_type


class QuestionValidationService:
    """
    题目内容审核服务
    
    审核规则：
    1. 内容必须是数学题目（包含数学公式、数字、数学术语等）
    2. 不能只是用户的提问词（如"这道题怎么做"、"求解"等）
    3. 题目内容应该完整、可理解
    4. 如果是图片提取的题目，需要验证提取质量
    """
    
    # 常见的非题目关键词（用于快速预筛选）
    NON_QUESTION_PATTERNS = [
        "这道题怎么",
        "这道题怎么做",
        "这道题怎么写",
        "这道题怎么解",
        "这道题如何做",
        "这道题如何解",
        "求解",
        "怎么做",
        "怎么写",
        "怎么解",
        "如何做",
        "如何解",
        "请教",
        "帮帮我",
        "救命",
        "急",
        "在线等",
    ]
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base
        )
        self.model = settings.llm_model
    
    def _quick_pre_check(self, content: str) -> Tuple[bool, str]:
        """
        快速预检查
        
        Returns:
            (是否通过, 原因)
        """
        if not content or not isinstance(content, str):
            return False, "内容为空"
        
        content = content.strip()
        
        # 检查长度
        if len(content) < 10:
            return False, f"内容太短 ({len(content)} 字符)，可能不是完整题目"
        
        # 检查是否只包含非题目关键词
        lower_content = content.lower()
        for pattern in self.NON_QUESTION_PATTERNS:
            if lower_content == pattern or lower_content.startswith(pattern) and len(content) < 20:
                return False, f"内容仅为提问词: '{content}'"
        
        # 检查是否包含数学相关元素
        math_indicators = [
            r'[\d]+',  # 数字
            r'[＋\-\×÷\/\=\(\)\[\]\{\}]',  # 运算符和括号
            r'[a-zA-Z][\d]*',  # 变量
            r'[\u4e00-\u9fa5]{2,}',  # 中文数学术语（至少2个汉字）
        ]
        
        import re
        has_math = False
        for pattern in math_indicators:
            if re.search(pattern, content):
                has_math = True
                break
        
        if not has_math:
            return False, "内容缺少数学相关元素（数字、运算符、变量等）"
        
        return True, "预检查通过"
    
    async def validate(
        self,
        content: str,
        source: str = "text",  # "text" 或 "image"
        original_input: Optional[str] = None
    ) -> QuestionValidationResult:
        """
        审核题目内容
        
        Args:
            content: 要审核的内容
            source: 内容来源 ("text" 或 "image")
            original_input: 原始用户输入（用于上下文）
            
        Returns:
            QuestionValidationResult: 审核结果
        """
        # 1. 快速预检查
        pre_check_passed, pre_check_reason = self._quick_pre_check(content)
        if not pre_check_passed:
            logger.warning(f"[题目审核] 预检查未通过: {pre_check_reason}")
            return QuestionValidationResult(
                is_valid=False,
                content=content,
                reason=pre_check_reason
            )
        
        # 2. LLM深度审核
        try:
            prompt = self._build_validation_prompt(content, source, original_input)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个数学教育内容审核专家，负责判断给定的内容是否是有效的数学题目。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            is_valid = result.get("is_valid", False)
            reason = result.get("reason", "")
            
            if is_valid:
                logger.info(f"[题目审核] 通过: {content[:50]}...")
                return QuestionValidationResult(
                    is_valid=True,
                    content=result.get("cleaned_content", content),
                    reason=reason,
                    knowledge_points=result.get("knowledge_points", []),
                    difficulty=result.get("difficulty", 0.5),
                    question_type=result.get("question_type", "解答题")
                )
            else:
                logger.warning(f"[题目审核] 未通过: {reason} | 内容: {content[:100]}...")
                return QuestionValidationResult(
                    is_valid=False,
                    content=content,
                    reason=reason
                )
                
        except Exception as e:
            logger.error(f"[题目审核] LLM审核失败: {e}")
            # 审核失败时，如果预检查通过，则允许通过（降级策略）
            return QuestionValidationResult(
                is_valid=pre_check_passed,
                content=content,
                reason=f"LLM审核失败，使用预检查结果: {pre_check_reason}"
            )
    
    def _build_validation_prompt(
        self,
        content: str,
        source: str,
        original_input: Optional[str]
    ) -> str:
        """构建审核提示词"""
        
        source_hint = "从图片中提取的" if source == "image" else "从用户输入中提取的"
        original_hint = f"\n原始用户输入: {original_input}" if original_input else ""
        
        return f"""请审核以下{source_hint}内容，判断它是否是一个有效的数学题目。

待审核内容：
{content}{original_hint}

请按以下JSON格式返回审核结果：
{{
    "is_valid": true/false,  // 是否是有效的数学题目
    "reason": "审核说明",  // 如果是false，说明原因；如果是true，可以简要说明题目类型
    "cleaned_content": "清理后的纯净题目内容",  // 去除所有非题目内容（如"这道题怎么做"等提问词）
    "knowledge_points": ["知识点1", "知识点2"],  // 题目涉及的知识点
    "difficulty": 0.5,  // 难度评估 0.1-1.0
    "question_type": "解答题/选择题/填空题"  // 题目类型
}}

审核标准：
1. **必须是数学题目**：包含数学概念、公式、计算或数学推理
2. **不能只是提问词**：如"这道题怎么做"、"求解"、"帮帮我"等不是题目
3. **内容要完整**：题目描述清晰，有明确的求解目标
4. **要有数学实质**：包含数字、变量、公式、几何图形描述等数学元素

常见无效内容示例：
- "这道题怎么做" ❌
- "求解" ❌  
- "帮帮我，我不会做" ❌
- "这个题答案是什么" ❌

有效题目示例：
- "已知等差数列{{a_n}}的首项a₁=2，公差d=3，求前10项和S₁₀" ✅
- "解方程：2x² - 5x + 2 = 0" ✅
- "求函数f(x) = x² - 4x + 3在区间[0,4]上的最大值和最小值" ✅

请严格审核，确保只让真正的数学题目通过。"""

    async def validate_batch(
        self,
        contents: list,
        source: str = "text"
    ) -> list[QuestionValidationResult]:
        """批量审核多个题目"""
        results = []
        for content in contents:
            result = await self.validate(content, source)
            results.append(result)
        return results


# 全局实例
question_validation_service = QuestionValidationService()
