import asyncio
import json
import logging

from services.groq_client import chat_completion

logger = logging.getLogger(__name__)


class LearningAgent:
    async def run(self, notes: dict, num_flashcards: int = 10, num_questions: int = 5, difficulty: str = "intermediate") -> dict:
        notes_text = json.dumps(notes)

        prompt = f"""You are an expert educator creating study materials from the following notes.

Generate exactly {num_flashcards} flashcards and {num_questions} multiple-choice quiz questions.

Difficulty level: {difficulty}
- Beginner: Simple concepts, basic recall, straightforward questions
- Intermediate: Moderate complexity, some analysis, practical application
- Advanced: Complex concepts, deep analysis, critical thinking, synthesis

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
            if not isinstance(data, dict):
                raise ValueError(f"Expected JSON object, got {type(data).__name__}")
            for i, q in enumerate(data.get("quiz_questions", [])):
                q["id"] = i
            return data
        except Exception as e:
            logger.error("Failed to parse learning material: %s", e)
            logger.debug("Raw output was: %s", raw)
            return {"flashcards": [], "quiz_questions": []}
