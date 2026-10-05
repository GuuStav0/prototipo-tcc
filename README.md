# SMI · Sistema de Monitoramento de Integridade para Servidores

Protótipo do Trabalho de Conclusão de Curso de Tecnologia em Análise e Desenvolvimento de Sistemas da FATEC Presidente Prudente (2026).

**Autores:** Luiz Gustavo de Souza Sá e Paulo Eduardo Pelosi Braz Silva
**Orientador:** Prof. Dr. Rodrigo Vilela

O SMI monitora a integridade física de servidores (CPU, memória, disco e temperatura) usando dados coletados via SNMP/IPMI. Um motor de gatilhos classifica cada host em **OK**, **Aviso** ou **Crítico**, e um assistente de IA integrado via **Model Context Protocol (MCP)** correlaciona alertas, gera relatórios e responde perguntas em linguagem natural.

## Estado atual

O front-end ainda usa dados simulados (`src/data/mockData.js`), e o assistente de IA é simulado em `src/utils/chatAssistant.js`. O backend já funciona com um coletor simulado; veja [`backend/README.md`](backend/README.md).

| Camada | Status |
| --- | --- |
| Dashboard (React) | ✅ protótipo com dados simulados |
| Backend REST + motor de gatilhos | ✅ pronto, com coletor simulado |
| Armazenamento (InfluxDB) | ✅ InfluxDB 2.x ou SQLite (desenvolvimento) |
| Front-end ligado à API | ⏳ a fazer |
| Servidor MCP + IA | ⏳ a fazer |
| Coletor SNMP/IPMI | ⏳ a fazer |

## Stack do front-end

React 18, Vite, React Router, Recharts e lucide-react.

## Como rodar

Requer Node.js 20.19 ou superior.

```bash
npm install
npm run dev      # servidor de desenvolvimento
npm run build    # build de produção em dist/
npm run lint     # ESLint
```

## Contrato da API

O formato dos dados e as rotas REST estão em [`docs/contrato/openapi.yaml`](docs/contrato/openapi.yaml). As decisões estão explicadas em [`docs/contrato/explicacao-contrato.txt`](docs/contrato/explicacao-contrato.txt).

## Estrutura

```
backend/          # API REST, motor de gatilhos e coletor simulado (Python)
docs/contrato/    # contrato da API (OpenAPI) e explicação das decisões
src/
├── components/   # componentes reutilizáveis (KpiCard, Led, MetricBar, ChatPanel, gráficos…)
├── config/       # navegação (rotas da barra lateral e da barra superior)
├── data/         # dados simulados (servidores, gatilhos, relatórios, séries)
├── layouts/      # DashboardLayout: barra lateral, barra superior e chat fixos
├── pages/        # Dashboard, Servidores, Gatilhos, Métricas, Topologia, Relatórios
└── utils/        # assistente de IA simulado
```
