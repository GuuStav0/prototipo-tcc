import { LayoutDashboard, Server, AlertTriangle, Activity, Share2, FileText } from "lucide-react";

// Fonte única de verdade para as rotas do painel.
// Sidebar usa "path" + "icon" para os links; Topbar usa "path" + "label" para o título/breadcrumb.
export const NAV = [
  { id: "dashboard", label: "Visão Geral", path: "/dashboard", icon: LayoutDashboard },
  { id: "servers", label: "Servidores", path: "/servidores", icon: Server },
  { id: "triggers", label: "Gatilhos", path: "/gatilhos", icon: AlertTriangle },
  { id: "metrics", label: "Métricas", path: "/metricas", icon: Activity },
  { id: "topology", label: "Topologia", path: "/topologia", icon: Share2 },
  { id: "reports", label: "Relatórios", path: "/relatorios", icon: FileText },
];
