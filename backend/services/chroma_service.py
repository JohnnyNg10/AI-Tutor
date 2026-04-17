"""
Chroma向量数据库服务
封装向量检索、元数据过滤和相似度计算

严格遵循PRD 3.3节硬指标实现

实现文件：backend/services/chroma_service.py
"""

import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

# 添加backend到路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import chromadb
from rag.retriever import KnowledgeRetriever, DashScopeEmbeddingFunction, SiliconFlowEmbeddingFunction
from utils.config import settings
from utils.logger import logger


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    question_id: str
    content: str
    difficulty: float
    knowledge_points: List[str]
    similarity: float  # 相似度分数 (0-1)
    metadata: Dict[str, Any]


class ChromaService:
    """
    Chroma向量数据库服务
    
    提供以下功能：
    1. 基于知识点的向量检索
    2. 元数据过滤（难度、知识点等）
    3. 相似度计算
    4. 批量查询支持
    """
    
    def __init__(self):
        """初始化Chroma服务"""
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        
        # 初始化embedding函数
        if settings.dashscope_api_key and settings.dashscope_embedding_model:
            logger.info(f"使用 DashScope Embedding: {settings.dashscope_embedding_model}")
            self.embedding_function = DashScopeEmbeddingFunction()
        elif settings.openai_api_key and settings.embedding_model:
            logger.info(f"使用硅基流动 Embedding: {settings.embedding_model}")
            self.embedding_function = SiliconFlowEmbeddingFunction()
        else:
            raise ValueError("未配置有效的Embedding服务")
        
        # 获取集合
        self.knowledge_collection = self.client.get_or_create_collection(
            name="knowledge_points"
        )
        self.examples_collection = self.client.get_or_create_collection(
            name="example_questions"
        )
        
        logger.info("Chroma服务初始化完成")
    
    # ==================== 向量检索 ====================
    
    def search_by_knowledge_point(
        self,
        knowledge_point: str,
        top_k: int = 10,
        difficulty_range: Optional[Tuple[float, float]] = None
    ) -> List[VectorSearchResult]:
        """
        基于知识点进行向量检索
        
        参数:
            knowledge_point: 知识点名称（如"等比数列"）
            top_k: 返回结果数量
            difficulty_range: 难度范围过滤 (min, max)
        
        返回:
            向量搜索结果列表
        """
        try:
            # 获取查询向量
            query_vector = self.embedding_function([knowledge_point])[0]
            
            # 构建过滤条件
            where_filter = None
            if difficulty_range:
                where_filter = {
                    "$and": [
                        {"difficulty": {"$gte": difficulty_range[0]}},
                        {"difficulty": {"$lte": difficulty_range[1]}}
                    ]
                }
            
            # 执行向量检索
            results = self.examples_collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where_filter
            )
            
            # 解析结果
            return self._parse_search_results(results)
            
        except Exception as e:
            logger.error(f"知识点检索失败 '{knowledge_point}': {e}")
            return []
    
    def search_by_knowledge_points(
        self,
        knowledge_points: List[str],
        top_k: int = 20,
        difficulty_range: Optional[Tuple[float, float]] = None
    ) -> List[VectorSearchResult]:
        """
        基于多个知识点进行批量向量检索
        
        策略：
        1. 对每个知识点分别检索
        2. 合并结果并去重
        3. 按相似度排序
        """
        if not knowledge_points:
            return []
        
        all_results = []
        seen_ids = set()
        
        # 每个知识点检索的数量
        per_kp_count = max(top_k // len(knowledge_points), 5)
        
        for kp in knowledge_points:
            results = self.search_by_knowledge_point(
                knowledge_point=kp,
                top_k=per_kp_count,
                difficulty_range=difficulty_range
            )
            
            for result in results:
                if result.question_id not in seen_ids:
                    seen_ids.add(result.question_id)
                    all_results.append(result)
        
        # 按相似度排序
        all_results.sort(key=lambda x: x.similarity, reverse=True)
        
        return all_results[:top_k]
    
    def search_by_content_similarity(
        self,
        content: str,
        top_k: int = 10
    ) -> List[VectorSearchResult]:
        """
        基于内容相似度进行检索
        
        用于计算上下文相似度
        """
        try:
            # 获取查询向量
            query_vector = self.embedding_function([content[:500]])[0]  # 限制长度
            
            # 执行向量检索
            results = self.examples_collection.query(
                query_embeddings=[query_vector],
                n_results=top_k
            )
            
            return self._parse_search_results(results)
            
        except Exception as e:
            logger.error(f"内容相似度检索失败: {e}")
            return []
    
    def _parse_search_results(
        self, 
        results: Dict[str, Any]
    ) -> List[VectorSearchResult]:
        """解析Chroma检索结果"""
        output = []
        
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        distances = results.get("distances") or []
        
        if not documents or not documents[0]:
            return output
        
        docs0 = documents[0]
        metas0 = metadatas[0] if metadatas else []
        dists0 = distances[0] if distances else []
        
        for idx, doc in enumerate(docs0):
            metadata = metas0[idx] if idx < len(metas0) else {}
            distance = dists0[idx] if idx < len(dists0) else 1.0
            
            # 距离转相似度 (Chroma返回的是L2距离，需要转换)
            similarity = max(0.0, 1.0 - distance)
            
            result = VectorSearchResult(
                question_id=metadata.get('question_id', ''),
                content=doc,
                difficulty=metadata.get('difficulty', 0),
                knowledge_points=metadata.get('knowledge_points', []),
                similarity=similarity,
                metadata=metadata
            )
            output.append(result)
        
        return output
    
    # ==================== 元数据过滤 ====================
    
    def filter_by_difficulty(
        self,
        question_ids: List[str],
        min_difficulty: float,
        max_difficulty: float
    ) -> List[str]:
        """
        按难度范围过滤题目
        
        参数:
            question_ids: 题目ID列表
            min_difficulty: 最小难度
            max_difficulty: 最大难度
        
        返回:
            符合难度范围的题目ID列表
        """
        filtered_ids = []
        
        for qid in question_ids:
            try:
                # 通过metadata查询
                results = self.examples_collection.get(
                    where={
                        "$and": [
                            {"question_id": qid},
                            {"difficulty": {"$gte": min_difficulty}},
                            {"difficulty": {"$lte": max_difficulty}}
                        ]
                    }
                )
                
                if results and results.get('ids') and len(results['ids']) > 0:
                    filtered_ids.append(qid)
                    
            except Exception as e:
                logger.error(f"难度过滤失败 '{qid}': {e}")
                continue
        
        return filtered_ids
    
    def filter_by_knowledge_points(
        self,
        question_ids: List[str],
        required_kps: List[str]
    ) -> List[str]:
        """
        按知识点过滤题目
        
        返回包含任一指定知识点的题目
        """
        if not required_kps:
            return question_ids
        
        filtered_ids = []
        required_kps_set = set(required_kps)
        
        for qid in question_ids:
            try:
                results = self.examples_collection.get(
                    where={"question_id": qid}
                )
                
                if results and results.get('metadatas'):
                    metadata = results['metadatas'][0]
                    kp_list = metadata.get('knowledge_points', [])
                    
                    # 检查是否有交集
                    if set(kp_list) & required_kps_set:
                        filtered_ids.append(qid)
                        
            except Exception as e:
                logger.error(f"知识点过滤失败 '{qid}': {e}")
                continue
        
        return filtered_ids
    
    # ==================== 相似度计算 ====================
    
    def calculate_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        计算两段文本的向量相似度
        
        返回: 余弦相似度 (-1 ~ 1)
        """
        try:
            # 获取向量
            vectors = self.embedding_function([text1, text2])
            
            if len(vectors) != 2:
                return 0.0
            
            vec1, vec2 = vectors[0], vectors[1]
            
            # 计算余弦相似度
            return self._cosine_similarity(vec1, vec2)
            
        except Exception as e:
            logger.error(f"相似度计算失败: {e}")
            return 0.0
    
    def calculate_batch_similarity(
        self,
        query: str,
        texts: List[str]
    ) -> List[float]:
        """
        批量计算查询文本与多个文本的相似度
        """
        try:
            # 获取所有向量
            all_texts = [query] + texts
            vectors = self.embedding_function(all_texts)
            
            if len(vectors) != len(all_texts):
                return [0.0] * len(texts)
            
            query_vector = vectors[0]
            text_vectors = vectors[1:]
            
            # 计算相似度
            similarities = []
            for vec in text_vectors:
                sim = self._cosine_similarity(query_vector, vec)
                similarities.append(sim)
            
            return similarities
            
        except Exception as e:
            logger.error(f"批量相似度计算失败: {e}")
            return [0.0] * len(texts)
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """计算余弦相似度"""
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
    
    # ==================== 统计信息 ====================
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            return {
                'knowledge_points_count': self.knowledge_collection.count(),
                'example_questions_count': self.examples_collection.count(),
                'persist_dir': settings.chroma_persist_dir
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取题目信息"""
        try:
            results = self.examples_collection.get(
                where={"question_id": question_id}
            )
            
            if results and results.get('documents') and len(results['documents']) > 0:
                return {
                    'question_id': question_id,
                    'content': results['documents'][0],
                    'metadata': results['metadatas'][0] if results.get('metadatas') else {}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"获取题目失败 '{question_id}': {e}")
            return None


# ==================== 便捷函数 ====================

def search_questions_by_kp(
    knowledge_point: str,
    top_k: int = 10,
    difficulty_range: Optional[Tuple[float, float]] = None
) -> List[VectorSearchResult]:
    """
    便捷函数：基于知识点搜索题目
    
    使用示例:
        results = search_questions_by_kp("等比数列", top_k=5)
    """
    service = ChromaService()
    return service.search_by_knowledge_point(knowledge_point, top_k, difficulty_range)


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    便捷函数：计算文本相似度
    
    使用示例:
        sim = calculate_text_similarity("等差数列", "等比数列")
    """
    service = ChromaService()
    return service.calculate_similarity(text1, text2)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("Chroma服务测试")
    print("=" * 60)
    
    service = ChromaService()
    
    # 测试统计信息
    stats = service.get_collection_stats()
    print(f"\n集合统计：")
    print(f"  知识点数量: {stats.get('knowledge_points_count', 0)}")
    print(f"  例题数量: {stats.get('example_questions_count', 0)}")
    
    # 测试知识点检索
    print("\n测试知识点检索：")
    results = search_questions_by_kp("等差数列", top_k=3)
    for i, r in enumerate(results, 1):
        print(f"  [{i}] ID: {r.question_id}, 相似度: {r.similarity:.4f}")
    
    # 测试相似度计算
    print("\n测试文本相似度：")
    sim = calculate_text_similarity("等差数列求和", "等差数列公式")
    print(f"  '等差数列求和' vs '等差数列公式': {sim:.4f}")
