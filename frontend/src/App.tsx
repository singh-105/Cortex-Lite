import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "./App.css";

type Message = {
  id?: number;
  query: string;
  answer: string;
  displayAnswer?: string;
  used: string;
  latency?: number;
  stage?: string;
};

const routeSteps = (used: string) => {
  const active = (name: string) => {
    if (name === "Memory") return true;
    if (name === "Router") return true;
    if (name === "Model") return used === "local" || used === "api";
    if (name === "Tool") return used === "tool";
    return false;
  };
  return ["Memory", "Router", "Model", "Tool"].map((name) => ({ name, active: active(name) }));
};

const STAGES = ["Analyzing route...", "Checking memory...", "Calling model...", "Formatting response..."];

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

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);
  const lineCount = code.split("\n").length;

  const doCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span>{lang}</span>
        <div className="code-block-actions">
          <button onClick={() => setCollapsed((c) => !c)}>{collapsed ? "Expand" : "Collapse"}</button>
          <button onClick={doCopy}>{copied ? "Copied" : "Copy"}</button>
        </div>
      </div>
      {!collapsed && (
        <SyntaxHighlighter
          style={oneDark}
          language={lang}
          PreTag="div"
          showLineNumbers={lineCount > 1}
        >
          {code}
        </SyntaxHighlighter>
      )}
    </div>
  );
}

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <path d="M3 12l18-8-8 18-2-8-8-2z" fill="currentColor" />
  </svg>
);

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [pinnedIds, setPinnedIds] = useState<Set<number>>(new Set());
  const [activeId, setActiveId] = useState<number | null>(null);
  const [attachedFile, setAttachedFile] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const t = setInterval(() => setPlaceholderIdx((i) => (i + 1) % suggestionsList.length), 3000);
    return () => clearInterval(t);
  }, []);

  const suggestionsList = ["Explain AI", "Today's weather", "Build a React app", "Summarize a PDF"];

  const startVoice = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice input not supported in this browser.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.onresult = (e: any) => {
      setQuery((prev) => (prev ? prev + " " : "") + e.results[0][0].transcript);
    };
    recognition.onend = () => setIsRecording(false);
    recognition.start();
    recognitionRef.current = recognition;
    setIsRecording(true);
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setIsRecording(false);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setAttachedFile(file.name);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) setAttachedFile(file.name);
  };

  const togglePin = (id: number) => {
    setPinnedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const deleteEntry = async (id: number) => {
    await fetch(`http://localhost:8000/history/${id}`, { method: "DELETE" });
    setMessages((prev) => prev.filter((m) => m.id !== id));
  };

  const scrollToMessage = (id: number) => {
    setActiveId(id);
    document.getElementById(`msg-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const [isStreaming, setIsStreaming] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/history")
      .then((res) => res.json())
      .then((data) => setMessages(data.reverse()));
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const streamAnswer = (index: number, fullText: string, speed = 12) => {
    let i = 0;
    const timer = window.setInterval(() => {
      i++;
      setMessages((prev) => {
        const copy = [...prev];
        if (!copy[index]) return prev;
        copy[index] = { ...copy[index], displayAnswer: fullText.slice(0, i) };
        return copy;
      });
      if (i >= fullText.length) clearInterval(timer);
    }, speed);
  };

  const stopResponse = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
  };

  const runStageTicker = (index: number) => {
    let stageI = 0;
    const timer = window.setInterval(() => {
      setMessages((prev) => {
        const copy = [...prev];
        if (!copy[index] || copy[index].used !== "pending") {
          clearInterval(timer);
          return prev;
        }
        stageI = (stageI + 1) % STAGES.length;
        copy[index] = { ...copy[index], stage: STAGES[stageI] };
        return copy;
      });
    }, 700);
    return timer;
  };

  const sendQuery = async () => {
    if (!query.trim()) return;
    const q = query;
    setQuery("");
    if (textRef.current) textRef.current.style.height = "auto";

    setMessages((prev) => [...prev, { query: q, answer: "", displayAnswer: "", used: "pending", stage: STAGES[0] }]);
    setIsStreaming(true);
    const stageTimer = runStageTicker(messages.length);

    const controller = new AbortController();
    abortRef.current = controller;

    const start = performance.now();
    let res;
    try {
      res = await fetch("http://localhost:8000/route-task", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
        signal: controller.signal,
      });
    } catch {
      clearInterval(stageTimer);
      setIsStreaming(false);
      return;
    }

    const data = await res.json();
    clearInterval(stageTimer);
    const latency = Math.round(performance.now() - start);
    setLastLatency(latency);

    setMessages((prev) => {
      const updated = [...prev];
      const idx = updated.length - 1;
      updated[idx] = { query: q, answer: data.answer, displayAnswer: "", used: data.used, latency };
      return updated;
    });

    setTimeout(() => {
      setMessages((prev) => {
        streamAnswer(prev.length - 1, data.answer);
        return prev;
      });
    }, 0);
    setIsStreaming(false);
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

    if (answer.startsWith("WEATHER_CARD|")) {
      const [, city, cond, temp, feels, hum, wind, pressure] = answer.split("|");
      return (
        <div className="tool-card weather-card">
          <div className="weather-main">
            <div className="tool-card-icon">🌦️</div>
            <div>
              <div className="tool-card-value">{temp}</div>
              <div className="tool-card-sub">{cond} · 📍 {city}</div>
            </div>
          </div>
          <div className="weather-grid">
            <div><span className="w-label">Feels like</span><span className="w-value">{feels}</span></div>
            <div><span className="w-label">Humidity</span><span className="w-value">{hum}</span></div>
            <div><span className="w-label">Wind</span><span className="w-value">{wind}</span></div>
            <div><span className="w-label">Pressure</span><span className="w-value">{pressure}</span></div>
          </div>
        </div>
      );
    }

    const currencyMatch = answer.match(/Live rate\s*—\s*1 USD = ([\d.]+) INR \(updated:\s*(.+)\)/i);
    if (currencyMatch) {
      const [, rate, updated] = currencyMatch;
      return (
        <div className="tool-card">
          <div className="tool-card-icon">💱</div>
          <div className="tool-card-body">
            <div className="tool-card-title">USD → INR</div>
            <div className="tool-card-value">₹{rate}</div>
            <div className="tool-card-sub">Updated {updated}</div>
          </div>
        </div>
      );
    }

    return null;
  };

  const suggestions = ["Explain AI", "Today's Weather", "Build a React app", "Summarize a PDF"];

  const copyText = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 1200);
  };

  const [reactions, setReactions] = useState<Record<number, "like" | "dislike" | null>>({});

  const toggleReaction = (idx: number, kind: "like" | "dislike") => {
    setReactions((prev) => ({ ...prev, [idx]: prev[idx] === kind ? null : kind }));
  };

  const regenerate = async (idx: number) => {
    const q = messages[idx].query;
    setMessages((prev) => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], used: "pending", answer: "", displayAnswer: "", stage: STAGES[0] };
      return copy;
    });

    const stageTimer = runStageTicker(idx);
    const start = performance.now();
    const res = await fetch("http://localhost:8000/route-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    const data = await res.json();
    clearInterval(stageTimer);
    const latency = Math.round(performance.now() - start);

    setMessages((prev) => {
      const copy = [...prev];
      copy[idx] = { query: q, answer: data.answer, displayAnswer: "", used: data.used, latency };
      return copy;
    });
    setTimeout(() => streamAnswer(idx, data.answer), 0);
  };

 const markdownComponents = {
    code({ inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || "");
      if (inline) return <code className="inline-code" {...props}>{children}</code>;
      const codeText = String(children).replace(/\n$/, "");
      return <CodeBlock lang={match?.[1] || "text"} code={codeText} />;
    },
    img({ src, alt }: any) {
      return <img src={src} alt={alt} className="md-image" loading="lazy" />;
    },
    blockquote({ children }: any) {
      const text = JSON.stringify(children);
      const isWarn = /⚠️|warning/i.test(text);
      const isNote = /ℹ️|note/i.test(text);
      const cls = isWarn ? "alert alert-warn" : isNote ? "alert alert-note" : "";
      return cls ? <div className={cls}>{children}</div> : <blockquote>{children}</blockquote>;
    },
    li({ children, className }: any) {
      if (className === "task-list-item") {
        return <li className="task-item">{children}</li>;
      }
      return <li>{children}</li>;
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

        <input
          className="sidebar-search"
          placeholder="Search history..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <div className="history-label">Recent</div>
        <div className="history-list">
          {[...messages]
            .filter((m) => m.query.toLowerCase().includes(searchTerm.toLowerCase()))
            .slice(-30)
            .reverse()
            .sort((a, b) => {
              const aPinned = a.id !== undefined && pinnedIds.has(a.id) ? 1 : 0;
              const bPinned = b.id !== undefined && pinnedIds.has(b.id) ? 1 : 0;
              return bPinned - aPinned;
            })
            .map((m) => (
              <div
                key={m.id ?? m.query}
                className={`history-item ${activeId === m.id ? "history-item-active" : ""}`}
                onClick={() => m.id !== undefined && scrollToMessage(m.id)}
              >
                <span className="history-dot" />
                <span className="history-text">{m.query}</span>
                {m.id !== undefined && (
                  <span className="history-actions">
                    <button onClick={(e) => { e.stopPropagation(); togglePin(m.id!); }}>
                      {pinnedIds.has(m.id) ? "📌" : "📍"}
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); deleteEntry(m.id!); }}>🗑</button>
                  </span>
                )}
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
          <div className="topbar-right"></div>
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
            <div key={i} id={`msg-${m.id ?? i}`} className="msg-block">
              <div className="row-user">
                <div className="bubble bubble-user">{m.query}</div>
              </div>
              <div className="row-bot">
                {m.used === "pending" ? (
                  <div className="bubble bubble-bot thinking-row">
                    <Logo spin />
                    <span className="thinking-stage">{m.stage}</span>
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
                        : <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{m.displayAnswer ?? m.answer}</ReactMarkdown>}
                    </div>
                    <span className={`badge ${badgeClass(m.used)}`}>
                      {badgeLabel(m.used)}{m.latency ? ` · ${m.latency}ms` : ""}
                    </span>
                    <div className="msg-actions">
                      <button onClick={() => regenerate(i)} title="Regenerate">↻</button>
                      <button
                        className={reactions[i] === "like" ? "action-active" : ""}
                        onClick={() => toggleReaction(i, "like")}
                        title="Like"
                      >👍</button>
                      <button
                        className={reactions[i] === "dislike" ? "action-active" : ""}
                        onClick={() => toggleReaction(i, "dislike")}
                        title="Dislike"
                      >👎</button>
                    </div>
                    
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
            <button className="send-btn" onClick={isStreaming ? stopResponse : sendQuery}>
              {isStreaming ? "■" : <SendIcon />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;