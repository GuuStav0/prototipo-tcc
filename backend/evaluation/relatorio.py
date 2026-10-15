"""Gera docs/resultados/RESULTADOS.md e os gráficos (docs/resultados/graficos/*.png) a partir
dos dados de cada teste (docs/resultados/dados/*.json). Pode ser rodado a qualquer momento:
testes ainda não executados aparecem como pendentes.

Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.relatorio
"""

import json

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .comum import DADOS_DIR, RESULTADOS_DIR, carregar  # noqa: E402

GRAF = RESULTADOS_DIR / "graficos"
# paleta categórica validada (claro): azul, laranja, água; tinta em tons de cinza
AZUL, LARANJA, AGUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA2, GRADE = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.edgecolor": TINTA2, "axes.labelcolor": TINTA, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def _grade(ax, eixo="x"):
    ax.grid(axis=eixo, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def _salvar(fig, nome):
    GRAF.mkdir(parents=True, exist_ok=True)
    fig.savefig(GRAF / nome, facecolor="white")
    plt.close(fig)
    return f"graficos/{nome}"


def fmt(v, casas=1, sufixo=""):
    if v is None:
        return "—"
    return f"{v:.{casas}f}".replace(".", ",") + sufixo


def cap(texto: str) -> str:
    """Primeira letra maiúscula sem mexer no resto (capitalize() deixaria "API" como "api")."""
    return texto[:1].upper() + texto[1:]


def ok(b):
    return "✅ atingida" if b else "❌ não atingida"


# ---------------------------------------------------------------- gráficos
def grafico_deteccao(d):
    ts = d["tentativas"]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(ts) + 1.4))
    rot = [f"{i + 1}. {t['host'].replace('srv-', '')} · {t['metrica']}" for i, t in enumerate(ts)]
    y = range(len(ts))[::-1]
    partes = [("espera da coleta", "espera_coleta_s", AZUL, None), ("confirmação do gatilho", "confirmacao_s", LARANJA, "//"),
              ("exibição na tela", "exibicao_s", AGUA, "..")]
    base = [0] * len(ts)
    for nome, chave, cor, hach in partes:
        vals = [t[chave] for t in ts]
        ax.barh(list(y), vals, left=base, color=cor, edgecolor="white", linewidth=2, hatch=hach, label=nome, height=0.7)
        base = [b + v for b, v in zip(base, vals)]
    for yi, tot in zip(y, base):
        ax.text(tot + 1, yi, fmt(tot, 0, " s"), va="center", fontsize=9, color=TINTA)
    ax.axvline(90, color=TINTA, linestyle="--", linewidth=1)
    ax.text(90, len(ts) - 0.3, " meta: 90 s", va="bottom", fontsize=9, color=TINTA)
    ax.set_yticks(list(y), rot)
    ax.set_xlabel("segundos desde o início da falha")
    ax.set_xlim(0, max(100, max(base) + 12))
    ax.set_title("Tempo de detecção por tentativa")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12 - 0.6 / len(ts)), ncol=3)
    _grade(ax)
    return _salvar(fig, "deteccao.png")


def grafico_precisao(d):
    fig, ax = plt.subplots(figsize=(7, 4))
    duracoes = [0, 15, 30, 60, 120]
    for (cen, cor, marc) in (("típico", AZUL, "o"), ("exigente", LARANJA, "s")):
        cons = d["cenarios"][cen]["consolidado"]
        vals = [cons[f"{x} s"]["precisao"] for x in duracoes]
        ax.plot(duracoes, vals, color=cor, linewidth=2, marker=marc, markersize=7, label=f"cenário {cen}")
        ax.annotate(fmt(vals[3], 1, "%"), (60, vals[3]), textcoords="offset points",
                    xytext=(-8, -16 if cen == "exigente" else 8), ha="right", fontsize=9, color=TINTA)
    ax.axvspan(65, 130, color="#ecebe7", zorder=0)
    ax.text(97, 45, "acima de ~65 s,\no pior caso de\ndetecção passaria\nde 90 s", ha="center", va="center",
            fontsize=8.5, color=TINTA2)
    ax.axhline(90, color=TINTA, linestyle="--", linewidth=1)
    ax.text(1, 91, "meta: 90%", fontsize=9, color=TINTA, va="bottom")
    ax.axvline(60, color=TINTA2, linestyle=":", linewidth=1)
    ax.set_xticks(duracoes, [f"{x} s" for x in duracoes])
    ax.set_xlim(-5, 130)
    ax.set_ylim(0, 105)
    ax.set_xlabel("duração exigida pelo gatilho (padrão do sistema: 60 s)")
    ax.set_ylabel("precisão dos alertas (%)")
    ax.set_title("Precisão dos alertas x duração do gatilho")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.84))
    _grade(ax, "y")
    return _salvar(fig, "precisao.png")


def grafico_carga(d):
    nv = d["niveis"]
    n = [x["servidores"] for x in nv]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.6))
    a1.plot(n, [x["envio_ms"]["p95"] for x in nv], color=AZUL, linewidth=2, marker="o", markersize=7)
    a1.set_title("Tempo de cada envio (p95)")
    a1.set_ylabel("milissegundos")
    a2.plot(n, [x["ciclo_s"]["max"] for x in nv], color=AZUL, linewidth=2, marker="o", markersize=7)
    a2.axhline(15, color=TINTA, linestyle="--", linewidth=1)
    a2.text(n[0], 14.6, " limite: 15 s (intervalo de coleta)", va="top", fontsize=9, color=TINTA)
    a2.set_title("Duração do ciclo de envio (máx.)")
    a2.set_ylabel("segundos")
    for a in (a1, a2):
        a.set_xscale("log")
        a.set_xticks(n, [str(x) for x in n])
        a.minorticks_off()
        a.set_xlabel("servidores enviando ao mesmo tempo")
        _grade(a, "y")
    fig.tight_layout(w_pad=3)
    return _salvar(fig, "carga.png")


def grafico_desempenho(d):
    telas = list(d["telas"])
    fria = [d["telas"][t]["fria_ms"]["max"] / 1000 for t in telas]
    quente = [d["telas"][t]["quente_ms"]["mediana"] / 1000 for t in telas]
    fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(telas) + 1.4))
    y = list(range(len(telas)))[::-1]
    ax.barh([v + 0.18 for v in y], fria, height=0.34, color=AZUL, edgecolor="white", linewidth=2,
            label="abrir a tela do zero (pior caso)")
    ax.barh([v - 0.18 for v in y], quente, height=0.34, color=LARANJA, edgecolor="white", linewidth=2, hatch="//",
            label="navegar pelo menu (mediana)")
    for yi, f, q in zip(y, fria, quente):
        ax.text(f + 0.03, yi + 0.18, fmt(f, 2, " s"), va="center", fontsize=8.5, color=TINTA)
        ax.text(q + 0.03, yi - 0.18, fmt(q, 2, " s"), va="center", fontsize=8.5, color=TINTA)
    ax.axvline(2, color=TINTA, linestyle="--", linewidth=1)
    ax.text(2, len(telas) - 0.4, " meta: 2 s", fontsize=9, color=TINTA, va="bottom")
    ax.set_yticks(y, telas)
    ax.set_xlim(0, max(2.4, max(fria) + 0.4))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v, 1)))  # vírgula decimal
    ax.set_xlabel("segundos até a tela estar completa")
    ax.set_title("Tempo de resposta do dashboard")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    _grade(ax)
    return _salvar(fig, "desempenho.png")


# ---------------------------------------------------------------- documento
def main() -> None:
    det, pre, des, car = carregar("deteccao"), carregar("precisao"), carregar("desempenho"), carregar("carga")
    ia, fun, dis = carregar("ia"), carregar("funcional"), carregar("disponibilidade")
    rec_ag = carregar("recursos_agente")
    rec_snmp = carregar("recursos_snmp_poller")
    vps = carregar("vps_recursos")
    pend = "_teste ainda não executado_"

    L = ["# Resultados dos testes do protótipo (etapa 6)", "",
         "Documento gerado por `backend/evaluation/relatorio.py` a partir dos dados em `docs/resultados/dados/`. "
         "Cada teste pode ser refeito com o script indicado; os números abaixo mudam a cada execução, mas o método é o mesmo.",
         ""]
    maquina = next((x["maquina"] for x in (det, pre, des, car, ia) if x), None)
    if maquina:
        L += [f"**Máquina dos testes:** {maquina['sistema']}, {maquina['processador']}, {maquina['nucleos_logicos']} núcleos lógicos, "
              f"{maquina['ram_gb']} GB de RAM, Python {maquina['python']}.", ""]

    # resumo
    L += ["## Resumo: metas da seção 4.5", "", "| Critério | Meta | Resultado | Situação |", "| --- | --- | --- | --- |"]
    if det:
        L.append(f"| Tempo para detectar a falha | < 90 s | média {fmt(det['total_s']['media'])} s, máximo {fmt(det['total_s']['max'])} s "
                 f"({det['total_s']['n']} tentativas) | {ok(det['atingiu_meta'])} |")
    else:
        L.append(f"| Tempo para detectar a falha | < 90 s | {pend} | — |")
    if pre:
        t = pre["cenarios"]["típico"]["consolidado"]["padrão do sistema (60 s; alcance 45 s)"]
        e = pre["cenarios"]["exigente"]["consolidado"]["padrão do sistema (60 s; alcance 45 s)"]
        L.append(f"| Precisão dos alertas | > 90% | cenário típico {fmt(t['precisao'])}%; exigente {fmt(e['precisao'])}% "
                 f"(críticos {fmt(e['precisao_criticos'])}%) | {ok(t['precisao'] > 90)} no típico; "
                 f"{ok(e['precisao'] > 90)} no exigente |")
    else:
        L.append(f"| Precisão dos alertas | > 90% | {pend} | — |")
    if rec_ag or vps:
        partes = []
        if vps:
            a = vps["servicos"].get("smi-agent")
            if a:
                partes.append(f"VPS: {fmt(a['cpu_pct_um_nucleo'], 2)}% de CPU, {fmt(a['memoria_max_mb'])} MB")
        if rec_ag:
            partes.append(f"PC: {fmt(rec_ag['cpu_pct_um_nucleo']['media'], 2)}% de CPU, {fmt(rec_ag['memoria_mb']['max'])} MB")
        atingiu = (not vps or (vps["servicos"].get("smi-agent", {}).get("cpu_pct_um_nucleo", 0) < 5
                               and vps["servicos"].get("smi-agent", {}).get("memoria_max_mb", 0) < 256)) \
            and (not rec_ag or rec_ag["atingiu_meta"])
        L.append(f"| Consumo de recursos do agente | < 5% CPU e < 256 MB | {'; '.join(partes)} | {ok(atingiu)} |")
    else:
        L.append(f"| Consumo de recursos do agente | < 5% CPU e < 256 MB | {pend} | — |")
    if des:
        L.append(f"| Tempo de resposta do dashboard | < 2 s | pior caso {fmt(des['pior_carregamento_frio_ms'] / 1000, 2)} s | {ok(des['atingiu_meta'])} |")
    else:
        L.append(f"| Tempo de resposta do dashboard | < 2 s | {pend} | — |")
    if dis and dis["horas"] < 1:
        L.append(f"| Disponibilidade do monitoramento | 99% | medição curta demais ({fmt(dis['horas'] * 60, 0)} min); "
                 "rodar `evaluation.disponibilidade` por 24 h | — |")
    elif dis:
        L.append(f"| Disponibilidade do monitoramento | 99% | {fmt(dis['disponibilidade_pct'], 3)}% em {fmt(dis['horas'])} h | {ok(dis['atingiu_meta'])} |")
    else:
        L.append(f"| Disponibilidade do monitoramento | 99% | {pend} (rodar `evaluation.disponibilidade` por 24 h) | — |")
    L.append("")

    # detecção
    L += ["## 1. Tempo de detecção de falhas", "", "Script: `python -m evaluation.deteccao`", ""]
    if det:
        L += [cap(det["metodo"]) + ".", "",
              f"![Tempo de detecção]({grafico_deteccao(det)})", "",
              "| Etapa | Média | Mínimo | Máximo |", "| --- | --- | --- | --- |"]
        for nome, k in (("Espera da coleta (intervalo de 15 s)", "espera_coleta_s"), ("Confirmação do gatilho", "confirmacao_s"),
                        ("Exibição na tela (atualização a cada 10 s)", "exibicao_s"), ("**Total**", "total_s")):
            r = det[k]
            L.append(f"| {nome} | {fmt(r['media'])} s | {fmt(r['min'])} s | {fmt(r['max'])} s |")
        if det["resolucao_s"].get("n"):
            L += ["", f"Depois que a falha termina, o alerta **resolve** em média em {fmt(det['resolucao_s']['media'])} s "
                      f"(máximo {fmt(det['resolucao_s']['max'])} s): a mesma duração é exigida para encerrar, o que evita alertas abrindo e fechando."]
        L += ["", "O tempo é praticamente determinado pela configuração: até 15 s de espera da coleta, a duração do gatilho "
                  "(60 s; 45 s para queda do servidor) e até 10 s de atualização da tela. O pior caso teórico é 85 s."]
    else:
        L.append(pend)
    L.append("")

    # precisão
    L += ["## 2. Precisão dos alertas", "", "Script: `python -m evaluation.precisao`", ""]
    if pre:
        c = pre["cenario"]
        L += [f"Cada execução passa {c['horas_por_semente']} h de leituras de {c['servidores']} servidores (uma a cada "
              f"{c['intervalo_s']} s) pela ingestão e pelo motor de gatilhos reais, com {c['falhas_reais_por_semente']} falhas reais "
              f"(2 a 8 min) e {c['picos_curtos_por_semente']} picos curtos (15 a 45 s), em {len(c['sementes'])} sementes aleatórias.",
              "", f"**Definição:** {pre['definicao']}.", "",
              "- **Cenário típico:** todos os servidores operam com folga em relação aos limites.",
              "- **Cenário exigente:** 3 dos 10 servidores operam perto do limite de aviso, gerando ruído capaz de cruzá-lo sozinho.", "",
              f"![Precisão x duração]({grafico_precisao(pre)})", "",
              "| Duração do gatilho | Precisão (típico) | Precisão (exigente) | Falhas detectadas | Atraso médio |",
              "| --- | --- | --- | --- | --- |"]
        for k in ["padrão do sistema (60 s; alcance 45 s)"] + [f"{x} s" for x in (0, 15, 30, 60, 120)]:
            t, e = pre["cenarios"]["típico"]["consolidado"][k], pre["cenarios"]["exigente"]["consolidado"][k]
            nome = f"**{k}**" if k.startswith("padrão") else k
            L.append(f"| {nome} | {fmt(t['precisao'])}% | {fmt(e['precisao'])}% (de {fmt(e['precisao_min_max_por_semente'][0])} "
                     f"a {fmt(e['precisao_min_max_por_semente'][1])}%) | {fmt(min(t['revocacao'], e['revocacao']))}% | "
                     f"{fmt(t['atraso_medio_s'])} s |")
        e = pre["cenarios"]["exigente"]["consolidado"]["padrão do sistema (60 s; alcance 45 s)"]
        L += ["", f"No cenário exigente, os alertas falsos restantes do padrão vieram de: {e['falsos_por_causa']}. "
                  f"Considerando só os alertas **críticos**, a precisão foi {fmt(e['precisao_criticos'])}%.",
              "", "**Leitura:** sem a confirmação por duração (0 s), quase todo pico vira alerta. A precisão sobe com a duração, "
                  "mas o atraso também; acima de ~65 s o pior caso de detecção passaria de 90 s. Os 60 s do padrão são o maior "
                  "valor que mantém as duas metas."]
    else:
        L.append(pend)
    L.append("")

    # desempenho
    L += ["## 3. Tempo de resposta do dashboard", "", "Script: `python -m evaluation.desempenho`", ""]
    if des:
        L += [cap(des["metodo"]) + ".", "", f"![Tempo de resposta]({grafico_desempenho(des)})", "",
              "| Tela | Abrir do zero: mediana | Abrir do zero: máximo | Navegar pelo menu: mediana |", "| --- | --- | --- | --- |"]
        for nome, t in des["telas"].items():
            L.append(f"| {nome} | {fmt(t['fria_ms']['mediana'], 0)} ms | {fmt(t['fria_ms']['max'], 0)} ms | {fmt(t['quente_ms']['mediana'], 0)} ms |")
        L += ["", "Rotas da API usadas pelas telas:", "", "| Rota | Mediana | p95 |", "| --- | --- | --- |"]
        for nome, r in des["api_ms"].items():
            L.append(f"| `{nome}` | {fmt(r['mediana'])} ms | {fmt(r['p95'])} ms |")
    else:
        L.append(pend)
    L.append("")

    # carga
    L += ["## 4. Carga e estresse", "", "Script: `python -m evaluation.carga`", ""]
    if car:
        L += [cap(car["metodo"]) + ".", "", f"![Carga]({grafico_carga(car)})", "",
              "| Servidores | Leituras/ciclo | Envio p95 | Ciclo máx. | Dashboard p95 | CPU da API (média) | Memória da API | Dentro dos limites |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for x in car["niveis"]:
            L.append(f"| {x['servidores']} | {x['leituras_por_ciclo']} | {fmt(x['envio_ms']['p95'], 0)} ms | {fmt(x['ciclo_s']['max'], 2)} s | "
                     f"{fmt(x['dashboard_ms'].get('p95'), 0)} ms | {fmt(x['api_cpu_pct_um_nucleo']['media'], 0)}% | "
                     f"{fmt(x['api_memoria_mb']['max'], 0)} MB | {'sim' if x['dentro_dos_limites'] else 'não'} |")
        L += ["", f"Maior carga dentro dos limites (ciclo < 15 s, sem erros, dashboard p95 < 2 s): **{car['maior_carga_suportada']} servidores**."]
    else:
        L.append(pend)
    L.append("")

    # recursos
    L += ["## 5. Consumo de recursos do agente", "",
          "Scripts: `python -m evaluation.recursos` (PC) e `bash vps_recursos.sh 60` (VPS)", ""]
    if vps or rec_ag or rec_snmp:
        L += ["| Onde | Processo | CPU (% de um núcleo) | Memória | Período |", "| --- | --- | --- | --- | --- |"]
        if vps:
            for s, v in vps["servicos"].items():
                L.append(f"| VPS ({vps['maquina']['nucleos']} núcleos) | {s} | {fmt(v['cpu_pct_um_nucleo'], 3)}% | "
                         f"média {fmt(v['memoria_media_mb'])} MB, máx {fmt(v['memoria_max_mb'])} MB | {vps['minutos']} min |")
        for nome, r in (("agente (smi_agent.py)", rec_ag), ("coletor SNMP", rec_snmp)):
            if r:
                L.append(f"| PC | {nome} | média {fmt(r['cpu_pct_um_nucleo']['media'], 2)}%, máx {fmt(r['cpu_pct_um_nucleo']['max'], 1)}% | "
                         f"média {fmt(r['memoria_mb']['media'])} MB, máx {fmt(r['memoria_mb']['max'])} MB | {fmt(r['minutos'])} min |")
        L += ["", "Na VPS o agente também roda com limites impostos pelo systemd (5% de CPU e 128 MB), "
                  "abaixo das metas do TCC: o consumo medido fica bem longe desses limites."]
    else:
        L.append(pend)
    L.append("")

    # IA
    L += ["## 6. Integração com a IA", "", "Script: `python -m evaluation.ia`", ""]
    if ia:
        L += [f"Modelo: **{ia['modelo']}**. {cap(ia['metodo'])}.", "",
              f"- Respostas corretas: **{fmt(ia['taxa_acerto_pct'])}%**",
              f"- Usou a ferramenta MCP adequada: {fmt(ia['ferramenta_adequada_pct'])}%",
              f"- Respostas que citaram servidor inexistente: {ia['respostas_com_servidor_inventado']}",
              f"- Tempo de resposta: mediana {fmt(ia['tempo_resposta_s']['mediana'])} s, máximo {fmt(ia['tempo_resposta_s']['max'])} s "
              + (f"(primeira pergunta após ligar: {fmt(ia['primeira_resposta_fria_s'])} s, carregamento do modelo)"
               if ia["primeira_resposta_fria_s"] > 15 else
               "(o modelo já estava carregado na memória; logo após ligar o computador, a primeira resposta leva cerca de 55 s)"),
              f"- Relatório com análise da IA: pronto em {fmt(ia['relatorio_com_ia']['segundos'])} s", "",
              "| Pergunta | Acertos | Ferramenta adequada | Tempo mediano |", "| --- | --- | --- | --- |"]
        for p, r in ia["por_pergunta"].items():
            L.append(f"| {p} | {r['acertos']}/{r['total']} | {r['ferramenta_adequada']}/{r['total']} | {fmt(r['tempo_s'].get('mediana'))} s |")
    else:
        L.append(pend)
    L.append("")

    # funcional e disponibilidade
    L += ["## 7. Testes funcionais", "", "Script: `python -m evaluation.funcional`", ""]
    if fun:
        L += ["| Área | Passaram |", "| --- | --- |"]
        for area, a in fun["backend_por_area"].items():
            L.append(f"| {area} | {a['passou']}/{a['total']}" + (f" ({a['pulado']} pulado: precisa de InfluxDB)" if a["pulado"] else "") + " |")
        for nome, s in fun["frontend"].items():
            L.append(f"| Front-end: {nome} | {s} |")
    else:
        L.append(pend)
    L += ["", "## 8. Disponibilidade do serviço de monitoramento", "", "Script: `python -m evaluation.disponibilidade --horas 24`", ""]
    if dis:
        L += [f"{dis['verificacoes']} verificações em {fmt(dis['horas'])} h: **{fmt(dis['disponibilidade_pct'], 3)}%** disponível; "
              f"{len(dis['quedas'])} interrupção(ões)."]
    else:
        L.append(pend + ". Deixe o sistema rodando normalmente e execute o script por 24 h.")
    obs = RESULTADOS_DIR / "observacoes.md"
    if obs.exists():
        L += ["", "## Observações da análise manual", "", obs.read_text(encoding="utf-8").strip()]
    L += ["", "## Limitações dos testes", "",
          "- Os testes de detecção, precisão, desempenho e carga usam o coletor simulado para provocar falhas sob demanda; "
          "a coleta real (agente e SNMP) foi validada separadamente na VPS (etapa 5).",
          "- A precisão depende de quão perto dos limites os servidores operam; por isso há dois cenários.",
          "- Os resultados da IA variam entre execuções (modelo de linguagem) e dependem do modelo usado.",
          "- Banco de séries usado nos testes: SQLite (padrão do protótipo). O InfluxDB foi validado quanto à equivalência dos resultados (etapa 2).",
          ""]

    destino = RESULTADOS_DIR / "RESULTADOS.md"
    destino.write_text("\n".join(L), encoding="utf-8")
    print(f"gerado {destino}")
    print("dados encontrados:", sorted(p.stem for p in DADOS_DIR.glob("*.json")) if DADOS_DIR.exists() else [])


if __name__ == "__main__":
    main()
