import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, X, Send, TerminalSquare, RotateCcw } from "lucide-react";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import "./ChatPanel.css";

const SUGGESTIONS = [
  "Resumo do estado da infraestrutura",
  "Qual servidor está em pior estado e por quê?",
  "Analise a CPU do srv-db-01 nas últimas 24 h",
  "Gerar relatório semanal de incidentes",
];

const GREETING = {
  role: "assistant",
  text: "Olá! Sou o assistente de infraestrutura do SMI. Consulto os dados reais pelas ferramentas do servidor MCP para analisar alertas, correlacionar eventos e gerar relatórios. Como posso ajudar?",
};

// get_server(host_id="srv-app-02")
function describeCall(c) {
  const args = Object.entries(c.arguments ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
  return `${c.name}(${args})`;
}

export default function ChatPanel({ open, onClose }) {
  const [messages, setMessages] = useState([GREETING]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const endRef = useRef(null);
  const status = useApi((signal) => (open ? api.assistantStatus({ signal }) : null), ["assistant-status", open], {
    interval: open ? 30_000 : undefined,
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // modelo local pode levar dezenas de segundos: mostra o tempo de espera
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => { clearInterval(timer); setElapsed(0); };
  }, [busy]);

  async function send(text) {
    const t = (text ?? input).trim();
    if (!t || busy) return;
    setMessages((m) => [...m, { role: "user", text: t }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api.assistantMessage({ conversation_id: conversationId, message: t });
      setConversationId(r.conversation_id);
      setMessages((m) => [...m, { role: "assistant", text: r.reply, tools: r.tool_calls }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: err.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setMessages([GREETING]);
    setConversationId(null);
  }

  const s = status.data;
  const ready = s?.available && s?.mcp.connected;
  const statusText = !s
    ? status.error ? "API indisponível" : "verificando…"
    : !s.enabled
      ? "IA desligada"
      : ready
        ? `${s.provider === "ollama" ? "Ollama" : "Claude"} · ${s.model} · MCP (${s.mcp.tools.length} ferramentas)`
        : s.available ? `MCP indisponível: ${s.mcp.detail}` : s.detail;

  return (
    <>
      <div className={"smi-chat-backdrop" + (open ? " smi-show" : "")} onClick={onClose} />
      <aside className={"smi-chat" + (open ? " smi-chat-open" : "")}>
        <div className="smi-chat-head">
          <div className="smi-chat-head-title">
            <div className="smi-chat-avatar"><Bot size={16} /></div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>Assistente de Infraestrutura</div>
              <div className="smi-chat-status" title={statusText}>
                <span className={ready ? "smi-dot-live" : "smi-dot-off"} /> <span className="smi-chat-status-text">{statusText}</span>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="smi-icon-btn" onClick={reset} title="Nova conversa" disabled={busy}><RotateCcw size={15} /></button>
            <button className="smi-icon-btn" onClick={onClose} title="Fechar"><X size={16} /></button>
          </div>
        </div>

        <div className="smi-chat-body">
          {messages.map((m, i) => (
            <div key={i} className={"smi-msg " + (m.role === "user" ? "smi-msg-user" : "smi-msg-ai")}>
              {m.tools?.length > 0 && (
                <div className="smi-msg-tools">
                  {m.tools.map((c, j) => (
                    <div key={j} className="smi-msg-tool"><TerminalSquare size={11} /> {describeCall(c)}</div>
                  ))}
                </div>
              )}
              <div className={"smi-msg-bubble" + (m.error ? " smi-msg-error" : "")}>
                {m.role === "assistant" && !m.error ? (
                  <div className="smi-msg-md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown></div>
                ) : (
                  m.text
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="smi-msg smi-msg-ai">
              <div className="smi-msg-tool"><TerminalSquare size={11} /> consultando dados via MCP… {elapsed > 2 && `${elapsed} s`}</div>
              <div className="smi-msg-bubble smi-typing"><span /><span /><span /></div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {messages.length < 2 && (
          <div className="smi-chat-suggestions">
            {SUGGESTIONS.map((sug) => (
              <button key={sug} className="smi-chip" onClick={() => send(sug)} disabled={busy}>{sug}</button>
            ))}
          </div>
        )}

        <form className="smi-chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pergunte sobre métricas, alertas ou relatórios…"
            disabled={busy}
          />
          <button type="submit" className="smi-icon-btn smi-icon-btn-accent" disabled={busy}><Send size={15} /></button>
        </form>
      </aside>
    </>
  );
}
