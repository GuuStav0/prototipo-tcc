import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout/DashboardLayout";
import Dashboard from "./pages/Dashboard/Dashboard";
import ServersList from "./pages/Servers/ServersList";
import ServerDetail from "./pages/Servers/ServerDetail";
import Triggers from "./pages/Triggers/Triggers";
import Metrics from "./pages/Metrics/Metrics";
import Topology from "./pages/Topology/Topology";
import Reports from "./pages/Reports/Reports";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/servidores" element={<ServersList />} />
          <Route path="/servidores/:hostId" element={<ServerDetail />} />
          <Route path="/gatilhos" element={<Triggers />} />
          <Route path="/metricas" element={<Metrics />} />
          <Route path="/topologia" element={<Topology />} />
          <Route path="/relatorios" element={<Reports />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
