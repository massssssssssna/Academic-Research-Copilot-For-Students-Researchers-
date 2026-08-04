import time
import json
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

# Test Prompts
TEST_PROMPTS = [
    {"name": "Prompt 1 (General Chat)", "text": "What can you help me with as an academic research copilot?"},
    {"name": "Prompt 2 (Email Intent)", "text": "Show me my recent emails and summarize the key topics."},
    {"name": "Prompt 3 (Task Creation)", "text": "Add a task to prepare research presentation slides for Friday."}
]

# Knob Configurations
KNOB_CONFIGS = [
    {
        "config_name": "Config A (Default / Heavy)",
        "model": "llama-3.3-70b-versatile",
        "temperature": 0.7,
        "max_tokens": 1000,
        "top": 25
    },
    {
        "config_name": "Config B (Ultra Fast / Low Tokens)",
        "model": "llama-3.1-8b-instant",
        "temperature": 0.1,
        "max_tokens": 250,
        "top": 5
    },
    {
        "config_name": "Config C (Balanced / Optimal)",
        "model": "llama-3.3-70b-versatile",
        "temperature": 0.3,
        "max_tokens": 400,
        "top": 10
    },
    {
        "config_name": "Config D (High Creativity / High Temp)",
        "model": "llama-3.1-8b-instant",
        "temperature": 0.9,
        "max_tokens": 800,
        "top": 20
    }
]

def run_benchmark():
    import os
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        from app.config import settings
        groq_api_key = settings.GROQ_API_KEY

    print("======================================================================")
    print("JARVIS AI AGENT: TUNING KNOBS & LATENCY BENCHMARK TEST")
    print("======================================================================")
    
    results = []

    for cfg in KNOB_CONFIGS:
        print(f"\n[Testing Configuration]: {cfg['config_name']}")
        print(f"   Model: {cfg['model']} | Temp: {cfg['temperature']} | MaxTokens: {cfg['max_tokens']} | Top: {cfg['top']}")
        
        cfg_results = []
        for p in TEST_PROMPTS:
            start_time = time.time()
            try:
                llm = ChatGroq(
                    groq_api_key=groq_api_key,
                    model_name=cfg["model"],
                    temperature=cfg["temperature"],
                    max_tokens=cfg["max_tokens"]
                )
                response = llm.invoke([HumanMessage(content=p["text"])])
                elapsed = time.time() - start_time
                content = response.content
                token_count = len(content.split()) # rough token count
                tps = round(token_count / elapsed, 2) if elapsed > 0 else 0
                
                print(f"   + [{p['name']}] Latency: {elapsed:.2f}s | Speed: ~{tps} words/s | Length: {len(content)} chars")
                
                cfg_results.append({
                    "prompt": p["name"],
                    "latency_sec": round(elapsed, 3),
                    "char_count": len(content),
                    "words_per_sec": tps,
                    "response_preview": content[:100] + "..."
                })
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"   X [{p['name']}] Error: {str(e)[:80]}")
                cfg_results.append({
                    "prompt": p["name"],
                    "latency_sec": round(elapsed, 3),
                    "error": str(e)
                })

        results.append({
            "config_name": cfg["config_name"],
            "config": cfg,
            "prompt_results": cfg_results
        })

    print("\n======================================================================")
    print("BENCHMARK SUMMARY JSON:")
    print("======================================================================")
    print(json.dumps(results, indent=2))
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
