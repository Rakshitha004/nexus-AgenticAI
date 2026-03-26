import os
from openai import OpenAI
from Intent_Agent3.base import BaseAgent, Message


def _get_client():
    api_key = os.getenv("NVIDIA_API_KEY", "")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )


_MODEL = "deepseek-ai/deepseek-v3.2"
_TEMPERATURE = 1
_TOP_P = 0.95
_MAX_TOKENS = 8192
_EXTRA_BODY = {"chat_template_kwargs": {"thinking": True}}


class LLMAgent(BaseAgent):

    def __init__(self):
        super().__init__("llm_agent")

    async def handle_message(self, message: Message):
        client = _get_client()

        completion = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "Always respond in English."},
                {"role": "user", "content": message.text}
            ],
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            max_tokens=_MAX_TOKENS,
            extra_body=_EXTRA_BODY,
        )

        response = completion.choices[0].message.content

        return Message(sender="llm_agent", text=response)

    async def stream(self, prompt: str):
        client = _get_client()

        completion = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "Always respond in English."},
                {"role": "user", "content": prompt}
            ],
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            max_tokens=_MAX_TOKENS,
            extra_body=_EXTRA_BODY,
            stream=True,
        )

        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield reasoning
            if delta and delta.content:
                yield delta.content
