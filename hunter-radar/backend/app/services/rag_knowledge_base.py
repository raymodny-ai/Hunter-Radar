"""V1.6.0 LLM RAG 知识库服务。

功能:
1. build_knowledge_base(): 从 form4_event/buyback_event/edgar_fulltext 表提取历史公告
2. query_knowledge_base(): 给定 ticker + context,检索最相关的 top-K 历史文档
3. build_rag_prompt(): 将检索到的历史文档注入 LLM prompt context

依赖:
- sentence-transformers (embedding 生成,可选)
- pgvector (向量存储,需 SQL migration)
- 无依赖时降级为文本匹配模式
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

log = logging.getLogger(__name__)

# ---- 常量 ----

EMBEDDING_DIM = 384  # sentence-transformers default
TOP_K = 5  # 检索最相关的 top-K 文档
MAX_CONTENT_LENGTH = 2000  # 单文档最大字符数


# ---- Data Models ----


@dataclass(slots=True)
class KnowledgeDocument:
    """知识库文档。"""

    doc_id: int | None
    symbol: str
    doc_type: str  # '8-K' | '10-Q' | '10-K' | 'form4' | 'news' | 'buyback'
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "symbol": self.symbol,
            "doc_type": self.doc_type,
            "content": self.content[:500],  # 截断
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass(slots=True)
class RAGContext:
    """RAG 检索结果(用于注入 LLM prompt)。"""

    symbol: str
    documents: list[KnowledgeDocument]
    context_text: str  # 拼接后的上下文
    doc_count: int


# ---- Embedding 生成 ----


def _get_embedding_model():
    """尝试加载 sentence-transformers 模型。

    Returns:
        model 或 None(不可用时)
    """
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dim, 22MB
        return model
    except ImportError:
        log.warning("rag.sentence_transformers.not_installed")
        return None
    except Exception as e:  # noqa: BLE001
        log.warning("rag.embedding_model.error", error=str(e))
        return None


def generate_embedding(text: str, model=None) -> list[float] | None:
    """生成文本 embedding。

    Args:
        text: 输入文本
        model: sentence-transformers 模型(或 None)

    Returns:
        384 维向量列表,或 None(降级模式)
    """
    if model is None:
        model = _get_embedding_model()
    if model is None:
        return None  # 降级:不生成 embedding

    try:
        embedding = model.encode(text[:MAX_CONTENT_LENGTH])
        return embedding.tolist()
    except Exception as e:  # noqa: BLE001
        log.warning("rag.embedding.error", error=str(e))
        return None


# ---- 知识库构建 ----


async def build_knowledge_base(
    symbol: str | None = None,
    *,
    session=None,
    batch_size: int = 100,
) -> int:
    """从数据库表提取历史公告,生成 embedding 并存入 knowledge_documents。

    Args:
        symbol: 指定标的(None 时处理所有)
        session: AsyncSession(或 None 时自行创建)
        batch_size: 批处理大小

    Returns:
        处理的文档数量
    """
    from sqlalchemy import text as _t

    from app.core.database import AsyncSessionLocal

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    model = _get_embedding_model()
    count = 0

    try:
        # 1) 从 form4_event 提取内部人交易公告
        sym_filter = f" AND symbol = '{symbol}'" if symbol else ""
        rs = await session.execute(
            _t(
                f"""SELECT symbol, filing_date, transaction_code, shares, price_per_share
                    FROM form4_event
                    WHERE 1=1 {sym_filter}
                    ORDER BY filing_date DESC LIMIT 500"""
            )
        )
        for row in rs.all():
            content = (
                f"Form4: {row[0]} {row[2]} {row[3]} shares @ ${row[4]} on {row[1]}"
            )
            embedding = generate_embedding(content, model)
            await session.execute(
                _t(
                    """INSERT INTO knowledge_documents (symbol, doc_type, content, embedding, metadata)
                       VALUES (:sym, 'form4', :content, :emb, :meta)
                       ON CONFLICT DO NOTHING"""
                ),
                {
                    "sym": row[0],
                    "content": content,
                    "emb": str(embedding) if embedding else None,
                    "meta": f'{{"filing_date": "{row[1]}", "transaction_code": "{row[2]}"}}',
                },
            )
            count += 1

        # 2) 从 buyback_event 提取回购公告
        rs2 = await session.execute(
            _t(
                f"""SELECT symbol, announcement_date, buyback_amount, buyback_shares
                    FROM buyback_event
                    WHERE 1=1 {sym_filter}
                    ORDER BY announcement_date DESC LIMIT 200"""
            )
        )
        for row in rs2.all():
            content = (
                f"Buyback: {row[0]} announced ${row[2]} buyback ({row[3]} shares) on {row[1]}"
            )
            embedding = generate_embedding(content, model)
            await session.execute(
                _t(
                    """INSERT INTO knowledge_documents (symbol, doc_type, content, embedding, metadata)
                       VALUES (:sym, 'buyback', :content, :emb, :meta)
                       ON CONFLICT DO NOTHING"""
                ),
                {
                    "sym": row[0],
                    "content": content,
                    "emb": str(embedding) if embedding else None,
                    "meta": f'{{"announcement_date": "{row[1]}"}}',
                },
            )
            count += 1

        # 3) 从 edgar_fulltext 提取 SEC 公告全文
        rs3 = await session.execute(
            _t(
                f"""SELECT symbol, filing_type, filing_date, LEFT(full_text, 2000)
                    FROM edgar_fulltext
                    WHERE 1=1 {sym_filter}
                    ORDER BY filing_date DESC LIMIT 200"""
            )
        )
        for row in rs3.all():
            content = f"EDGAR {row[1]}: {row[0]} filed on {row[2]}. {row[3]}"
            embedding = generate_embedding(content, model)
            await session.execute(
                _t(
                    """INSERT INTO knowledge_documents (symbol, doc_type, content, embedding, metadata)
                       VALUES (:sym, :dtype, :content, :emb, :meta)
                       ON CONFLICT DO NOTHING"""
                ),
                {
                    "sym": row[0],
                    "dtype": row[1],
                    "content": content,
                    "emb": str(embedding) if embedding else None,
                    "meta": f'{{"filing_date": "{row[2]}"}}',
                },
            )
            count += 1

        if count > 0:
            await session.commit()

    except Exception as e:  # noqa: BLE001
        log.error("rag.build.error", error=str(e))
        if own_session:
            await session.rollback()
    finally:
        if own_session:
            await session.close()

    log.info("rag.build.complete", symbol=symbol or "all", count=count)
    return count


# ---- 知识库检索 ----


async def query_knowledge_base(
    symbol: str,
    query_text: str | None = None,
    *,
    top_k: int = TOP_K,
    session=None,
) -> list[KnowledgeDocument]:
    """检索最相关的 top-K 历史文档。

    Args:
        symbol: 标的代码
        query_text: 查询文本(用于向量相似度检索)
        top_k: 返回数量
        session: AsyncSession

    Returns:
        KnowledgeDocument 列表(按相关性排序)
    """
    from sqlalchemy import text as _t

    from app.core.database import AsyncSessionLocal

    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    docs: list[KnowledgeDocument] = []

    try:
        # 尝试向量检索(query_text 有 embedding 且表有 embedding 列时)
        if query_text:
            model = _get_embedding_model()
            query_emb = generate_embedding(query_text, model)
            if query_emb:
                rs = await session.execute(
                    _t(
                        """SELECT id, symbol, doc_type, content, metadata, created_at
                           FROM knowledge_documents
                           WHERE symbol = :sym AND embedding IS NOT NULL
                           ORDER BY embedding <=> :emb::vector
                           LIMIT :k"""
                    ),
                    {"sym": symbol, "emb": str(query_emb), "k": top_k},
                )
                for row in rs.all():
                    docs.append(
                        KnowledgeDocument(
                            doc_id=row[0],
                            symbol=row[1],
                            doc_type=row[2],
                            content=row[3],
                            metadata=dict(row[4] or {}),
                            created_at=row[5],
                        )
                    )

        # 降级:无 embedding 时按时间排序取最新
        if not docs:
            rs2 = await session.execute(
                _t(
                    """SELECT id, symbol, doc_type, content, metadata, created_at
                       FROM knowledge_documents
                       WHERE symbol = :sym
                       ORDER BY created_at DESC
                       LIMIT :k"""
                ),
                {"sym": symbol, "k": top_k},
            )
            for row in rs2.all():
                docs.append(
                    KnowledgeDocument(
                        doc_id=row[0],
                        symbol=row[1],
                        doc_type=row[2],
                        content=row[3],
                        metadata=dict(row[4] or {}),
                        created_at=row[5],
                    )
                )
    except Exception as e:  # noqa: BLE001
        log.warning("rag.query.error", symbol=symbol, error=str(e))
    finally:
        if own_session:
            await session.close()

    return docs


# ---- RAG Prompt 构建 ----


def build_rag_prompt(
    symbol: str,
    documents: list[KnowledgeDocument],
    original_prompt: str,
    context: str | None = None,
) -> str:
    """将历史文档注入 LLM prompt context。

    Args:
        symbol: 标的代码
        documents: 检索到的历史文档
        original_prompt: 原始 prompt
        context: 前端传入的额外上下文

    Returns:
        增强后的 prompt 字符串
    """
    if not documents:
        return original_prompt

    rag_section = f"\n\n--- Historical Context for {symbol} ---\n"
    rag_section += f"(Based on {len(documents)} relevant historical documents)\n\n"

    for i, doc in enumerate(documents, 1):
        doc_date = doc.created_at.strftime("%Y-%m-%d") if doc.created_at else "unknown"
        rag_section += f"[{i}] ({doc.doc_type}, {doc_date}): {doc.content[:300]}\n\n"

    rag_section += "--- End Historical Context ---\n"

    enhanced = original_prompt + rag_section
    if context:
        enhanced += f"\n\nAdditional context:\n{context}"

    return enhanced


# ---- 入口函数 ----


async def get_rag_context(
    symbol: str,
    query_text: str | None = None,
    *,
    top_k: int = TOP_K,
    session=None,
) -> RAGContext:
    """获取 RAG 上下文(检索 + 格式化)。

    Args:
        symbol: 标的代码
        query_text: 查询文本
        top_k: 文档数量
        session: AsyncSession

    Returns:
        RAGContext
    """
    docs = await query_knowledge_base(
        symbol, query_text, top_k=top_k, session=session
    )

    # 拼接上下文
    context_parts: list[str] = []
    for doc in docs:
        doc_date = doc.created_at.strftime("%Y-%m-%d") if doc.created_at else ""
        context_parts.append(f"[{doc.doc_type} {doc_date}] {doc.content[:200]}")

    return RAGContext(
        symbol=symbol,
        documents=docs,
        context_text="\n".join(context_parts),
        doc_count=len(docs),
    )
