import { SERVERS } from "../data/mockData";

export const SUGGESTIONS = [
  "Resumo de disponibilidade de hoje",
  "Por que o srv-app-02 está crítico?",
  "Gerar relatório semanal de incidentes",
  "Algum padrão nos alertas do srv-db-01?",
];

export function buildAnswer(text) {
  const q = text.toLowerCase();
  const critical = SERVERS.filter((s) => s.status === "critical");
  const warn = SERVERS.filter((s) => s.status === "warning");

  if (q.includes("app-02") || (q.includes("crítico") && q.includes("por"))) {
    const s = SERVERS.find((s) => s.id === "srv-app-02");
    return {
      tool: `mcp.triggers.history(host="srv-app-02")`,
      text: `O srv-app-02 está em estado crítico há cerca de 6 minutos. CPU em ${s.cpu}% (limite: 90%) e temperatura em ${s.temp}°C (limite: 75°C), acima do normal para esse host desde os últimos 3 ciclos de coleta. O padrão sugere um processo consumindo CPU de forma contínua, elevando a temperatura junto. Recomendo verificar os processos ativos e, se necessário, redistribuir carga para o srv-app-01.`,
    };
  }
  if (q.includes("disponibilidade") || q.includes("resumo")) {
    return {
      tool: `mcp.metrics.summary(period="24h")`,
      text: `Disponibilidade geral nas últimas 24h: 99,94%. ${SERVERS.length} hosts monitorados, sendo ${SERVERS.filter((s) => s.status === "ok").length} saudáveis, ${warn.length} em aviso (${warn.map((s) => s.name).join(", ")}) e ${critical.length} crítico (${critical.map((s) => s.name).join(", ") || "nenhum"}). Nenhuma janela de indisponibilidade total foi registrada.`,
    };
  }
  if (q.includes("relatório") || q.includes("relatorio")) {
    return {
      tool: `mcp.reports.generate(type="incidentes", period="7d")`,
      text: `Relatório de incidentes dos últimos 7 dias gerado. Principais pontos: 2 gatilhos ativos (crítico: srv-app-02; aviso: srv-backup-01), MTTR médio de 18 min. Você pode revisar o arquivo na aba Relatórios.`,
    };
  }
  if (q.includes("db-01") || q.includes("padrão") || q.includes("padrao")) {
    return {
      tool: `mcp.triggers.correlate(host="srv-db-01")`,
      text: `Correlacionando o histórico do srv-db-01: os avisos de RAM (84%) coincidem com picos de uso de CPU acima de 75% em janelas de manutenção noturna. Não há indício de vazamento de memória — o padrão é sazonal e ligado a rotinas de backup. Sugiro monitorar por mais 48h antes de qualquer ação.`,
    };
  }
  return {
    tool: `mcp.metrics.query(scope="infraestrutura")`,
    text: `Analisando os dados coletados via SNMP/IPMI: no momento ${critical.length} host(s) em estado crítico e ${warn.length} em aviso. Posso detalhar um servidor específico, correlacionar o histórico de um gatilho ou gerar um relatório automático — é só pedir.`,
  };
}
