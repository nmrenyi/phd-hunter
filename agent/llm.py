import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from .config import LLM_MODEL, LLM_NUM_CTX, LLM_NUM_PREDICT, LLM_TEMPERATURE

logger = logging.getLogger(__name__)

_llm: ChatOllama | None = None


def get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            num_ctx=LLM_NUM_CTX,
            num_predict=LLM_NUM_PREDICT,
        )
    return _llm


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_json(text: str) -> dict | list | None:
    text = _strip_think(text)
    for attempt in (
        text,
        re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text),
        re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text),
    ):
        if attempt is None:
            continue
        s = attempt if isinstance(attempt, str) else attempt.group(1)
        try:
            return json.loads(s)
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def call(system: str, user: str) -> dict | list | None:
    """Call the LLM and return parsed JSON, or None on failure."""
    messages = [
        SystemMessage(content=system),
        # /no_think disables Qwen3 extended reasoning
        HumanMessage(content=user + "\n\n/no_think"),
    ]
    try:
        resp = get_llm().invoke(messages)
        result = _parse_json(resp.content)
        if result is None:
            logger.warning("LLM returned non-JSON: %.120s", resp.content)
        return result
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return None
