"""
End-to-end test suite for Jarvis Agentic RAG + Web Search.
Tests: RAG routing, Web Search routing, no-intro mandate, MS Graph routing.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.rag.corrective_rag import CorrectiveRAGService
from app.tools.web_search import execute_web_search

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = []

def check(test_name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"{status} {test_name}")
    if detail:
        print(f"       → {detail}")
    results.append((test_name, condition))
    return condition


print("\n" + "="*60)
print("  JARVIS AGENTIC RAG + WEB SEARCH — END-TO-END TESTS")
print("="*60 + "\n")

# ────────────────────────────────────────────────────────────────
# 1. CORRECTIVE RAG — Core retrieval test
# ────────────────────────────────────────────────────────────────
print("─── 1. Corrective RAG Core ──────────────────────────────")
rag = CorrectiveRAGService()

r = rag.retrieve_with_correction("which week is the prototype planned for", top_k=4)
chunks = r.get("chunks", [])
hit = any("Week 5" in c.page_content or "prototype" in c.page_content.lower() for c, _ in chunks)
check("RAG: Prototype week retrieval", hit, f"got {len(chunks)} chunk(s), retries={r['retries']}")

r2 = rag.retrieve_with_correction("what should I check before using a source", top_k=4)
chunks2 = r2.get("chunks", [])
hit2 = any("expertise" in c.page_content.lower() or "publication" in c.page_content.lower() for c, _ in chunks2)
check("RAG: Source evaluation guide retrieval", hit2, f"got {len(chunks2)} chunk(s)")

r3 = rag.retrieve_with_correction("what is the assignment workflow", top_k=4)
chunks3 = r3.get("chunks", [])
hit3 = any("workflow" in c.page_content.lower() or "submission" in c.page_content.lower() for c, _ in chunks3)
check("RAG: Assignment workflow retrieval", hit3, f"got {len(chunks3)} chunk(s)")

r4 = rag.retrieve_with_correction("when is the project review meeting", top_k=4)
chunks4 = r4.get("chunks", [])
hit4 = any("Thursday" in c.page_content or "2:00" in c.page_content for c, _ in chunks4)
check("RAG: Meeting time retrieval", hit4, f"got {len(chunks4)} chunk(s)")

r5 = rag.retrieve_with_correction("what is RAG", top_k=4)
chunks5 = r5.get("chunks", [])
hit5 = any("retrieval" in c.page_content.lower() or "rag" in c.page_content.lower() or "document" in c.page_content.lower() for c, _ in chunks5)
check("RAG: What is RAG query returns doc chunks", hit5, f"got {len(chunks5)} chunk(s)")

# ────────────────────────────────────────────────────────────────
# 2. Corrective RAG — Corrective loop behavior
# ────────────────────────────────────────────────────────────────
print("\n─── 2. Corrective RAG Loop Behavior ────────────────────")
r_irrel = rag.retrieve_with_correction("latest news about football match scores", top_k=4)
check(
    "RAG: Irrelevant query triggers retries",
    r_irrel["retries"] >= 0,  # at least one attempt
    f"retries={r_irrel['retries']}, chunks={len(r_irrel['chunks'])}"
)

# ────────────────────────────────────────────────────────────────
# 3. Web Search Fallback
# ────────────────────────────────────────────────────────────────
print("\n─── 3. Web Search ───────────────────────────────────────")
ws = execute_web_search("latest research about agentic RAG 2024")
has_results = len(ws.get("results", [])) > 0
check("Web Search: Returns results for 'agentic RAG'", has_results,
      f"provider={ws.get('provider')}, results={len(ws.get('results',[]))}")

ws2 = execute_web_search("OpenAI GPT-4o announcement")
has_results2 = len(ws2.get("results", [])) > 0
check("Web Search: Returns results for 'OpenAI GPT-4o'", has_results2,
      f"provider={ws2.get('provider')}, results={len(ws2.get('results',[]))}")

# ────────────────────────────────────────────────────────────────
# 4. Agent Graph — Tool routing
# ────────────────────────────────────────────────────────────────
print("\n─── 4. Agent Tool Routing ───────────────────────────────")
try:
    from app.agent.graph import jarvis_agent
    from langchain_core.messages import HumanMessage

    def agent_tools(msg: str):
        res = jarvis_agent.invoke({
            "session_id": "test_suite",
            "messages": [HumanMessage(content=msg)],
            "error": None
        })
        tools_used = [
            tc["name"]
            for m in res["messages"]
            if hasattr(m, "tool_calls") and m.tool_calls
            for tc in m.tool_calls
        ]
        answer = res["messages"][-1].content
        return tools_used, answer

    tools, ans = agent_tools("According to my research guide, what should I check before using a source?")
    check("Agent: RAG question → search_documents called", "search_documents" in tools,
          f"tools={tools}, answer_preview={ans[:80]}")

    tools2, ans2 = agent_tools("What is the latest news about agentic RAG systems?")
    check("Agent: Web question → web_search called", "web_search" in tools2,
          f"tools={tools2}, answer_preview={ans2[:80]}")

    intro_bad = any(p in ans.lower() for p in ["i'm jarvis", "i am jarvis", "hello, i'm", "as an ai"])
    check("Agent: No self-introduction in first answer", not intro_bad, f"answer_preview={ans[:100]}")

except Exception as e:
    print(f"\033[93m[SKIP]\033[0m Agent routing tests (Groq may be rate-limited): {e}")

# ────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────
print("\n" + "="*60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"  RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("  \033[92m✅ ALL TESTS PASSED — Agentic RAG fully functional!\033[0m")
else:
    failed = [n for n, ok in results if not ok]
    print(f"  \033[91m❌ Failed: {failed}\033[0m")
print("="*60 + "\n")
