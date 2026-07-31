import React, { useState, useRef, useEffect } from "react";
import { Bot, X, Send, TerminalSquare } from "lucide-react";
import { SUGGESTIONS, buildAnswer } from "../../utils/chatAssistant";
import "./ChatPanel.css";

export default function ChatPanel({ open, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Olá! Sou o assistente de infraestrutura, conectado via MCP aos dados de triggers e métricas do sistema. Posso analisar alertas, correlacionar históricos e gerar relatórios. Como posso ajudar?",
    },
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  function send(text) {
    const t = (text ?? input).trim();
    if (!t) return;
    setMessages((m) => [...m, { role: "user", text: t }]);
    setInput("");
    setTyping(true);
    setTimeout(() => {
      const { tool, text: answer } = buildAnswer(t);
      setMessages((m) => [...m, { role: "assistant", tool, text: answer }]);
      setTyping(false);
    }, 950);
  }

  return (
    <>
      <div className={"smi-chat-backdrop" + (open ? " smi-show" : "")} onClick={onClose} />
      <aside className={"smi-chat" + (open ? " smi-chat-open" : "")}>
        <div className="smi-chat-head">
          <div className="smi-chat-head-title">
            <div className="smi-chat-avatar"><Bot size={16} /></div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>Assistente de Infraestrutura</div>
              <div className="smi-chat-status"><span className="smi-dot-live" /> Conectado via MCP</div>
            </div>
          </div>
          <button className="smi-icon-btn" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="smi-chat-body">
          {messages.map((m, i) => (
            <div key={i} className={"smi-msg " + (m.role === "user" ? "smi-msg-user" : "smi-msg-ai")}>
              {m.tool && <div className="smi-msg-tool"><TerminalSquare size={11} /> {m.tool}</div>}
              <div className="smi-msg-bubble">{m.text}</div>
            </div>
          ))}
          {typing && (
            <div className="smi-msg smi-msg-ai">
              <div className="smi-msg-tool"><TerminalSquare size={11} /> consultando dados via MCP…</div>
              <div className="smi-msg-bubble smi-typing"><span /><span /><span /></div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {messages.length < 2 && (
          <div className="smi-chat-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="smi-chip" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}

        <form className="smi-chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pergunte sobre métricas, alertas ou relatórios…"
          />
          <button type="submit" className="smi-icon-btn smi-icon-btn-accent"><Send size={15} /></button>
        </form>
      </aside>
    </>
  );
}
