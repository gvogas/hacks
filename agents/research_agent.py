import os
from tavily import TavilyClient


class ResearchAgent:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        return self._client

    async def run(self, topic: str) -> list[dict]:
        client = self._get_client()
        max_results = int(os.getenv("MAX_SEARCH_RESULTS", 6))
        response = client.search(
            query=topic,
            search_depth="advanced",
            max_results=max_results,
        )
        return response.get("results", [])
