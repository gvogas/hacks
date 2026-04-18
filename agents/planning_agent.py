import asyncio
import json
import logging

from services.groq_client import chat_completion

logger = logging.getLogger(__name__)


class PlanningAgent:
    async def run(
        self,
        notes: dict,
        weak_topics: list[str],
        available_days: int,
        hours_per_day: float,
    ) -> dict:
        key_concepts = notes.get("key_concepts", [])
        sections = [s["title"] for s in notes.get("sections", [])]
        total_hours = available_days * hours_per_day

        weak_str = ", ".join(weak_topics) if weak_topics else "none identified"

        prompt = f"""You are a personalized learning coach. Create a {available_days}-day study plan.

Student details:
- Available: {available_days} days, {hours_per_day} hours/day ({total_hours} total hours)
- Key concepts to cover: {", ".join(key_concepts)}
- Topic sections: {", ".join(sections)}
- Weak areas (need extra focus): {weak_str}

Rules:
- Spread content evenly but give weak areas 1.5x time
- Mix activities: review notes, flashcards, practice questions, summary writing
- Day 1 should be overview; final day should be review/mock quiz

Return a JSON object with this exact structure:
{{
  "plan": [
    {{
      "day": 1,
      "focus": "Main focus for this day",
      "tasks": [
        {{
          "topic": "Topic name",
          "activity": "Read notes / Do flashcards / Practice questions / Write summary",
          "duration_mins": 30,
          "priority": "high/medium/low",
          "is_weak_area": true/false
        }}
      ]
    }}
  ]
}}"""

        raw = await asyncio.to_thread(
            chat_completion,
            [{"role": "user", "content": prompt}],
            True,
        )
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError(f"Expected JSON object, got {type(data).__name__}")
            return data
        except Exception as e:
            logger.error("Failed to parse study plan: %s", e)
            logger.debug("Raw output was: %s", raw)
            return {"plan": []}
