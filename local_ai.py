"""Loopback-only structured generation shared by summary and comparison features."""
import json
import httpx

URL = "http://127.0.0.1:11434"


async def structured_reply(model, instruction, content, schema, validate):
    """Retry malformed model output once; never silently accept invalid evidence."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8), trust_env=False) as client:
        reason = ""
        for attempt in range(2):
            response = await client.post(URL + "/api/chat", json={
                "model": model, "stream": False, "format": schema,
                "messages": [{"role": "system", "content": instruction},
                             {"role": "user", "content": content + (f"\n上次格式錯誤：{reason}。重新寫出完整具體內容。" if attempt else "")}],
                "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 3000},
            })
            response.raise_for_status()
            data = response.json()
            try:
                if data.get("done_reason") == "length":
                    raise ValueError("模型輸出超過上限")
                answer = json.loads(data["message"]["content"])
                validate(answer)
                return answer
            except (ValueError, KeyError, TypeError) as exc:
                reason = str(exc)[:160]
        raise ValueError("模型回覆未通過檢查：" + reason)
