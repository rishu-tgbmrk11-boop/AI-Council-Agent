# tools/web_search.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def web_search(query: str) -> str:
    """
    Search the web for current information. Use this when you need facts,
    statistics, recent news, or data you're not confident about.
    Returns the top 2 results with sources.
    """
    print(f"\n🔧 [TOOL] web_search(query='{query}')")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not set."

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 2,
        "include_answer": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        output = ""
        if data.get("answer"):
            output += f"Direct Answer: {data['answer']}\n\n"

        for i, r in enumerate(data.get("results", []), 1):
            output += f"[{i}] {r.get('title', 'Untitled')}\n"
            output += f"URL: {r.get('url', 'N/A')}\n"
            snippet = r.get("content", "")[:400]
            output += f"Content: {snippet}\n\n"

        return output.strip() or "No results found."
    except Exception as e:
        return f"Search error: {str(e)[:100]}"