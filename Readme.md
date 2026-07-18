# Cortex Lite

A hybrid inference routing system that classifies incoming queries in real time and dispatches each one to the most appropriate execution path — a lightweight model, a stronger reasoning model, or a direct data API — rather than sending every request through a single, expensive model call.

**Live application:** https://cortex-lite-bg6jj5xz1-singh-105s-projects.vercel.app
**API documentation:** https://cortex-lite.onrender.com/docs
**Repository:** https://github.com/singh-105/Cortex-Lite

---

## Motivation

Most conversational AI systems route every request through the same model regardless of complexity, which is inefficient in both cost and latency. A greeting and a request for a technical explanation do not require the same computational budget.

Cortex Lite is a personal project built to explore this problem directly: an LLM-driven classification layer inspects each query and routes it to one of three paths — a fast model for simple exchanges, a stronger model for reasoning-heavy queries, or a live external API for factual, time-sensitive data such as weather or exchange rates. The classification is model-based rather than keyword-based, so it correctly interprets typos, ambiguity, and casual phrasing rather than relying on brittle pattern matching.

## System Design

```
User Query
    |
    v
Intent Classifier (LLM-based)
    |
    +-- Tool Path        -> live weather / time / currency API (bypasses the LLM)
    +-- Fast Model Path   -> lightweight model, simple queries and small talk
    +-- Reasoning Path    -> stronger model, explanations and multi-step logic
    |
    v
Response returned with execution path and latency attached
```

Each response is tagged with the path taken and the time it took, so the routing decision is observable rather than hidden inside the system.

## Architecture Notes

The routing logic was originally developed and validated against a genuinely local inference tier, running small open-weight models through Ollama (`qwen2.5:0.5b`, later `phi3:mini`) entirely on-device. This provided true zero-cost, zero-network-latency inference for the fast-path branch and was the basis on which the classification thresholds were tuned.

The publicly deployed version substitutes this branch with a second, smaller cloud model instead of a self-hosted one, since the free-tier infrastructure used for hosting does not support a persistent local inference server. The routing architecture and classification logic are unchanged between the two configurations — only the execution target for the fast-path branch differs. Running the project locally with Ollama installed restores the original on-device inference exactly as built.

## Features

**Routing and inference**
- LLM-based intent classification across three execution tiers
- Conversation memory persisted in SQLite and injected into model context for coherent follow-up exchanges
- Per-response routing indicator with measured latency
- Regeneration of any prior response through the same routing pipeline

**Live data integration**
- Real-time weather with temperature, feels-like, humidity, wind, and pressure
- Live currency conversion between USD and INR
- Current local time, resolved without a model call

**Conversational interface**
- Streamed, character-level response rendering with the ability to cancel mid-response
- Multi-stage processing indicator reflecting the actual request lifecycle
- Full Markdown rendering: tables, task lists, blockquote alerts, and syntax-highlighted code blocks with copy, collapse, and line numbers
- Per-message actions: copy, regenerate, like, dislike

**Input**
- Voice input via the Web Speech API
- Text file attachment (.txt, .md, .csv, .json, .log) with content parsed directly into the model's context
- Responsive layout with a collapsible navigation panel on smaller screens

**History**
- Searchable and pinnable conversation history
- Individual entry deletion
- Click-to-navigate to any prior exchange in the conversation

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Markdown rendering | react-markdown, remark-gfm, react-syntax-highlighter |
| Backend | FastAPI, Python 3.11 |
| Local inference (development) | Ollama (phi3:mini) |
| Cloud inference | Groq API |
| Persistence | SQLite |
| External data | wttr.in, open.er-api.com |
| Deployment | Render (API), Vercel (client) |

## Repository Structure

```
routing-agent/
  backend/
    app/
      main.py           application entry point, CORS, router registration
      routes.py         endpoint definitions
      router_logic.py   classification, inference calls, tool handlers
    requirements.txt
    runtime.txt
  frontend/
    src/
      App.tsx
      App.css
    .env                 local API target
    .env.production      deployed API target
```

## Running Locally

**Backend**

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/app/.env`:

```
GROQ_API_KEY=your_key_here
```

To restore local-model inference, install Ollama and pull a model:

```
ollama pull phi3:mini
```

Start the server:

```
uvicorn app.main:app --reload
```

**Frontend**

```
cd frontend
npm install
npm run dev
```

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | /route-task | Submit a query; returns the routed response, execution path, and latency |
| GET | /history | Retrieve recent conversation history |
| DELETE | /history/{id} | Remove a specific history entry |
| GET | /health | Service health check |

Full interactive documentation is available at `/docs` on the deployed API.

## Roadmap

- True backend-streamed token responses, replacing the current client-side simulated streaming
- Additional tool integrations: calculator, stock prices, news, web search
- Persistent multi-conversation sessions
- Migration to a managed database for durable history on ephemeral hosting

## Author

Harsh Singh
GitHub: https://github.com/singh-105
LinkedIn: https://linkedin.com/in/harsh-singh-5503372b8/