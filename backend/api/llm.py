"""
LLM API接口
提供大模型提示生成和情感响应的HTTP接口

对应需求：
- 需求16: 要求大模型根据hint_level参数控制输出颗粒度
- 需求18: 当学生陷入困境时，讲师Agent主动介入下发提示
- 需求24: 规范大模型生成推荐理由的输入上下文

实现文件：backend/api/llm.py
"""

import sys
import os

# 添加backend目录到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from services.llm_service import LLMService, HintLevel, LLMResponse
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/llm", tags=["大模型服务"])


# ============ 数据模型 ============

class GenerateHintRequest(BaseModel):
    """生成提示请求"""
    hint_level: int = Field(..., ge=0, le=4, description="提示等级 L0-L4")
    question_content: str = Field(..., description="题目内容")
    knowledge_points: List[str] = Field(default=[], description="知识点列表")
    student_message: Optional[str] = Field(default=None, description="学生消息（可选）")


class GenerateHintResponse(BaseModel):
    """生成提示响应"""
    success: bool
    hint_level: int
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cached: bool


class EmotionalResponseRequest(BaseModel):
    """情感响应请求"""
    sentiment: str = Field(..., description="检测到的情感类型")
    confidence: float = Field(..., ge=0, le=1, description="情感置信度")
    question_content: str = Field(..., description="题目内容")
    knowledge_points: List[str] = Field(default=[], description="知识点列表")


class EmotionalResponseResponse(BaseModel):
    """情感响应响应"""
    success: bool
    sentiment: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


class RecommendationReasonRequest(BaseModel):
    """推荐理由请求"""
    weak_knowledge_points: List[str] = Field(..., description="薄弱知识点列表")
    question_difficulty: float = Field(..., description="题目难度")
    user_theta: float = Field(..., description="学生能力值")
    days_since_last_error: int = Field(..., description="距上次做错天数")
    question_source: str = Field(..., description="题目来源（review/weak/explore）")


class RecommendationReasonResponse(BaseModel):
    """推荐理由响应"""
    success: bool
    reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


class HintConstraintsResponse(BaseModel):
    """提示约束响应"""
    success: bool
    constraints: Dict[str, Any]


# ============ API端点 ============

@router.post("/generate-hint", response_model=GenerateHintResponse)
async def generate_hint(
    request: GenerateHintRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    生成指定等级的提示
    
    对应需求16: 根据hint_level严格控制输出颗粒度
    
    L0: 仅批改，不干预
    L1: 只输出解题方向、方法名称或苏格拉底式反问（绝不包含公式）
    L2: 输出特定的公式、定理（绝不包含计算步骤）
    L3: 代入具体数值，输出第一步或核心计算步骤（绝不给出最终答案）
    L4: 给出包含所有中间推导的完整解答
    """
    try:
        user_id = current_user.id
        logger.info(f"生成提示: 用户={user_id}, 等级=L{request.hint_level}")
        
        service = LLMService()
        hint_level = HintLevel(request.hint_level)
        
        response = service.generate_hint(
            hint_level=hint_level,
            question_content=request.question_content,
            knowledge_points=request.knowledge_points,
            student_message=request.student_message
        )
        
        return GenerateHintResponse(
            success=True,
            hint_level=request.hint_level,
            content=response.content,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            model=response.model,
            cached=response.cached
        )
        
    except Exception as e:
        logger.error(f"生成提示失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emotional-response", response_model=EmotionalResponseResponse)
async def generate_emotional_response(
    request: EmotionalResponseRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    生成情感感知响应
    
    对应需求18: 当学生陷入困境时，讲师Agent主动介入下发提示
    
    根据检测到的情感类型（困难感知/信心充足/步骤困惑/挫败感）
    生成相应的情感支持和教学提示
    """
    try:
        user_id = current_user.id
        logger.info(f"生成情感响应: 用户={user_id}, 情感={request.sentiment}")
        
        service = LLMService()
        
        response = service.generate_emotional_response(
            sentiment=request.sentiment,
            confidence=request.confidence,
            question_content=request.question_content,
            knowledge_points=request.knowledge_points
        )
        
        return EmotionalResponseResponse(
            success=True,
            sentiment=request.sentiment,
            content=response.content,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            model=response.model
        )
        
    except Exception as e:
        logger.error(f"生成情感响应失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendation-reason", response_model=RecommendationReasonResponse)
async def generate_recommendation_reason(
    request: RecommendationReasonRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    生成推荐理由
    
    对应需求24: 规范大模型生成推荐理由的输入上下文
    
    必须注入的变量：
    - weak_knowledge_points: 薄弱点名称
    - days_since_last_error: 距上次做错天数
    - difficulty_level: 题目难度评级
    
    约束：
    - 采用"导师/教练"口吻
    - 字数严格控制在30字以内
    """
    try:
        user_id = current_user.id
        logger.info(f"生成推荐理由: 用户={user_id}")
        
        service = LLMService()
        
        response = service.generate_recommendation_reason(
            weak_knowledge_points=request.weak_knowledge_points,
            question_difficulty=request.question_difficulty,
            user_theta=request.user_theta,
            days_since_last_error=request.days_since_last_error,
            question_source=request.question_source
        )
        
        return RecommendationReasonResponse(
            success=True,
            reason=response.content,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            model=response.model
        )
        
    except Exception as e:
        logger.error(f"生成推荐理由失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hint-constraints/{hint_level}", response_model=HintConstraintsResponse)
async def get_hint_constraints(hint_level: int):
    """
    获取提示等级约束
    
    返回指定等级的约束条件，供前端参考
    """
    try:
        if hint_level < 0 or hint_level > 4:
            raise HTTPException(status_code=400, detail="提示等级必须在0-4之间")
        
        service = LLMService()
        level = HintLevel(hint_level)
        constraints = service.HINT_LEVEL_CONSTRAINTS[level]
        
        return HintConstraintsResponse(
            success=True,
            constraints={
                'level': hint_level,
                'description': constraints['description'],
                'constraints': constraints['constraints'],
                'max_length': constraints['max_length']
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取提示约束失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hint-constraints/all")
async def get_all_hint_constraints():
    """获取所有提示等级的约束"""
    try:
        service = LLMService()
        
        all_constraints = {}
        for level in HintLevel:
            constraints = service.HINT_LEVEL_CONSTRAINTS[level]
            all_constraints[f"L{level.value}"] = {
                'description': constraints['description'],
                'constraints': constraints['constraints'],
                'max_length': constraints['max_length']
            }
        
        return {
            'success': True,
            'constraints': all_constraints
        }
        
    except Exception as e:
        logger.error(f"获取所有提示约束失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """LLM服务健康检查"""
    try:
        service = LLMService()
        return {
            'status': 'healthy',
            'provider': service.provider.value,
            'model': service._get_model_name(),
            'cache_size': len(service.cache)
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
