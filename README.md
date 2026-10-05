# SMI · Sistema de Monitoramento de Integridade para Servidores

Protótipo do Trabalho de Conclusão de Curso de Tecnologia em Análise e Desenvolvimento de Sistemas da FATEC Presidente Prudente (2026).

**Autores:** Luiz Gustavo de Souza Sá e Paulo Eduardo Pelosi Braz Silva
**Orientador:** Prof. Dr. Rodrigo Vilela

O SMI monitora a integridade física de servidores (CPU, memória, disco e temperatura) usando dados coletados via SNMP/IPMI. Um motor de gatilhos classifica cada host em **OK**, **Aviso** ou **Crítico**, e um assistente de IA integrado via **Model Context Protocol (MCP)** correlaciona alertas, gera relatórios e responde perguntas em linguagem natural.

## Estado atual

O dashboard lê todos os dados da API, que por enquanto recebe as leituras de um coletor simulado. O assistente de IA ainda é simulado (`src/utils/chatAssistant.js`), mas suas respostas já usam os dados reais.

| Camada | Status |
| --- | --- |
| Dashboard (React) | ✅ ligado à API, com atualização a cada 10 s |
| Backend REST + motor de gatilhos | ✅ pronto, com coletor simulado |
| Armazenamento (InfluxDB) | ✅ InfluxDB 2.x ou SQLite (desenvolvimento) |
| Servidor MCP + IA | ⏳ a fazer (etapa 4) |
| Coletor SNMP/IPMI | ⏳ a fazer (etapa 5) |

## Stack do front-end

React 18, Vite, React Router, Recharts e lucide-react.

## Como rodar

Requer Node.js 20.19 ou superior e Python 3.12 ou superior. A instalação do backend é feita uma vez, conforme o [`backend/README.md`](backend/README.md).

Use três terminais, todos abertos na pasta do projeto:

```powershell
# 1) API (http://127.0.0.1:8000)
cd backend; .venv\Scripts\python -m uvicorn app.main:app --reload

# 2) coletor simulado (gera 24 h de histórico e continua coletando a cada 15 s)
cd backend; .venv\Scripts\python simulator\simulate.py --backfill 24h

# 3) dashboard (http://localhost:5173)
npm install
npm run dev
```

Em desenvolvimento, o Vite repassa as chamadas a `/api` para `http://127.0.0.1:8000` (`vite.config.js`). Para usar outro endereço, defina `SMI_API_TARGET` ao rodar o Vite, ou `VITE_API_URL` para o front chamar a API direto.

Outros comandos do front-end:

```bash
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
├── api/          # cliente HTTP da API (client.js)
├── components/   # componentes reutilizáveis (KpiCard, Led, MetricBar, AlertTable, ChatPanel, gráficos…)
├── config/       # navegação, rótulos de estados e métricas
├── context/      # dados compartilhados pelo layout (Visão Geral atualizada a cada 10 s)
├── hooks/        # useApi: busca dados da API com atualização automática
├── layouts/      # DashboardLayout: barra lateral, barra superior e chat fixos
├── pages/        # Dashboard, Servidores, Gatilhos, Métricas, Topologia, Relatórios
└── utils/        # formatação, regras de gatilho e assistente de IA simulado
```
