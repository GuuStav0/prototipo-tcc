import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../../components/Sidebar/Sidebar";
import Topbar from "../../components/Topbar/Topbar";
import ChatPanel from "../../components/ChatPanel/ChatPanel";
import { ApiOfflineBanner } from "../../components/Feedback/Feedback";
import LiveProvider from "../../context/LiveProvider";
import { useLive } from "../../context/live";
import "./DashboardLayout.css";

// Molde fixo do painel. Sidebar, Topbar e o ChatPanel da IA vivem aqui —
// fora do <Outlet/> — para persistirem entre as trocas de página.
// Cada rota (Dashboard, Servidores, Gatilhos...) é renderizada dentro do <Outlet/>.
export default function DashboardLayout() {
  return (
    <LiveProvider>
      <Shell />
    </LiveProvider>
  );
}

function Shell() {
  const [chatOpen, setChatOpen] = useState(false);
  const { error } = useLive();

  return (
    <div className="smi-app">
      <Sidebar />

      <div className="smi-main">
        <Topbar chatOpen={chatOpen} onToggleChat={() => setChatOpen((v) => !v)} />
        <main className="smi-content">
          <ApiOfflineBanner error={error} />
          <Outlet />
        </main>
      </div>

      <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
