import os
import sqlite3
import ollama
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.db")

GREETINGS = {"hi", "hello", "heloo", "hey", "thanks", "thank you", "bye", "ok", "okay", "yo", "sup"}

def get_recent_history(limit=6):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, query TEXT, used TEXT, answer TEXT)"
    )
    rows = conn.execute("SELECT query, answer FROM logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    rows.reverse()
    history = []
    for q, a in rows:
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": a})
    return history

def should_escalate(query: str) -> bool:
    simple = query.strip().lower()
    if simple in GREETINGS or len(simple.split()) <= 3:
        return False
    prompt = f"""Classify this query as EASY or HARD.
EASY = greetings, casual chat, simple personal questions, short facts.
HARD = explanation, teaching, technical concepts, reasoning, coding, comparisons.
One word only: EASY or HARD.
Query: {query}"""
    response = ollama.chat(
        model="qwen2.5:0.5b",
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = response["message"]["content"].strip().upper()
    return "HARD" in verdict

def handle_locally(query: str) -> str:
    messages = get_recent_history() + [{"role": "user", "content": query}]
    response = ollama.chat(model="qwen2.5:0.5b", messages=messages)
    return response["message"]["content"]

def handle_via_api(query: str) -> str:
    messages = get_recent_history() + [{"role": "user", "content": query}]
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
    )
    return response.choices[0].message.content

def log_call(query: str, used: str, answer: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, query TEXT, used TEXT, answer TEXT)"
    )
    conn.execute("INSERT INTO logs (query, used, answer) VALUES (?, ?, ?)", (query, used, answer))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, query TEXT, used TEXT, answer TEXT)"
    )
    rows = conn.execute("SELECT query, used, answer FROM logs ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return [{"query": r[0], "used": r[1], "answer": r[2]} for r in rows]