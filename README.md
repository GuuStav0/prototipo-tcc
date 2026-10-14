# SMI · Sistema de Monitoramento de Integridade para Servidores

Protótipo do Trabalho de Conclusão de Curso de Tecnologia em Análise e Desenvolvimento de Sistemas da FATEC Presidente Prudente (2026).

**Autores:** Luiz Gustavo de Souza Sá e Paulo Eduardo Pelosi Braz Silva
**Orientador:** Prof. Dr. Rodrigo Vilela

O SMI monitora a integridade física de servidores (CPU, memória, disco e temperatura) usando dados coletados via SNMP/IPMI. Um motor de gatilhos classifica cada host em **OK**, **Aviso** ou **Crítico**, e um assistente de IA integrado via **Model Context Protocol (MCP)** correlaciona alertas, gera relatórios e responde perguntas em linguagem natural.

## Estado atual

O dashboard lê todos os dados da API. Os servidores podem ser **reais**, como a VPS monitorada por agente ou por SNMP v3, ou **simulados**, para demonstrar falhas sob demanda. Cada servidor tem o seu modo, e um nunca recebe dados do outro. O assistente de IA usa um modelo local (Ollama, gratuito) ou o Claude, e consulta os dados pelas ferramentas de um servidor MCP.

| Camada | Status |
| --- | --- |
| Dashboard (React) | ✅ ligado à API, com atualização a cada 10 s |
| Backend REST + motor de gatilhos | ✅ pronto, com coletor simulado |
| Armazenamento (InfluxDB) | ✅ InfluxDB 2.x ou SQLite (desenvolvimento) |
| Servidor MCP + IA | ✅ Ollama (padrão) ou Claude; chat e análise dos relatórios |
| Coleta real | ✅ agente para Linux (envio) e coletor SNMP v3 (consulta), com detecção de queda; IPMI não testado (sem hardware) |
| Testes da seção 4.5 | ⏳ a fazer (etapa 6) |

## Stack do front-end

React 18, Vite, React Router, Recharts e lucide-react.

## Como iniciar o projeto

### Pré-requisitos

- **Node.js** 20.19 ou superior
- **Python** 3.12 ou superior
- **Ollama**, para o assistente de IA: https://ollama.com (no Windows também dá com `winget install Ollama.Ollama`). Depois de instalado, ele abre sozinho com o Windows e fica na bandeja do sistema.

Os comandos abaixo são para o PowerShell, partindo da pasta do projeto (`D:\xampp\htdocs\tcc-prototipo`).

### 1. Instalação (só na primeira vez, ou depois de atualizar o projeto)

```powershell
# backend: ambiente Python e dependências
cd backend
python -m venv .venv                            # só se a pasta .venv ainda não existir
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m app.seed                # cria os 10 servidores e as 5 regras (se ainda não existirem)
cd ..

# frontend: dependências
npm install

# assistente de IA: baixa o modelo local (cerca de 4,7 GB, uma vez só)
ollama pull qwen2.5:7b
```

### 2. Iniciar (toda vez que for usar)

São três terminais. O Ollama não precisa ser iniciado à mão.

**Terminal 1, a API (backend):**

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload
```

**Terminal 2, o coletor simulado:**

```powershell
cd backend
.venv\Scripts\python simulator\simulate.py
```

> Na **primeira vez**, rode `.venv\Scripts\python simulator\simulate.py --backfill 24h` para gerar 24 h de histórico. Nas outras vezes, rode **sem** o `--backfill`; senão o histórico é gerado de novo por cima do que já existe.

**Terminal 3, o painel (frontend):**

```powershell
npm run dev
```

Depois abra **http://localhost:5173**.

**Terminal 4 (opcional), coletor SNMP:** só é preciso se houver servidor real cadastrado com coleta SNMP.

```powershell
cd backend
.venv\Scripts\python -m collector.snmp_poller
```

Para desligar, aperte `Ctrl+C` em cada terminal.

### Monitorar um servidor real (a VPS)

O passo a passo completo está em [`docs/vps/GUIA-VPS.md`](docs/vps/GUIA-VPS.md): Tailscale, token forte, firewall, instalação do agente, SNMP opcional e como desfazer tudo. Para receber dados da VPS, a API precisa ser iniciada com `--host 0.0.0.0`, e a porta 8000 fica liberada só para a rede do Tailscale.

### 3. Conferir se está tudo no ar

- http://127.0.0.1:8000/api/v1/health deve mostrar `"status":"ok"`.
- No painel, abra o **Assistente MCP**. O cabeçalho deve mostrar "Ollama · qwen2.5:7b · MCP (7 ferramentas)" com o ponto verde. Se aparecer "Ollama não está rodando", abra o aplicativo Ollama pelo menu Iniciar.
- A primeira pergunta ao assistente demora perto de 1 minuto (o modelo é carregado na placa de vídeo). As seguintes levam de 5 a 20 s.

### Problemas comuns

| Sintoma | Causa e solução |
| --- | --- |
| Faixa vermelha "API do SMI indisponível" no painel, ou `http proxy error ... ECONNREFUSED 127.0.0.1:8000` no terminal do Vite | A API (terminal 1) não está rodando. |
| Nenhum servidor aparece | O banco não foi criado: rode `.venv\Scripts\python -m app.seed` na pasta `backend`. |
| Servidores simulados em "Sem dados" | O coletor simulado (terminal 2) não está rodando. |
| Servidor real em "Sem dados" | O agente ou o coletor SNMP ainda não enviou nada. Veja a seção "Problemas comuns" do [guia da VPS](docs/vps/GUIA-VPS.md). |
| Assistente diz que o modelo não está baixado | Rode `ollama pull qwen2.5:7b`. |

Mais detalhes do backend (InfluxDB, Claude como alternativa ao Ollama, injeção de falhas para testar os gatilhos) estão no [`backend/README.md`](backend/README.md).

### Configurações opcionais

Em desenvolvimento, o Vite repassa as chamadas a `/api` para `http://127.0.0.1:8000` (`vite.config.js`). Para usar outro endereço, defina `SMI_API_TARGET` ao rodar o Vite, ou `VITE_API_URL` para o front chamar a API direto. As configurações do backend ficam em `backend/.env` (modelo em [`backend/.env.example`](backend/.env.example)).

Outros comandos do front-end:

```bash
npm run build    # build de produção em dist/
npm run lint     # ESLint
```

## Contrato da API

O formato dos dados e as rotas REST estão em [`docs/contrato/openapi.yaml`](docs/contrato/openapi.yaml). As decisões estão explicadas em [`docs/contrato/explicacao-contrato.txt`](docs/contrato/explicacao-contrato.txt).

## Estrutura

```
backend/          # API REST, motor de gatilhos, assistente de IA, servidor MCP e coletores (Python)
├── agent/        # agente para os servidores reais (Linux) + instalador e serviço systemd
└── collector/    # coletor SNMP v3 + configuração do snmpd
docs/contrato/    # contrato da API (OpenAPI) e explicação das decisões
docs/vps/         # guia para monitorar a VPS real (Tailscale, agente, SNMP)
src/
├── api/          # cliente HTTP da API (client.js)
├── components/   # componentes reutilizáveis (KpiCard, Led, MetricBar, AlertTable, ChatPanel, gráficos…)
├── config/       # navegação, rótulos de estados e métricas
├── context/      # dados compartilhados pelo layout (Visão Geral atualizada a cada 10 s)
├── hooks/        # useApi: busca dados da API com atualização automática
├── layouts/      # DashboardLayout: barra lateral, barra superior e chat fixos
├── pages/        # Dashboard, Servidores, Gatilhos, Métricas, Topologia, Relatórios
└── utils/        # formatação e regras de gatilho
```
