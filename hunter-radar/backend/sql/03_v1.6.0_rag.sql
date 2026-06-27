-- V1.6.0 RAG 知识库表结构
-- 需要 pgvector 扩展支持向量检索

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 知识库文档表
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    doc_type VARCHAR(20) NOT NULL,  -- '8-K' | '10-Q' | '10-K' | 'form4' | 'news' | 'buyback'
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- sentence-transformers default dim=384
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引: 按 symbol 过滤
CREATE INDEX IF NOT EXISTS idx_kd_symbol ON knowledge_documents (symbol);

-- 索引: 按 doc_type 过滤
CREATE INDEX IF NOT EXISTS idx_kd_doc_type ON knowledge_documents (doc_type);

-- 索引: 向量相似度检索 (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_kd_embedding ON knowledge_documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 注释
COMMENT ON TABLE knowledge_documents IS 'V1.6.0 RAG 知识库:存储历史公告/事件/新闻的向量化文档';
COMMENT ON COLUMN knowledge_documents.embedding IS 'sentence-transformers 生成的 384 维向量';
COMMENT ON COLUMN knowledge_documents.doc_type IS '文档类型:8-K/10-Q/10-K/form4/news/buyback';
