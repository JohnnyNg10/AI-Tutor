from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Sequence


import chromadb
from openai import OpenAI

from utils.config import settings
from utils.logger import logger


class DashScopeEmbeddingFunction:
    """DashScope（通义千问官方）Embedding 适配器"""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.dashscope_embedding_model or "text-embedding-v3"
        self.api_key = settings.dashscope_api_key
        self.api_base = settings.dashscope_api_base or "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    def name(self) -> str:
        return "dashscope_embedding"

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        """ChromaDB 会以字符串列表形式调用该函数。"""
        import requests
        
        clean_texts = [str(t).strip() for t in input if str(t).strip()]
        if not clean_texts:
            logger.warning("Embedding 输入为空，返回空向量")
            return []

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # DashScope Embedding API
            url = self.api_base
            
            payload = {
                "model": self.model,
                "input": {
                    "texts": clean_texts
                }
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            embeddings = []
            for item in data.get("output", {}).get("embeddings", []):
                embedding = item.get("embedding", [])
                embeddings.append(embedding)
            
            logger.info(f"成功获取 {len(embeddings)} 个文本的向量表示")
            return embeddings
            
        except Exception as e:
            logger.error(f"DashScope Embedding 调用失败: {e}")
            raise


class SiliconFlowEmbeddingFunction:
    """硅基流动 Embedding 适配器"""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.embedding_model or "Qwen/Qwen3-Embedding-8B"
        # Use dedicated SiliconFlow API key if available, fallback to OpenAI key
        api_key = settings.siliconflow_api_key or settings.openai_api_key
        base_url = settings.siliconflow_api_base or settings.openai_api_base
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def name(self) -> str:
        return "siliconflow_embedding"

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        """ChromaDB 会以字符串列表形式调用该函数。"""
        clean_texts = [str(t).strip() for t in input if str(t).strip()]
        if not clean_texts:
            logger.warning("Embedding 输入为空，返回空向量")
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=clean_texts
            )
            vectors = [item.embedding for item in response.data]
            return vectors
        except Exception as e:
            logger.error(f"硅基流动 Embedding 调用失败: {e}")
            raise


class ChaoSuanEmbeddingFunction:
    """超算互联网 Qwen3-Embedding 适配器"""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.chaosuan_embedding_model or "Qwen3-Embedding-8B"
        self.client = OpenAI(
            api_key=settings.chaosuan_api_key,
            base_url=settings.chaosuan_api_base
        )

    def name(self) -> str:
        return "chaosuan_embedding"

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        """ChromaDB 会以字符串列表形式调用该函数。"""
        clean_texts = [str(t).strip() for t in input if str(t).strip()]
        if not clean_texts:
            logger.warning("Embedding 输入为空，返回空向量")
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=clean_texts
            )
            vectors = [item.embedding for item in response.data]
            return vectors
        except Exception as e:
            logger.error(f"超算互联网 Embedding 调用失败: {e}")
            raise


class VolcEmbeddingFunction:
    """火山引擎 Embedding 适配器（兼容不同 Ark SDK 形态）。"""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = (model or settings.volc_embedding_model or "").strip()
        if not self.model:
            raise ValueError("VOLC_EMBEDDING_MODEL 未配置，无法初始化向量模型")

        self.client = self._build_ark_client()

    @staticmethod
    def name() -> str:
        return "volc_ark_embedding"

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "VolcEmbeddingFunction":
        return VolcEmbeddingFunction(model=config.get("model"))

    def get_config(self) -> Dict[str, Any]:
        return {"model": self.model}


    def _build_ark_client(self):
        init_errors: List[str] = []

        #volcenginesdkarkruntime（API Key）
        try:
            from volcenginesdkarkruntime import Ark as RuntimeArk  # type: ignore

            return RuntimeArk(api_key=settings.volc_access_key)
        except Exception as e:
            init_errors.append(f"volcenginesdkarkruntime 初始化失败: {e}")

        #volcengine.ark（AK/SK）
        try:
            from volcengine.ark import Ark as VolcArk  # type: ignore

            return VolcArk(
                access_key_id=settings.volc_access_key,
                secret_access_key=settings.volc_secret_key,
                region=settings.volc_region,
            )
        except Exception as e:
            init_errors.append(f"volcengine.ark(AK/SK) 初始化失败: {e}")

        #volcengine.ark（API Key）
        try:
            from volcengine.ark import Ark as VolcArk  # type: ignore

            return VolcArk(api_key=settings.volc_access_key)
        except Exception as e:
            init_errors.append(f"volcengine.ark(API Key) 初始化失败: {e}")

        err_msg = " | ".join(init_errors)
        logger.error(f"Ark 客户端初始化失败: {err_msg}")
        raise RuntimeError("Ark 客户端初始化失败，请检查依赖与鉴权配置")

    @staticmethod
    def _extract_embeddings_from_response(resp: Any) -> List[List[float]]:
        data = getattr(resp, "data", None)
        if data is None and isinstance(resp, dict):
            data = resp.get("data")

        if data is None:
            return []

        #单条对象，直接包含 embedding
        if isinstance(data, dict):
            vec = data.get("embedding")
            return [vec] if isinstance(vec, list) and vec else []

        vec = getattr(data, "embedding", None)
        if isinstance(vec, list) and vec:
            return [vec]

        #列表/可迭代
        vectors: List[List[float]] = []
        try:
            items = list(data)
        except TypeError:
            items = []

        for item in items:
            if isinstance(item, dict):
                item_vec = item.get("embedding")
            elif isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[1], list):
                item_vec = item[1]
            else:
                item_vec = getattr(item, "embedding", None)
            if isinstance(item_vec, list) and item_vec:
                vectors.append(item_vec)

        return vectors


    def _request_embeddings(self, texts: List[str]) -> List[List[float]]:
        errors: List[str] = []

        # 优先尝试 multimodal_embeddings（你当前模型为 embedding-vision，更匹配该接口）
        try:
            if hasattr(self.client, "multimodal_embeddings"):
                mm_input = [{"type": "text", "text": t} for t in texts]
                resp = self.client.multimodal_embeddings.create(model=self.model, input=mm_input)
                vectors = self._extract_embeddings_from_response(resp)
                if vectors:
                    return vectors
                errors.append("multimodal_embeddings.create 返回空向量")
            else:
                errors.append("客户端不支持 multimodal_embeddings.create")
        except Exception as e:
            msg = f"multimodal_embeddings.create 失败: {e}"
            errors.append(msg)
            logger.error(msg, exc_info=True)

        # 仅当模型看起来不是 vision 系列时，再尝试 embeddings.create 兜底
        if "vision" not in self.model.lower():
            try:
                if hasattr(self.client, "embeddings"):
                    resp = self.client.embeddings.create(model=self.model, input=texts)
                    vectors = self._extract_embeddings_from_response(resp)
                    if vectors:
                        return vectors
                    errors.append("embeddings.create 返回空向量")
                else:
                    errors.append("客户端不支持 embeddings.create")
            except Exception as e:
                msg = f"embeddings.create 失败: {e}"
                errors.append(msg)
                logger.warning(msg)

        detail = " | ".join(errors)
        raise RuntimeError(
            f"Embedding 接口调用失败，model={self.model}。"
            f"请确认 `VOLC_EMBEDDING_MODEL` 配置的是可用的向量模型 Endpoint。详情: {detail}"
        )



    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        """ChromaDB 会以字符串列表形式调用该函数。"""
        clean_texts = [str(t).strip() for t in input if str(t).strip()]
        if not clean_texts:
            logger.warning("Embedding 输入为空，返回空向量")
            return []

        vectors = self._request_embeddings(clean_texts)
        if len(vectors) == len(clean_texts):
            return vectors

        # 某些模型/接口批量输入只返回 1 条，降级为逐条请求
        if len(clean_texts) > 1:
            logger.warning(
                f"Embedding 批量返回数量异常，降级逐条请求：输入 {len(clean_texts)}，输出 {len(vectors)}"
            )
            single_vectors: List[List[float]] = []
            for text in clean_texts:
                one = self._request_embeddings([text])
                if len(one) != 1:
                    raise RuntimeError(
                        f"逐条 Embedding 失败：文本长度 1，返回 {len(one)}"
                    )
                single_vectors.append(one[0])
            return single_vectors

        raise RuntimeError(
            f"Embedding 返回数量异常：输入 {len(clean_texts)}，输出 {len(vectors)}"
        )



# 单例
_retriever_instance: Optional["KnowledgeRetriever"] = None


def get_retriever() -> "KnowledgeRetriever":
    """获取 KnowledgeRetriever 单例"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = KnowledgeRetriever()
    return _retriever_instance


class KnowledgeRetriever:
    """知识点/例题检索器 - 基于 ChromaDB 向量数据库 (单例模式)"""

    def __init__(self):
        global _retriever_instance
        if _retriever_instance is not None:
            self.__dict__ = _retriever_instance.__dict__
            return

        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        # 优先使用 DashScope（通义千问官方），其次硅基流动，然后超算互联网，最后火山引擎
        if settings.dashscope_api_key and settings.dashscope_embedding_model:
            logger.info(f"使用 DashScope Embedding 模型: {settings.dashscope_embedding_model}")
            self.embedding_function = DashScopeEmbeddingFunction()
        elif settings.openai_api_key and settings.embedding_model:
            logger.info(f"使用硅基流动Embedding模型: {settings.embedding_model}")
            self.embedding_function = SiliconFlowEmbeddingFunction()
        elif settings.chaosuan_api_key and settings.chaosuan_embedding_model:
            logger.info(f"使用超算互联网Embedding模型: {settings.chaosuan_embedding_model}")
            self.embedding_function = ChaoSuanEmbeddingFunction()
        else:
            logger.info(f"使用火山引擎Embedding模型: {settings.volc_embedding_model}")
            self.embedding_function = VolcEmbeddingFunction()

        self.knowledge_collection = self._get_or_create_collection("knowledge_points")
        self.examples_collection = self._get_or_create_collection("example_questions")

        # 维度校验
        try:
            self._validate_dimension()
        except Exception as e:
            logger.error(f"Embedding 维度校验失败，检索可能不可用: {e}")

        _retriever_instance = self

    def _validate_dimension(self):
        """验证 embedding 模型输出维度与 ChromaDB collection 一致"""
        test_vector = self.embedding_function(["test"])[0]
        emb_dim = len(test_vector)
        existing = self.examples_collection.get(limit=1, include=["embeddings"])
        emb_list = existing.get("embeddings") if existing else None
        if emb_list is not None and len(emb_list) > 0:
            first_emb = emb_list[0]
            if first_emb is not None and len(first_emb) > 0:
                db_dim = len(first_emb)
                if emb_dim != db_dim:
                    raise ValueError(
                        f"Embedding 维度不匹配：模型={emb_dim}, 数据库={db_dim}。"
                        f"请删除 chroma_db 目录重新导入数据"
                    )
        logger.info(f"Embedding 维度校验通过: {emb_dim}")

    def _get_or_create_collection(self, name: str):
        """获取或创建 collection，处理 embedding function 冲突"""
        try:
            # 先尝试获取已存在的 collection
            collection = self.client.get_collection(name=name)
            logger.info(f"使用已存在的 collection: {name}")
            return collection
        except Exception:
            # 如果不存在，创建新的
            try:
                collection = self.client.create_collection(
                    name=name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"创建新的 collection: {name}")
                return collection
            except Exception as e:
                logger.warning(f"创建 collection 失败，尝试获取: {e}")
                # 如果创建失败（比如已存在但获取也失败），再次尝试获取
                return self.client.get_collection(name=name)


    @staticmethod
    def _format_query_results(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        distances = results.get("distances") or []

        if not documents or not documents[0]:
            return output

        docs0 = documents[0]
        metas0 = metadatas[0] if metadatas else []
        dists0 = distances[0] if distances else []

        for idx, doc in enumerate(docs0):
            output.append(
                {
                    "content": doc,
                    "metadata": metas0[idx] if idx < len(metas0) else {},
                    "distance": dists0[idx] if idx < len(dists0) else 0,
                }
            )
        return output

    def search_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            logger.warning("搜索知识点的查询文本为空或非法")
            return []
        query_text = query.strip()
        try:
            query_vector = self.embedding_function([query_text])[0]
            results = self.knowledge_collection.query(
                query_embeddings=[query_vector], n_results=max(1, int(top_k)),
            )
            data = self._format_query_results(results)
            logger.info(f"知识点检索完成：找到 {len(data)} 条结果")
            return data
        except ValueError as e:
            logger.error(f"[检索] 维度不匹配: {e}。可能需要重建 ChromaDB")
            return []
        except ConnectionError as e:
            logger.error(f"[检索] 网络错误: {e}")
            return []
        except Exception as e:
            logger.error(f"[检索] 知识点检索失败: {e}", exc_info=True)
            return []

    def search_examples(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            logger.warning("搜索例题的查询文本为空或非法")
            return []
        query_text = query.strip()
        try:
            query_vector = self.embedding_function([query_text])[0]
            results = self.examples_collection.query(
                query_embeddings=[query_vector], n_results=max(1, int(top_k)),
            )
            data = self._format_query_results(results)
            logger.info(f"例题检索完成：找到 {len(data)} 条结果")
            return data
        except ValueError as e:
            logger.error(f"[检索] 维度不匹配: {e}。可能需要重建 ChromaDB")
            return []
        except ConnectionError as e:
            logger.error(f"[检索] 网络错误: {e}")
            return []
        except Exception as e:
            logger.error(f"[检索] 例题检索失败: {e}", exc_info=True)
            return []

    def batch_insert(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,

    ) -> None:
        if not documents:
            logger.warning("批量插入被跳过：documents 为空")
            return

        clean_docs = [str(d).strip() for d in documents if str(d).strip()]
        if not clean_docs:
            logger.warning("批量插入被跳过：清洗后 documents 为空")
            return

        if metadatas is None:
            metadatas = [{} for _ in clean_docs]
        elif len(metadatas) != len(documents):
            raise ValueError("metadatas 长度必须与 documents 一致")

        clean_metas = []
        for idx, doc in enumerate(documents):
            if not str(doc).strip():
                continue
            clean_metas.append(metadatas[idx] if idx < len(metadatas) else {})

        if collection_name == "knowledge_points":
            collection = self.knowledge_collection
        elif collection_name == "example_questions":
            collection = self.examples_collection
        else:
            raise ValueError(f"未知集合名：{collection_name}")

        ids = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{collection_name}:{doc}:{json.dumps(meta, ensure_ascii=False, sort_keys=True)}"))
            for doc, meta in zip(clean_docs, clean_metas)
        ]

        # DashScope 每次最多处理 10 条文本
        max_batch_size = 10
        all_embeddings = []
        for i in range(0, len(clean_docs), max_batch_size):
            batch_docs = clean_docs[i:i+max_batch_size]
            batch_embeddings = self.embedding_function(batch_docs)
            all_embeddings.extend(batch_embeddings)
            logger.info(f"  已获取 {min(i+max_batch_size, len(clean_docs))}/{len(clean_docs)} 条向量")
        
        try:
            collection.upsert(
                ids=ids,
                documents=clean_docs,
                metadatas=clean_metas,
                embeddings=all_embeddings,
            )
        except Exception:
            collection.add(
                ids=ids,
                documents=clean_docs,
                metadatas=clean_metas,
                embeddings=all_embeddings,
            )


        logger.info(f"成功写入 {len(ids)} 条数据到 {collection_name} 集合")


if __name__ == "__main__":
    retriever = KnowledgeRetriever()
    print("知识点检索结果：", retriever.search_knowledge("等差数列求和公式", top_k=1))
    print("例题检索结果：", retriever.search_examples("等差数列求和公式例题", top_k=1))
