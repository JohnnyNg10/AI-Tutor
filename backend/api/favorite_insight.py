"""
收藏夹顿悟标签API接口
提供收藏夹顿悟标签管理的HTTP接口

对应行号13: 强化收藏夹的记忆辅助属性，引导学生记录瞬间的思维火花

实现文件: backend/api/favorite_insight.py
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

from services.favorite_insight_service import (
    FavoriteInsightService,
    add_favorite_with_insight_tag,
    get_favorites_for_display
)
from utils.logger import logger
from utils.auth import get_current_user

router = APIRouter(prefix="/favorite-insight", tags=["收藏夹顿悟标签"])


# ============ 数据模型 ============

class AddFavoriteRequest(BaseModel):
    """添加收藏请求"""
    question_id: str = Field(..., description="题目ID")
    question_title: str = Field(..., description="题目标题")
    insight_tag: str = Field(..., description="顿悟标签（预设ID或自定义文本）")
    insight_note: str = Field(default="", description="详细笔记")


class UpdateFavoriteRequest(BaseModel):
    """更新收藏请求"""
    insight_tag: Optional[str] = Field(default=None, description="顿悟标签")
    insight_note: Optional[str] = Field(default=None, description="详细笔记")


class FavoriteResponse(BaseModel):
    """收藏响应"""
    success: bool
    favorite_id: str
    message: str
    tag_info: Dict[str, Any]


class FavoriteListResponse(BaseModel):
    """收藏列表响应"""
    success: bool
    user_id: int
    total: int
    favorites: List[Dict[str, Any]]


class TagStatisticsResponse(BaseModel):
    """标签统计响应"""
    success: bool
    user_id: int
    total_favorites: int
    unique_tags: int
    tag_distribution: List[Dict[str, Any]]


class PresetTagsResponse(BaseModel):
    """预设标签响应"""
    success: bool
    tags: List[Dict[str, Any]]


class SearchFavoritesRequest(BaseModel):
    """搜索收藏请求"""
    keyword: str = Field(..., description="搜索关键词")
    tag_filter: Optional[str] = Field(default=None, description="标签筛选")


# ============ API端点 ============

@router.get("/preset-tags", response_model=PresetTagsResponse)
async def get_preset_tags(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取预设顿悟标签
    
    返回所有可用的预设顿悟标签列表
    """
    try:
        service = FavoriteInsightService()
        tags = service.get_preset_tags()
        
        return PresetTagsResponse(
            success=True,
            tags=tags
        )
        
    except Exception as e:
        logger.error(f"获取预设标签失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add", response_model=FavoriteResponse)
async def add_favorite(
    request: AddFavoriteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    添加收藏（带顿悟标签）
    
    对应行号13: 点击收藏时弹出轻量级表单，要求选择或输入顿悟标签
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        result = service.add_favorite_with_insight(
            user_id=user_id,
            question_id=request.question_id,
            question_title=request.question_title,
            insight_tag=request.insight_tag,
            insight_note=request.insight_note
        )
        
        if result['success']:
            return FavoriteResponse(
                success=True,
                favorite_id=result['favorite_id'],
                message=result['message'],
                tag_info=result['tag_info']
            )
        else:
            raise HTTPException(status_code=400, detail=result['error'])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{favorite_id}")
async def update_favorite(
    favorite_id: str,
    request: UpdateFavoriteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """更新收藏的顿悟标签"""
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        result = service.update_favorite_insight(
            user_id=user_id,
            favorite_id=favorite_id,
            insight_tag=request.insight_tag,
            insight_note=request.insight_note
        )
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['error'])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=FavoriteListResponse)
async def get_favorites(
    tag_filter: Optional[str] = Query(None, description="标签筛选"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取收藏列表
    
    返回用户的收藏列表，包含顿悟标签信息
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        favorites = service.get_user_favorites(
            user_id=user_id,
            tag_filter=tag_filter,
            limit=limit,
            offset=offset
        )
        
        return FavoriteListResponse(
            success=True,
            user_id=user_id,
            total=len(favorites),
            favorites=favorites
        )
        
    except Exception as e:
        logger.error(f"获取收藏列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/highlighted")
async def get_highlighted_favorites(
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    获取高亮展示的收藏列表
    
    对应行号13: 在收藏夹列表中，顿悟标签内容高亮展示于题目下方
    """
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        favorites = service.get_favorites_with_highlight(user_id, limit)
        
        return {
            'success': True,
            'user_id': user_id,
            'total': len(favorites),
            'favorites': favorites
        }
        
    except Exception as e:
        logger.error(f"获取高亮收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{favorite_id}")
async def get_favorite_detail(
    favorite_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取收藏详情"""
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        favorite = service.get_favorite(user_id, favorite_id)
        
        if not favorite:
            raise HTTPException(status_code=404, detail="收藏不存在")
        
        return {
            'success': True,
            'favorite': favorite
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取收藏详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{favorite_id}")
async def delete_favorite(
    favorite_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """删除收藏"""
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        success = service.delete_favorite(user_id, favorite_id)
        
        if success:
            return {
                'success': True,
                'message': '收藏已删除',
                'favorite_id': favorite_id
            }
        else:
            raise HTTPException(status_code=500, detail="删除失败")
        
    except Exception as e:
        logger.error(f"删除收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/tags", response_model=TagStatisticsResponse)
async def get_tag_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """获取标签统计"""
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        stats = service.get_tag_statistics(user_id)
        
        return TagStatisticsResponse(
            success=True,
            user_id=user_id,
            total_favorites=stats['total_favorites'],
            unique_tags=stats['unique_tags'],
            tag_distribution=stats['tag_distribution']
        )
        
    except Exception as e:
        logger.error(f"获取标签统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_favorites(
    request: SearchFavoritesRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """搜索收藏"""
    try:
        user_id = current_user.get('id', 0)
        
        service = FavoriteInsightService()
        results = service.search_favorites(
            user_id=user_id,
            keyword=request.keyword,
            tag_filter=request.tag_filter
        )
        
        return {
            'success': True,
            'user_id': user_id,
            'keyword': request.keyword,
            'total': len(results),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"搜索收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-tag")
async def validate_insight_tag(
    tag: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """验证顿悟标签"""
    try:
        service = FavoriteInsightService()
        validation = service.validate_tag(tag)
        
        return {
            'success': True,
            'tag': tag,
            'validation': validation
        }
        
    except Exception as e:
        logger.error(f"验证标签失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """服务健康检查"""
    try:
        service = FavoriteInsightService()
        preset_tags = service.get_preset_tags()
        
        return {
            'status': 'healthy',
            'service': 'favorite_insight',
            'preset_tags_count': len(preset_tags),
            'features': ['preset_tags', 'custom_tags', 'highlight_display', 'tag_statistics']
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
