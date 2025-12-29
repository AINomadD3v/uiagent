import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from model import ChatMessageContent, LlmServiceChatRequest

from services.llm.prompt.messages import build_llm_payload_messages

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")



async def generate_chat_completion_stream(
    request_data: LlmServiceChatRequest,
) -> AsyncGenerator[str, None]:
    if not DEEPSEEK_API_KEY:
        yield f"event: error\ndata: {json.dumps({'error': 'DeepSeek API key is not configured'})}\n\n"
        yield f"event: end-of-stream\ndata: {json.dumps({'message': 'Stream terminated'})}\n\n"
        return

    messages = build_llm_payload_messages(
        user_prompt=request_data.prompt,
        context_data=dict(request_data.context or {}),
        history=request_data.history,
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }

    tool_choice_setting = "auto"
    full_response_content = ""
    tool_calls_to_process: Optional[List[Dict[str, Any]]] = None

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            payload = {
                "model": request_data.model or DEEPSEEK_DEFAULT_MODEL,
                "messages": messages,
                "stream": True,
                "temperature": request_data.temperature or 0.7,
                "max_tokens": request_data.max_tokens or 2048,
                "tool_choice": tool_choice_setting,
            }

            async with client.stream(
                "POST", DEEPSEEK_API_URL, json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    yield f"event: error\ndata: {json.dumps({'error': err.decode(errors='replace')})}\n\n"
                    yield f"event: end-of-stream\ndata: {json.dumps({'message': 'Stream failed'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line == "data: [DONE]":
                        yield f"event: end-of-stream\ndata: {json.dumps({'message': 'Complete'})}\n\n"
                        return

                    if not line.startswith("data: "):
                        continue

                    try:
                        data = json.loads(line[6:])
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})

                        if delta.get("content"):
                            yield f"data: {json.dumps(delta['content'])}\n\n"


                    except Exception as e:
                        logger.warning(f"DeepSeek stream chunk parse error: {e}")

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            yield f"event: end-of-stream\ndata: {json.dumps({'message': 'Stream exception'})}\n\n"
            return
