"""
LLM服务模块
统一封装大模型调用，支持多种模型提供商

对应需求：
- 需求16: 要求大模型根据hint_level参数控制输出颗粒度
- 需求18: 当学生陷入困境时，讲师Agent主动介入下发提示
- 需求24: 规范大模型生成推荐理由的输入上下文

实现文件：backend/services/llm_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Generator
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from datetime import datetime, timedelta

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from openai import OpenAI
from utils.logger import logger
from utils.config import settings


class LLMProvider(Enum):
    """LLM提供商"""
    OPENAI = "openai"
    CLAUDE = "claude"
    DASHSCOPE = "dashscope"  # 阿里通义千问
    SILICONFLOW = "siliconflow"  # 硅基流动


class HintLevel(Enum):
    """提示等级"""
    L0_AUTONOMOUS = 0
    L1_DIRECTION = 1
    L2_FORMULA = 2
    L3_STEP = 3
    L4_ANSWER = 4


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cached: bool = False


class LLMService:
    """
    LLM服务
    
    功能：
    1. 统一封装多模型提供商调用
    2. L0-L4提示生成Prompt模板
    3. 情感感知响应Prompt模板
    4. 推荐理由生成Prompt模板
    5. 响应缓存机制
    """
    
    # 提示等级约束（硬指标 - 需求16）
    HINT_LEVEL_CONSTRAINTS = {
        HintLevel.L0_AUTONOMOUS: {
            'description': '学生自主完成，仅批改不干预',
            'constraints': ['仅提供批改结果', '不给出任何提示', '不透露答案'],
            'max_length': 100
        },
        HintLevel.L1_DIRECTION: {
            'description': '给出解题方向提示',
            'constraints': [
                '只输出解题方向、方法名称或苏格拉底式反问',
                '绝不包含具体公式',
                '绝不包含计算步骤',
                '绝不透露答案'
            ],
            'max_length': 200
        },
        HintLevel.L2_FORMULA: {
            'description': '给出相关公式定理',
            'constraints': [
                '输出特定的公式、定理',
                '可以指出题干中的隐含条件',
                '绝不包含具体计算步骤',
                '绝不透露答案'
            ],
            'max_length': 300
        },
        HintLevel.L3_STEP: {
            'description': '给出关键推导步骤',
            'constraints': [
                '代入题目具体数值',
                '推导并输出第一步或最核心的计算步骤',
                '可以展示中间推导',
                '绝不给出最终答案'
            ],
            'max_length': 400
        },
        HintLevel.L4_ANSWER: {
            'description': '给出完整解答',
            'constraints': [
                '给出包含所有中间推导的完整解答',
                '展示Standard Answer',
                '包含最终答案'
            ],
            'max_length': 800
        }
    }
    
    def __init__(self, provider: LLMProvider = None):
        """初始化LLM服务"""
        self.provider = provider or self._get_default_provider()
        self.client = self._create_client()
        self.cache = {}  # 简单内存缓存
        self.cache_ttl = 3600  # 缓存1小时
        logger.info(f"LLM服务初始化完成，提供商: {self.provider.value}")
    
    def _get_default_provider(self) -> LLMProvider:
        """获取默认LLM提供商"""
        # 优先级：OpenAI > Claude > DashScope > SiliconFlow
        if settings.openai_api_key:
            return LLMProvider.OPENAI
        elif settings.anthropic_api_key:
            return LLMProvider.CLAUDE
        elif settings.dashscope_api_key:
            return LLMProvider.DASHSCOPE
        else:
            return LLMProvider.SILICONFLOW
    
    def _create_client(self) -> OpenAI:
        """创建LLM客户端"""
        if self.provider == LLMProvider.OPENAI:
            return OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base or "https://api.openai.com/v1"
            )
        elif self.provider == LLMProvider.CLAUDE:
            return OpenAI(
                api_key=settings.anthropic_api_key,
                base_url="https://api.anthropic.com/v1"
            )
        elif self.provider == LLMProvider.DASHSCOPE:
            return OpenAI(
                api_key=settings.dashscope_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        else:  # SILICONFLOW
            return OpenAI(
                api_key=settings.siliconflow_api_key or settings.openai_api_key,
                base_url=settings.openai_api_base or "https://api.siliconflow.cn/v1"
            )
    
    # ==================== 需求16: L0-L4提示生成 ====================
    
    def generate_hint(
        self,
        hint_level: HintLevel,
        question_content: str,
        knowledge_points: List[str],
        student_message: str = None,
        use_cache: bool = True
    ) -> LLMResponse:
        """
        生成指定等级的提示
        
        对应需求16: 根据hint_level严格控制输出颗粒度
        """
        # 构建Prompt
        prompt = self._build_hint_prompt(
            hint_level=hint_level,
            question_content=question_content,
            knowledge_points=knowledge_points,
            student_message=student_message
        )
        
        # 检查缓存
        if use_cache:
            cache_key = self._get_cache_key(prompt)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                cached_response.cached = True
                return cached_response
        
        # 调用LLM
        response = self._call_llm(prompt, max_tokens=self.HINT_LEVEL_CONSTRAINTS[hint_level]['max_length'])
        
        # 存入缓存
        if use_cache:
            self._set_cache(cache_key, response)
        
        return response
    
    def _build_hint_prompt(
        self,
        hint_level: HintLevel,
        question_content: str,
        knowledge_points: List[str],
        student_message: str = None
    ) -> str:
        """构建提示生成Prompt"""
        constraints = self.HINT_LEVEL_CONSTRAINTS[hint_level]
        
        prompt = f"""你是一位数学辅导老师。请根据以下要求为学生提供提示：

【题目内容】
{question_content}

【涉及知识点】
{', '.join(knowledge_points)}

【提示等级】L{hint_level.value} - {constraints['description']}

【严格约束】（必须遵守）
"""
        for i, constraint in enumerate(constraints['constraints'], 1):
            prompt += f"{i}. {constraint}\n"
        
        prompt += f"\n【字数限制】不超过{constraints['max_length']}字\n"
        
        if student_message:
            prompt += f"\n【学生当前状态】{student_message}\n"
        
        prompt += """
【输出要求】
- 只输出提示内容，不要有任何前缀说明
- 使用Markdown格式，数学公式使用LaTeX
- 语气友好、鼓励性

请生成提示："""
        
        return prompt
    
    # ==================== 需求18: 情感感知响应 ====================
    
    def generate_emotional_response(
        self,
        sentiment: str,
        confidence: float,
        question_content: str,
        knowledge_points: List[str],
        use_cache: bool = True
    ) -> LLMResponse:
        """
        生成情感感知响应
        
        对应需求18: 当学生陷入困境时，主动介入下发提示
        """
        prompt = self._build_emotional_prompt(
            sentiment=sentiment,
            confidence=confidence,
            question_content=question_content,
            knowledge_points=knowledge_points
        )
        
        if use_cache:
            cache_key = self._get_cache_key(prompt)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                cached_response.cached = True
                return cached_response
        
        response = self._call_llm(prompt, max_tokens=300)
        
        if use_cache:
            self._set_cache(cache_key, response)
        
        return response
    
    def _build_emotional_prompt(
        self,
        sentiment: str,
        confidence: float,
        question_content: str,
        knowledge_points: List[str]
    ) -> str:
        """构建情感感知Prompt"""
        
        sentiment_descriptions = {
            'difficult_perceived': '学生觉得题目很难，感到挫败',
            'confident': '学生信心充足，觉得题目简单',
            'confused': '学生对步骤感到困惑，看不懂',
            'frustrated': '学生连续错误，感到沮丧'
        }
        
        sentiment_desc = sentiment_descriptions.get(sentiment, '学生处于正常状态')
        
        prompt = f"""你是一位富有同理心的数学辅导老师。检测到学生当前的学习状态：

【检测到的情感】{sentiment}（置信度: {confidence:.0%}）
【情感描述】{sentiment_desc}

【题目内容】
{question_content}

【涉及知识点】
{', '.join(knowledge_points)}

【响应策略】
"""
        
        if sentiment == 'difficult_perceived':
            prompt += """
- 先给予情感支持，缓解焦虑
- 分解题目难度，降低心理门槛
- 提供L1级别的方向提示
- 强调"错误是学习的机会"
"""
        elif sentiment == 'confident':
            prompt += """
- 肯定学生的信心
- 鼓励挑战更高难度
- 减少提示，给予自主空间
- 提醒注意细节
"""
        elif sentiment == 'confused':
            prompt += """
- 承认步骤的复杂性
- 详细解释中间推导步骤
- 使用类比帮助理解
- 确认每一步的理解
"""
        elif sentiment == 'frustrated':
            prompt += """
- 首先给予情感安抚
- 强调"连续错误是发现薄弱点的机会"
- 降低当前题目难度或换题
- 提供额外的鼓励和支持
"""
        
        prompt += """
【输出要求】
- 语气温暖、支持性
- 包含具体的数学提示（根据上述策略）
- 不超过300字
- 使用Markdown格式

请生成响应："""
        
        return prompt
    
    # ==================== 需求24: 推荐理由生成 ====================
    
    def generate_recommendation_reason(
        self,
        weak_knowledge_points: List[str],
        question_difficulty: float,
        user_theta: float,
        days_since_last_error: int,
        question_source: str,
        use_cache: bool = True
    ) -> LLMResponse:
        """
        生成推荐理由
        
        对应需求24: 规范推荐理由的输入上下文，确保数据准确性
        """
        prompt = self._build_recommendation_prompt(
            weak_knowledge_points=weak_knowledge_points,
            question_difficulty=question_difficulty,
            user_theta=user_theta,
            days_since_last_error=days_since_last_error,
            question_source=question_source
        )
        
        if use_cache:
            cache_key = self._get_cache_key(prompt)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                cached_response.cached = True
                return cached_response
        
        response = self._call_llm(prompt, max_tokens=100)
        
        if use_cache:
            self._set_cache(cache_key, response)
        
        return response
    
    def _build_recommendation_prompt(
        self,
        weak_knowledge_points: List[str],
        question_difficulty: float,
        user_theta: float,
        days_since_last_error: int,
        question_source: str
    ) -> str:
        """构建推荐理由Prompt"""
        
        source_descriptions = {
            'review': '复习队列中的错题',
            'weak': '基于薄弱知识点的攻坚题',
            'explore': '拓展新题'
        }
        
        source_desc = source_descriptions.get(question_source, '推荐题目')
        
        difficulty_gap = abs(question_difficulty - user_theta)
        difficulty_match = "完美匹配" if difficulty_gap <= 0.3 else "略有挑战" if difficulty_gap <= 0.5 else "难度较高"
        
        prompt = f"""你是一位数学辅导Advisor。请根据以下上下文生成推荐理由：

【上下文变量】
- 薄弱知识点：{', '.join(weak_knowledge_points)}
- 距上次做错天数：{days_since_last_error}天
- 题目难度：{question_difficulty:.1f}
- 学生能力值：{user_theta:.1f}
- 难度匹配度：{difficulty_match}
- 题目来源：{source_desc}

【输出要求】
- 采用"导师/教练"口吻
- 严格控制在30字以内
- 自然融入上述变量
- 消除学生的"黑盒感"

【示例】
"距离上次做错放缩法已过{days_since_last_error}天，测测肌肉记忆还在不？"
"你在【{weak_kps}】还需加强，这道题难度正好匹配你当前水平。"

请生成推荐理由（30字以内）："""
        
        return prompt
    
    # ==================== LLM调用和缓存 ====================
    
    def _call_llm(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> LLMResponse:
        """调用LLM"""
        try:
            model = self._get_model_name()
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业的数学辅导老师，擅长因材施教。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return LLMResponse(
                content=response.choices[0].message.content.strip(),
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                model=model,
                cached=False
            )
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
    
    def _get_model_name(self) -> str:
        """获取模型名称"""
        model_map = {
            LLMProvider.OPENAI: "gpt-4",
            LLMProvider.CLAUDE: "claude-3-sonnet-20240229",
            LLMProvider.DASHSCOPE: "qwen-max",
            LLMProvider.SILICONFLOW: "deepseek-ai/DeepSeek-V2.5"
        }
        return model_map.get(self.provider, "gpt-4")
    
    def _get_cache_key(self, prompt: str) -> str:
        """生成缓存key"""
        return hashlib.md5(prompt.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[LLMResponse]:
        """从缓存获取"""
        if key in self.cache:
            cached_time, response = self.cache[key]
            if datetime.now() - cached_time < timedelta(seconds=self.cache_ttl):
                return response
            else:
                del self.cache[key]
        return None
    
    def _set_cache(self, key: str, response: LLMResponse):
        """设置缓存"""
        self.cache[key] = (datetime.now(), response)
        
        # 清理过期缓存
        if len(self.cache) > 1000:
            self._clean_cache()
    
    def _clean_cache(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [
            k for k, (t, _) in self.cache.items()
            if now - t > timedelta(seconds=self.cache_ttl)
        ]
        for k in expired_keys:
            del self.cache[k]


# ==================== 便捷函数 ====================

def generate_hint_by_level(
    level: int,
    question_content: str,
    knowledge_points: List[str]
) -> str:
    """
    便捷函数：生成指定等级的提示
    
    使用示例:
        hint = generate_hint_by_level(
            level=1,
            question_content="已知等差数列...",
            knowledge_points=["等差数列"]
        )
    """
    service = LLMService()
    hint_level = HintLevel(level)
    response = service.generate_hint(
        hint_level=hint_level,
        question_content=question_content,
        knowledge_points=knowledge_points
    )
    return response.content


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("LLM服务测试")
    print("=" * 60)
    
    service = LLMService()
    
    # 测试提示等级约束
    print("\n提示等级约束：")
    for level in HintLevel:
        constraints = service.HINT_LEVEL_CONSTRAINTS[level]
        print(f"\nL{level.value}: {constraints['description']}")
        print(f"  约束: {constraints['constraints']}")
        print(f"  字数: {constraints['max_length']}")
