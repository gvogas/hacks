import os
from groq import Groq
from services.exceptions import ExternalServiceError

_client = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ExternalServiceError(
                "Groq",
                "GROQ_API_KEY is not configured.",
            )
        _client = Groq(api_key=api_key)
    return _client


def chat_completion(messages: list, json_mode: bool = True) -> str:
    client = get_groq_client()
    kwargs = {
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as exc:
        raise ExternalServiceError(
            "Groq",
            "Groq request failed. Check GROQ_API_KEY, GROQ_MODEL, and network/proxy settings.",
        ) from exc
