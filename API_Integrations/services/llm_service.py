import os
from openai import OpenAI


# ── NVIDIA DeepSeek v3.2 config ──────────────────
_MODEL = "deepseek-ai/deepseek-v3.2"
_TEMPERATURE = 1
_TOP_P = 0.95
_MAX_TOKENS = 8192
_EXTRA_BODY = {"chat_template_kwargs": {"thinking": True}}


def get_llm_client():
    """Create and return an OpenAI-compatible client for NVIDIA API."""
    api_key = os.getenv("NVIDIA_API_KEY", "")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )


async def generate_response(prompt: str):
    """Generate a single LLM response for a given prompt (with thinking enabled)."""
    client = get_llm_client()

    completion = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=_TEMPERATURE,
        top_p=_TOP_P,
        max_tokens=_MAX_TOKENS,
        extra_body=_EXTRA_BODY,
    )

    return completion.choices[0].message.content
