import { useState, useEffect, useRef } from "react";
import "./App.css";

type Message = { query: string; answer: string; used: string };

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("http://localhost:8000/history")
      .then((res) => res.json())
      .then((data) => setMessages(data.reverse()));
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const sendQuery = async () => {
    if (!query.trim()) return;
    setLoading(true);
    const res = await fetch("http://localhost:8000/route-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    setMessages((prev) => [...prev, { query, answer: data.answer, used: data.used }]);
    setQuery("");
    setLoading(false);
  };

  return (
    <div className="page">
      <div className="header">
        <h1>Cortex Lite</h1>
        <p>Hybrid routing agent — local model handles easy tasks, cloud handles the rest</p>
      </div>

      <div className="chat-box" ref={chatRef}>
        {messages.map((m, i) => (
          <div key={i}>
            <div className="row-user">
              <div className="bubble bubble-user">{m.query}</div>
            </div>
            <div className="row-bot" style={{ marginTop: 8 }}>
              <div className="bubble bubble-bot">
                <span className={`badge ${m.used === "local" ? "badge-local" : "badge-api"}`}>
                  <span className="dot" />
                  {m.used === "local" ? "local" : "cloud"}
                </span>
                <div>{m.answer}</div>
              </div>
            </div>
          </div>
        ))}
        {loading && <p className="thinking">routing your request...</p>}
      </div>

      <div className="input-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendQuery()}
          placeholder="Ask something..."
        />
        <button onClick={sendQuery}>Send</button>
      </div>
    </div>
  );
}

export default App;