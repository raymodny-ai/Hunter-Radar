"""LLM 分析代理 API。将前端请求转发到 DeepSeek / Gemini 等模型。"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class LlmAnalyzeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    model: str = Field(default="deepseek-v4-pro", pattern=r"^(deepseek-v4-pro|gemini-3\.5-flash)$")
    prompt: str = Field(..., min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=8000)


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


@router.post(
    "/llm/analyze",
    response_model=LlmAnalyzeResponse,
    summary="LLM 分析标的(代理 DeepSeek/Gemini)",
)
async def llm_analyze(req: LlmAnalyzeRequest) -> LlmAnalyzeResponse:
    keys = _get_keys()
    model = req.model
    system_prompt = req.prompt
    user_prompt = f"股票代码: {req.ticker}"
    if req.context:
        user_prompt += f"\n\n当前数据:\n{req.context}"

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
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
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
                return LlmAnalyzeResponse(model=model, content=content, tokens_used=tokens)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="DeepSeek API timeout")
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
                        "contents": [
                            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
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
                # Gemini 不返回 token 数，用文本长度估算
                tokens = max(1, len(content) // 4)
                return LlmAnalyzeResponse(model=model, content=content, tokens_used=tokens)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Gemini API timeout")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")

    raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")
