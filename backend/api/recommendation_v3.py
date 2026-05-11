"""
AI Tutor V3 推荐系统 API
提供基于RAG的候选池构建和题目推荐接口

实现文件：backend/api/recommendation_v3.py
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
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends
from database.db import get_db

from algorithms.rag_candidate_pool import (
    RAGCandidatePoolBuilder,
    CandidateQuestion
)
from algorithms.question_recommendation import (
    QuestionRecommendationEngine,
    RecommendedQuestion
)
from services.chroma_service import ChromaService
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/recommendation/v3", tags=["V3推荐系统"])


# ============ 数据模型 ============

class CandidatePoolRequest(BaseModel):
    """候选池构建请求"""
    weak_kps: List[str] = Field(..., description="薄弱知识点列表", example=["等比数列", "递推公式"])
    theta: float = Field(..., ge=-3, le=3, description="学生当前能力值", example=0.5)
    recent_context: Optional[str] = Field(default=None, description="最近学习上下文")
    top_k: int = Field(default=20, ge=1, le=100, description="返回候选数量")


class CandidatePoolResponse(BaseModel):
    """候选池构建响应"""
    success: bool
    total: int
    candidates: List[Dict[str, Any]]


class QuestionRecommendRequest(BaseModel):
    """题目推荐请求"""
    weak_kps: List[str] = Field(..., description="薄弱知识点列表", example=["等比数列", "递推公式"])
    theta: float = Field(..., ge=-3, le=3, description="学生当前能力值", example=0.5)
    recent_context: Optional[str] = Field(default=None, description="最近学习上下文")
    count: int = Field(default=5, ge=1, le=20, description="推荐题目数量")


class QuestionRecommendResponse(BaseModel):
    """题目推荐响应"""
    success: bool
    total: int
    new_count: int
    review_count: int
    questions: List[Dict[str, Any]]


class VectorSearchRequest(BaseModel):
    """向量搜索请求"""
    knowledge_point: str = Field(..., description="知识点", example="等差数列")
    top_k: int = Field(default=10, ge=1, le=50, description="返回数量")
    min_difficulty: Optional[float] = Field(default=None, ge=-3, le=3)
    max_difficulty: Optional[float] = Field(default=None, ge=-3, le=3)


class VectorSearchResponse(BaseModel):
    """向量搜索响应"""
    success: bool
    total: int
    results: List[Dict[str, Any]]


class ChromaStatsResponse(BaseModel):
    """Chroma统计信息响应"""
    success: bool
    knowledge_points_count: int
    example_questions_count: int
    persist_dir: str


# ============ API端点 ============

@router.post("/candidate-pool", response_model=CandidatePoolResponse)
async def build_candidate_pool(
    request: CandidatePoolRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    构建RAG候选池
    
    推题漏斗三层架构：
    1. 召回层：Chroma向量检索，基于薄弱知识点标签
    2. 过滤层：Redis Seen Pool去重 + 难度匹配 |S - θ| ≤ 1.0
    3. 精排层：相似度加权 0.6×kp_relevance + 0.3×difficulty_match + 0.1×context_similarity
    """
    try:
        user_id = current_user.id
        logger.info(f"构建候选池请求：用户={user_id}, 薄弱知识点={request.weak_kps}, θ={request.theta}")
        
        builder = RAGCandidatePoolBuilder()
        candidates = builder.build_candidate_pool(
            user_id=user_id,
            weak_kps=request.weak_kps,
            theta=request.theta,
            recent_context=request.recent_context,
            top_k=request.top_k
        )
        
        # 转换响应格式
        candidate_list = [builder.get_candidate_details(c) for c in candidates]
        
        return CandidatePoolResponse(
            success=True,
            total=len(candidate_list),
            candidates=candidate_list
        )
        
    except Exception as e:
        logger.error(f"构建候选池失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/questions", response_model=QuestionRecommendResponse)
async def recommend_questions(
    request: QuestionRecommendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    推荐题目（完整流程）
    
    整合以下功能：
    1. Redis复习队列调度（优先级复习）
    2. RAG候选池构建（新题探索）
    3. 新题/复习策略分配（70%新题 + 30%复习）
    4. 推荐理由生成（LLM适配层）
    """
    try:
        user_id = current_user.id
        logger.info(f"推荐题目请求：用户={user_id}, θ={request.theta}, 数量={request.count}")
        
        engine = QuestionRecommendationEngine()
        recommendations = await engine.recommend_questions_async(
            db=db,
            user_id=user_id,
            weak_kps=request.weak_kps,
            theta=request.theta,
            recent_context=request.recent_context,
            count=request.count
        )
        
        return engine.format_recommendation_response(recommendations)
        
    except Exception as e:
        logger.error(f"推荐题目失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-search", response_model=VectorSearchResponse)
async def vector_search(
    request: VectorSearchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    基于知识点的向量检索
    
    使用Chroma向量数据库进行语义检索
    """
    try:
        logger.info(f"向量搜索请求：知识点={request.knowledge_point}")
        
        service = ChromaService()
        
        # 构建难度范围
        difficulty_range = None
        if request.min_difficulty is not None and request.max_difficulty is not None:
            difficulty_range = (request.min_difficulty, request.max_difficulty)
        
        results = service.search_by_knowledge_point(
            knowledge_point=request.knowledge_point,
            top_k=request.top_k,
            difficulty_range=difficulty_range
        )
        
        # 转换响应格式
        result_list = [
            {
                'question_id': r.question_id,
                'content': r.content[:200] + '...' if len(r.content) > 200 else r.content,
                'difficulty': r.difficulty,
                'knowledge_points': r.knowledge_points,
                'similarity': round(r.similarity, 4),
                'metadata': r.metadata
            }
            for r in results
        ]
        
        return VectorSearchResponse(
            success=True,
            total=len(result_list),
            results=result_list
        )
        
    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chroma-stats", response_model=ChromaStatsResponse)
async def get_chroma_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取Chroma向量数据库统计信息
    """
    try:
        service = ChromaService()
        stats = service.get_collection_stats()
        
        return ChromaStatsResponse(
            success=True,
            knowledge_points_count=stats.get('knowledge_points_count', 0),
            example_questions_count=stats.get('example_questions_count', 0),
            persist_dir=stats.get('persist_dir', '')
        )
        
    except Exception as e:
        logger.error(f"获取Chroma统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/question/{question_id}")
async def get_question_detail(
    question_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取题目详情（从Chroma向量库）
    """
    try:
        service = ChromaService()
        question = service.get_question_by_id(question_id)
        
        if not question:
            raise HTTPException(status_code=404, detail="题目未找到")
        
        return {
            'success': True,
            'question': question
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取题目详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        # 检查Chroma连接
        service = ChromaService()
        stats = service.get_collection_stats()
        
        return {
            'status': 'healthy',
            'chroma_connected': True,
            'knowledge_points_count': stats.get('knowledge_points_count', 0),
            'example_questions_count': stats.get('example_questions_count', 0)
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
