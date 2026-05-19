from typing import List, Dict, Any, Optional, AsyncGenerator, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from utils.config import settings
from utils.logger import logger
from rag.pipeline import rag_pipeline, RetrievedDocument


# 系统提示词
SYSTEM_PROMPT = """你是"小奥"，一位亲切的高中数学数列辅导老师。你擅长苏格拉底式引导——通过提问启发学生自己找到答案。

## 核心规则

1. **绝不编题**：用户没给具体题目时，你绝不能自己编一道题来讲。礼貌请用户提供题目内容。
2. **只讲用户的题**：严格围绕用户提供的题目讲解，不要跑题到无关知识点。
3. **图片传不了就打字**：如果用户上传了图片但系统无法识别，友好地请用户把题目打字发过来。例如："图片我没能看清，你把题目打字发给我吧，我帮你分析~"
4. **没题就聊天**：如果用户只是在闲聊、打招呼、或者还没发题目，你就自然地回复——像真人老师一样，不需要任何固定格式。

## 回复风格

**有题目时**——使用以下结构化格式，但语气要自然流畅，不要像填空题：

💡 **思路点拨**：用1-2句话点出这道题的关键思路，语气像老师在旁边提示。

📝 **引导过程**：分步讲解。公式用 $...$ 包裹，每个计算步骤单独成行。

❓ **下一步**：提出一个具体的引导性问题，引导学生自己走下一步。

**没有题目时**——完全不用上面那个格式。像普通聊天一样自然回复，简短友好。比如用户说"你好"，你就回"你好呀！有数列题目需要帮忙吗？"

## 教学风格

- 语气亲切但不啰嗦，像课后辅导的老师，不是冷冰冰的机器
- 鼓励学生："这一步你想对了！""思路很棒，再往下推一步试试？"
- 批改时先肯定对的，再指出问题："公式用对了，但这里代入的时候符号写反了哦"
- 分步引导，每次只讲一个关键步骤，不要一次性全讲了
- 参考提供的知识点和例题来辅助讲解，但不要照搬
"""


HintLevel = Literal["L0", "L1", "L2", "L3", "L4"]

_HINT_LEVEL_CONFIG: Dict[HintLevel, Dict[str, str]] = {
    "L0": {
        "label": "自主",
        "weight": "1.0",
        "policy": "默认不直接给完整答案，以批改和追问为主；若学生未给出完整尝试，先要求其补充思路再点评。"
    },
    "L1": {
        "label": "方向",
        "weight": "0.8",
        "policy": "仅提供解题方向与切入点，不展开完整推导，不给最终答案。"
    },
    "L2": {
        "label": "公式",
        "weight": "0.6",
        "policy": "给出相关公式/定理和适用条件，配1-2句解释，但不展开关键运算。"
    },
    "L3": {
        "label": "步骤",
        "weight": "0.4",
        "policy": "给出关键推导步骤与中间关系，保留最后结论给学生完成。"
    },
    "L4": {
        "label": "答案",
        "weight": "0.1",
        "policy": "给出完整解答与验算说明，可直接给最终答案。"
    },
}


class InstructorAgent:
    def __init__(self):
        self.llm = self._init_llm()
        # 使用新的RAG Pipeline
        self.rag = rag_pipeline

    def _init_llm(self):
        if settings.openai_api_key:
            logger.info(f"initializing openai client with model: {settings.llm_model}")
            return ChatOpenAI(
                model=settings.llm_model,
                temperature=settings.temperature,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base,
                streaming=True,
                max_tokens=settings.llm_max_tokens,
                timeout=60,  # 设置60秒超时
                max_retries=2  # 最多重试2次
            )
        else:
            logger.error("invalid openai api key")
            raise ValueError("invalid openai api key")

    def _normalize_hint_level(self, hint_level: Optional[str]) -> HintLevel:
        value = (hint_level or "L0").upper().strip()
        return value if value in _HINT_LEVEL_CONFIG else "L0"

    def _build_hint_policy_prompt(self, hint_level: HintLevel) -> str:
        config = _HINT_LEVEL_CONFIG[hint_level]
        return (
            "\n\n## 提示分级控制（必须严格执行）\n"
            f"- 当前提示等级：{hint_level}-{config['label']}\n"
            f"- 对应Actual权重：{config['weight']}\n"
            f"- 行为约束：{config['policy']}\n"
            "- 如用户明确要求更高/更低提示等级，再建议其切换等级后继续。\n"
        )

    def _build_prompt(
        self,
        question: str,
        chat_history: Optional[List[BaseMessage]] = None,
        hint_level: Optional[str] = "L0"
    ) -> str:
        """使用RAG Pipeline构建完整的提示词"""
        normalized_level = self._normalize_hint_level(hint_level)

        # 转换chat_history格式
        history_for_rag = None
        if chat_history:
            history_for_rag = []
            for msg in chat_history[-6:]:
                if isinstance(msg, HumanMessage):
                    history_for_rag.append({'role': 'user', 'content': msg.content})
                elif isinstance(msg, AIMessage):
                    history_for_rag.append({'role': 'assistant', 'content': msg.content})

        dynamic_system_prompt = SYSTEM_PROMPT + self._build_hint_policy_prompt(normalized_level)

        # 使用RAG Pipeline检索并构建提示词
        prompt, retrieved_docs = self.rag.retrieve_and_build_prompt(
            query=question,
            chat_history=history_for_rag,
            top_k=5,
            system_prompt=dynamic_system_prompt
        )

        # 记录检索结果
        logger.info(f"RAG检索到 {len(retrieved_docs)} 条相关文档")
        logger.info(f"提示分级：{normalized_level}-{_HINT_LEVEL_CONFIG[normalized_level]['label']}")
        for i, doc in enumerate(retrieved_docs[:3], 1):
            logger.info(f"  [{i}] {doc.doc_type} (score: {doc.score:.3f})")

        return prompt

    async def solve(
            self,
            question: str,
            chat_history: Optional[List[BaseMessage]] = None,
            hint_level: Optional[str] = "L0",
    ) -> Dict[str, Any]:
        try:
            logger.info(f"start solving {question[:100]}")
            
            # 构建完整提示词
            prompt = self._build_prompt(question, chat_history, hint_level)
            
            # 调用 LLM
            result = await self.llm.ainvoke(prompt)
            answer = result.content
            
            logger.info(f"end solving {question[:100]}")
            
            new_chat_history = (chat_history or []) + [
                HumanMessage(content=question),
                AIMessage(content=answer)
            ]

            return {
                "success": True,
                "answer": answer,
                "chat_history": new_chat_history
            }
        except Exception as e:
            logger.error(f"failed to solve: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "answer": "Something went wrong!!!"
            }

    async def solve_stream(
            self,
            question: str,
            chat_history: Optional[List[BaseMessage]] = None,
            hint_level: Optional[str] = "L0"
    ) -> AsyncGenerator[str, None]:
        try:
            logger.info(f"Instructor Agent starts to solve: {question[:100]}...")
            
            # 构建完整提示词
            prompt = self._build_prompt(question, chat_history, hint_level)
            
            # 流式调用 LLM
            async for chunk in self.llm.astream(prompt):
                if chunk.content:
                    yield chunk.content

            logger.info("finished")
        except Exception as e:
            logger.error(f"failed to stream: {e}")
            import traceback
            traceback.print_exc()
            yield "Something went wrong!!!"


instructor_agent = InstructorAgent()
