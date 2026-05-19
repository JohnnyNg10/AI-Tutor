"""
错题本错误原因分类API接口
提供错题按错误原因分类的HTTP接口

对应行号13: 错题本的分类不仅依靠章节，更依靠 AI 诊断出的"错误原因"进行聚类

实现文件: backend/api/error_classification.py
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
from fastapi import APIRouter, HTTPException, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession
from database.db import get_db
from services.error_classification_service import (
    ErrorClassificationService,
    get_wrong_questions_by_error_category,
    get_rehabilitation_pack
)
from services.error_diagnosis_service import error_diagnosis_service, ErrorDiagnosisResult
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/error-classification", tags=["错题本错误原因分类"])


# ============ 数据模型 ============

class ErrorCategoryResponse(BaseModel):
    """错误分类响应"""
    success: bool
    categories: Dict[str, Any]


class WrongQuestionsViewResponse(BaseModel):
    """错题视图响应"""
    success: bool
    user_id: int
    view_type: str
    title: str
    groups: Dict[str, Any]


class RehabilitationPackResponse(BaseModel):
    """专项复健题包响应"""
    success: bool
    user_id: int
    error_category: str
    category_name: str
    pack_name: str
    description: str
    question_count: int
    questions: List[Dict[str, Any]]
    study_suggestion: str


class ErrorStatisticsResponse(BaseModel):
    """错误统计响应"""
    success: bool
    user_id: int
    total_errors: int
    category_count: int
    distribution: List[Dict[str, Any]]
    top_error_type: Optional[str]


# ============ API端点 ============

@router.get("/categories")
async def get_error_categories(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取错误原因分类定义
    
    返回所有错误原因分类的定义（计算失误、公式错误等）
    """
    try:
        service = ErrorClassificationService()
        
        return {
            'success': True,
            'categories': service.ERROR_CATEGORIES
        }
        
    except Exception as e:
        logger.error(f"获取错误分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wrong-questions/by-category", response_model=WrongQuestionsViewResponse)
async def get_wrong_questions_by_category(
    db: AsyncSession = Depends(get_db),
    category_filter: Optional[str] = Query(None, description="分类筛选"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """按错误原因获取错题（真实数据库查询）"""
    try:
        user_id = current_user.id

        service = ErrorClassificationService()
        data = await service.get_categories_async(db, user_id)

        groups = {
            cat_name: {
                'category': cat_name,
                'count': cat['count'],
                'questions': cat['questions']
            }
            for cat_name, cat in data['categories'].items()
        }

        return WrongQuestionsViewResponse(
            success=True,
            user_id=user_id,
            view_type='error_category',
            title='按错误原因分类',
            groups=groups
        )

    except Exception as e:
        logger.error(f"获取错题分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wrong-questions/by-chapter")
async def get_wrong_questions_by_chapter(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """按章节获取错题"""
    try:
        user_id = current_user.id
        
        service = ErrorClassificationService()
        view = service.get_wrong_questions_by_view(user_id, 'chapter')
        
        return {
            'success': True,
            'user_id': user_id,
            'view_type': view['view_type'],
            'title': view['title'],
            'groups': view['groups']
        }
        
    except Exception as e:
        logger.error(f"获取章节错题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wrong-questions/by-time")
async def get_wrong_questions_by_time(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """按时间获取错题"""
    try:
        user_id = current_user.id
        
        service = ErrorClassificationService()
        view = service.get_wrong_questions_by_view(user_id, 'time')
        
        return {
            'success': True,
            'user_id': user_id,
            'view_type': view['view_type'],
            'title': view['title'],
            'groups': view['groups']
        }
        
    except Exception as e:
        logger.error(f"获取时间错题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rehabilitation/{error_category}", response_model=RehabilitationPackResponse)
async def generate_rehabilitation_pack(
    error_category: str,
    question_count: int = Query(3, ge=1, le=5, description="题目数量"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    生成专项复健题包
    
    对应行号13: 一键专项复健，连续推送3道同错因题目
    """
    try:
        user_id = current_user.id
        
        service = ErrorClassificationService()
        pack = service.generate_rehabilitation_pack(
            user_id=user_id,
            error_category=error_category,
            question_count=question_count
        )
        
        if pack['success']:
            return RehabilitationPackResponse(
                success=True,
                user_id=user_id,
                error_category=error_category,
                category_name=pack['category_name'],
                pack_name=pack['pack_name'],
                description=pack['description'],
                question_count=pack['question_count'],
                questions=pack['questions'],
                study_suggestion=pack['study_suggestion']
            )
        else:
            raise HTTPException(status_code=400, detail=pack['error'])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成复健题包失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=ErrorStatisticsResponse)
async def get_error_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取错误统计"""
    try:
        user_id = current_user.id
        
        service = ErrorClassificationService()
        stats = service.get_error_statistics(user_id)
        
        return ErrorStatisticsResponse(
            success=True,
            user_id=user_id,
            total_errors=stats['total_errors'],
            category_count=stats['category_count'],
            distribution=stats['distribution'],
            top_error_type=stats['top_error_type']
        )
        
    except Exception as e:
        logger.error(f"获取错误统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 错因诊断（LLM驱动） ============

class DiagnosisRequest(BaseModel):
    """错因诊断请求"""
    question_text: str = Field(..., description="题目内容")
    standard_answer: str = Field("", description="标准答案/解析")
    student_answer: str = Field(..., description="学生答案")
    knowledge_points: List[str] = Field(default_factory=list, description="关联知识点名称")
    user_mastery: Dict[str, float] = Field(default_factory=dict, description="学生掌握度 {kp_name: p_known}")
    hint_levels_used: int = Field(0, description="使用的提示等级数")


class DiagnosisResponse(BaseModel):
    """错因诊断响应"""
    success: bool
    diagnosis: Dict[str, Any]


@router.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose_error(request: DiagnosisRequest):
    """
    LLM错因诊断

    对标猿辅导"五重错因分析法"：
    1. 概念错误 (concept_error) — 不知道/记错了知识点
    2. 过程错误 (process_error) — 思路/方法错了
    3. 计算错误 (calculation_error) — 算错了
    4. 审题错误 (reading_error) — 读错题了
    5. 格式错误 (format_error) — 会做但表达有误

    返回结构化诊断：错误类型、位置、严重程度、引导提示、是否需要重试
    """
    try:
        result = await error_diagnosis_service.diagnose(
            question_text=request.question_text,
            standard_answer=request.standard_answer,
            student_answer=request.student_answer,
            knowledge_points=request.knowledge_points,
            user_mastery=request.user_mastery,
            hint_levels_used=request.hint_levels_used
        )
        return DiagnosisResponse(success=True, diagnosis=result.to_dict())
    except Exception as e:
        logger.error(f"错因诊断失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = ErrorClassificationService()
        return {
            'status': 'healthy',
            'service': 'error_classification',
            'error_categories': len(service.ERROR_CATEGORIES),
            'features': ['error_category_clustering', 'view_switching', 'rehabilitation_pack']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
