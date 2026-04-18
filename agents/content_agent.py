import asyncio
import json
import os

from services.groq_client import chat_completion

MAX_NOTES = int(os.getenv("MAX_NOTES_CHARS", 8000))


class ContentAgent:
    async def run(
        self,
        topic: str,
        search_results: list[dict],
        uploaded_texts: list[str] | None = None,
    ) -> dict:
        snippets = "\n\n".join(
            f"Source: {r.get('url', '')}\n{r.get('content', '')}"
            for r in search_results
        )
        file_text = "\n\n".join(uploaded_texts or [])

        context = f"=== WEB RESEARCH ===\n{snippets}"
        if file_text:
            context += f"\n\n=== UPLOADED MATERIALS ===\n{file_text}"

        context = context[:MAX_NOTES]

        topic_label = f' on the topic: "{topic}"' if topic else ''
        prompt = f"""You are an expert educator. Using the provided research materials, create comprehensive structured study notes{topic_label}.

Return a JSON object with this exact structure:
{{
  "summary": "2-3 sentence overview of the topic",
  "key_concepts": ["concept1", "concept2", "concept3", ...],
  "sections": [
    {{
      "title": "Section Title",
      "content": "Detailed explanation of this section...",
      "image_description": "Brief description of what image would visually represent this section for visual learners"
    }}
  ]
}}

For each section, provide a brief image_description that describes what visual element would help illustrate that concept.

Research materials:
{context}"""

        raw = await asyncio.to_thread(
            chat_completion,
            [{"role": "user", "content": prompt}],
            True,
        )
        try:
            return json.loads(raw)
        except Exception:
            return {
                "summary": raw[:500],
                "key_concepts": [],
                "sections": [{"title": "Notes", "content": raw}],
            }
