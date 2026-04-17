"""
收藏夹顿悟标签服务
强化收藏夹的记忆辅助属性，引导学生记录瞬间的思维火花

对应行号13: 强化收藏夹的记忆辅助属性，引导学生记录瞬间的思维火花

功能：
1. 收藏时弹出顿悟标签表单
2. 顿悟标签分类管理
3. 收藏夹列表高亮展示标签
4. 标签筛选和搜索

实现文件: backend/services/favorite_insight_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.redis_service import RedisService
from utils.logger import logger


@dataclass
class InsightTag:
    """顿悟标签"""
    tag_id: str
    tag_name: str
    tag_category: str  # preset / custom
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None


@dataclass
class FavoriteWithInsight:
    """带顿悟标签的收藏"""
    favorite_id: str
    user_id: int
    question_id: str
    question_title: str
    insight_tag: str  # 标签ID或自定义文本
    insight_note: str  # 详细笔记
    created_at: str
    updated_at: str
    is_highlighted: bool = True  # 是否高亮显示


class FavoriteInsightService:
    """
    收藏夹顿悟标签服务
    
    功能：
    1. 预设顿悟标签管理
    2. 收藏时标签选择/输入
    3. 收藏夹列表高亮展示
    4. 标签筛选和统计
    """
    
    # Redis Key前缀
    FAVORITE_KEY = "ai:tutor:favorite:{user_id}:{favorite_id}"
    FAVORITE_LIST_KEY = "ai:tutor:favorites:{user_id}"
    TAG_STATS_KEY = "ai:tutor:favorite-tags:{user_id}"
    
    # 预设顿悟标签
    PRESET_INSIGHT_TAGS = [
        InsightTag(
            tag_id="breakthrough",
            tag_name="💡 顿悟时刻",
            tag_category="preset",
            description="突然理解了之前不懂的知识点",
            icon="💡",
            color="#FFD700"
        ),
        InsightTag(
            tag_id="tricky",
            tag_name="🎣 切入点奇葩",
            tag_category="preset",
            description="解题思路很巧妙，值得记住",
            icon="🎣",
            color="#FF6B6B"
        ),
        InsightTag(
            tag_id="pitfall",
            tag_name="⚠️ 防坑指南",
            tag_category="preset",
            description="容易犯错的地方，需要警惕",
            icon="⚠️",
            color="#FF4D4F"
        ),
        InsightTag(
            tag_id="classic",
            tag_name="📚 经典题型",
            tag_category="preset",
            description="典型的解题方法，需要熟练掌握",
            icon="📚",
            color="#52C41A"
        ),
        InsightTag(
            tag_id="formula",
            tag_name="🔢 公式妙用",
            tag_category="preset",
            description="公式的巧妙应用或变形",
            icon="🔢",
            color="#1890FF"
        ),
        InsightTag(
            tag_id="mistake",
            tag_name="❌ 粗心错误",
            tag_category="preset",
            description="因为粗心导致的错误，提醒自己注意",
            icon="❌",
            color="#FAAD14"
        ),
        InsightTag(
            tag_id="review",
            tag_name="🔄 需要复习",
            tag_category="preset",
            description="还没有完全掌握，需要经常回顾",
            icon="🔄",
            color="#722ED1"
        ),
        InsightTag(
            tag_id="technique",
            tag_name="🛠️ 解题技巧",
            tag_category="preset",
            description="实用的解题技巧或方法",
            icon="🛠️",
            color="#13C2C2"
        )
    ]
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("收藏夹顿悟标签服务初始化完成")
    
    # ==================== 预设标签管理 ====================
    
    def get_preset_tags(self) -> List[Dict[str, Any]]:
        """获取所有预设标签"""
        return [
            {
                'tag_id': tag.tag_id,
                'tag_name': tag.tag_name,
                'tag_category': tag.tag_category,
                'description': tag.description,
                'icon': tag.icon,
                'color': tag.color
            }
            for tag in self.PRESET_INSIGHT_TAGS
        ]
    
    def get_tag_by_id(self, tag_id: str) -> Optional[InsightTag]:
        """根据ID获取标签"""
        for tag in self.PRESET_INSIGHT_TAGS:
            if tag.tag_id == tag_id:
                return tag
        return None
    
    def validate_tag(self, tag: str) -> Dict[str, Any]:
        """
        验证标签
        
        如果是预设标签ID，返回标签详情
        如果是自定义文本，返回自定义类型
        """
        preset = self.get_tag_by_id(tag)
        if preset:
            return {
                'valid': True,
                'type': 'preset',
                'tag_id': preset.tag_id,
                'tag_name': preset.tag_name,
                'icon': preset.icon,
                'color': preset.color
            }
        
        # 自定义标签
        if len(tag) <= 50:  # 限制长度
            return {
                'valid': True,
                'type': 'custom',
                'tag_id': f"custom_{datetime.now().timestamp()}",
                'tag_name': tag,
                'icon': '📝',
                'color': '#999999'
            }
        
        return {
            'valid': False,
            'error': '标签长度不能超过50字符'
        }
    
    # ==================== 收藏管理 ====================
    
    def add_favorite_with_insight(
        self,
        user_id: int,
        question_id: str,
        question_title: str,
        insight_tag: str,
        insight_note: str = ""
    ) -> Dict[str, Any]:
        """
        添加收藏（带顿悟标签）
        
        对应行号13: 点击收藏时弹出轻量级表单，要求选择或输入顿悟标签
        """
        try:
            # 验证标签
            tag_validation = self.validate_tag(insight_tag)
            if not tag_validation['valid']:
                return {'success': False, 'error': tag_validation['error']}
            
            # 生成收藏ID
            favorite_id = f"fav_{user_id}_{question_id}_{int(datetime.now().timestamp())}"
            
            now = datetime.now().isoformat()
            
            # 构建收藏数据
            favorite_data = {
                'favorite_id': favorite_id,
                'user_id': user_id,
                'question_id': question_id,
                'question_title': question_title,
                'insight_tag': insight_tag,
                'insight_tag_type': tag_validation['type'],
                'insight_tag_name': tag_validation['tag_name'],
                'insight_tag_icon': tag_validation.get('icon', '📝'),
                'insight_tag_color': tag_validation.get('color', '#999999'),
                'insight_note': insight_note,
                'created_at': now,
                'updated_at': now,
                'is_highlighted': True
            }
            
            # 存储收藏
            favorite_key = self.FAVORITE_KEY.format(
                user_id=user_id,
                favorite_id=favorite_id
            )
            self.redis_service.redis_client.hset(favorite_key, mapping={
                'data': json.dumps(favorite_data)
            })
            
            # 添加到用户收藏列表
            list_key = self.FAVORITE_LIST_KEY.format(user_id=user_id)
            self.redis_service.redis_client.zadd(
                list_key,
                {favorite_id: datetime.now().timestamp()}
            )
            
            # 更新标签统计
            self._update_tag_stats(user_id, insight_tag)
            
            logger.info(f"添加收藏成功: 用户={user_id}, 题目={question_id}, 标签={insight_tag}")
            
            return {
                'success': True,
                'favorite_id': favorite_id,
                'message': '收藏添加成功',
                'tag_info': tag_validation
            }
            
        except Exception as e:
            logger.error(f"添加收藏失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def update_favorite_insight(
        self,
        user_id: int,
        favorite_id: str,
        insight_tag: Optional[str] = None,
        insight_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新收藏的顿悟标签"""
        try:
            favorite_key = self.FAVORITE_KEY.format(
                user_id=user_id,
                favorite_id=favorite_id
            )
            
            # 获取现有数据
            existing = self.redis_service.redis_client.hget(favorite_key, 'data')
            if not existing:
                return {'success': False, 'error': '收藏不存在'}
            
            favorite_data = json.loads(existing)
            
            # 更新标签
            if insight_tag:
                tag_validation = self.validate_tag(insight_tag)
                if not tag_validation['valid']:
                    return {'success': False, 'error': tag_validation['error']}
                
                favorite_data['insight_tag'] = insight_tag
                favorite_data['insight_tag_type'] = tag_validation['type']
                favorite_data['insight_tag_name'] = tag_validation['tag_name']
                favorite_data['insight_tag_icon'] = tag_validation.get('icon', '📝')
                favorite_data['insight_tag_color'] = tag_validation.get('color', '#999999')
            
            # 更新笔记
            if insight_note is not None:
                favorite_data['insight_note'] = insight_note
            
            favorite_data['updated_at'] = datetime.now().isoformat()
            
            # 保存更新
            self.redis_service.redis_client.hset(favorite_key, mapping={
                'data': json.dumps(favorite_data)
            })
            
            return {
                'success': True,
                'message': '收藏更新成功',
                'favorite': favorite_data
            }
            
        except Exception as e:
            logger.error(f"更新收藏失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_favorite(self, user_id: int, favorite_id: str) -> Optional[Dict[str, Any]]:
        """获取单个收藏详情"""
        try:
            favorite_key = self.FAVORITE_KEY.format(
                user_id=user_id,
                favorite_id=favorite_id
            )
            
            data = self.redis_service.redis_client.hget(favorite_key, 'data')
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"获取收藏失败: {e}")
            return None
    
    def get_user_favorites(
        self,
        user_id: int,
        tag_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取用户收藏列表
        
        对应行号13: 在收藏夹列表中，顿悟标签内容高亮展示于题目下方
        """
        try:
            list_key = self.FAVORITE_LIST_KEY.format(user_id=user_id)
            
            # 获取收藏ID列表
            favorite_ids = self.redis_service.redis_client.zrevrange(
                list_key, offset, offset + limit - 1
            )
            
            favorites = []
            for fav_id in favorite_ids:
                favorite = self.get_favorite(user_id, fav_id)
                if favorite:
                    # 标签筛选
                    if tag_filter and favorite.get('insight_tag') != tag_filter:
                        continue
                    favorites.append(favorite)
            
            return favorites
            
        except Exception as e:
            logger.error(f"获取收藏列表失败: {e}")
            return []
    
    def delete_favorite(self, user_id: int, favorite_id: str) -> bool:
        """删除收藏"""
        try:
            favorite_key = self.FAVORITE_KEY.format(
                user_id=user_id,
                favorite_id=favorite_id
            )
            list_key = self.FAVORITE_LIST_KEY.format(user_id=user_id)
            
            # 获取标签用于更新统计
            favorite = self.get_favorite(user_id, favorite_id)
            if favorite:
                tag = favorite.get('insight_tag')
                self._decrement_tag_stats(user_id, tag)
            
            # 删除数据
            self.redis_service.redis_client.delete(favorite_key)
            self.redis_service.redis_client.zrem(list_key, favorite_id)
            
            return True
            
        except Exception as e:
            logger.error(f"删除收藏失败: {e}")
            return False
    
    # ==================== 标签统计 ====================
    
    def _update_tag_stats(self, user_id: int, tag: str) -> None:
        """更新标签统计"""
        try:
            stats_key = self.TAG_STATS_KEY.format(user_id=user_id)
            self.redis_service.redis_client.hincrby(stats_key, tag, 1)
        except Exception as e:
            logger.error(f"更新标签统计失败: {e}")
    
    def _decrement_tag_stats(self, user_id: int, tag: str) -> None:
        """减少标签统计"""
        try:
            stats_key = self.TAG_STATS_KEY.format(user_id=user_id)
            current = int(self.redis_service.redis_client.hget(stats_key, tag) or 0)
            if current > 0:
                self.redis_service.redis_client.hset(stats_key, tag, current - 1)
        except Exception as e:
            logger.error(f"减少标签统计失败: {e}")
    
    def get_tag_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户标签统计"""
        try:
            stats_key = self.TAG_STATS_KEY.format(user_id=user_id)
            stats = self.redis_service.redis_client.hgetall(stats_key)
            
            # 转换为整数
            tag_counts = {tag: int(count) for tag, count in stats.items()}
            
            # 排序
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
            
            return {
                'total_favorites': sum(tag_counts.values()),
                'unique_tags': len(tag_counts),
                'tag_distribution': [
                    {
                        'tag': tag,
                        'count': count,
                        'percentage': round(count / sum(tag_counts.values()) * 100, 1)
                    }
                    for tag, count in sorted_tags
                ]
            }
            
        except Exception as e:
            logger.error(f"获取标签统计失败: {e}")
            return {'total_favorites': 0, 'unique_tags': 0, 'tag_distribution': []}
    
    # ==================== 收藏夹展示增强 ====================
    
    def get_favorites_with_highlight(
        self,
        user_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取高亮展示的收藏列表
        
        对应行号13: 顿悟标签高亮展示于题目下方
        """
        favorites = self.get_user_favorites(user_id, limit=limit)
        
        # 增强展示信息
        enhanced = []
        for fav in favorites:
            enhanced.append({
                'favorite_id': fav['favorite_id'],
                'question': {
                    'id': fav['question_id'],
                    'title': fav['question_title']
                },
                'insight': {
                    'tag_id': fav['insight_tag'],
                    'tag_name': fav['insight_tag_name'],
                    'tag_icon': fav['insight_tag_icon'],
                    'tag_color': fav['insight_tag_color'],
                    'note': fav['insight_note'],
                    'is_highlighted': fav['is_highlighted']
                },
                'created_at': fav['created_at'],
                'display': {
                    'title': fav['question_title'],
                    'subtitle': f"{fav['insight_tag_icon']} {fav['insight_tag_name']}",
                    'note_preview': fav['insight_note'][:50] + '...' if len(fav['insight_note']) > 50 else fav['insight_note'],
                    'highlight_color': fav['insight_tag_color']
                }
            })
        
        return enhanced
    
    def search_favorites(
        self,
        user_id: int,
        keyword: str,
        tag_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索收藏"""
        try:
            # 获取所有收藏
            all_favorites = self.get_user_favorites(user_id, limit=1000)
            
            results = []
            keyword_lower = keyword.lower()
            
            for fav in all_favorites:
                # 标签筛选
                if tag_filter and fav.get('insight_tag') != tag_filter:
                    continue
                
                # 关键词匹配
                match = (
                    keyword_lower in fav['question_title'].lower() or
                    keyword_lower in fav['insight_tag_name'].lower() or
                    keyword_lower in fav.get('insight_note', '').lower()
                )
                
                if match:
                    results.append(fav)
            
            return results
            
        except Exception as e:
            logger.error(f"搜索收藏失败: {e}")
            return []


# ==================== 便捷函数 ====================

def add_favorite_with_insight_tag(
    user_id: int,
    question_id: str,
    question_title: str,
    insight_tag: str,
    insight_note: str = ""
) -> Dict[str, Any]:
    """便捷函数：添加带顿悟标签的收藏"""
    service = FavoriteInsightService()
    return service.add_favorite_with_insight(
        user_id, question_id, question_title, insight_tag, insight_note
    )


def get_favorites_for_display(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """便捷函数：获取用于展示的收藏列表"""
    service = FavoriteInsightService()
    return service.get_favorites_with_highlight(user_id, limit)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("收藏夹顿悟标签服务测试")
    print("=" * 60)
    
    service = FavoriteInsightService()
    
    # 测试预设标签
    print("\n预设标签测试：")
    tags = service.get_preset_tags()
    for tag in tags[:3]:
        print(f"  {tag['icon']} {tag['tag_name']}: {tag['description']}")
    
    # 测试添加收藏
    print("\n添加收藏测试：")
    result = service.add_favorite_with_insight(
        user_id=1,
        question_id="q001",
        question_title="等差数列求和",
        insight_tag="breakthrough",
        insight_note="终于理解了等差数列求和公式的推导过程！"
    )
    print(f"  结果: {result['message']}")
    if result['success']:
        print(f"  标签: {result['tag_info']['tag_name']}")
    
    # 测试获取收藏列表
    print("\n收藏列表测试：")
    favorites = service.get_favorites_with_highlight(user_id=1, limit=5)
    for fav in favorites[:2]:
        print(f"  {fav['display']['title']}")
        print(f"    标签: {fav['display']['subtitle']}")
    
    # 测试标签统计
    print("\n标签统计测试：")
    stats = service.get_tag_statistics(user_id=1)
    print(f"  总收藏数: {stats['total_favorites']}")
    print(f"  标签种类: {stats['unique_tags']}")
    
    print("\n测试完成")
