# SMI · Backend

API REST, motor de gatilhos e assistente de IA do SMI, em Python + FastAPI. Implementa o contrato em [`../docs/contrato/openapi.yaml`](../docs/contrato/openapi.yaml).

```
simulador (servidores simulados)   agente na VPS (envia)   coletor SNMP (consulta a VPS)
   │  POST /api/v1/ingest/metrics
   ▼
API ──► séries temporais: InfluxDB (ou SQLite, em desenvolvimento)
   ├──► motor de gatilhos ──► alertas, cadastros e relatórios: SQLite
   └──► assistente de IA ──► LLM (Ollama ou Claude)
              │ cliente MCP (stdio)
              ▼
        servidor MCP (smi_mcp) ──► consulta a própria API por HTTP
```

## Instalação

Requer Python 3.12 ou superior. Os comandos abaixo são para o PowerShell, rodando dentro da pasta `backend`:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m app.seed        # cria o banco com 10 servidores e as 5 regras padrão
```

## Executar

Use dois terminais:

```powershell
# 1) API em http://127.0.0.1:8000 (documentação interativa em /docs)
.venv\Scripts\python -m uvicorn app.main:app --reload

# 2) coletor simulado: gera 24 h de histórico e continua coletando a cada 15 s
.venv\Scripts\python simulator\simulate.py --backfill 24h
```

## Assistente de IA (Ollama ou Claude)

O chat do painel e a análise dos relatórios usam um modelo de linguagem que consulta os dados pelas ferramentas do **servidor MCP** (`smi_mcp/`). O backend inicia esse servidor sozinho, como um processo separado.

### Ollama (padrão, gratuito e local)

1. Instale o Ollama: https://ollama.com (no Windows também dá com `winget install Ollama.Ollama`). Ele fica rodando em segundo plano, na bandeja do sistema.
2. Baixe o modelo, cerca de 4,7 GB (uma vez só):
   ```powershell
   ollama pull qwen2.5:7b
   ```
3. Inicie a API normalmente. Em `GET /api/v1/assistant/status` deve aparecer `"available": true` e as 7 ferramentas do MCP.

A primeira pergunta depois de ligar o computador demora mais (de 30 s a 1 min), porque o modelo é carregado na placa de vídeo. As seguintes levam de 5 a 20 s. Com 8 GB de VRAM o `qwen2.5:7b` roda inteiro na GPU. Em máquinas mais fracas, use um modelo menor, como `SMI_LLM_MODEL=qwen2.5:3b`, que é mais rápido mas menos preciso.

### Claude (alternativa, pago por uso)

No `backend/.env`:

```
SMI_LLM_PROVIDER=anthropic
SMI_ANTHROPIC_API_KEY=sk-ant-...
# opcional: SMI_LLM_MODEL=claude-sonnet-5-5 ou claude-haiku-5-5, mais baratos
```

O padrão é `claude-opus-5-5`, com nível de esforço `medium` (`SMI_ANTHROPIC_EFFORT`). Se o modelo recusar uma pergunta, a própria API da Anthropic tenta de novo com outro modelo (fallback no servidor).

Para desligar a IA: `SMI_LLM_PROVIDER=none`. Os relatórios continuam saindo, só sem a seção de análise.

### Usar o servidor MCP em outros clientes

O servidor MCP é independente do backend. Para conectá-lo, por exemplo, ao Claude Desktop (com a API rodando), adicione em `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "smi": {
      "command": "D:/xampp/htdocs/tcc-prototipo/backend/.venv/Scripts/python.exe",
      "args": ["-m", "smi_mcp"],
      "cwd": "D:/xampp/htdocs/tcc-prototipo/backend",
      "env": { "SMI_API_URL": "http://127.0.0.1:8000/api/v1" }
    }
  }
}
```

Ferramentas disponíveis: `get_overview`, `list_servers`, `get_server`, `get_metrics`, `list_alerts`, `get_trigger_rules` e `create_report`.

## Servidores reais e simulados

Cada servidor tem um **modo**:

- **simulated** só aceita leituras do coletor simulado. É o caso dos 10 servidores de demonstração do seed.
- **real** só aceita leituras do agente ou do SNMP, e só das formas de coleta ativas no cadastro.

A API recusa qualquer mistura, então rodar o simulador nunca sobrescreve dados reais. O modo é trocado no painel (**Servidores → detalhe → Passar para real/simulado**), e servidores cadastrados pelo painel nascem reais.

- **Agente** (`agent/smi_agent.py`): roda no servidor monitorado e **envia** CPU, memória, disco, temperatura (quando há sensor) e uptime a cada 15 s. Se a API estiver fora, guarda as leituras (até ~24 h) e reenvia depois. Instalação na VPS com `agent/install.sh`, como serviço systemd com limite de 5% de CPU e 128 MB.
- **Coletor SNMP** (`collector/snmp_poller.py`): roda junto com a API e **consulta** por SNMP v2c/v3 os servidores reais com coleta SNMP. Para testar uma consulta sem enviar: `.venv\Scripts\python -m collector.snmp_poller --test <id>`.
- **Watchdog** (`app/watchdog.py`): se um servidor real que já enviou dados fica mais de 30 s em silêncio (`SMI_HEARTBEAT_TIMEOUT_SECONDS`), o backend registra `reachable=0` e o gatilho "Host inalcançável" dispara. O tempo em que a própria API ficou desligada não conta, para não gerar alerta falso ao religar o PC.

O passo a passo para a VPS (Tailscale, firewall, agente e SNMP) está em [`../docs/vps/GUIA-VPS.md`](../docs/vps/GUIA-VPS.md).

Tempos medidos nos testes (meta da seção 4.5: menos de 90 s):

| Situação | Alerta "Host inalcançável" |
| --- | --- |
| Agente para de enviar (VPS caiu) | 77 s |
| Agente SNMP para de responder | 58 s |

## Testar os gatilhos (injeção de falhas)

Com o simulador rodando, crie `simulator/faults.json`:

```json
[
  { "host": "srv-web-01", "metric": "cpu", "value": 97 },
  { "host": "srv-mail-01", "metric": "reachable", "value": 0 }
]
```

Cada falha vale enquanto estiver no arquivo. Para encerrá-la, apague a linha ou deixe o arquivo como `[]`. O início e o fim de cada falha ficam registrados em `simulator/faults-log.csv`. Para medir o tempo de detecção (TCC 4.5), compare esse horário com o `started_at` do alerta em `GET /api/v1/alerts`.

## Usar o InfluxDB

Por padrão as séries ficam numa tabela do SQLite, então nada precisa ser instalado. Para usar o InfluxDB 2.x, como define o TCC:

1. Instale e inicie o `influxd` e faça a configuração inicial com org `smi` e bucket `metrics`.
2. Copie `.env.example` para `.env` e defina:
   ```
   SMI_METRICS_BACKEND=influx
   SMI_INFLUX_TOKEN=<token gerado na configuração>
   ```
3. Reinicie a API. `GET /api/v1/health` deve mostrar `"influxdb": "ok"`.

`python -m app.seed --reset` apaga apenas o banco SQLite. Os dados do InfluxDB continuam no bucket.

## Testes

```powershell
.venv\Scripts\python -m pytest tests
```

O teste `test_influx_store.py` compara as respostas do InfluxDB com as do SQLite. Ele só roda quando as variáveis `SMI_TEST_INFLUX_URL` e `SMI_TEST_INFLUX_TOKEN` estão definidas.

Os testes do assistente (`test_assistant.py`) usam um modelo simulado, então não chamam o Ollama nem a Anthropic. Um deles inicia o servidor MCP de verdade, por stdio, para conferir o protocolo.

## Estrutura

```
app/
├── main.py            # cria o app, CORS e rotas sob /api/v1
├── config.py          # variáveis de ambiente SMI_*
├── domain.py          # métricas, unidades, estados e operadores
├── models.py          # tabelas (servidores, gatilhos, alertas, relatórios...)
├── schemas.py         # formatos de entrada e saída (espelham o openapi.yaml)
├── metrics_store.py   # séries temporais: SQLite ou InfluxDB
├── engine.py          # motor de gatilhos (duração, escalonamento, resolução)
├── status.py          # status dos hosts e indicadores da Visão Geral
├── reports.py         # relatórios: números do sistema + análise da IA
├── seed.py            # dados iniciais
├── assistant/         # agente de IA: provedores (Ollama/Claude), cliente MCP e laço de ferramentas
├── ingestion.py       # entrada única das leituras (valida fonte x modo, grava, roda os gatilhos)
├── watchdog.py        # detecção de servidor real em silêncio
├── migrations.py      # adiciona colunas novas a bancos antigos sem perder dados
└── routers/           # uma rota por recurso
agent/                 # agente para servidores Linux + install.sh, uninstall.sh e serviço systemd
collector/             # coletor SNMP + configuração do snmpd para a VPS
smi_mcp/server.py      # servidor MCP: as ferramentas que a IA usa
simulator/simulate.py  # coletor simulado (só para servidores em modo simulado)
evaluation/            # testes da etapa 6 (precisão, detecção, desempenho, carga, recursos, IA); ver evaluation/README.md
tests/                 # testes do motor, da API, do assistente, dos servidores reais e do SNMP
```
