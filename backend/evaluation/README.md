# Testes da etapa 6 (seções 4.4 e 4.5 do TCC)

> **Rode todos os comandos de dentro da pasta `backend`** (`cd backend`). Na pasta do projeto, o Python não encontra o módulo `evaluation`.

Cada script mede uma meta, grava os dados brutos em `docs/resultados/dados/` e pode ser refeito a qualquer momento. Depois de rodar qualquer um deles, gere o documento com tabelas e gráficos:

```powershell
.venv\Scripts\python -m evaluation.relatorio      # -> docs/resultados/RESULTADOS.md e graficos/
```

Antes, instale as dependências (uma vez só):

```powershell
.venv\Scripts\pip install -r requirements-eval.txt
```

## Testes que rodam sozinhos no PC

Eles sobem uma cópia isolada do sistema (API na porta 8010, painel na 5175, banco temporário) e não mexem no sistema de vocês.

| Script | Mede | Duração |
| --- | --- | --- |
| `python -m evaluation.precisao` | precisão dos alertas (> 90%) em 2 cenários e 6 configurações | ~12 min |
| `python -m evaluation.deteccao 10` | tempo até o alerta aparecer na tela (< 90 s), com navegador real | ~15 min |
| `python -m evaluation.desempenho` | tempo de resposta do dashboard (< 2 s) | ~4 min |
| `python -m evaluation.carga` | carga e estresse: de 10 a 1000 servidores | ~8 min |
| `python -m evaluation.recursos` | consumo do agente (< 5% CPU, < 256 MB) | 10 min |
| `python -m evaluation.ia` | integração com a IA (precisa do Ollama aberto) | ~3 min |
| `python -m evaluation.funcional` | suíte automatizada + lint e build do front | ~1 min |

Os testes com navegador usam o Microsoft Edge já instalado no Windows.

## Testes que vocês rodam

1. **Disponibilidade (24 h)**, com o sistema de vocês funcionando normalmente:
   ```powershell
   .venv\Scripts\python -m evaluation.disponibilidade --horas 24
   ```
   Pode interromper com Ctrl+C: o resumo é gerado com o que foi coletado até ali.

2. **Consumo do agente na VPS**: copie `evaluation/vps_recursos.sh` para a VPS (por `scp`, pelo IP público) e rode:
   ```bash
   bash vps_recursos.sh 60
   ```
   No fim ele imprime um JSON. Salve-o em `docs/resultados/dados/vps_recursos.json` (ou mande para o Claude) e gere o relatório de novo.

3. **Consumo do coletor SNMP** (opcional), com ele rodando:
   ```powershell
   .venv\Scripts\python -m evaluation.recursos --anexar snmp_poller --minutos 30
   ```

## Observações manuais

O que for percebido lendo os dados e as respostas, e que a conferência automática não cobre, vai em `docs/resultados/observacoes.md`. Esse arquivo entra no relatório gerado.
