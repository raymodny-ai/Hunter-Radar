"""LLM 分析代理 API。将前端请求转发到 DeepSeek / Gemini 等模型。

V1.6.1 安全加固:
- 输入验证: model 白名单、prompt ≤ 2000 字符、context ≤ 8000 字符
- Redis 每日 token 预算: free 50k / pro 500k
- 固定 system prompt 模板(用户输入永远不作为 system prompt)
- 输出过滤: forbidden_recommendation_words 检查
- 速率限制: 5 req/min/user (Redis sliding window)
"""

from __future__ import annotations

import logging
import re
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import TUser, get_current_user
from app.core.config import settings

log = logging.getLogger(__name__)

router = APIRouter()

# ---- 安全常量 ----
ALLOWED_MODELS: set[str] = {"deepseek-v4-pro", "gemini-3.5-flash"}
MAX_PROMPT_LEN: int = 2000
MAX_CONTEXT_LEN: int = 8000
RATE_LIMIT_PER_MIN: int = 5
DAILY_TOKEN_LIMIT_FREE: int = 50_000
DAILY_TOKEN_LIMIT_PRO: int = 500_000

# 固定 system prompt 模板——用户输入永远不进入 system prompt
HARDENED_SYSTEM_PROMPT: str = (
    "You are a quantitative risk analyst assistant for Hunter Radar. "
    "Analyze the given ticker based on provided market data. "
    "NEVER give buy/sell recommendations. "
    "NEVER guarantee returns or claim certainty. "
    "Focus on risk factors, anomaly signals, and data-driven observations. "
    "Respond in the same language as the user's question."
)

# 控制字符清理正则
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class LlmAnalyzeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    model: str = Field(default="deepseek-v4-pro")
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LEN)
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_LEN)


class LlmAnalyzeResponse(BaseModel):
    model: str
    content: str
    tokens_used: int = 0


# 从后端配置读取 API Key
def _get_keys() -> dict:
    import os
    return {
        "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
        "gemini": os.environ.get("GEMINI_API_KEY", ""),
    }


def _get_redis():
    """Lazy import Redis client(沙箱环境无 Redis 时降级为无限制)。"""
    try:
        from app.core.redis import get_redis_client
        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None


def _check_forbidden_words(text: str) -> str | None:
    """检查输出是否含禁止词,返回第一个命中的禁止词或 None。"""
    for word in settings.forbidden_recommendation_words:
        if word in text:
            return word
    return None


async def _check_rate_limit(user_id: str) -> None:
    """速率限制: 5 req/min/user (Redis sliding window)。"""
    redis = _get_redis()
    if redis is None:
        return  # 沙箱降级
    import time
    key = f"llm:rate:{user_id}"
    now = time.time()
    window_start = now - 60
    try:
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, 120)
        results = await pipe.execute()
        count = results[1]
        if count >= RATE_LIMIT_PER_MIN:
            raise HTTPException(status_code=429, detail="Rate limit exceeded: max 5 requests/min")
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        pass  # Redis 不可用时降级


async def _check_daily_budget(user_id: str, tier: str, estimated_tokens: int) -> None:
    """每日 token 预算检查。"""
    redis = _get_redis()
    if redis is None:
        return  # 沙箱降级
    limit = DAILY_TOKEN_LIMIT_FREE if tier == "free" else DAILY_TOKEN_LIMIT_PRO
    budget_key = f"llm:budget:{user_id}:{date.today().isoformat()}"
    try:
        used = await redis.incrby(budget_key, estimated_tokens)
        await redis.expire(budget_key, 86400)
        if used > limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily LLM token quota exceeded ({limit:,} tokens/day for {tier} tier)",
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        pass  # Redis 不可用时降级


@router.post(
    "/llm/analyze",
    response_model=LlmAnalyzeResponse,
    summary="LLM 分析标的(代理 DeepSeek/Gemini)",
)
async def llm_analyze(
    req: LlmAnalyzeRequest,
    user: TUser = Depends(get_current_user),
) -> LlmAnalyzeResponse:
    # ---- 输入验证 ----
    if req.model not in ALLOWED_MODELS:
        raise HTTPException(status_code=400, detail=f"Unsupported model: {req.model}. Allowed: {sorted(ALLOWED_MODELS)}")
    if len(req.prompt) > MAX_PROMPT_LEN:
        raise HTTPException(status_code=400, detail=f"Prompt too long (max {MAX_PROMPT_LEN} chars)")
    if req.context and len(req.context) > MAX_CONTEXT_LEN:
        raise HTTPException(status_code=400, detail=f"Context too long (max {MAX_CONTEXT_LEN} chars)")

    # 清理控制字符
    clean_prompt = _CONTROL_CHARS_RE.sub("", req.prompt)
    clean_context = _CONTROL_CHARS_RE.sub("", req.context) if req.context else None

    # ---- 速率限制 ----
    user_id = str(user.user_id)
    await _check_rate_limit(user_id)

    # ---- 每日 token 预算 ----
    estimated_tokens = len(clean_prompt) // 4 + (len(clean_context) // 4 if clean_context else 0) + 500
    await _check_daily_budget(user_id, user.tier, estimated_tokens)

    # ---- 构建消息(固定 system prompt,用户输入永远不作为 system) ----
    user_msg = f"Ticker: {req.ticker}\nQuestion: {clean_prompt}"
    if clean_context:
        user_msg += f"\n\nMarket Data Context:\n{clean_context}"

    # V1.6.0 RAG 知识库增强
    rag_context = ""
    try:
        from app.services.rag_knowledge_base import get_rag_context
        rag_ctx = await get_rag_context(req.ticker, query_text=clean_prompt)
        if rag_ctx.doc_count > 0:
            rag_context = f"\n\n--- Historical Context for {req.ticker} ---\n{rag_ctx.context_text}\n--- End Historical Context ---"
    except Exception:  # noqa: BLE001
        pass  # RAG 不可用时降级

    keys = _get_keys()
    model = req.model

    if model == "deepseek-v4-pro":
        api_key = keys.get("deepseek", "")
        if not api_key:
            raise HTTPException(status_code=503, detail="DeepSeek API key not configured")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": HARDENED_SYSTEM_PROMPT + rag_context},
                            {"role": "user", "content": user_msg},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                )
                data = resp.json()
                if "choices" not in data:
                    raise HTTPException(status_code=502, detail=f"DeepSeek API error: {data.get('error', {}).get('message', str(data))}")
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="DeepSeek API timeout")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"DeepSeek API error: {e}")

    elif model == "gemini-3.5-flash":
        api_key = keys.get("gemini", "")
        if not api_key:
            raise HTTPException(status_code=503, detail="Gemini API key not configured")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "system_instruction": {"parts": [{"text": HARDENED_SYSTEM_PROMPT + rag_context}]},
                        "contents": [
                            {"role": "user", "parts": [{"text": user_msg}]}
                        ],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 2000,
                        },
                    },
                )
                data = resp.json()
                if "candidates" not in data:
                    raise HTTPException(status_code=502, detail=f"Gemini API error: {data.get('error', {}).get('message', str(data))}")
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                tokens = max(1, len(content) // 4)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Gemini API timeout")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")

    # ---- 输出过滤 ----
    hit = _check_forbidden_words(content)
    if hit:
        log.warning("llm.output.forbidden_word", user=user_id, word=hit, model=model)
        raise HTTPException(
            status_code=422,
            detail="Response filtered: contains prohibited recommendation language",
        )

    return LlmAnalyzeResponse(model=model, content=content, tokens_used=tokens)
