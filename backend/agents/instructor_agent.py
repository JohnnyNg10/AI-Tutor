"""
Instructor Agent 核心模块
整合提示生成、情感分析和教学策略

严格遵循PRD 2.1节和2.2节硬指标实现

功能：
1. 分等级提示系统 (L0-L4)
2. 引导式教学 (情感感知响应)
3. 与Hint Button状态机联动
4. 与Advisor指令集联动

实现文件：backend/agents/instructor_agent.py
"""

import sys
import os
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from algorithms.hint_generator import (
    HintGenerator, 
    HintLevel, 
    HintContent
)
from algorithms.sentiment_analyzer import (
    SentimentAnalyzer,
    SentimentAnalysisResult,
    SentimentType,
    LearningStyle
)
from algorithms.hint_button_state_machine import (
    HintButtonStateMachine,
    HintButtonState
)
from utils.logger import logger


class TeachingMode(Enum):
    """教学模式枚举"""
    SCAFFOLD = "scaffold"       # 脚手架模式
    CHALLENGE = "challenge"     # 挑战模式
    ENCOURAGE = "encourage"     # 鼓励模式
    STANDARD = "standard"       # 标准模式


@dataclass
class InstructorResponse:
    """Instructor响应数据结构"""
    content: str
    hint_level: Optional[int]
    actual_weight: float
    teaching_mode: TeachingMode
    sentiment_adjusted: bool
    follow_up_question: Optional[str]
    latex_formulas: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class InstructorAgent:
    """
    Instructor Agent 核心
    
    职责：
    1. 根据Hint Button状态生成对应等级提示
    2. 根据情感分析调整教学策略
    3. 根据Advisor指令调整讲解深度
    4. 维护对话上下文
    """
    
    def __init__(self):
        """初始化Instructor Agent"""
        self.hint_generator = HintGenerator()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.button_state_machine = HintButtonStateMachine()
        
        # 对话上下文
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_hint_level: int = 0
        
        logger.info("Instructor Agent初始化完成")
    
    # ==================== 核心响应方法 ====================
    
    def respond_to_hint_button_click(
        self,
        user_id: int,
        question_id: str,
        question_content: str,
        knowledge_points: List[str],
        current_state: Optional[str] = None
    ) -> InstructorResponse:
        """
        响应Hint Button点击
        
        流程：
        1. 获取当前按钮状态
        2. 根据状态确定hint_level
        3. 生成对应等级提示
        4. 返回响应
        """
        # 恢复或创建状态机
        if current_state:
            self.button_state_machine.restore_state(user_id, question_id, current_state)
        
        # 获取当前配置
        config = self.button_state_machine.get_current_config()
        hint_level = config.hint_level if config.hint_level else 0
        
        logger.info(f"Hint Button点击：用户={user_id}, 题目={question_id}, 等级=L{hint_level}")
        
        # 生成提示
        hint = self.hint_generator.generate_hint(
            level=HintLevel(hint_level),
            question_content=question_content,
            knowledge_points=knowledge_points
        )
        
        # 构建响应
        response = InstructorResponse(
            content=hint.content,
            hint_level=hint_level,
            actual_weight=hint.actual_weight,
            teaching_mode=TeachingMode.STANDARD,
            sentiment_adjusted=False,
            follow_up_question=hint.follow_up_question,
            latex_formulas=hint.latex_formulas,
            metadata={
                'button_text': config.text,
                'next_button_text': self._get_next_button_text(user_id, question_id)
            }
        )
        
        # 记录到对话历史
        self._record_interaction(user_id, question_id, 'hint_button', hint_level, hint.content)
        
        return response
    
    def respond_to_user_message(
        self,
        user_id: int,
        question_id: str,
        question_content: str,
        knowledge_points: List[str],
        user_message: str,
        advisor_instruction: Optional[Dict[str, Any]] = None
    ) -> InstructorResponse:
        """
        响应用户消息
        
        流程：
        1. 情感分析
        2. 根据Advisor指令调整策略
        3. 生成适当响应
        """
        logger.info(f"用户消息：{user_message[:50]}...")
        
        # 情感分析
        sentiment_result = self.sentiment_analyzer.analyze(user_message)
        
        # 确定教学模式
        teaching_mode = self._determine_teaching_mode(
            sentiment_result, 
            advisor_instruction
        )
        
        # 根据情感调整hint_level
        adjusted_hint_level = self._adjust_hint_level_by_sentiment(
            self.current_hint_level,
            sentiment_result
        )
        
        # 生成响应
        hint = self.hint_generator.generate_hint(
            level=HintLevel(adjusted_hint_level),
            question_content=question_content,
            knowledge_points=knowledge_points
        )
        
        # 根据教学模式调整内容
        adjusted_content = self._apply_teaching_mode(
            hint.content,
            teaching_mode,
            sentiment_result
        )
        
        response = InstructorResponse(
            content=adjusted_content,
            hint_level=adjusted_hint_level,
            actual_weight=hint.actual_weight,
            teaching_mode=teaching_mode,
            sentiment_adjusted=True,
            follow_up_question=hint.follow_up_question,
            latex_formulas=hint.latex_formulas,
            metadata={
                'sentiment': sentiment_result.sentiment.value,
                'confidence': sentiment_result.confidence,
                'strategy': sentiment_result.suggested_response_strategy
            }
        )
        
        # 记录到对话历史
        self._record_interaction(user_id, question_id, 'user_message', adjusted_hint_level, adjusted_content)
        
        return response
    
    def respond_to_advisor_instruction(
        self,
        user_id: int,
        question_id: str,
        question_content: str,
        knowledge_points: List[str],
        instruction: Dict[str, Any]
    ) -> InstructorResponse:
        """
        响应Advisor指令
        
        Advisor通过指令控制Instructor的教学策略
        """
        instruction_code = instruction.get('instruction', 'MODE_SCAFFOLD')
        control_params = instruction.get('control_params', {})
        
        logger.info(f"Advisor指令：{instruction_code}")
        
        # 根据指令确定教学模式
        mode_map = {
            'MODE_SCAFFOLD': TeachingMode.SCAFFOLD,
            'MODE_CHALLENGE': TeachingMode.CHALLENGE,
            'MODE_ENCOURAGE': TeachingMode.ENCOURAGE
        }
        teaching_mode = mode_map.get(instruction_code, TeachingMode.STANDARD)
        
        # 根据控制参数确定hint_level
        hint_level = control_params.get('hint_level', 'adaptive')
        if hint_level == 'detailed':
            level = HintLevel.L3_STEP
        elif hint_level == 'minimal':
            level = HintLevel.L1_DIRECTION
        elif hint_level == 'adaptive':
            level = HintLevel.L2_FORMULA
        else:
            level = HintLevel(self.current_hint_level)
        
        # 生成提示
        hint = self.hint_generator.generate_hint(
            level=level,
            question_content=question_content,
            knowledge_points=knowledge_points
        )
        
        # 应用教学模式
        adjusted_content = self._apply_teaching_mode(
            hint.content,
            teaching_mode,
            None
        )
        
        # 添加instructor_prompt（如果Advisor提供了）
        instructor_prompt = instruction.get('instructor_prompt', '')
        if instructor_prompt:
            adjusted_content = f"{instructor_prompt}\n\n{adjusted_content}"
        
        response = InstructorResponse(
            content=adjusted_content,
            hint_level=level.value,
            actual_weight=hint.actual_weight,
            teaching_mode=teaching_mode,
            sentiment_adjusted=False,
            follow_up_question=hint.follow_up_question,
            latex_formulas=hint.latex_formulas,
            metadata={
                'advisor_instruction': instruction_code,
                'control_params': control_params
            }
        )
        
        return response
    
    # ==================== 辅助方法 ====================
    
    def _determine_teaching_mode(
        self,
        sentiment_result: SentimentAnalysisResult,
        advisor_instruction: Optional[Dict[str, Any]]
    ) -> TeachingMode:
        """确定教学模式"""
        # 优先使用Advisor指令
        if advisor_instruction:
            instruction_code = advisor_instruction.get('instruction', '')
            if instruction_code == 'MODE_SCAFFOLD':
                return TeachingMode.SCAFFOLD
            elif instruction_code == 'MODE_CHALLENGE':
                return TeachingMode.CHALLENGE
            elif instruction_code == 'MODE_ENCOURAGE':
                return TeachingMode.ENCOURAGE
        
        # 根据情感确定模式
        sentiment = sentiment_result.sentiment
        if sentiment == SentimentType.FRUSTRATED:
            return TeachingMode.ENCOURAGE
        elif sentiment == SentimentType.CONFIDENT:
            return TeachingMode.CHALLENGE
        elif sentiment == SentimentType.DIFFICULT_PERCEIVED:
            return TeachingMode.SCAFFOLD
        
        return TeachingMode.STANDARD
    
    def _adjust_hint_level_by_sentiment(
        self,
        current_level: int,
        sentiment_result: SentimentAnalysisResult
    ) -> int:
        """根据情感调整hint_level"""
        adjustment = 0
        
        sentiment = sentiment_result.sentiment
        if sentiment == SentimentType.DIFFICULT_PERCEIVED:
            adjustment = 1
        elif sentiment == SentimentType.CONFUSED:
            adjustment = 1
        elif sentiment == SentimentType.CONFIDENT:
            adjustment = -1
        elif sentiment == SentimentType.FRUSTRATED:
            adjustment = 1
        
        new_level = current_level + adjustment
        return max(0, min(4, new_level))  # 限制在0-4之间
    
    def _apply_teaching_mode(
        self,
        content: str,
        mode: TeachingMode,
        sentiment_result: Optional[SentimentAnalysisResult]
    ) -> str:
        """应用教学模式调整内容"""
        if mode == TeachingMode.SCAFFOLD:
            # 脚手架模式：增加引导，分步讲解
            prefix = "🎯 **分步引导**\n\n"
            suffix = "\n\n💡 **小提示**：如果这步理解了，试着继续下一步；如果还有疑问，随时告诉我！"
            return prefix + content + suffix
        
        elif mode == TeachingMode.CHALLENGE:
            # 挑战模式：简洁，鼓励自主
            prefix = "🏆 **挑战模式**\n\n"
            suffix = "\n\n💪 **加油**：相信你能独立完成，有问题再问我！"
            return prefix + content + suffix
        
        elif mode == TeachingMode.ENCOURAGE:
            # 鼓励模式：情感支持
            prefix = "🤗 **别担心**\n\n"
            if sentiment_result and sentiment_result.sentiment == SentimentType.FRUSTRATED:
                prefix += "学习过程中遇到困难很正常，错误是学习的机会！\n\n"
            suffix = "\n\n🌟 **你做得很好**：每一步努力都在进步，继续加油！"
            return prefix + content + suffix
        
        return content
    
    def _get_next_button_text(self, user_id: int, question_id: str) -> str:
        """获取下一阶段的按钮文案"""
        # 模拟点击，获取下一状态
        current_state = self.button_state_machine.state
        
        # 状态映射到下一状态
        next_state_map = {
            HintButtonState.INITIAL: HintButtonState.LEVEL_1,
            HintButtonState.LEVEL_1: HintButtonState.LEVEL_2,
            HintButtonState.LEVEL_2: HintButtonState.LEVEL_3,
            HintButtonState.LEVEL_3: HintButtonState.LEVEL_4,
            HintButtonState.LEVEL_4: HintButtonState.HIDDEN,
            HintButtonState.HIDDEN: HintButtonState.HIDDEN
        }
        
        next_state = next_state_map.get(current_state, HintButtonState.HIDDEN)
        
        # 获取下一状态的配置
        from algorithms.hint_button_state_machine import ButtonConfig
        state_config = self.button_state_machine.STATE_CONFIG.get(next_state)
        
        if state_config and state_config.is_visible:
            return state_config.text
        return ""
    
    def _record_interaction(
        self,
        user_id: int,
        question_id: str,
        interaction_type: str,
        hint_level: int,
        content: str
    ):
        """记录交互到对话历史"""
        self.conversation_history.append({
            'user_id': user_id,
            'question_id': question_id,
            'type': interaction_type,
            'hint_level': hint_level,
            'content': content[:100]  # 只记录前100字符
        })
        
        # 更新当前hint_level
        self.current_hint_level = hint_level
    
    # ==================== 上下文管理 ====================
    
    def reset_context(self):
        """重置对话上下文"""
        self.conversation_history = []
        self.current_hint_level = 0
        self.button_state_machine = HintButtonStateMachine()
        logger.info("Instructor Agent上下文已重置")
    
    def get_conversation_summary(self, user_id: int, question_id: str) -> Dict[str, Any]:
        """获取对话摘要"""
        relevant_history = [
            h for h in self.conversation_history
            if h['user_id'] == user_id and h['question_id'] == question_id
        ]
        
        if not relevant_history:
            return {'hint_level_progression': [], 'total_interactions': 0}
        
        hint_levels = [h['hint_level'] for h in relevant_history]
        
        return {
            'hint_level_progression': hint_levels,
            'total_interactions': len(relevant_history),
            'max_hint_level': max(hint_levels),
            'interaction_types': list(set(h['type'] for h in relevant_history))
        }


# ==================== 便捷函数 ====================

def get_instructor_response(
    user_id: int,
    question_id: str,
    question_content: str,
    knowledge_points: List[str],
    user_message: Optional[str] = None,
    hint_button_clicked: bool = False,
    advisor_instruction: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    便捷函数：获取Instructor响应
    
    使用示例:
        response = get_instructor_response(
            user_id=1,
            question_id="q001",
            question_content="已知等差数列...",
            knowledge_points=["等差数列"],
            hint_button_clicked=True
        )
    """
    instructor = InstructorAgent()
    
    if hint_button_clicked:
        result = instructor.respond_to_hint_button_click(
            user_id=user_id,
            question_id=question_id,
            question_content=question_content,
            knowledge_points=knowledge_points
        )
    elif advisor_instruction:
        result = instructor.respond_to_advisor_instruction(
            user_id=user_id,
            question_id=question_id,
            question_content=question_content,
            knowledge_points=knowledge_points,
            instruction=advisor_instruction
        )
    else:
        result = instructor.respond_to_user_message(
            user_id=user_id,
            question_id=question_id,
            question_content=question_content,
            knowledge_points=knowledge_points,
            user_message=user_message or ""
        )
    
    return {
        'content': result.content,
        'hint_level': result.hint_level,
        'actual_weight': result.actual_weight,
        'teaching_mode': result.teaching_mode.value,
        'sentiment_adjusted': result.sentiment_adjusted,
        'follow_up_question': result.follow_up_question,
        'latex_formulas': result.latex_formulas,
        'metadata': result.metadata
    }


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Instructor Agent测试")
    print("=" * 60)
    
    instructor = InstructorAgent()
    
    question = "已知等差数列{a_n}中，a_3 = 5，a_7 = 13，求通项公式"
    kps = ["等差数列", "通项公式"]
    
    # 测试Hint Button响应
    print("\n【测试1】Hint Button点击")
    print("-" * 60)
    
    for i in range(5):
        response = instructor.respond_to_hint_button_click(
            user_id=1,
            question_id="q001",
            question_content=question,
            knowledge_points=kps
        )
        
        print(f"\n点击 #{i+1}:")
        print(f"  Hint Level: L{response.hint_level}")
        print(f"  Actual权重: {response.actual_weight}")
        print(f"  内容预览: {response.content[:80]}...")
        
        # 模拟点击，进入下一状态
        instructor.button_state_machine.handle_click(1, "q001")
    
    # 测试用户消息响应
    print("\n" + "=" * 60)
    print("【测试2】用户消息响应")
    print("-" * 60)
    
    test_messages = [
        "这道题好难，我完全没思路",
        "太简单了，轻松搞定",
        "看不懂，跳得太快了"
    ]
    
    instructor.reset_context()
    
    for msg in test_messages:
        response = instructor.respond_to_user_message(
            user_id=1,
            question_id="q002",
            question_content=question,
            knowledge_points=kps,
            user_message=msg
        )
        
        print(f"\n用户: {msg}")
        print(f"  教学模式: {response.teaching_mode.value}")
        print(f"  Hint Level: L{response.hint_level}")
        print(f"  情感调整: {response.sentiment_adjusted}")
        print(f"  内容预览: {response.content[:80]}...")
    
    # 测试Advisor指令响应
    print("\n" + "=" * 60)
    print("【测试3】Advisor指令响应")
    print("-" * 60)
    
    advisor_instructions = [
        {
            'instruction': 'MODE_SCAFFOLD',
            'control_params': {'hint_level': 'detailed', 'step_by_step': True},
            'instructor_prompt': '请使用苏格拉底式提问引导学生'
        },
        {
            'instruction': 'MODE_CHALLENGE',
            'control_params': {'hint_level': 'minimal'}
        },
        {
            'instruction': 'MODE_ENCOURAGE',
            'control_params': {'hint_level': 'adaptive'}
        }
    ]
    
    for instruction in advisor_instructions:
        response = instructor.respond_to_advisor_instruction(
            user_id=1,
            question_id="q003",
            question_content=question,
            knowledge_points=kps,
            instruction=instruction
        )
        
        print(f"\n指令: {instruction['instruction']}")
        print(f"  教学模式: {response.teaching_mode.value}")
        print(f"  Hint Level: L{response.hint_level}")
        print(f"  内容预览: {response.content[:80]}...")
