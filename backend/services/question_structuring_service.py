"""
题目结构化服务
将用户上传的图片或文字提问转换为标准格式的题目
"""

import re
from typing import Optional, Dict, Any
from openai import OpenAI
from utils.config import settings
from utils.logger import logger


class QuestionStructuringService:
    """将用户输入（图片/文字）结构化为标准题目格式"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base
        )
        self.model = settings.llm_model
    
    async def structure_from_text(self, user_input: str) -> Dict[str, Any]:
        """
        从文字输入中提取结构化题目
        logger.info(f"[题目结构化] 处理文字输入: {user_input[:50]}...")
        
        Args:
            user_input: 用户的原始文字输入（可能包含多余提示词）
            
        Returns:
            {
                "content": "纯净的题目内容",
                "knowledge_points": ["知识点1", "知识点2"],
                "difficulty": 0.5,
                "question_type": "解答题"
            }
        """
        # 首先进行简单的规则清理
        cleaned_input = self._clean_prompt_words(user_input)
        
        # 如果清理后的内容很短，可能不是题目（但如果是图片相关的提问，保留）
        if len(cleaned_input) < 5:
            logger.warning(f"输入太短，可能不是题目: {cleaned_input}")
            return None
        
        # 使用 LLM 提取结构化信息
        prompt = f"""请从以下用户输入中提取数学题目，并转换为标准格式。

用户输入：
{cleaned_input}

请分析并返回以下信息（JSON格式）：
{{
    "content": "提取后的纯净题目内容（只保留数学题目本身，去掉所有提问词如'这道题怎么做'等）",
    "knowledge_points": ["涉及的知识点1", "知识点2"],
    "difficulty": 0.5,
    "question_type": "解答题/选择题/填空题"
}}

注意：
1. content 字段只保留数学题目本身，去掉所有非题目内容
2. 如果输入不是数学题目，返回 null
3. difficulty 范围 0.1-1.0，根据题目复杂度判断"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个数学题目提取专家，擅长从用户输入中提取纯净的数学题目。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            # 验证结果
            if not result or not result.get("content"):
                logger.warning(f"无法从输入中提取题目: {user_input[:100]}")
                # 降级：返回清理后的原始内容
                return {
                    "content": cleaned_input,
                    "knowledge_points": [],
                    "difficulty": 0.5,
                    "question_type": "解答题"
                }
            
            # 如果清理后的内容与原始内容差异很大，记录日志
            if len(result["content"]) < len(user_input) * 0.5:
                logger.info(f"题目已清理: '{user_input[:50]}...' -> '{result['content'][:50]}...'")
            
            return result
            
        except Exception as e:
            logger.error(f"题目结构化失败: {e}")
            # 降级：返回清理后的原始内容
            return {
                "content": cleaned_input,
                "knowledge_points": [],
                "difficulty": 0.5,
                "question_type": "解答题"
            }
    
    async def structure_from_image(self, image_path: str) -> Dict[str, Any]:
        """从图片中提取结构化题目（使用视觉模型 OCR）"""
        import base64
        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')

            import os
            # 检测图片格式
            with open(image_path, "rb") as f:
                header = f.read(12)
            if header.startswith(b'\x89PNG'):
                fmt = 'png'
            elif header.startswith(b'\xff\xd8'):
                fmt = 'jpeg'
            elif header.startswith(b'GIF'):
                fmt = 'gif'
            elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
                fmt = 'webp'
            else:
                fmt = 'jpeg'

            model = settings.vision_model or "Qwen/Qwen3-VL-32B-Instruct"
            logger.info(f"调用视觉模型 {model} 识别图片...")

            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """请识别图片中的数学题目，并转换为标准格式。

请返回以下信息（JSON格式）：
{
    "content": "图片中的纯净题目内容（LaTeX格式，只保留题目本身）",
    "knowledge_points": ["涉及的知识点1", "知识点2"],
    "difficulty": 0.5,
    "question_type": "解答题/选择题/填空题"
}

注意：
1. 只提取数学题目，忽略其他文字
2. 使用LaTeX格式表示数学公式
3. 如果图片中没有数学题目，返回 null"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{fmt};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )

            import json
            raw = response.choices[0].message.content.strip()
            logger.info(f"视觉模型原始返回: {raw[:200]}...")

            # Try to parse JSON from the response (may be wrapped in ```json blocks)
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(l for l in lines if not l.startswith("```"))

            result = json.loads(raw) if raw else None

            if not result or not result.get("content"):
                logger.warning(f"无法从图片中提取题目: {image_path}")
                return None

            logger.info(f"图片OCR成功: {result.get('content', '')[:80]}...")
            return result

        except Exception as e:
            logger.error(f"图片题目提取失败: {e}")
            return None
    
    def _clean_prompt_words(self, text: str) -> str:
        """清理常见的提问提示词"""
        cleaned = text.strip()
        
        # 只清理特定的提问前缀/后缀，不要清理题目内容
        # 这些模式只匹配纯提问词，不匹配包含数学内容的句子
        prompt_patterns = [
            r"^请问[，,]?",
            r"^我想知道[，,]?",
            r"^能[不能]帮我[，,]?",
            r"^如何[做写解][，,]?",
            r"^求解[，,]?",
            r"^帮忙[，,]?",
            r"^教教我[，,]?",
            r"^这道题[的]?第[一二三四五12345]小?问?[怎么]?[做写解]?[？?]$",
            r"^[这个那道]题[怎么]?[做写解]?[？?]$",
        ]
        
        # 移除常见的提问前缀
        for pattern in prompt_patterns:
            new_cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            if new_cleaned != cleaned and len(new_cleaned.strip()) > 0:
                cleaned = new_cleaned
        
        # 清理多余的空格
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 如果清理后内容为空或太短，返回原始内容
        if len(cleaned) < 5:
            return text.strip()
        
        return cleaned


# 全局实例
question_structuring_service = QuestionStructuringService()
