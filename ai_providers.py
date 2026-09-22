"""Validated structured generation for local Ollama and opt-in cloud APIs."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
import httpx

SUPPORTED_PROVIDERS = ("basic", "ollama", "openai", "gemini")
CLOUD_PROVIDERS = ("openai", "gemini")
LABELS = {"basic": "基本摘錄", "ollama": "本機 AI", "openai": "OpenAI API", "gemini": "Gemini API"}
ENDPOINTS = {"ollama": "http://127.0.0.1:11434", "openai": "https://api.openai.com/v1", "gemini": "https://generativelanguage.googleapis.com/v1beta"}


@dataclass(frozen=True, slots=True)
class AIProviderConfig:
    """Only non-secret settings belong in preferences."""
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    endpoint: str | None = None


class ProviderError(ValueError):
    """Safe error that never includes raw headers or response bodies."""


def validate_provider_config(config):
    if config.provider not in SUPPORTED_PROVIDERS:
        raise ProviderError("不支援的 AI 供應商")
    if config.provider != "basic" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", config.model):
        raise ProviderError("請填入有效的模型 ID（英數、點、冒號、底線或連字號）")
    if config.provider == "ollama" and "cloud" in config.model.lower():
        raise ProviderError("本機模式不接受 cloud 模型；請選擇已下載的本機模型")
    if config.endpoint and config.endpoint.rstrip("/") != ENDPOINTS.get(config.provider):
        raise ProviderError("此版僅支援內建的本機與官方 API 位址")


class AIProvider:
    def __init__(self, config, *, api_key="", cloud_allowed=False):
        validate_provider_config(config)
        self.config = config
        self.name = config.provider
        self._key = api_key.strip()
        self.blocked = False
        if self.name in CLOUD_PROVIDERS:
            if not cloud_allowed:
                raise ProviderError("請先同意將擷取文字傳送到選定的雲端 AI")
            if not self._key or any(ord(c) < 33 or ord(c) > 126 for c in self._key):
                raise ProviderError("請輸入有效的 API 金鑰")

    def __repr__(self):
        return f"AIProvider(provider={self.name!r})"

    def headers(self):
        if self.name == "openai":
            return {"Authorization": "Bearer " + self._key}
        if self.name == "gemini":
            return {"x-goog-api-key": self._key}
        return {}

    async def request(self, client, method, path, **kwargs):
        if self.blocked:
            raise ProviderError("此批次 AI 連線已停止，請檢查金鑰、額度或模型後重試")
        try:
            response = await getattr(client, method)(ENDPOINTS[self.name] + path, headers=self.headers(), **kwargs)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Expected object')
            return data
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            self.blocked = True
            reasons = {400: "模型或輸出格式不支援，請換用支援 JSON Schema 的文字模型", 401: "API 金鑰無效", 403: "帳號沒有此模型的存取權限", 404: "找不到模型或 API", 429: "API 額度不足或請求過於頻繁"}
            raise ProviderError(reasons.get(status, f"AI 服務暫時無法使用（HTTP {status}）")) from None
        except (httpx.HTTPError, ValueError):
            self.blocked = True
            raise ProviderError("AI 連線逾時、失敗或回傳格式異常；原文將保留") from None

    async def models(self):
        if self.name == "basic":
            return []
        path = "/api/tags" if self.name == "ollama" else "/models"
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            data = await self.request(client, "get", path)
        try:
            if self.name == "ollama":
                return sorted(x["name"] for x in data.get("models", []) if "cloud" not in x["name"].lower())
            if self.name == "openai":
                return sorted(x["id"] for x in data["data"])
            return sorted(x["name"].removeprefix("models/") for x in data.get("models", []) if "generateContent" in x.get("supportedGenerationMethods", []))
        except (TypeError, KeyError, AttributeError):
            raise ProviderError("模型清單格式異常") from None

    async def structured_reply(self, model, instruction, content, schema, validate):
        if self.name == "basic":
            raise ProviderError("基本摘錄不使用 AI 生成")
        validate_provider_config(AIProviderConfig(self.name, model))
        feedback = ''
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8), trust_env=False, follow_redirects=False) as client:
            for attempt in range(2):
                prompt = content + ("\n上次回覆未通過檢查。" + feedback + " 請重新輸出完整 JSON。" if attempt else "")
                if self.name == "ollama":
                    data = await self.request(client, "post", "/api/chat", json={"model": model, "stream": False, "format": schema, "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": prompt}], "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 3000}})
                elif self.name == "openai":
                    data = await self.request(client, "post", "/chat/completions", json={"model": model, "store": False, "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": prompt}], "max_completion_tokens": 6000, "response_format": {"type": "json_schema", "json_schema": {"name": "research_summary", "strict": True, "schema": schema}}})
                else:
                    data = await self.request(client, "post", f"/models/{model}:generateContent", json={"systemInstruction": {"parts": [{"text": instruction}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": 6000}})
                try:
                    if self.name == "ollama":
                        if data.get("done_reason") == "length":
                            raise ValueError()
                        raw = data["message"]["content"]
                    elif self.name == "openai":
                        choice = data["choices"][0]
                        if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                            raise ValueError()
                        raw = choice["message"]["content"]
                    else:
                        choice = data["candidates"][0]
                        if choice.get("finishReason") != "STOP":
                            raise ValueError()
                        raw = "".join(p.get("text", "") for p in choice["content"]["parts"] if not p.get("thought"))
                    answer = json.loads(raw)
                    validate(answer)
                    return answer
                except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
                    # Only locally authored quality feedback may enter retry prompts.
                    feedback = getattr(exc, 'retry_feedback', '')
        raise ProviderError("模型回覆未通過格式或來源編號檢查（可能拒答或超過輸出長度）" + ('；' + feedback if feedback else ''))

    async def structured_vision_reply(self, model, instruction, content, images, schema, validate):
        """Structured multimodal request. Images are bounded JPEG base64 strings."""
        if self.name == "basic":
            raise ProviderError("基本摘錄不使用視覺 AI")
        validate_provider_config(AIProviderConfig(self.name, model))
        if not 1 <= len(images) <= 12 or any(len(x.get("data", "")) > 2_500_000 for x in images):
            raise ProviderError("影格數量或大小超過安全上限")
        async with httpx.AsyncClient(timeout=httpx.Timeout(240, connect=8), trust_env=False, follow_redirects=False) as client:
            if self.name == "ollama":
                # Some Ollama vision models return an empty response for a full
                # JSON Schema while supporting JSON mode. We still validate the
                # decoded object locally before accepting it.
                props = schema.get('properties', {}).get('notes', {}).get('items', {}).get('properties', {})
                example = {}
                for key, spec in props.items():
                    enum = spec.get('enum', []) if isinstance(spec, dict) else []
                    example[key] = enum[0] if enum else '...'
                shape = json.dumps({'notes': [example]}, ensure_ascii=False, separators=(',', ':'))
                message = {"role": "user", "content": content + "\n只輸出 JSON，格式例如：" + shape, "images": [x["data"] for x in images]}
                data = await self.request(client, "post", "/api/chat", json={"model": model, "stream": False, "format": "json",
                    "messages": [{"role": "system", "content": instruction}, message], "options": {"temperature": 0, "num_predict": 2400, "num_thread": 2, "num_ctx": 4096}})
                raw = data.get("message", {}).get("content", "")
            elif self.name == "openai":
                parts = [{"type": "text", "text": content}]
                parts += [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + x["data"], "detail": "low"}} for x in images]
                data = await self.request(client, "post", "/chat/completions", json={"model": model, "store": False,
                    "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": parts}],
                    "max_completion_tokens": 4000, "response_format": {"type": "json_schema", "json_schema": {"name": "visual_notes", "strict": True, "schema": schema}}})
                raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                parts = [{"text": content}]
                parts += [{"inlineData": {"mimeType": "image/jpeg", "data": x["data"]}} for x in images]
                data = await self.request(client, "post", f"/models/{model}:generateContent", json={"systemInstruction": {"parts": [{"text": instruction}]},
                    "contents": [{"role": "user", "parts": parts}], "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": 4000}})
                raw = "".join(p.get("text", "") for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []) if not p.get("thought"))
            try:
                answer = json.loads(raw)
                validate(answer)
                return answer
            except (ValueError, TypeError, KeyError, IndexError):
                raise ProviderError("視覺模型回覆未通過格式檢查；關鍵影格仍已保存") from None


def create_provider(config, **kwargs):
    return AIProvider(config, **kwargs)
