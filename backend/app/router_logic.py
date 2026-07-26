import os
import sqlite3
import datetime
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.db")

GREETINGS = {"hi", "hello", "hey", "thanks", "thank you", "bye", "ok", "okay", "yo", "sup"}
HARD_SIGNALS = ["what is", "what are", "why", "how does", "how do", "explain", "compare", "difference between", "teach me"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT, name TEXT, picture TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY, user_id TEXT, query TEXT, used TEXT, answer TEXT
    )""")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(logs)").fetchall()]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE logs ADD COLUMN user_id TEXT")
    conn.commit()
    conn.close()

init_db()

def upsert_user(user_id: str, email: str, name: str, picture: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO users (id, email, name, picture) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET email=excluded.email, name=excluded.name, picture=excluded.picture",
        (user_id, email, name, picture),
    )
    conn.commit()
    conn.close()

def get_recent_history(user_id: str, limit=6):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT query, answer FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    rows.reverse()
    history = []
    for q, a in rows:
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": a})
    return history

def classify_tool(query: str) -> str:
    prompt = f"""Classify this query into exactly one category: WEATHER, CURRENCY, TIME, CALCULATOR, CRYPTO, or NONE.
CALCULATOR = any arithmetic/math expression to compute (e.g. "what is 45*12", "calculate 200/7").
CRYPTO = asking for the current price of a cryptocurrency (e.g. "price of bitcoin", "how much is ethereum").
Use meaning, not exact spelling — handle typos and casual phrasing.
Query: "{query}"
Answer with one word only."""
    response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content.strip().upper()

import re

def looks_like_math(query: str) -> bool:
    q = query.lower()
    has_numbers = bool(re.search(r"\d", q))
    has_math_words = any(w in q for w in ["calculate", "what is", "+", "-", "*", "/", "times", "plus", "minus", "divided"])
    has_operator = bool(re.search(r"[\d\s]*[\+\-\*/][\d\s]", q))
    return has_numbers and (has_operator or "calculate" in q)

def is_tool_query(query: str) -> bool:
    if looks_like_math(query):
        return True
    return classify_tool(query) in {"WEATHER", "CURRENCY", "TIME", "CALCULATOR", "CRYPTO"}

CRYPTO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "cardano": "cardano", "ada": "cardano",
    "ripple": "ripple", "xrp": "ripple",
}

def extract_expression(query: str) -> str:
    prompt = f"""Extract only the pure math expression from this query, nothing else.
Example: "what is 45 times 12" -> "45*12"
Example: "calculate 200 divided by 7" -> "200/7"
Query: "{query}"
Answer with only the expression, no words, no explanation."""
    response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content.strip()

def safe_eval(expr: str):
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expr):
        raise ValueError("unsafe expression")
    return eval(expr, {"__builtins__": {}}, {})

def extract_coin(query: str) -> str:
    q = query.lower()
    for name, coin_id in CRYPTO_IDS.items():
        if name in q:
            return coin_id
    return "bitcoin"

def handle_tool_query(query: str) -> str:
    kind = "CALCULATOR" if looks_like_math(query) else classify_tool(query)
    try:
        if kind == "CALCULATOR":
            expr = extract_expression(query)
            result = safe_eval(expr)
            return f"CALC_CARD|{expr}|{result}"
        if kind == "CRYPTO":
            coin_id = extract_coin(query)
            resp = requests.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,inr&include_24hr_change=true",
                timeout=5,
            ).json()
            data = resp.get(coin_id, {})
            usd = data.get("usd", "N/A")
            inr = data.get("inr", "N/A")
            change = data.get("usd_24h_change", 0)
            return f"CRYPTO_CARD|{coin_id}|{usd}|{inr}|{change:.2f}"
        if kind == "CURRENCY":
            resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5).json()
            rate = resp["rates"]["INR"]
            return f"Live rate — 1 USD = {rate:.2f} INR (updated: {resp['time_last_update_utc']})"
        if kind == "TIME":
            ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
            now = datetime.datetime.now(ist).strftime("%I:%M %p, %d %b %Y")
            return f"Current local time: {now}"
        fmt = "%C|%t|%f|%h|%w|%p|%P"
        resp = requests.get(f"https://wttr.in/Mumbai?format={fmt}&m", timeout=5)
        parts = resp.text.strip().split("|")
        if len(parts) == 7:
            cond, temp, feels, hum, wind, precip, pressure = parts
            return f"WEATHER_CARD|Mumbai|{cond.strip()}|{temp.strip()}|{feels.strip()}|{hum.strip()}|{wind.strip()}|{pressure.strip()}"
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
    response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}])
    verdict = response.choices[0].message.content.strip().upper()
    return "HARD" in verdict

def handle_locally(query: str, user_id: str) -> str:
    messages = get_recent_history(user_id) + [{"role": "user", "content": query}]
    response = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages)
    return response.choices[0].message.content

def handle_via_api(query: str, user_id: str) -> str:
    messages = get_recent_history(user_id) + [{"role": "user", "content": query}]
    response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
    return response.choices[0].message.content

def log_call(user_id: str, query: str, used: str, answer: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO logs (user_id, query, used, answer) VALUES (?, ?, ?, ?)", (user_id, query, used, answer))
    conn.commit()
    conn.close()

def get_history(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, query, used, answer FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT 30", (user_id,)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "query": r[1], "used": r[2], "answer": r[3]} for r in rows]

def delete_entry(entry_id: int, user_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM logs WHERE id = ? AND user_id = ?", (entry_id, user_id))
    conn.commit()
    conn.close()