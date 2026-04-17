"""
计算失误处理API接口
提供错误诊断和权重保护的HTTP接口

对应需求17: 复用V2的错误诊断能力，避免在"纯计算失误"时错误扣除学生的Actual权重

实现文件：backend/api/calculation_error.py
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

from algorithms.calculation_error_handler import (
    CalculationErrorHandler,
    ErrorType,
    diagnose_and_protect_score
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/calculation-error", tags=["计算失误处理"])


# ============ 数据模型 ============

class DiagnoseErrorRequest(BaseModel):
    """错误诊断请求"""
    student_answer: str = Field(..., description="学生答案")
    correct_answer: str = Field(..., description="正确答案")
    solution_steps: List[str] = Field(default=[], description="解题步骤")
    error_analysis: Optional[str] = Field(default=None, description="错误分析（可选）")
    hint_level: int = Field(default=0, ge=0, le=4, description="当前提示等级")


class DiagnoseErrorResponse(BaseModel):
    """错误诊断响应"""
    success: bool
    error_type: str
    is_calculation_error: bool
    confidence: float
    description: str
    suggested_hint: str
    should_preserve_weight: bool


class CalculateScoreRequest(BaseModel):
    """计算分数请求"""
    base_score: float = Field(..., ge=0, le=1, description="基础分数")
    hint_level: int = Field(..., ge=0, le=4, description="提示等级")
    error_analysis: str = Field(..., description="错误分析")


class CalculateScoreResponse(BaseModel):
    """计算分数响应"""
    success: bool
    final_score: float
    base_score: float
    hint_penalty: float
    effective_hint_penalty: float
    protection_applied: bool
    protection_reason: Optional[str]
    error_type: str


class LightHintResponse(BaseModel):
    """轻提示响应"""
    success: bool
    hint: str
    is_calculation_error: bool


# ============ API端点 ============

@router.post("/diagnose", response_model=DiagnoseErrorResponse)
async def diagnose_error(
    request: DiagnoseErrorRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    诊断错误类型
    
    识别纯计算失误 vs 逻辑/公式错误
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"诊断错误: 用户={user_id}")
        
        handler = CalculationErrorHandler()
        
        result = handler.diagnose_error(
            student_answer=request.student_answer,
            correct_answer=request.correct_answer,
            solution_steps=request.solution_steps,
            error_analysis=request.error_analysis
        )
        
        return DiagnoseErrorResponse(
            success=True,
            error_type=result.error_type.value,
            is_calculation_error=result.is_calculation_error,
            confidence=result.confidence,
            description=result.description,
            suggested_hint=result.suggested_hint,
            should_preserve_weight=result.should_preserve_weight
        )
        
    except Exception as e:
        logger.error(f"诊断错误失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-score", response_model=CalculateScoreResponse)
async def calculate_score_with_protection(
    request: CalculateScoreRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    计算Actual Score（带权重保护）
    
    对应需求17: 纯计算失误时不降低Actual权重
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"计算受保护分数: 用户={user_id}")
        
        handler = CalculationErrorHandler()
        
        # 先诊断错误
        diagnosis = handler.diagnose_error(
            student_answer="",  # 简化处理
            correct_answer="",
            solution_steps=[],
            error_analysis=request.error_analysis
        )
        
        # 计算受保护的分数
        result = handler.calculate_actual_score_with_protection(
            base_score=request.base_score,
            hint_level=request.hint_level,
            error_diagnosis=diagnosis
        )
        
        return CalculateScoreResponse(
            success=True,
            **result
        )
        
    except Exception as e:
        logger.error(f"计算分数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnose-and-score")
async def diagnose_and_calculate(
    request: DiagnoseErrorRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    诊断错误并计算分数（组合接口）
    """
    try:
        user_id = current_user.get('id', 0)
        logger.info(f"诊断并计算: 用户={user_id}")
        
        result = diagnose_and_protect_score(
            student_answer=request.student_answer,
            correct_answer=request.correct_answer,
            hint_level=request.hint_level,
            base_score=1.0,  # 默认基础分数
            error_analysis=request.error_analysis
        )
        
        return {
            'success': True,
            'diagnosis': result['diagnosis'],
            'score_calculation': result['score_calculation']
        }
        
    except Exception as e:
        logger.error(f"诊断并计算失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/light-hint")
async def get_light_hint(
    error_analysis: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取轻提示
    
    对应需求17: 纯计算失误时弹出轻提示，不触发L1-L4降权重
    """
    try:
        user_id = current_user.get('id', 0)
        
        handler = CalculationErrorHandler()
        
        # 诊断错误
        error_type, confidence = handler._classify_error_type(error_analysis)
        
        # 生成轻提示
        hint = handler._generate_light_hint(error_type, error_analysis)
        
        is_calc_error = (error_type == ErrorType.CALCULATION_ERROR and confidence > 0.7)
        
        return LightHintResponse(
            success=True,
            hint=hint,
            is_calculation_error=is_calc_error
        )
        
    except Exception as e:
        logger.error(f"获取轻提示失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/error-types")
async def get_error_types():
    """获取错误类型列表"""
    return {
        'success': True,
        'error_types': [
            {
                'type': 'calculation_error',
                'name': '纯计算失误',
                'description': '思路和方法正确，但计算过程出错',
                'weight_protection': True
            },
            {
                'type': 'logic_error',
                'name': '逻辑错误',
                'description': '解题思路存在问题',
                'weight_protection': False
            },
            {
                'type': 'formula_error',
                'name': '公式错误',
                'description': '公式记忆或应用不当',
                'weight_protection': False
            },
            {
                'type': 'concept_error',
                'name': '概念错误',
                'description': '对知识点的理解有误',
                'weight_protection': False
            }
        ]
    }


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        handler = CalculationErrorHandler()
        return {
            'status': 'healthy',
            'service': 'calculation_error_handler',
            'error_patterns_loaded': True
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
