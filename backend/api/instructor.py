"""
Instructor Agent API接口
提供教学交互和提示生成的HTTP接口

实现文件：backend/api/instructor.py
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

from agents.instructor_agent import InstructorAgent, InstructorResponse
from algorithms.hint_generator import HintGenerator, HintLevel
from algorithms.sentiment_analyzer import SentimentAnalyzer, analyze_sentiment
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/instructor", tags=["Instructor教学"])


# ============ 数据模型 ============

class HintButtonRequest(BaseModel):
    """Hint Button点击请求"""
    question_id: str = Field(..., description="题目ID")
    question_content: str = Field(..., description="题目内容")
    knowledge_points: List[str] = Field(default=[], description="知识点列表")
    current_state: Optional[str] = Field(default=None, description="当前按钮状态")


class HintButtonResponse(BaseModel):
    """Hint Button点击响应"""
    success: bool
    content: str
    hint_level: int
    actual_weight: float
    next_button_text: str
    latex_formulas: List[str]


class UserMessageRequest(BaseModel):
    """用户消息请求"""
    question_id: str = Field(..., description="题目ID")
    question_content: str = Field(..., description="题目内容")
    knowledge_points: List[str] = Field(default=[], description="知识点列表")
    user_message: str = Field(..., description="用户消息内容")
    advisor_instruction: Optional[Dict[str, Any]] = Field(default=None, description="Advisor指令")


class UserMessageResponse(BaseModel):
    """用户消息响应"""
    success: bool
    content: str
    hint_level: int
    actual_weight: float
    teaching_mode: str
    sentiment: Optional[str]
    sentiment_confidence: Optional[float]
    latex_formulas: List[str]


class GenerateHintRequest(BaseModel):
    """生成提示请求"""
    level: int = Field(..., ge=0, le=4, description="提示等级 (0-4)")
    question_content: str = Field(..., description="题目内容")
    knowledge_points: List[str] = Field(default=[], description="知识点列表")


class GenerateHintResponse(BaseModel):
    """生成提示响应"""
    success: bool
    level: int
    title: str
    content: str
    actual_weight: float
    latex_formulas: List[str]
    follow_up_question: Optional[str]


class SentimentAnalysisRequest(BaseModel):
    """情感分析请求"""
    message: str = Field(..., description="要分析的消息")


class SentimentAnalysisResponse(BaseModel):
    """情感分析响应"""
    success: bool
    sentiment: str
    confidence: float
    keywords: List[str]
    learning_style: Optional[str]
    suggested_strategy: str


class BatchSentimentRequest(BaseModel):
    """批量情感分析请求"""
    messages: List[str] = Field(..., description="消息列表")


class BatchSentimentResponse(BaseModel):
    """批量情感分析响应"""
    success: bool
    results: List[Dict[str, Any]]
    needs_intervention: bool


# ============ API端点 ============

@router.post("/hint-button", response_model=HintButtonResponse)
async def handle_hint_button_click(
    request: HintButtonRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    处理Hint Button点击
    
    根据当前按钮状态生成对应等级的提示
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"Hint Button点击：用户={user_id}, 题目={request.question_id}")
        
        instructor = InstructorAgent()
        response = instructor.respond_to_hint_button_click(
            user_id=user_id,
            question_id=request.question_id,
            question_content=request.question_content,
            knowledge_points=request.knowledge_points,
            current_state=request.current_state
        )
        
        return HintButtonResponse(
            success=True,
            content=response.content,
            hint_level=response.hint_level if response.hint_level else 0,
            actual_weight=response.actual_weight,
            next_button_text=response.metadata.get('next_button_text', ''),
            latex_formulas=response.latex_formulas
        )
        
    except Exception as e:
        logger.error(f"Hint Button处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/respond", response_model=UserMessageResponse)
async def respond_to_user_message(
    request: UserMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    响应用户消息
    
    进行情感分析，根据Advisor指令调整教学策略
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"用户消息：用户={user_id}, 消息={request.user_message[:50]}...")
        
        instructor = InstructorAgent()
        response = instructor.respond_to_user_message(
            user_id=user_id,
            question_id=request.question_id,
            question_content=request.question_content,
            knowledge_points=request.knowledge_points,
            user_message=request.user_message,
            advisor_instruction=request.advisor_instruction
        )
        
        return UserMessageResponse(
            success=True,
            content=response.content,
            hint_level=response.hint_level if response.hint_level else 0,
            actual_weight=response.actual_weight,
            teaching_mode=response.teaching_mode.value,
            sentiment=response.metadata.get('sentiment'),
            sentiment_confidence=response.metadata.get('confidence'),
            latex_formulas=response.latex_formulas
        )
        
    except Exception as e:
        logger.error(f"响应用户消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-hint", response_model=GenerateHintResponse)
async def generate_hint(
    request: GenerateHintRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    生成指定等级的提示
    
    直接生成L0-L4等级的提示内容
    """
    try:
        logger.info(f"生成提示：等级=L{request.level}")
        
        generator = HintGenerator()
        hint = generator.generate_hint(
            level=HintLevel(request.level),
            question_content=request.question_content,
            knowledge_points=request.knowledge_points
        )
        
        return GenerateHintResponse(
            success=True,
            level=hint.level.value,
            title=hint.title,
            content=hint.content,
            actual_weight=hint.actual_weight,
            latex_formulas=hint.latex_formulas,
            follow_up_question=hint.follow_up_question
        )
        
    except Exception as e:
        logger.error(f"生成提示失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-sentiment", response_model=SentimentAnalysisResponse)
async def analyze_message_sentiment(
    request: SentimentAnalysisRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    分析消息情感
    
    检测用户表达的学习状态和情感
    """
    try:
        logger.info(f"情感分析：{request.message[:50]}...")
        
        result = analyze_sentiment(request.message)
        
        return SentimentAnalysisResponse(
            success=True,
            sentiment=result['sentiment'],
            confidence=result['confidence'],
            keywords=result['keywords'],
            learning_style=result['learning_style'],
            suggested_strategy=result['suggested_response_strategy']
        )
        
    except Exception as e:
        logger.error(f"情感分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-sentiment/batch", response_model=BatchSentimentResponse)
async def analyze_batch_sentiment(
    request: BatchSentimentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    批量分析消息情感
    
    分析最近的多轮对话，判断是否需要干预
    """
    try:
        logger.info(f"批量情感分析：{len(request.messages)}条消息")
        
        from algorithms.sentiment_analyzer import detect_learning_difficulty
        
        result = detect_learning_difficulty(request.messages)
        
        # 转换结果格式
        detailed_results = []
        analyzer = SentimentAnalyzer()
        for msg in request.messages:
            analysis = analyzer.analyze(msg)
            detailed_results.append({
                'message': msg[:50] + '...' if len(msg) > 50 else msg,
                'sentiment': analysis.sentiment.value,
                'confidence': analysis.confidence
            })
        
        return BatchSentimentResponse(
            success=True,
            results=detailed_results,
            needs_intervention=result['needs_intervention']
        )
        
    except Exception as e:
        logger.error(f"批量情感分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advisor-instruction")
async def handle_advisor_instruction(
    request: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    处理Advisor指令
    
    Advisor通过指令控制Instructor的教学策略
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"Advisor指令：用户={user_id}, 指令={request.get('instruction', '')}")
        
        instructor = InstructorAgent()
        response = instructor.respond_to_advisor_instruction(
            user_id=user_id,
            question_id=request.get('question_id', ''),
            question_content=request.get('question_content', ''),
            knowledge_points=request.get('knowledge_points', []),
            instruction=request.get('instruction', {})
        )
        
        return {
            'success': True,
            'content': response.content,
            'hint_level': response.hint_level,
            'actual_weight': response.actual_weight,
            'teaching_mode': response.teaching_mode.value,
            'latex_formulas': response.latex_formulas
        }
        
    except Exception as e:
        logger.error(f"处理Advisor指令失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        # 初始化各组件检查
        generator = HintGenerator()
        analyzer = SentimentAnalyzer()
        instructor = InstructorAgent()
        
        return {
            'status': 'healthy',
            'hint_generator': 'ok',
            'sentiment_analyzer': 'ok',
            'instructor_agent': 'ok'
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
