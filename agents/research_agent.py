import asyncio
import os

from requests import RequestException
from tavily import TavilyClient

from services.exceptions import ExternalServiceError


class ResearchAgent:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise ExternalServiceError(
                    "Tavily",
                    "TAVILY_API_KEY is not configured.",
                )
            self._client = TavilyClient(api_key=api_key)
        return self._client

    async def run(self, topic: str) -> list[dict]:
        client = self._get_client()
        max_results = int(os.getenv("MAX_SEARCH_RESULTS", 6))
        try:
            response = await asyncio.to_thread(
                client.search,
                query=topic,
                search_depth="advanced",
                max_results=max_results,
            )
        except RequestException as exc:
            raise ExternalServiceError(
                "Tavily",
                "Could not connect to Tavily search. Check your network/proxy settings and TAVILY_API_KEY.",
            ) from exc
        except Exception as exc:
            raise ExternalServiceError(
                "Tavily",
                "Tavily search failed. Check TAVILY_API_KEY and service availability.",
            ) from exc
        return response.get("results", [])
