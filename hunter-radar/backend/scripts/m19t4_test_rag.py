"""m19t4 V1.6.0 P2 RAG 知识库自测(25 测点)。

Section 1: KnowledgeDocument 模型 (5)
Section 2: Embedding 生成 + 存储 (5)
Section 3: 知识库检索 (5)
Section 4: RAG Prompt 构建 (5)
Section 5: LLM API 集成 (5)

静态分析为主。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

PASS = "[PASS]"
FAIL = "[FAIL]"
_passed = 0
_total = 0


def t(name: str, ok: bool, detail: str = "") -> None:
    global _passed, _total
    _total += 1
    if ok:
        _passed += 1
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)


# ============================================================
# Section 1: KnowledgeDocument 模型 (5)
# ============================================================
def test_knowledge_model() -> None:
    print("\n=== Section 1: KnowledgeDocument 模型 (5) ===", flush=True)
    fp = BACKEND / "app" / "services" / "rag_knowledge_base.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: 文件存在
    t("rag_file_exists", fp.exists(), str(fp))

    # t2: KnowledgeDocument dataclass
    t("rag_knowledge_doc", "class KnowledgeDocument" in src)

    # t3: RAGContext dataclass
    t("rag_context", "class RAGContext" in src)

    # t4: doc_type 字段
    t("rag_doc_type", "doc_type" in src and ("8-K" in src or "form4" in src))

    # t5: embedding 字段
    t("rag_embedding", "embedding" in src and "VECTOR" in src or "384" in src)


# ============================================================
# Section 2: Embedding 生成 (5)
# ============================================================
def test_embedding() -> None:
    print("\n=== Section 2: Embedding 生成 (5) ===", flush=True)
    fp = BACKEND / "app" / "services" / "rag_knowledge_base.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: generate_embedding 函数
    t("emb_generate_fn", "def generate_embedding" in src)

    # t2: sentence_transformers 导入
    t("emb_sentence_transformers", "sentence_transformers" in src or "SentenceTransformer" in src)

    # t3: 降级处理(模型不可用)
    t("emb_fallback", "None" in src and ("降级" in src or "not_installed" in src))

    # t4: EMBEDDING_DIM 常量
    t("emb_dim_const", "EMBEDDING_DIM" in src and "384" in src)

    # t5: MAX_CONTENT_LENGTH
    t("emb_max_content", "MAX_CONTENT_LENGTH" in src)


# ============================================================
# Section 3: 知识库检索 (5)
# ============================================================
def test_query() -> None:
    print("\n=== Section 3: 知识库检索 (5) ===", flush=True)
    fp = BACKEND / "app" / "services" / "rag_knowledge_base.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: query_knowledge_base 函数
    t("query_fn", "async def query_knowledge_base" in src)

    # t2: build_knowledge_base 函数
    t("build_fn", "async def build_knowledge_base" in src)

    # t3: TOP_K 常量
    t("query_top_k", "TOP_K" in src)

    # t4: 向量相似度查询 (<=> 操作符)
    t("query_vector_sim", "<=>" in src or "cosine" in src)

    # t5: 降级:无 embedding 时按时间排序
    t("query_fallback", "created_at DESC" in src)


# ============================================================
# Section 4: RAG Prompt 构建 (5)
# ============================================================
def test_rag_prompt() -> None:
    print("\n=== Section 4: RAG Prompt 构建 (5) ===", flush=True)
    fp = BACKEND / "app" / "services" / "rag_knowledge_base.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: build_rag_prompt 函数
    t("prompt_fn", "def build_rag_prompt" in src)

    # t2: get_rag_context 入口函数
    t("prompt_context_fn", "async def get_rag_context" in src)

    # t3: Historical Context 标记
    t("prompt_context_marker", "Historical Context" in src)

    # t4: 空文档时返回原始 prompt
    t("prompt_empty_docs", "if not documents" in src and "return original_prompt" in src)

    # t5: context 拼接
    t("prompt_context_text", "context_text" in src)


# ============================================================
# Section 5: LLM API 集成 (5)
# ============================================================
def test_llm_integration() -> None:
    print("\n=== Section 5: LLM API 集成 (5) ===", flush=True)

    # t1: SQL migration 文件
    sql_fp = BACKEND / "sql" / "03_v1.6.0_rag.sql"
    t("llm_sql_exists", sql_fp.exists(), str(sql_fp))

    sql_src = sql_fp.read_text(encoding="utf-8") if sql_fp.exists() else ""

    # t2: knowledge_documents 表
    t("llm_sql_table", "knowledge_documents" in sql_src)

    # t3: pgvector 扩展
    t("llm_sql_pgvector", "vector" in sql_src.lower())

    # t4: LLM API RAG 集成
    llm_fp = BACKEND / "app" / "api" / "llm.py"
    llm_src = llm_fp.read_text(encoding="utf-8") if llm_fp.exists() else ""
    t("llm_rag_import", "rag_knowledge_base" in llm_src or "get_rag_context" in llm_src)

    # t5: RAG 降级(try/except)
    t("llm_rag_fallback", "except" in llm_src and "RAG" in llm_src)


# ============================================================
# main
# ============================================================
def main() -> int:
    test_knowledge_model()
    test_embedding()
    test_query()
    test_rag_prompt()
    test_llm_integration()

    print(flush=True)
    ok = _passed == _total
    if ok:
        print(f"[m19t4] {_passed}/{_total} ALL PASSED")
    else:
        print(f"[m19t4] {_passed}/{_total} ({_total - _passed} FAILED)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
