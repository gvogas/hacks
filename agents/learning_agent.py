import asyncio
import json

from services.groq_client import chat_completion


class LearningAgent:
    async def run(self, notes: dict, num_flashcards: int = 10, num_questions: int = 5) -> dict:
        notes_text = json.dumps(notes)

        prompt = f"""You are an expert educator creating study materials from the following notes.

Generate exactly {num_flashcards} flashcards and {num_questions} multiple-choice quiz questions.

Return a JSON object with this exact structure:
{{
  "flashcards": [
    {{"front": "Question or term", "back": "Answer or definition"}}
  ],
  "quiz_questions": [
    {{
      "id": 0,
      "question": "Question text",
      "options": ["A. option", "B. option", "C. option", "D. option"],
      "answer": "A",
      "topic_tag": "specific sub-topic this question covers",
      "explanation": "Why this answer is correct"
    }}
  ]
}}

The "answer" field must be just the letter (A, B, C, or D).
Cover different aspects of the material. Tag each question with a specific sub-topic for weak-area tracking.

Study notes:
{notes_text}"""

        raw = await asyncio.to_thread(
            chat_completion,
            [{"role": "user", "content": prompt}],
            True,
        )
        try:
            data = json.loads(raw)
            for i, q in enumerate(data.get("quiz_questions", [])):
                q["id"] = i
            return data
        except Exception:
            return {"flashcards": [], "quiz_questions": []}
