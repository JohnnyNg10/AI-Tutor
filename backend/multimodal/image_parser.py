from typing import Dict, Any, Optional
import base64
import os

from utils.config import settings
from utils.logger import logger
from utils.siliconflow_vision import siliconflow_vision_client


# 通用图片分析提示词 - 同时支持印刷题目和手写答案
VISION_ANALYSIS_PROMPT = """请仔细分析这张图片中的所有文字和数学内容。

这张图片可能是：
- 印刷的数学题目（从教辅/试卷上截图或拍照）
- 手写的解题过程（学生在纸上写的答案和演算）

你的任务：
1. 识别图片中所有的文字、数学公式、符号和数字
2. 区分"题目内容"和"解题/答案内容"
3. 数学公式请用 LaTeX 格式表示（行内公式用 $...$，独立公式用 $$...$$）

请严格按以下 JSON 格式返回（不要添加任何其他文字）：
```json
{
  "question_text": "提取到的题目内容（含LaTeX公式），如果没有题目则为空字符串",
  "answer_text": "提取到的解题过程或手写答案（含LaTeX公式），如果没有解题过程则为空字符串",
  "has_question": true或false,
  "has_answer": true或false
}
```

注意：
- 如果图片是印刷题目，question_text 填写题目内容，answer_text 留空
- 如果图片是手写答案，answer_text 填写识别到的手写内容，question_text 留空
- 如果图片同时包含题目和解答，分别填入对应字段
- 手写内容请尽力识别，即使字迹不太清晰也要尝试提取
- LaTeX公式示例：$a_{n+1}=2a_n+1$、$$S_n=\\frac{n(a_1+a_n)}{2}$$
- 如果图片中完全没有数学相关内容，has_question和has_answer都设为false
"""


class ImageParser:
    def __init__(self):
        pass
    
    async def parse_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image path {image_path} does not exist")
                return None
            
            logger.info(f"Parsing image {image_path}")

            # 读取图片并编码为base64
            with open(image_path, "rb") as f:
                image_bytes = f.read()
                image_data = base64.b64encode(image_bytes).decode()
                logger.info(f"Image base64 encoded, length: {len(image_data)} chars")

            # 检测图片格式
            image_format = self._detect_image_format(image_bytes)
            logger.info(f"Detected image format: {image_format}")

            # 构建 messages，正确的多模态格式
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": VISION_ANALYSIS_PROMPT,
                        }
                    ]
                }
            ]

            logger.info(f"Sending image to vision model: {settings.vision_model}")
            response = await siliconflow_vision_client.analyze_image(messages=messages)

            if not response:
                logger.error(f"Vision model returned empty response for {image_path}")
                return {
                    "success": False,
                    "question_text": "",
                    "has_question": False,
                    "error": "视觉模型返回空结果"
                }

            # 尝试解析JSON返回
            import json
            import re

            try:
                # 尝试提取JSON（可能包裹在```json```中）
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                else:
                    # 尝试直接解析
                    parsed = json.loads(response)

                question_text = parsed.get("question_text", "").strip()
                answer_text = parsed.get("answer_text", "").strip()
                has_question = parsed.get("has_question", bool(question_text))
                has_answer = parsed.get("has_answer", bool(answer_text))

                # 如果没有区分，整段当作题目文本
                if not question_text and not answer_text:
                    question_text = response.strip()
                    has_question = len(question_text) > 10

                logger.info(f"Parsed image: has_question={has_question}, has_answer={has_answer}")
                logger.info(f"Question preview: {question_text[:100] if question_text else '(empty)'}...")
                logger.info(f"Answer preview: {answer_text[:100] if answer_text else '(empty)'}...")

                return {
                    "success": True,
                    "question_text": question_text,
                    "answer_text": answer_text,
                    "has_question": has_question,
                    "has_answer": has_answer,
                }

            except (json.JSONDecodeError, AttributeError):
                # JSON解析失败，回退到纯文本处理
                has_question = "未识别到" not in response and len(response.strip()) > 10
                logger.info(f"JSON parse failed, fallback plain text, has_question: {has_question}")

                return {
                    "success": True,
                    "question_text": response.strip(),
                    "answer_text": "",
                    "has_question": has_question,
                    "has_answer": False,
                }
            
        except Exception as e:
            logger.error(f"Image parsing error: {e}", exc_info=True)
            return {
                "success": False,
                "question_text": "",
                "has_question": False,
                "error": str(e)
            }
    
    def _detect_image_format(self, image_bytes: bytes) -> str:
        """检测图片格式"""
        if image_bytes.startswith(b'\x89PNG'):
            return 'png'
        elif image_bytes.startswith(b'\xff\xd8'):
            return 'jpeg'
        elif image_bytes.startswith(b'GIF89a') or image_bytes.startswith(b'GIF87a'):
            return 'gif'
        elif image_bytes.startswith(b'RIFF') and image_bytes[8:12] == b'WEBP':
            return 'webp'
        else:
            return 'jpeg'  # 默认返回jpeg


image_parser = ImageParser()
            