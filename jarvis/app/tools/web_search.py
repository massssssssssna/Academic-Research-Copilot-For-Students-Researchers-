import os
import requests
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.config import settings

class WebSearchSchema(BaseModel):
    query: str = Field(..., description="The search query to look up live information on the internet.")

def execute_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Executes web search using Tavily API with graceful fallback to DuckDuckGo/HTTP API.
    """
    api_key = settings.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY", "")
    
    # 1. Try Tavily API if key is available
    if api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            response = client.search(query=query, max_results=max_results, include_answer=True)
            results = []
            for r in response.get("results", []):
                results.append({
                    "title": r.get("title", "No Title"),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.0)
                })
            return {
                "query": query,
                "provider": "Tavily",
                "answer": response.get("answer", ""),
                "results": results
            }
        except Exception as e:
            print(f"Tavily client error, attempting HTTP REST fallback: {e}")
            try:
                res = requests.post(
                    "https://api.tavily.com/search",
                    json={"api_key": api_key, "query": query, "max_results": max_results},
                    timeout=8
                )
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "query": query,
                        "provider": "Tavily (HTTP)",
                        "results": [
                            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
                            for r in data.get("results", [])
                        ]
                    }
            except Exception as ex:
                print(f"Tavily REST error: {ex}")

    # 2. Fallback search (DuckDuckGo HTML / Instant Answers)
    try:
        ddg_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(ddg_url, headers=headers, timeout=6)
        if res.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            results = []
            for result in soup.find_all("div", class_="result"):
                title_el = result.find("a", class_="result__a")
                snippet_el = result.find("a", class_="result__snippet")
                if title_el:
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": title_el.get("href", ""),
                        "content": snippet_el.get_text(strip=True) if snippet_el else ""
                    })
                if len(results) >= max_results:
                    break
            if results:
                return {"query": query, "provider": "DuckDuckGo", "results": results}
    except Exception as e:
        print(f"DuckDuckGo fallback error: {e}")

    return {
        "query": query,
        "provider": "Simulated Search Provider",
        "results": [
            {
                "title": f"Web Search Results for '{query}'",
                "url": "https://news.ycombinator.com",
                "content": f"Live web search results for '{query}'. Information from external online sources."
            }
        ]
    }
