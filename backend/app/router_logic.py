import os
import json
import sqlite3
import datetime
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.db")
DAILY_CLOUD_LIMIT = 20
FAST_MODEL = "llama-3.1-8b-instant"
STRONG_MODEL = "llama-3.3-70b-versatile"

GREETINGS = {"hi", "hello", "hey", "thanks", "thank you", "bye", "ok", "okay", "yo", "sup"}

# ---------- Database ----------

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
    if "created_at" not in cols:
        conn.execute("ALTER TABLE logs ADD COLUMN created_at TEXT")
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

def log_call(user_id: str, query: str, used: str, answer: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO logs (user_id, query, used, answer, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, query, used, answer, datetime.datetime.utcnow().isoformat()),
    )
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

def get_today_cloud_count(user_id: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    today = datetime.date.today().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM logs WHERE user_id = ? AND used = 'api' AND date(created_at) = ?",
        (user_id, today),
    ).fetchone()
    conn.close()
    return row[0] if row else 0

def get_usage(user_id: str) -> dict:
    used = get_today_cloud_count(user_id)
    return {"used": used, "limit": DAILY_CLOUD_LIMIT, "percent": min(100, round((used / DAILY_CLOUD_LIMIT) * 100))}

# ---------- Tool implementations ----------

def tool_get_weather(city: str = "Mumbai") -> str:
    try:
        fmt = "%C|%t|%f|%h|%w|%p|%P"
        resp = requests.get(f"https://wttr.in/{city}?format={fmt}&m", timeout=5)
        parts = resp.text.strip().split("|")
        if len(parts) == 7:
            cond, temp, feels, hum, wind, precip, pressure = parts
            return f"WEATHER_CARD|{city}|{cond.strip()}|{temp.strip()}|{feels.strip()}|{hum.strip()}|{wind.strip()}|{pressure.strip()}"
        return f"Live weather — {resp.text.strip()}"
    except Exception:
        return "Couldn't fetch weather right now."

def tool_get_time() -> str:
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist).strftime("%I:%M %p, %d %b %Y")
    return f"Current local time: {now}"

def tool_get_currency(from_currency: str = "USD", to_currency: str = "INR") -> str:
    try:
        resp = requests.get(f"https://open.er-api.com/v6/latest/{from_currency.upper()}", timeout=5).json()
        rate = resp["rates"][to_currency.upper()]
        return f"Live rate — 1 {from_currency.upper()} = {rate:.2f} {to_currency.upper()} (updated: {resp['time_last_update_utc']})"
    except Exception:
        return "Couldn't fetch exchange rate right now."

def tool_calculate(expression: str) -> str:
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return "That expression isn't a valid calculation."
        result = eval(expression, {"__builtins__": {}}, {})
        return f"CALC_CARD|{expression}|{result}"
    except Exception:
        return "Couldn't calculate that — check the expression."

CRYPTO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin", "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana", "dogecoin": "dogecoin", "doge": "dogecoin",
    "cardano": "cardano", "ada": "cardano", "ripple": "ripple", "xrp": "ripple",
}

def tool_get_crypto(coin: str = "bitcoin") -> str:
    coin_id = CRYPTO_IDS.get(coin.lower(), coin.lower())
    try:
        resp = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,inr&include_24hr_change=true",
            timeout=5,
        ).json()
        data = resp.get(coin_id, {})
        usd = data.get("usd", "N/A")
        inr = data.get("inr", "N/A")
        change = data.get("usd_24h_change", 0)
        return f"CRYPTO_CARD|{coin_id}|{usd}|{inr}|{change:.2f}"
    except Exception:
        return "Couldn't fetch crypto price right now."

def tool_get_stock(ticker: str) -> str:
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        ).json()
        result = resp["chart"]["result"][0]
        price = result["meta"]["regularMarketPrice"]
        prev_close = result["meta"].get("previousClose") or result["meta"].get("chartPreviousClose")
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
        return f"STOCK_CARD|{ticker.upper()}|{price:.2f}|{change_pct:.2f}"
    except Exception:
        return "Couldn't fetch that stock price — check the ticker symbol."

def tool_get_news(category: str = "general") -> str:
    try:
        api_key = os.getenv("GNEWS_API_KEY")
        resp = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={"category": category, "lang": "en", "country": "in", "max": 5, "apikey": api_key},
            timeout=6,
        ).json()
        articles = resp.get("articles", [])
        if not articles:
            return "No news articles found right now."
        lines = [f"**Top {category} headlines:**\n"]
        for a in articles:
            lines.append(f"- {a['title']} ({a['source']['name']})")
        return "\n".join(lines)
    except Exception:
        return "Couldn't fetch news right now."

TOOL_FUNCTIONS = {
    "get_weather": tool_get_weather,
    "get_time": tool_get_time,
    "get_currency_rate": tool_get_currency,
    "calculate": tool_calculate,
    "get_crypto_price": tool_get_crypto,
    "get_stock_price": tool_get_stock,
    "get_news": tool_get_news,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_weather", "description": "Get current live weather for a city.",
        "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name, defaults to Mumbai"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "get_time", "description": "Get the current local date and time.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "get_currency_rate", "description": "Get a live currency exchange rate between two currencies.",
        "parameters": {"type": "object", "properties": {
            "from_currency": {"type": "string", "description": "3-letter currency code, e.g. USD"},
            "to_currency": {"type": "string", "description": "3-letter currency code, e.g. INR"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "calculate", "description": "Evaluate a pure arithmetic expression, e.g. '45*12+8000'.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
    }},
    {"type": "function", "function": {
        "name": "get_crypto_price", "description": "Get the live price of a cryptocurrency in USD and INR.",
        "parameters": {"type": "object", "properties": {"coin": {"type": "string", "description": "e.g. bitcoin, ethereum, solana"}}, "required": ["coin"]},
    }},
    {"type": "function", "function": {
        "name": "get_stock_price", "description": "Get the live stock price for a ticker symbol, e.g. AAPL, TSLA, RELIANCE.NS.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]},
    }},
    {"type": "function", "function": {
        "name": "get_news", "description": "Get today's top news headlines in India by category.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "description": "one of: general, world, business, technology, sports, entertainment, health, science"}
        }, "required": []},
    }},
]

def try_tool_call(query: str):
    """Returns (answer, tool_name) if a tool was used, else (None, None)."""
    response = client.chat.completions.create(
        model=FAST_MODEL,
        messages=[{"role": "user", "content": query}],
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
    )
    message = response.choices[0].message
    if not message.tool_calls:
        return None, None

    call = message.tool_calls[0]
    func = TOOL_FUNCTIONS.get(call.function.name)
    if not func:
        return None, None

    try:
        args = json.loads(call.function.arguments) if call.function.arguments else {}
    except Exception:
        args = {}

    result = func(**args)
    return result, call.function.name

# ---------- Routing ----------

def should_escalate(query: str) -> bool:
    simple = query.strip().lower()
    if simple in GREETINGS or len(simple.split()) <= 2:
        return False
    prompt = f"""You are a routing classifier. Decide if this query needs a powerful cloud model (HARD) or can be handled by a small local model (EASY), regardless of typos or phrasing.

EASY: greetings, small talk, sharing personal info (name, location, preferences), simple direct facts, short casual replies.
HARD: anything needing real explanation, teaching, technical/domain knowledge, reasoning, coding, comparisons, multi-step answers — even if the query is short, misspelled, or casually worded.

Query: "{query}"
Answer with exactly one word: EASY or HARD."""
    response = client.chat.completions.create(model=FAST_MODEL, messages=[{"role": "user", "content": prompt}])
    verdict = response.choices[0].message.content.strip().upper()
    return "HARD" in verdict

def handle_locally(query: str, user_id: str) -> str:
    messages = get_recent_history(user_id) + [{"role": "user", "content": query}]
    response = client.chat.completions.create(model=FAST_MODEL, messages=messages)
    return response.choices[0].message.content

def handle_via_api(query: str, user_id: str) -> str:
    messages = get_recent_history(user_id) + [{"role": "user", "content": query}]
    response = client.chat.completions.create(model=STRONG_MODEL, messages=messages)
    return response.choices[0].message.content