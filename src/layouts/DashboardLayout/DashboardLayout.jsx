import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../../components/Sidebar/Sidebar";
import Topbar from "../../components/Topbar/Topbar";
import ChatPanel from "../../components/ChatPanel/ChatPanel";
import "./DashboardLayout.css";

// Molde fixo do painel. Sidebar, Topbar e o ChatPanel da IA vivem aqui —
// fora do <Outlet/> — para persistirem entre as trocas de página.
// Cada rota (Dashboard, Servidores, Gatilhos...) é renderizada dentro do <Outlet/>.
export default function DashboardLayout() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="smi-app">
      <Sidebar />

      <div className="smi-main">
        <Topbar chatOpen={chatOpen} onToggleChat={() => setChatOpen((v) => !v)} />
        <main className="smi-content">
          <Outlet />
        </main>
      </div>

      <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
