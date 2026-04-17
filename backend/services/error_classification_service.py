"""
错题本错误原因分类服务
错题本的分类不仅依靠章节，更依靠 AI 诊断出的"错误原因"进行聚类

对应行号13: 错题本的分类不仅依靠章节，更依靠 AI 诊断出的"错误原因"进行聚类

功能：
1. 按错误原因分类（计算失误、公式错误、概念错误等）
2. 分类下提供"一键专项复健"按钮
3. 视图切换：时间/章节/错因

实现文件: backend/services/error_classification_service.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
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
class ErrorCategory:
    """错误分类"""
    category_id: str
    category_name: str
    description: str
    icon: str
    color: str
    error_count: int
    questions: List[Dict[str, Any]]
    last_updated: str


@dataclass
class ClassifiedWrongQuestion:
    """分类后的错题"""
    question_id: str
    question_title: str
    error_category: str
    error_analysis: str
    wrong_answer: str
    correct_answer: str
    created_at: str
    review_count: int
    is_mastered: bool


class ErrorClassificationService:
    """
    错题本错误原因分类服务
    
    功能：
    1. 按错误原因聚类
    2. 多视图切换
    3. 专项复健推荐
    """
    
    # Redis Key前缀
    ERROR_CLASSIFICATION_KEY = "ai:tutor:error-class:{user_id}"
    WRONG_QUESTIONS_KEY = "ai:tutor:wrong-q:{user_id}"
    
    # 错误原因分类定义
    ERROR_CATEGORIES = {
        'calculation_error': {
            'name': '计算失误',
            'description': '数值计算、符号处理等计算过程中的错误',
            'icon': '🔢',
            'color': '#FF6B6B'
        },
        'formula_error': {
            'name': '公式错误',
            'description': '公式记忆错误、公式应用不当',
            'icon': '📐',
            'color': '#FAAD14'
        },
        'concept_error': {
            'name': '概念错误',
            'description': '对数学概念、定理理解有误',
            'icon': '❓',
            'color': '#FF4D4F'
        },
        'logic_error': {
            'name': '逻辑错误',
            'description': '解题思路、推理过程存在逻辑问题',
            'icon': '🧩',
            'color': '#EB2F96'
        },
        'careless_error': {
            'name': '粗心大意',
            'description': '审题不清、漏看条件、抄写错误等',
            'icon': '👀',
            'color': '#FA8C16'
        },
        'boundary_error': {
            'name': '边界条件',
            'description': '未讨论边界情况、特殊情况',
            'icon': '📏',
            'color': '#F5222D'
        },
        'transformation_error': {
            'name': '变形困难',
            'description': '题目变形后无法适应、缺乏灵活性',
            'icon': '🔄',
            'color': '#722ED1'
        },
        'unknown_error': {
            'name': '未分类',
            'description': '暂时无法归类的错误',
            'icon': '❔',
            'color': '#999999'
        }
    }
    
    def __init__(self):
        """初始化服务"""
        self.redis_service = RedisService()
        logger.info("错题本错误原因分类服务初始化完成")
    
    # ==================== 错误分类核心 ====================
    
    def classify_wrong_questions(
        self,
        user_id: int,
        questions: Optional[List[Dict]] = None
    ) -> Dict[str, ErrorCategory]:
        """
        按错误原因对错题进行分类聚类
        
        对应行号13: 错题本按错误原因聚类
        """
        try:
            # 获取用户的错题
            if questions is None:
                questions = self._get_user_wrong_questions(user_id)
            
            # 按错误原因分类
            classified = {cat_id: [] for cat_id in self.ERROR_CATEGORIES.keys()}
            
            for q in questions:
                error_category = q.get('error_category', 'unknown_error')
                if error_category not in classified:
                    error_category = 'unknown_error'
                classified[error_category].append(q)
            
            # 生成分类结果
            categories = {}
            for cat_id, cat_config in self.ERROR_CATEGORIES.items():
                cat_questions = classified[cat_id]
                
                categories[cat_id] = ErrorCategory(
                    category_id=cat_id,
                    category_name=cat_config['name'],
                    description=cat_config['description'],
                    icon=cat_config['icon'],
                    color=cat_config['color'],
                    error_count=len(cat_questions),
                    questions=cat_questions[:20],  # 最多20题
                    last_updated=datetime.now().isoformat()
                )
            
            # 缓存结果
            self._cache_classification(user_id, categories)
            
            return categories
            
        except Exception as e:
            logger.error(f"分类错题失败: {e}")
            return {}
    
    def _get_user_wrong_questions(self, user_id: int) -> List[Dict]:
        """获取用户错题"""
        # TODO: 从数据库查询
        # 临时返回模拟数据
        return [
            {
                'question_id': 'q001',
                'question_title': '等差数列求和',
                'error_category': 'calculation_error',
                'error_analysis': '最后一步计算出错',
                'created_at': datetime.now().isoformat()
            },
            {
                'question_id': 'q002',
                'question_title': '等比数列通项',
                'error_category': 'formula_error',
                'error_analysis': '记错了等比数列通项公式',
                'created_at': datetime.now().isoformat()
            }
        ]
    
    def _cache_classification(
        self,
        user_id: int,
        categories: Dict[str, ErrorCategory]
    ) -> None:
        """缓存分类结果"""
        try:
            key = self.ERROR_CLASSIFICATION_KEY.format(user_id=user_id)
            
            data = {
                cat_id: {
                    'category_id': cat.category_id,
                    'category_name': cat.category_name,
                    'error_count': cat.error_count,
                    'last_updated': cat.last_updated
                }
                for cat_id, cat in categories.items()
            }
            
            self.redis_service.redis_client.hset(key, mapping={
                'data': json.dumps(data),
                'updated_at': datetime.now().isoformat()
            })
            self.redis_service.redis_client.expire(key, 3600)
            
        except Exception as e:
            logger.error(f"缓存分类结果失败: {e}")
    
    # ==================== 视图切换 ====================
    
    def get_wrong_questions_by_view(
        self,
        user_id: int,
        view_type: str = 'error_category',
        category_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取不同视图的错题
        
        视图类型：time（时间）/ chapter（章节）/ error_category（错因）
        """
        try:
            questions = self._get_user_wrong_questions(user_id)
            
            if view_type == 'time':
                # 按时间排序
                sorted_qs = sorted(questions, key=lambda x: x.get('created_at', ''), reverse=True)
                return {
                    'view_type': 'time',
                    'title': '按时间排序',
                    'groups': {
                        'recent': sorted_qs[:10]
                    }
                }
            
            elif view_type == 'chapter':
                # 按章节分组
                chapters = {}
                for q in questions:
                    chapter = q.get('chapter', '未分类')
                    if chapter not in chapters:
                        chapters[chapter] = []
                    chapters[chapter].append(q)
                
                return {
                    'view_type': 'chapter',
                    'title': '按章节分类',
                    'groups': chapters
                }
            
            elif view_type == 'error_category':
                # 按错误原因分类（行号13核心）
                categories = self.classify_wrong_questions(user_id, questions)
                
                groups = {}
                for cat_id, cat in categories.items():
                    if cat.error_count > 0:
                        if category_filter is None or cat_id == category_filter:
                            groups[cat_id] = {
                                'category_name': cat.category_name,
                                'description': cat.description,
                                'icon': cat.icon,
                                'color': cat.color,
                                'error_count': cat.error_count,
                                'questions': cat.questions
                            }
                
                return {
                    'view_type': 'error_category',
                    'title': '按错误原因分类',
                    'groups': groups
                }
            
            else:
                return {'error': '不支持的视图类型'}
                
        except Exception as e:
            logger.error(f"获取错题视图失败: {e}")
            return {'error': str(e)}
    
    # ==================== 专项复健（行号13核心） ====================
    
    def generate_rehabilitation_pack(
        self,
        user_id: int,
        error_category: str,
        question_count: int = 3
    ) -> Dict[str, Any]:
        """
        生成专项复健题包
        
        对应行号13: 在特定错因分类下，提供"一键专项复健"按钮，连续推送3道同错因题目
        """
        try:
            # 获取该错因类型的题目
            categories = self.classify_wrong_questions(user_id)
            category = categories.get(error_category)
            
            if not category or category.error_count == 0:
                return {
                    'success': False,
                    'error': '该错误类型下没有错题'
                }
            
            # 推荐同错因的新题（变式题）
            recommended = self._recommend_similar_questions(
                user_id,
                error_category,
                category.questions,
                question_count
            )
            
            return {
                'success': True,
                'user_id': user_id,
                'error_category': error_category,
                'category_name': category.category_name,
                'pack_name': f"{category.category_name}专项复健",
                'description': f"针对{category.category_name}的专项训练，共{len(recommended)}题",
                'question_count': len(recommended),
                'questions': recommended,
                'study_suggestion': self._generate_study_suggestion(error_category)
            }
            
        except Exception as e:
            logger.error(f"生成复健题包失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _recommend_similar_questions(
        self,
        user_id: int,
        error_category: str,
        wrong_questions: List[Dict],
        count: int
    ) -> List[Dict]:
        """推荐同错因的相似题目"""
        # TODO: 从题库推荐变式题
        # 临时返回模拟数据
        return [
            {
                'question_id': f'similar_{i}',
                'title': f'{self.ERROR_CATEGORIES[error_category]["name"]}练习题{i+1}',
                'difficulty': 'medium',
                'error_category': error_category
            }
            for i in range(count)
        ]
    
    def _generate_study_suggestion(self, error_category: str) -> str:
        """生成学习建议"""
        suggestions = {
            'calculation_error': '建议：加强基础计算练习，养成检查习惯，注意符号和数值',
            'formula_error': '建议：整理易混淆公式，理解公式推导过程，多做公式应用题',
            'concept_error': '建议：回归课本重新理解概念，多做概念辨析题',
            'logic_error': '建议：多画思维导图，理清解题思路，学习标准解题步骤',
            'careless_error': '建议：放慢速度仔细审题，圈画关键词，做完后检查',
            'boundary_error': '建议：特别关注边界条件，养成讨论特殊情况的习惯',
            'transformation_error': '建议：多做变式题，培养灵活思维，总结题型规律'
        }
        return suggestions.get(error_category, '建议：针对性练习，避免重复犯错')
    
    # ==================== 统计与分析 ====================
    
    def get_error_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取错误统计"""
        try:
            categories = self.classify_wrong_questions(user_id)
            
            total_errors = sum(cat.error_count for cat in categories.values())
            
            # 按错误数量排序
            sorted_categories = sorted(
                categories.items(),
                key=lambda x: x[1].error_count,
                reverse=True
            )
            
            return {
                'total_errors': total_errors,
                'category_count': sum(1 for cat in categories.values() if cat.error_count > 0),
                'distribution': [
                    {
                        'category_id': cat_id,
                        'category_name': cat.category_name,
                        'count': cat.error_count,
                        'percentage': round(cat.error_count / total_errors * 100, 1) if total_errors > 0 else 0,
                        'icon': cat.icon,
                        'color': cat.color
                    }
                    for cat_id, cat in sorted_categories if cat.error_count > 0
                ],
                'top_error_type': sorted_categories[0][1].category_name if sorted_categories and sorted_categories[0][1].error_count > 0 else None
            }
            
        except Exception as e:
            logger.error(f"获取错误统计失败: {e}")
            return {'total_errors': 0, 'distribution': []}


# ==================== 便捷函数 ====================

def get_wrong_questions_by_error_category(user_id: int) -> Dict[str, Any]:
    """便捷函数：按错误原因获取错题"""
    service = ErrorClassificationService()
    return service.get_wrong_questions_by_view(user_id, 'error_category')


def get_rehabilitation_pack(user_id: int, error_category: str) -> Dict[str, Any]:
    """便捷函数：获取专项复健题包"""
    service = ErrorClassificationService()
    return service.generate_rehabilitation_pack(user_id, error_category)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("错题本错误原因分类服务测试")
    print("=" * 60)
    
    service = ErrorClassificationService()
    
    # 测试分类
    print("\n错题分类测试：")
    categories = service.classify_wrong_questions(1)
    for cat_id, cat in categories.items():
        if cat.error_count > 0:
            print(f"  {cat.icon} {cat.category_name}: {cat.error_count}题")
    
    # 测试视图
    print("\n错因视图测试：")
    view = service.get_wrong_questions_by_view(1, 'error_category')
    print(f"  视图: {view['title']}")
    print(f"  分类数: {len(view['groups'])}")
    
    # 测试专项复健
    print("\n专项复健测试：")
    pack = service.generate_rehabilitation_pack(1, 'calculation_error')
    if pack['success']:
        print(f"  题包: {pack['pack_name']}")
        print(f"  题数: {pack['question_count']}")
    
    print("\n测试完成")
