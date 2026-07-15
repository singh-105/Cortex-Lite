import { useState } from "react";

function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState("");

  const callBackend = async () => {
    const res = await fetch("http://localhost:8000/route-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    setResult(JSON.stringify(data));
  };

  return (
    <div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <button onClick={callBackend}>Send</button>
      <p>{result}</p>
    </div>
  );
}

export default App;