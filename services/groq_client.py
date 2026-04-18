import os
from groq import Groq

_client = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def chat_completion(messages: list, json_mode: bool = True) -> str:
    client = get_groq_client()
    kwargs = {
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
