"""Teste do tempo de resposta do dashboard (TCC 4.5: < 2 s).

Mede o intervalo entre a requisição do usuário (abrir uma tela) e o carregamento COMPLETO da
interface, com todos os dados e gráficos na tela, no Microsoft Edge, usando o build de
produção do painel e 7 dias de histórico no banco.

- carga fria: navegador novo a cada vez (sem cache), o pior caso;
- carga quente: navegação dentro do painel já aberto (uso normal).

Mede também o tempo de cada rota da API usada pelas telas.

Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.desempenho
"""

import time

from playwright.sync_api import sync_playwright

from .ambiente import Ambiente
from .comum import resumo, salvar

META_MS = 2000
TELAS = {
    "Visão Geral": "/dashboard",
    "Servidores": "/servidores",
    "Detalhe do servidor": "/servidores/srv-app-02",
    "Gatilhos": "/gatilhos",
    "Métricas": "/metricas",
    "Topologia": "/topologia",
    "Relatórios": "/relatorios",
}
ROTAS = {
    "GET /overview": ("overview", {}),
    "GET /servers": ("servers", {}),
    "GET /servers/{id}": ("servers/srv-app-02", {}),
    "GET /servers/{id}/metrics (4 séries, 24 h)": ("servers/srv-app-02/metrics", {"metric": "cpu,ram,disk,temp", "range": "24h"}),
    "GET /servers/{id}/metrics (4 séries, 7 dias)": ("servers/srv-app-02/metrics", {"metric": "cpu,ram,disk,temp", "range": "7d"}),
    "GET /alerts (100 mais recentes)": ("alerts", {"limit": 100}),
    "GET /triggers": ("triggers", {}),
    "GET /reports": ("reports", {}),
}
FRIAS, QUENTES, REQS_API = 5, 10, 30

# pronto = há conteúdo na área principal, nenhum indicador de carregamento e, na Visão Geral,
# todos os minigráficos de CPU desenhados (eles carregam sem indicador próprio)
PRONTO = """() => {
  const main = document.querySelector('main');
  if (!main || !main.querySelector('.smi-card, .smi-servergrid, .smi-kpi') || main.querySelector('.smi-spin')) return false;
  return [...main.querySelectorAll('.smi-minicard')].every(c => c.querySelector('.recharts-area-curve'));
}"""


def medir_tela(pagina, url: str) -> float:
    t0 = time.perf_counter()
    pagina.goto(url, wait_until="domcontentloaded")
    pagina.wait_for_function(PRONTO, timeout=30_000)
    return (time.perf_counter() - t0) * 1000


def main() -> None:
    with Ambiente(simulador=True, historico="7d", painel=True) as amb, sync_playwright() as pw:
        time.sleep(20)  # algumas coletas ao vivo além do histórico

        print("rotas da API…")
        api = {}
        for nome, (rota, params) in ROTAS.items():
            amb.api.get(rota, params=params)  # aquecimento
            tempos = []
            for _ in range(REQS_API):
                t0 = time.perf_counter()
                amb.api.get(rota, params=params).raise_for_status()
                tempos.append((time.perf_counter() - t0) * 1000)
            api[nome] = resumo(tempos)
            print(f"  {nome:45} mediana {api[nome]['mediana']:7.1f} ms  p95 {api[nome]['p95']:7.1f} ms")

        navegador = pw.chromium.launch(channel="msedge", headless=True)
        telas = {}
        for nome, caminho in TELAS.items():
            url = amb.painel_url + caminho
            frias = []
            for _ in range(FRIAS):
                contexto = navegador.new_context(viewport={"width": 1400, "height": 900})
                frias.append(medir_tela(contexto.new_page(), url))
                contexto.close()
            contexto = navegador.new_context(viewport={"width": 1400, "height": 900})
            pagina = contexto.new_page()
            # ponto de partida: outra tela (navegar para a própria tela não renderiza nada)
            origem = "/relatorios" if caminho == "/dashboard" else "/dashboard"
            medir_tela(pagina, amb.painel_url + origem)
            quentes = []
            for _ in range(QUENTES):
                pagina.goto(amb.painel_url + origem, wait_until="domcontentloaded")
                pagina.wait_for_function(PRONTO, timeout=30_000)
                # navegação interna (clique no menu), como o usuário faz
                t0 = time.perf_counter()
                pagina.evaluate(f"window.history.pushState({{}}, '', '{caminho}'); "
                                "window.dispatchEvent(new PopStateEvent('popstate'))")
                pagina.wait_for_function(PRONTO, timeout=30_000)
                quentes.append((time.perf_counter() - t0) * 1000)
            contexto.close()
            telas[nome] = {"fria_ms": resumo(frias), "quente_ms": resumo(quentes)}
            print(f"  {nome:22} fria: mediana {telas[nome]['fria_ms']['mediana']:6.0f} ms, máx {telas[nome]['fria_ms']['max']:6.0f} ms"
                  f" | quente: mediana {telas[nome]['quente_ms']['mediana']:5.0f} ms")
        navegador.close()

    pior = max(t["fria_ms"]["max"] for t in telas.values())
    print(f"\npior carregamento (frio): {pior:.0f} ms (meta < {META_MS} ms)")
    salvar("desempenho", {
        "meta": f"< {META_MS} ms entre abrir a tela e o carregamento completo da interface",
        "metodo": "Microsoft Edge (headless), build de produção do painel, 7 dias de histórico de 10 servidores; "
                  "cronômetro até haver conteúdo na tela e nenhum indicador de carregamento",
        "repeticoes": {"fria": FRIAS, "quente": QUENTES, "api": REQS_API},
        "telas": telas,
        "api_ms": api,
        "pior_carregamento_frio_ms": round(pior),
        "atingiu_meta": pior < META_MS,
    })


if __name__ == "__main__":
    main()
