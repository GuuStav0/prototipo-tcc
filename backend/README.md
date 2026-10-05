# SMI · Backend

API REST e motor de gatilhos do SMI, em Python + FastAPI. Implementa o contrato em [`../docs/contrato/openapi.yaml`](../docs/contrato/openapi.yaml).

```
coletor (simulador / SNMP / IPMI / agente)
   │  POST /api/v1/ingest/metrics
   ▼
API ──► séries temporais: InfluxDB (ou SQLite, em desenvolvimento)
   └──► motor de gatilhos ──► alertas, cadastros e relatórios: SQLite
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
├── reports.py         # geração dos relatórios (modelo fixo até a etapa 4)
├── seed.py            # dados iniciais
└── routers/           # uma rota por recurso
simulator/simulate.py  # coletor simulado com injeção de falhas
tests/                 # testes do motor e da API
```
