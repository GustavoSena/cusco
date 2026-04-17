from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator

import openai

from cusco.models import ChatMessage, EntityReport
from cusco.overview import truncate_report_for_llm

SYSTEM_PROMPT_TEMPLATE = """\
You are an analyst specializing in Portuguese company intelligence. \
You have access to a detailed report for the entity with NIF {nif}. \
Answer the user's questions based on the data below. \
Be concise and factual. Give direct answers — do not show calculations, \
formulas, or step-by-step reasoning unless the user explicitly asks for it. \
Do not over-explain or repeat data the user can already see on screen. \
When the data does not contain enough information to answer a question, \
say so clearly.

Report data:
{report_json}
"""

def build_system_prompt(report: EntityReport) -> str:
    data = truncate_report_for_llm(report)
    report_json = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return SYSTEM_PROMPT_TEMPLATE.format(nif=report.nif, report_json=report_json)


def build_messages(
    system_prompt: str,
    history: list[ChatMessage],
    user_message: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


async def stream_chat(
    report: EntityReport,
    message: str,
    history: list[ChatMessage],
) -> AsyncGenerator[str, None]:
    client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.getenv("CUSCO_CHAT_MODEL", "gpt-5.1")

    system_prompt = build_system_prompt(report)
    messages = build_messages(system_prompt, history, message)

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield f"data: {delta.content}\n\n"
    except openai.RateLimitError:
        yield "data: [Error: OpenAI rate limit exceeded. Please try again in a moment.]\n\n"
    except openai.APIError as e:
        yield f"data: [Error: {e.message}]\n\n"

    yield "data: [DONE]\n\n"
