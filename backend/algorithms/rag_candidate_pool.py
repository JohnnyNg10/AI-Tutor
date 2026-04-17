"""
RAG候选池构建模块
严格遵循PRD 3.3节硬指标实现

功能：
1. 召回层：Chroma向量检索，基于薄弱知识点标签
2. 过滤层：Redis Seen Pool去重 + 难度匹配 |S - θ| ≤ 1.0
3. 精排层：相似度加权 0.6×kp_relevance + 0.3×difficulty_match + 0.1×context_similarity

实现文件：backend/algorithms/rag_candidate_pool.py
"""

import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from rag.retriever import KnowledgeRetriever
from services.redis_service import RedisService
from utils.logger import logger
from utils.config import settings


@dataclass
class CandidateQuestion:
    """候选题目数据结构"""
    question_id: str
    content: str
    difficulty: float  # IRT难度参数 (-3 ~ +3)
    knowledge_points: List[str] = field(default_factory=list)
    kp_relevance: float = 0.0  # 知识点相关度 (0-1)
    difficulty_match: float = 0.0  # 难度匹配度 (0-1)
    context_similarity: float = 0.0  # 上下文相似度 (0-1)
    final_score: float = 0.0  # 最终加权分数
    metadata: Dict[str, Any] = field(default_factory=dict)


class RAGCandidatePoolBuilder:
    """
    RAG候选池构建器
    
    推题漏斗三层架构：
    1. 召回层：Chroma向量检索，基于薄弱知识点标签
    2. 过滤层：Redis Seen Pool去重 + 难度匹配
    3. 精排层：相似度加权排序
    """
    
    # 硬指标：难度匹配阈值
    DIFFICULTY_MATCH_THRESHOLD = 1.0  # |S - θ| ≤ 1.0
    
    # 硬指标：相似度加权系数
    WEIGHT_KP_RELEVANCE = 0.6      # 知识点相关度权重
    WEIGHT_DIFFICULTY_MATCH = 0.3  # 难度匹配度权重
    WEIGHT_CONTEXT_SIM = 0.1       # 上下文相似度权重
    
    # 硬指标：召回数量
    RECALL_TOP_K = 50  # 向量检索召回数量
    
    def __init__(self):
        """初始化RAG候选池构建器"""
        self.retriever = KnowledgeRetriever()
        self.redis_service = RedisService()
        logger.info("RAG候选池构建器初始化完成")
    
    # ==================== 召回层：向量检索 ====================
    
    def recall_by_weak_kps(
        self, 
        weak_kps: List[str], 
        top_k: int = RECALL_TOP_K
    ) -> List[Dict[str, Any]]:
        """
        基于薄弱知识点进行向量检索召回
        
        输入: weak_kps = ["等比数列", "递推公式"]
        输出: candidate_pool (最多top_k个候选)
        
        策略：
        1. 对每个薄弱知识点分别检索
        2. 合并结果并去重
        3. 按向量相似度排序
        """
        if not weak_kps:
            logger.warning("薄弱知识点为空，无法召回候选题目")
            return []
        
        all_candidates = []
        seen_ids = set()
        
        # 对每个薄弱知识点进行检索
        for kp in weak_kps:
            try:
                # 检索知识点相关的例题
                results = self.retriever.search_examples(kp, top_k=top_k // len(weak_kps) + 10)
                
                for result in results:
                    metadata = result.get('metadata', {})
                    question_id = metadata.get('question_id')
                    
                    if not question_id or question_id in seen_ids:
                        continue
                    
                    seen_ids.add(question_id)
                    
                    # 构建候选题目数据
                    candidate = {
                        'question_id': question_id,
                        'content': result.get('content', ''),
                        'difficulty': metadata.get('difficulty', 0),
                        'knowledge_points': metadata.get('knowledge_points', []),
                        'kp_relevance': 1.0 - result.get('distance', 0),  # 距离转相似度
                        'source': metadata.get('source', ''),
                        'metadata': metadata
                    }
                    all_candidates.append(candidate)
                
                logger.info(f"知识点 '{kp}' 召回 {len(results)} 条候选")
                
            except Exception as e:
                logger.error(f"检索知识点 '{kp}' 失败: {e}")
                continue
        
        # 按知识点相关度排序，取top_k
        all_candidates.sort(key=lambda x: x['kp_relevance'], reverse=True)
        final_candidates = all_candidates[:top_k]
        
        logger.info(f"召回层完成：共召回 {len(final_candidates)} 道候选题目")
        return final_candidates
    
    # ==================== 过滤层：去重 + 难度匹配 ====================
    
    def filter_by_seen_pool(
        self, 
        user_id: int, 
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Redis Seen Pool去重过滤
        
        Key: ai:tutor:seen-q:{uid}
        数据结构: Set
        """
        if not candidates:
            return []
        
        filtered = []
        removed_count = 0
        
        for candidate in candidates:
            question_id = candidate.get('question_id')
            
            # 检查是否已在Seen Pool中
            if self.redis_service.is_question_seen(user_id, question_id):
                removed_count += 1
                continue
            
            filtered.append(candidate)
        
        logger.info(f"去重过滤：移除 {removed_count} 道已做题目，剩余 {len(filtered)} 道")
        return filtered
    
    def filter_by_difficulty(
        self, 
        candidates: List[Dict[str, Any]], 
        theta: float
    ) -> List[Dict[str, Any]]:
        """
        难度匹配过滤
        
        硬指标：|S - θ| ≤ 1.0
        
        参数:
            candidates: 候选题目列表
            theta: 学生当前能力值 (-3 ~ +3)
        """
        if not candidates:
            return []
        
        filtered = []
        removed_count = 0
        
        for candidate in candidates:
            difficulty = candidate.get('difficulty', 0)
            
            # 计算难度差值
            diff_gap = abs(difficulty - theta)
            
            if diff_gap <= self.DIFFICULTY_MATCH_THRESHOLD:
                # 计算难度匹配度 (0-1，越接近越匹配)
                candidate['difficulty_match'] = 1.0 - (diff_gap / self.DIFFICULTY_MATCH_THRESHOLD)
                filtered.append(candidate)
            else:
                removed_count += 1
        
        logger.info(f"难度过滤：移除 {removed_count} 道难度不匹配题目，剩余 {len(filtered)} 道")
        return filtered
    
    def filter_by_knowledge_points(
        self, 
        candidates: List[Dict[str, Any]], 
        weak_kps: List[str]
    ) -> List[Dict[str, Any]]:
        """
        知识点关联过滤
        
        硬指标：knowledge_points ∩ weak_kps ≠ ∅
        """
        if not candidates or not weak_kps:
            return candidates
        
        weak_kps_set = set(weak_kps)
        filtered = []
        removed_count = 0
        
        for candidate in candidates:
            kp_list = candidate.get('knowledge_points', [])
            kp_set = set(kp_list) if isinstance(kp_list, list) else set()
            
            # 检查是否有交集
            if kp_set & weak_kps_set:
                filtered.append(candidate)
            else:
                removed_count += 1
        
        logger.info(f"知识点过滤：移除 {removed_count} 道无关题目，剩余 {len(filtered)} 道")
        return filtered
    
    # ==================== 精排层：相似度加权 ====================
    
    def calculate_context_similarity(
        self, 
        candidates: List[Dict[str, Any]], 
        recent_context: str
    ) -> List[Dict[str, Any]]:
        """
        计算上下文相似度
        
        使用向量相似度计算候选题目与最近学习上下文的相似度
        """
        if not candidates or not recent_context:
            # 无上下文时，所有候选的上下文相似度为0
            for candidate in candidates:
                candidate['context_similarity'] = 0.0
            return candidates
        
        try:
            # 获取上下文的向量表示
            context_vector = self.retriever.embedding_function([recent_context])[0]
            
            for candidate in candidates:
                content = candidate.get('content', '')
                if not content:
                    candidate['context_similarity'] = 0.0
                    continue
                
                # 获取题目内容的向量表示
                content_vector = self.retriever.embedding_function([content[:500]])[0]  # 限制长度
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(context_vector, content_vector)
                candidate['context_similarity'] = max(0.0, similarity)  # 确保非负
            
            logger.info(f"上下文相似度计算完成：{len(candidates)} 道题目")
            
        except Exception as e:
            logger.error(f"计算上下文相似度失败: {e}")
            # 失败时所有候选的上下文相似度为0
            for candidate in candidates:
                candidate['context_similarity'] = 0.0
        
        return candidates
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(np.dot(v1, v2) / (norm1 * norm2))
        except Exception as e:
            logger.error(f"余弦相似度计算失败: {e}")
            return 0.0
    
    def rank_by_weighted_score(
        self, 
        candidates: List[Dict[str, Any]]
    ) -> List[CandidateQuestion]:
        """
        相似度加权排序
        
        硬指标：final_score = 0.6×kp_relevance + 0.3×difficulty_match + 0.1×context_similarity
        """
        if not candidates:
            return []
        
        ranked_candidates = []
        
        for candidate in candidates:
            kp_relevance = candidate.get('kp_relevance', 0)
            difficulty_match = candidate.get('difficulty_match', 0)
            context_similarity = candidate.get('context_similarity', 0)
            
            # 计算最终加权分数
            final_score = (
                self.WEIGHT_KP_RELEVANCE * kp_relevance +
                self.WEIGHT_DIFFICULTY_MATCH * difficulty_match +
                self.WEIGHT_CONTEXT_SIM * context_similarity
            )
            
            # 构建CandidateQuestion对象
            cq = CandidateQuestion(
                question_id=candidate.get('question_id', ''),
                content=candidate.get('content', ''),
                difficulty=float(candidate.get('difficulty', 0)),
                knowledge_points=candidate.get('knowledge_points', []),
                kp_relevance=kp_relevance,
                difficulty_match=difficulty_match,
                context_similarity=context_similarity,
                final_score=final_score,
                metadata=candidate.get('metadata', {})
            )
            ranked_candidates.append(cq)
        
        # 按最终分数降序排序
        ranked_candidates.sort(key=lambda x: x.final_score, reverse=True)
        
        logger.info(f"精排层完成：{len(ranked_candidates)} 道题目按分数排序")
        return ranked_candidates
    
    # ==================== 完整流程：构建候选池 ====================
    
    def build_candidate_pool(
        self,
        user_id: int,
        weak_kps: List[str],
        theta: float,
        recent_context: Optional[str] = None,
        top_k: int = 20
    ) -> List[CandidateQuestion]:
        """
        构建RAG候选池（完整流程）
        
        推题漏斗：
        1. 召回层：基于薄弱知识点向量检索
        2. 过滤层：Seen Pool去重 + 难度匹配 + 知识点关联
        3. 精排层：相似度加权排序
        
        参数:
            user_id: 用户ID
            weak_kps: 薄弱知识点列表 ["等比数列", "递推公式"]
            theta: 学生当前能力值 (-3 ~ +3)
            recent_context: 最近学习上下文（可选）
            top_k: 返回候选数量
        
        返回:
            排序后的候选题目列表
        """
        logger.info(f"开始构建RAG候选池：用户={user_id}, 薄弱知识点={weak_kps}, θ={theta}")
        
        # Step 1: 召回层 - 向量检索
        candidates = self.recall_by_weak_kps(weak_kps, top_k=self.RECALL_TOP_K)
        if not candidates:
            logger.warning("召回层未找到任何候选题目")
            return []
        
        # Step 2: 过滤层 - 去重
        candidates = self.filter_by_seen_pool(user_id, candidates)
        if not candidates:
            logger.warning("过滤层（去重）后无剩余候选")
            return []
        
        # Step 3: 过滤层 - 难度匹配
        candidates = self.filter_by_difficulty(candidates, theta)
        if not candidates:
            logger.warning("过滤层（难度）后无剩余候选")
            return []
        
        # Step 4: 过滤层 - 知识点关联
        candidates = self.filter_by_knowledge_points(candidates, weak_kps)
        if not candidates:
            logger.warning("过滤层（知识点）后无剩余候选")
            return []
        
        # Step 5: 精排层 - 上下文相似度
        candidates = self.calculate_context_similarity(candidates, recent_context or '')
        
        # Step 6: 精排层 - 加权排序
        ranked_candidates = self.rank_by_weighted_score(candidates)
        
        # 返回top_k个候选
        final_result = ranked_candidates[:top_k]
        
        logger.info(f"RAG候选池构建完成：返回 {len(final_result)} 道题目")
        return final_result
    
    def get_candidate_details(self, candidate: CandidateQuestion) -> Dict[str, Any]:
        """获取候选题目的详细信息（用于调试和日志）"""
        return {
            'question_id': candidate.question_id,
            'difficulty': candidate.difficulty,
            'knowledge_points': candidate.knowledge_points,
            'kp_relevance': round(candidate.kp_relevance, 4),
            'difficulty_match': round(candidate.difficulty_match, 4),
            'context_similarity': round(candidate.context_similarity, 4),
            'final_score': round(candidate.final_score, 4),
            'content_preview': candidate.content[:200] + '...' if len(candidate.content) > 200 else candidate.content
        }


# ==================== 便捷函数 ====================

def build_rag_candidate_pool(
    user_id: int,
    weak_kps: List[str],
    theta: float,
    recent_context: Optional[str] = None,
    top_k: int = 20
) -> List[CandidateQuestion]:
    """
    便捷函数：构建RAG候选池
    
    使用示例:
        candidates = build_rag_candidate_pool(
            user_id=1,
            weak_kps=["等比数列", "递推公式"],
            theta=0.5,
            recent_context="最近在学习数列相关知识",
            top_k=5
        )
    """
    builder = RAGCandidatePoolBuilder()
    return builder.build_candidate_pool(
        user_id=user_id,
        weak_kps=weak_kps,
        theta=theta,
        recent_context=recent_context,
        top_k=top_k
    )


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("RAG候选池构建模块测试")
    print("=" * 60)
    
    # 测试构建候选池
    candidates = build_rag_candidate_pool(
        user_id=1,
        weak_kps=["等差数列", "等比数列"],
        theta=0.5,
        recent_context="等差数列求和公式的应用",
        top_k=5
    )
    
    print(f"\n找到 {len(candidates)} 道候选题目：")
    print("-" * 60)
    
    for i, candidate in enumerate(candidates, 1):
        details = candidate.get_candidate_details()
        print(f"\n[{i}] 题目ID: {details['question_id']}")
        print(f"    难度: {details['difficulty']}")
        print(f"    知识点: {details['knowledge_points']}")
        print(f"    知识点相关度: {details['kp_relevance']}")
        print(f"    难度匹配度: {details['difficulty_match']}")
        print(f"    上下文相似度: {details['context_similarity']}")
        print(f"    最终分数: {details['final_score']}")
        print(f"    内容预览: {details['content_preview'][:100]}...")
