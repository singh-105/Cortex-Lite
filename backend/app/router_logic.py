import os
import sqlite3
import datetime
import requests
import ollama
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.db")

GREETINGS = {"hi", "hello", "heloo", "hey", "thanks", "thank you", "bye", "ok", "okay", "yo", "sup"}
PERSONAL_PATTERNS = ["my name is", "i am ", "i live in", "call me", "i'm "]
HARD_SIGNALS = ["what is", "what are", "why", "how does", "how do", "explain", "compare", "difference between", "teach me"]
TOOL_SIGNALS = ["weather", "waether", "wather", "temperature", "climate", "current time", "what time", "time now"]
CURRENCY_SIGNALS = ["dollar", "rupee", "rupp", "usd", "inr", "exchange rate", "currency"]

def get_recent_history(limit=6):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, query TEXT, used TEXT, answer TEXT)")
    rows = conn.execute("SELECT query, answer FROM logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    rows.reverse()
    history = []
    for q, a in rows:
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": a})
    return history

CODE_EXCLUDE = ["complexity", "algorithm", "big o", "runtime"]
def classify_tool(query: str) -> str:
    prompt = f"""Classify this query into exactly one category: WEATHER, CURRENCY, TIME, or NONE.
Use meaning, not exact spelling — handle typos and casual phrasing.
Query: "{query}"
Answer with one word only."""
    response = ollama.chat(model="phi3:mini", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"].strip().upper()

def is_tool_query(query: str) -> bool:
    return classify_tool(query) in {"WEATHER", "CURRENCY", "TIME"}

def handle_tool_query(query: str) -> str:
    kind = classify_tool(query)
    try:
        if kind == "CURRENCY":
            resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5).json()
            rate = resp["rates"]["INR"]
            return f"Live rate — 1 USD = {rate:.2f} INR (updated: {resp['time_last_update_utc']})"
        if kind == "TIME":
            now = datetime.datetime.now().strftime("%I:%M %p, %d %b %Y")
            return f"Current local time: {now}"
        resp = requests.get("https://wttr.in/Mumbai?format=3", timeout=5)
        return f"Live weather — {resp.text.strip()}"
    except Exception:
        return "Couldn't fetch live data right now, try again in a moment."


def handle_tool_query(query: str) -> str:
    q = query.lower()
    try:
        if "time" in q and "weather" not in q:
            now = datetime.datetime.now().strftime("%I:%M %p, %d %b %Y")
            return f"Current local time: {now}"
        resp = requests.get("https://wttr.in/Mumbai?format=3", timeout=5)
        return f"Live weather — {resp.text.strip()}"
    except Exception:
        return "Couldn't fetch live data right now, try again in a moment."

def should_escalate(query: str) -> bool:
    simple = query.strip().lower()
    if simple in GREETINGS or len(simple.split()) <= 2:
        return False
    prompt = f"""You are a routing classifier. Decide if this query needs a powerful cloud model (HARD) or can be handled by a small local model (EASY), regardless of typos or phrasing.

EASY: greetings, small talk, sharing personal info (name, location, preferences), simple direct facts, short casual replies.
HARD: anything needing real explanation, teaching, technical/domain knowledge, reasoning, coding, comparisons, multi-step answers — even if the query is short, misspelled, or casually worded.

Query: "{query}"
Answer with exactly one word: EASY or HARD."""
    response = ollama.chat(
        model="phi3:mini",
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
    response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages)
    return response.choices[0].message.content

def log_call(query: str, used: str, answer: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, query TEXT, used TEXT, answer TEXT)")
    conn.execute("INSERT INTO logs (query, used, answer) VALUES (?, ?, ?)", (query, used, answer))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, query TEXT, used TEXT, answer TEXT)")
    rows = conn.execute("SELECT query, used, answer FROM logs ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return [{"query": r[0], "used": r[1], "answer": r[2]} for r in rows]