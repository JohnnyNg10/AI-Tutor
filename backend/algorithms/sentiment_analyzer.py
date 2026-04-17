"""
情感分析器模块
检测用户表达，识别学习状态和情感

严格遵循PRD 2.1.1节硬指标实现

检测场景：
| 用户表达 | 检测关键词 | 系统画像更新 | Instructor响应策略 |
|---------|-----------|-------------|-------------------|
| 困难感知 | "好难"、"太难了" | 难度感知+1 | 分解步骤，增加中间推导 |
| 信心充足 | "能克服"、"简单" | 学习风格="进取型" | 减少提示，鼓励自主探索 |
| 步骤困惑 | "看不懂"、"跳太快" | 需要详细解释 | 展开被省略的中间步骤 |

实现文件：backend/algorithms/sentiment_analyzer.py
"""

import sys
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from utils.logger import logger


class SentimentType(Enum):
    """情感类型枚举"""
    DIFFICULT_PERCEIVED = "difficult_perceived"    # 困难感知
    CONFIDENT = "confident"                         # 信心充足
    CONFUSED = "confused"                           # 步骤困惑
    FRUSTRATED = "frustrated"                       # 挫败感
    NEUTRAL = "neutral"                             # 中性
    ENCOURAGED = "encouraged"                       # 受到鼓励


class LearningStyle(Enum):
    """学习风格枚举"""
    AGGRESSIVE = "aggressive"       # 进取型
    CAUTIOUS = "cautious"           # 谨慎型
    BALANCED = "balanced"           # 平衡型
    UNKNOWN = "unknown"             # 未知


@dataclass
class SentimentAnalysisResult:
    """情感分析结果"""
    sentiment: SentimentType
    confidence: float  # 置信度 (0-1)
    keywords: List[str] = field(default_factory=list)
    learning_style: Optional[LearningStyle] = None
    difficulty_perception: int = 0  # 难度感知计数
    needs_detailed_explanation: bool = False
    suggested_response_strategy: str = ""


class SentimentAnalyzer:
    """
    情感分析器
    
    检测用户消息中的情感和学习状态
    """
    
    # 关键词词典
    KEYWORDS = {
        SentimentType.DIFFICULT_PERCEIVED: [
            "好难", "太难了", "看不懂", "不会", "怎么做", "没思路",
            "卡住了", "想不出来", "太难了", "费劲", "吃力",
            "不理解", "不明白", "不清楚", "搞不定", "解决不了",
            "难死了", "太难了", "崩溃", "绝望", "放弃"
        ],
        SentimentType.CONFIDENT: [
            "能克服", "简单", "容易", "会了", "懂了", "明白",
            "没问题", "小意思", "轻松", "搞定", "拿下",
            "学会了", "掌握了", "理解了", "清楚了", "可以"
        ],
        SentimentType.CONFUSED: [
            "看不懂", "跳太快", "太快", "跟不上", "没看懂",
            "不明白", "不清楚", "困惑", "迷茫", "晕",
            "怎么来的", "为什么", "怎么推导", "中间步骤"
        ],
        SentimentType.FRUSTRATED: [
            "烦", "烦躁", "郁闷", "沮丧", "挫败", "失败",
            "总是错", "又错了", "还是错", "怎么都错",
            "不想做了", "不做了", "放弃", "算了", "没意思"
        ],
        SentimentType.ENCOURAGED: [
            "谢谢", "明白了", "懂了", "会了", "好的", "继续",
            "加油", "努力", "坚持", "可以", "行", "没问题"
        ]
    }
    
    # 学习风格检测关键词
    STYLE_KEYWORDS = {
        LearningStyle.AGGRESSIVE: [
            "简单", "容易", "挑战", "进阶", "更难", "有意思",
            "想试试", "敢不敢", "挑战一下"
        ],
        LearningStyle.CAUTIOUS: [
            "仔细", "稳妥", "基础", "巩固", "复习", "慢慢来",
            "一步一步", "详细", "清楚"
        ]
    }
    
    def __init__(self):
        """初始化情感分析器"""
        self._compile_patterns()
        logger.info("情感分析器初始化完成")
    
    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.patterns = {}
        for sentiment, keywords in self.KEYWORDS.items():
            # 为每个关键词创建匹配模式
            escaped_keywords = [re.escape(kw) for kw in keywords]
            pattern = re.compile('|'.join(escaped_keywords))
            self.patterns[sentiment] = pattern
    
    # ==================== 核心分析方法 ====================
    
    def analyze(self, message: str) -> SentimentAnalysisResult:
        """
        分析用户消息的情感
        
        参数:
            message: 用户消息内容
        
        返回:
            SentimentAnalysisResult对象
        """
        if not message or not message.strip():
            return SentimentAnalysisResult(
                sentiment=SentimentType.NEUTRAL,
                confidence=1.0,
                suggested_response_strategy="neutral"
            )
        
        message = message.strip()
        
        # 检测各种情感类型
        detected_sentiments = []
        
        for sentiment_type, pattern in self.patterns.items():
            matches = pattern.findall(message)
            if matches:
                detected_sentiments.append({
                    'type': sentiment_type,
                    'keywords': matches,
                    'count': len(matches)
                })
        
        # 如果没有检测到任何情感，返回中性
        if not detected_sentiments:
            return SentimentAnalysisResult(
                sentiment=SentimentType.NEUTRAL,
                confidence=1.0,
                suggested_response_strategy="neutral"
            )
        
        # 按匹配次数排序，选择最主要的情感
        detected_sentiments.sort(key=lambda x: x['count'], reverse=True)
        primary_sentiment = detected_sentiments[0]
        
        # 计算置信度
        confidence = min(0.5 + primary_sentiment['count'] * 0.1, 1.0)
        
        # 检测学习风格
        learning_style = self._detect_learning_style(message)
        
        # 确定响应策略
        strategy = self._determine_response_strategy(
            primary_sentiment['type'],
            learning_style
        )
        
        # 构建结果
        result = SentimentAnalysisResult(
            sentiment=primary_sentiment['type'],
            confidence=confidence,
            keywords=primary_sentiment['keywords'],
            learning_style=learning_style,
            difficulty_perception=self._calculate_difficulty_perception(message),
            needs_detailed_explanation=primary_sentiment['type'] == SentimentType.CONFUSED,
            suggested_response_strategy=strategy
        )
        
        logger.info(f"情感分析结果: {result.sentiment.value}, 置信度={result.confidence:.2f}")
        
        return result
    
    def analyze_batch(self, messages: List[str]) -> List[SentimentAnalysisResult]:
        """
        批量分析多条消息
        
        用于分析最近的多轮对话
        """
        return [self.analyze(msg) for msg in messages if msg]
    
    # ==================== 辅助检测方法 ====================
    
    def _detect_learning_style(self, message: str) -> Optional[LearningStyle]:
        """检测学习风格"""
        aggressive_count = sum(1 for kw in self.STYLE_KEYWORDS[LearningStyle.AGGRESSIVE] if kw in message)
        cautious_count = sum(1 for kw in self.STYLE_KEYWORDS[LearningStyle.CAUTIOUS] if kw in message)
        
        if aggressive_count > cautious_count:
            return LearningStyle.AGGRESSIVE
        elif cautious_count > aggressive_count:
            return LearningStyle.CAUTIOUS
        else:
            return None
    
    def _calculate_difficulty_perception(self, message: str) -> int:
        """计算难度感知计数"""
        difficult_keywords = self.KEYWORDS[SentimentType.DIFFICULT_PERCEIVED]
        count = sum(1 for kw in difficult_keywords if kw in message)
        return min(count, 5)  # 上限5
    
    def _determine_response_strategy(
        self,
        sentiment: SentimentType,
        learning_style: Optional[LearningStyle]
    ) -> str:
        """确定响应策略"""
        strategy_map = {
            SentimentType.DIFFICULT_PERCEIVED: "break_down_steps",
            SentimentType.CONFIDENT: "reduce_hints",
            SentimentType.CONFUSED: "detailed_explanation",
            SentimentType.FRUSTRATED: "emotional_support",
            SentimentType.ENCOURAGED: "positive_reinforcement",
            SentimentType.NEUTRAL: "neutral"
        }
        
        base_strategy = strategy_map.get(sentiment, "neutral")
        
        # 根据学习风格调整
        if learning_style == LearningStyle.AGGRESSIVE and sentiment == SentimentType.CONFIDENT:
            base_strategy = "challenge_mode"
        elif learning_style == LearningStyle.CAUTIOUS and sentiment == SentimentType.DIFFICULT_PERCEIVED:
            base_strategy = "step_by_step_guidance"
        
        return base_strategy
    
    # ==================== 特定场景检测 ====================
    
    def is_difficult_perceived(self, message: str) -> bool:
        """检测是否表达困难感知"""
        result = self.analyze(message)
        return result.sentiment == SentimentType.DIFFICULT_PERCEIVED
    
    def is_confident(self, message: str) -> bool:
        """检测是否表达信心充足"""
        result = self.analyze(message)
        return result.sentiment == SentimentType.CONFIDENT
    
    def is_confused(self, message: str) -> bool:
        """检测是否表达步骤困惑"""
        result = self.analyze(message)
        return result.sentiment == SentimentType.CONFUSED
    
    def is_frustrated(self, message: str) -> bool:
        """检测是否表达挫败感"""
        result = self.analyze(message)
        return result.sentiment == SentimentType.FRUSTRATED
    
    def detect_consecutive_sentiment(
        self,
        messages: List[str],
        sentiment_type: SentimentType,
        threshold: int = 2
    ) -> bool:
        """
        检测连续多次表达某种情感
        
        用于检测连续挫败、连续困惑等场景
        """
        if len(messages) < threshold:
            return False
        
        # 分析最近的消息
        recent_messages = messages[-threshold:]
        results = self.analyze_batch(recent_messages)
        
        # 检查是否都匹配目标情感
        return all(r.sentiment == sentiment_type for r in results)
    
    # ==================== 画像更新建议 ====================
    
    def get_profile_update_suggestions(
        self,
        analysis_result: SentimentAnalysisResult
    ) -> Dict[str, Any]:
        """
        获取用户画像更新建议
        
        根据情感分析结果，建议更新哪些画像字段
        """
        suggestions = {}
        
        if analysis_result.sentiment == SentimentType.DIFFICULT_PERCEIVED:
            suggestions['difficulty_perception'] = analysis_result.difficulty_perception
        
        if analysis_result.learning_style:
            suggestions['learning_style'] = analysis_result.learning_style.value
        
        if analysis_result.needs_detailed_explanation:
            suggestions['needs_detailed_explanation'] = True
        
        if analysis_result.sentiment == SentimentType.FRUSTRATED:
            suggestions['frustration_count'] = 1  # 需要累加
        
        return suggestions
    
    def generate_instructor_strategy(
        self,
        analysis_result: SentimentAnalysisResult
    ) -> Dict[str, Any]:
        """
        生成Instructor响应策略
        
        根据情感分析结果，生成具体的教学策略
        """
        strategy = {
            'hint_level_adjustment': 0,
            'explanation_detail_level': 'normal',
            'encouragement_needed': False,
            'step_by_step': False,
            'skip_allowed': True
        }
        
        sentiment = analysis_result.sentiment
        
        if sentiment == SentimentType.DIFFICULT_PERCEIVED:
            strategy['hint_level_adjustment'] = 1  # 提升提示等级
            strategy['explanation_detail_level'] = 'detailed'
            strategy['step_by_step'] = True
            strategy['encouragement_needed'] = True
        
        elif sentiment == SentimentType.CONFIDENT:
            strategy['hint_level_adjustment'] = -1  # 降低提示等级
            strategy['explanation_detail_level'] = 'minimal'
            strategy['skip_allowed'] = False  # 鼓励独立完成
        
        elif sentiment == SentimentType.CONFUSED:
            strategy['explanation_detail_level'] = 'very_detailed'
            strategy['step_by_step'] = True
            strategy['hint_level_adjustment'] = 1
        
        elif sentiment == SentimentType.FRUSTRATED:
            strategy['encouragement_needed'] = True
            strategy['explanation_detail_level'] = 'detailed'
            strategy['step_by_step'] = True
        
        return strategy


# ==================== 便捷函数 ====================

def analyze_sentiment(message: str) -> Dict[str, Any]:
    """
    便捷函数：分析单条消息的情感
    
    使用示例:
        result = analyze_sentiment("这道题好难，我完全没思路")
        print(result['sentiment'])  # "difficult_perceived"
    """
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze(message)
    
    return {
        'sentiment': result.sentiment.value,
        'confidence': result.confidence,
        'keywords': result.keywords,
        'learning_style': result.learning_style.value if result.learning_style else None,
        'difficulty_perception': result.difficulty_perception,
        'needs_detailed_explanation': result.needs_detailed_explanation,
        'suggested_response_strategy': result.suggested_response_strategy
    }


def detect_learning_difficulty(messages: List[str]) -> Dict[str, Any]:
    """
    便捷函数：检测学习困难程度
    
    分析最近的多条消息，判断学生是否遇到困难
    """
    analyzer = SentimentAnalyzer()
    results = analyzer.analyze_batch(messages)
    
    # 统计各种情感的出现次数
    sentiment_counts = {}
    for r in results:
        sentiment_counts[r.sentiment.value] = sentiment_counts.get(r.sentiment.value, 0) + 1
    
    # 检测连续挫败
    consecutive_frustrated = analyzer.detect_consecutive_sentiment(
        messages, SentimentType.FRUSTRATED, threshold=3
    )
    
    # 检测连续困惑
    consecutive_confused = analyzer.detect_consecutive_sentiment(
        messages, SentimentType.CONFUSED, threshold=2
    )
    
    return {
        'sentiment_distribution': sentiment_counts,
        'consecutive_frustrated': consecutive_frustrated,
        'consecutive_confused': consecutive_confused,
        'needs_intervention': consecutive_frustrated or consecutive_confused
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("情感分析器测试")
    print("=" * 60)
    
    analyzer = SentimentAnalyzer()
    
    test_messages = [
        "这道题好难，我完全没思路",
        "太简单了，轻松搞定",
        "看不懂，跳得太快了",
        "又错了，烦死了",
        "谢谢，我明白了"
    ]
    
    print("\n单条消息分析：")
    print("-" * 60)
    for msg in test_messages:
        result = analyzer.analyze(msg)
        print(f"\n消息: {msg}")
        print(f"  情感: {result.sentiment.value}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  关键词: {result.keywords}")
        print(f"  策略: {result.suggested_response_strategy}")
    
    print("\n" + "=" * 60)
    print("连续消息分析：")
    print("-" * 60)
    
    difficult_messages = [
        "这道题好难",
        "还是不会做",
        "完全没思路"
    ]
    
    result = detect_learning_difficulty(difficult_messages)
    print(f"消息序列: {difficult_messages}")
    print(f"情感分布: {result['sentiment_distribution']}")
    print(f"需要干预: {result['needs_intervention']}")
