import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "./App.css";

type Message = { query: string; answer: string; used: string; ts?: number };

const Logo = ({ spin = false }: { spin?: boolean }) => (
  <svg width="26" height="26" viewBox="0 0 28 28" fill="none" className={spin ? "logo-spin" : ""}>
    <circle cx="14" cy="14" r="5" fill="#2dd4bf" />
    <circle cx="4" cy="5" r="2.5" fill="#f5a623" />
    <circle cx="24" cy="5" r="2.5" fill="#f5a623" />
    <circle cx="24" cy="23" r="2.5" fill="#f5a623" />
    <circle cx="4" cy="23" r="2.5" fill="#f5a623" />
    <line x1="14" y1="14" x2="4" y2="5" stroke="#3a4356" strokeWidth="1.4" />
    <line x1="14" y1="14" x2="24" y2="5" stroke="#3a4356" strokeWidth="1.4" />
    <line x1="14" y1="14" x2="24" y2="23" stroke="#3a4356" strokeWidth="1.4" />
    <line x1="14" y1="14" x2="4" y2="23" stroke="#3a4356" strokeWidth="1.4" />
  </svg>
);

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <path d="M3 12l18-8-8 18-2-8-8-2z" fill="currentColor" />
  </svg>
);

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [now, setNow] = useState(new Date());
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetch("http://localhost:8000/history")
      .then((res) => res.json())
      .then((data) => setMessages(data.reverse()));
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const sendQuery = async () => {
    if (!query.trim()) return;
    const q = query;
    setQuery("");
    if (textRef.current) textRef.current.style.height = "auto";

    setMessages((prev) => [...prev, { query: q, answer: "", used: "pending" }]);
    const start = performance.now();

    const res = await fetch("http://localhost:8000/route-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    const data = await res.json();
    setLastLatency(Math.round(performance.now() - start));

    setMessages((prev) => {
      const updated = [...prev];
      updated[updated.length - 1] = { query: q, answer: data.answer, used: data.used };
      return updated;
    });
  };

  const newChat = () => setMessages([]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuery();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuery(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  };

  const badgeClass = (used: string) =>
    used === "local" ? "badge-local" : used === "tool" ? "badge-tool" : "badge-api";
  const badgeLabel = (used: string) => (used === "local" ? "local" : used === "tool" ? "tool" : "cloud");

  const renderToolCard = (answer: string) => {
    const timeMatch = answer.match(/Current local time:\s*(.+)/i);
    if (timeMatch) {
      return (
        <div className="tool-card">
          <div className="tool-card-icon">🕐</div>
          <div className="tool-card-body">
            <div className="tool-card-title">Current Time</div>
            <div className="tool-card-value">{timeMatch[1]}</div>
          </div>
        </div>
      );
    }
    const weatherMatch = answer.match(/Live weather\s*—\s*(.+):\s*(\S+)\s*([+-]?\d+°[CF])/i);
    if (weatherMatch) {
      const [, city, icon, temp] = weatherMatch;
      return (
        <div className="tool-card">
          <div className="tool-card-icon">{icon}</div>
          <div className="tool-card-body">
            <div className="tool-card-title">Weather</div>
            <div className="tool-card-value">{temp}</div>
            <div className="tool-card-sub">📍 {city}</div>
          </div>
        </div>
      );
    }
    return null;
  };

  const suggestions = ["Explain AI", "Today's Weather", "Build a React app", "Summarize a PDF"];

  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const copyText = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 1200);
  };

  const markdownComponents = {
    code({ inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || "");
      if (inline) return <code className="inline-code" {...props}>{children}</code>;
      return (
        <div className="code-block">
          <div className="code-block-header">
            <span>{match?.[1] || "text"}</span>
          </div>
          <SyntaxHighlighter style={oneDark} language={match?.[1] || "text"} PreTag="div">
            {String(children).replace(/\n$/, "")}
          </SyntaxHighlighter>
        </div>
      );
    },
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand-row">
          <Logo />
          <div>
            <div className="brand">Cortex Lite</div>
            <div className="brand-sub">Hybrid Routing AI</div>
          </div>
        </div>

        <button className="new-chat-btn" onClick={newChat}>+ New Chat</button>

        <div className="history-label">Recent</div>
        <div className="history-list">
          {messages.slice(-15).reverse().map((m, i) => (
            <div key={i} className="history-item">
              <span className="history-dot" />
              {m.query}
            </div>
          ))}
          {messages.length === 0 && <div className="history-empty">No conversations yet</div>}
        </div>

        <div className="sidebar-footer">
          <div className="legend-row"><span className="dot dot-local" /> Local — on-device, fast</div>
          <div className="legend-row"><span className="dot dot-cloud" /> Cloud — Groq API</div>
          <div className="legend-row"><span className="dot dot-tool" /> Tool — live weather/time</div>
          <div className="memory-pill">🧠 Memory Enabled</div>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <div className="topbar-left">
            <Logo />
            <div>
              <div className="topbar-title">Cortex Lite</div>
              <div className="topbar-sub">Hybrid AI Assistant</div>
            </div>
          </div>
          <div className="topbar-right">
            <span className="status-pill"><span className="status-dot" /> Online</span>
            {lastLatency !== null && <span className="status-pill">{lastLatency} ms</span>}
            <span className="status-pill">{now.toLocaleTimeString()}</span>
          </div>
        </div>

        <div className="chat-box" ref={chatRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              <Logo />
              <div className="empty-title">Cortex Lite</div>
              <div className="empty-sub">Ask anything. Local, cloud, and live tools work together.</div>
              <div className="suggestion-grid">
                {suggestions.map((s) => (
                  <button key={s} className="suggestion-card" onClick={() => setQuery(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className="msg-block">
              <div className="row-user">
                <div className="bubble bubble-user">{m.query}</div>
              </div>
              <div className="row-bot">
                {m.used === "pending" ? (
                  <div className="bubble bubble-bot thinking-row">
                    <Logo spin />
                    <span className="dots"><span></span><span></span><span></span></span>
                  </div>
                ) : (
                  <div className="bubble bubble-bot">
                    <div className="bot-header">
                      <Logo /> <span className="bot-name">Cortex Lite</span>
                      <button className="copy-btn" onClick={() => copyText(m.answer, i)}>
                        {copiedIdx === i ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <div className="markdown-body">
                      {m.used === "tool" && renderToolCard(m.answer)
                        ? renderToolCard(m.answer)
                        : <ReactMarkdown components={markdownComponents}>{m.answer}</ReactMarkdown>}
                    </div>
                    <span className={`badge ${badgeClass(m.used)}`}>{badgeLabel(m.used)}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="input-area">
          <div className="input-row">
            <textarea
              ref={textRef}
              value={query}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Ask Cortex Lite anything..."
              rows={1}
            />
            <button className="send-btn" onClick={sendQuery}><SendIcon /></button>
          </div>
          <div className="hint">Enter to send · Shift+Enter for new line</div>
        </div>
      </div>
    </div>
  );
}

export default App;