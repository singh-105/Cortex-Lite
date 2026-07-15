import ollama

def should_escalate(query: str) -> bool:
    prompt = f"Classify this query as EASY or HARD only. Query: {query}"
    response = ollama.chat(
        model="qwen2.5:0.5b",
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = response["message"]["content"].strip().upper()
    return "HARD" in verdict

def handle_locally(query: str) -> str:
    return f"[local] Echo: {query}"