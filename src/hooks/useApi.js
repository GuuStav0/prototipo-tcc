import { useCallback, useEffect, useRef, useState } from "react";

// Atualização automática das telas. 10 s mantém o pior caso de detecção dentro da
// meta de 90 s do TCC (15 s de coleta + 60 s de duração do gatilho + 10 s de tela).
export const LIVE_INTERVAL = 10_000;
export const SERIES_INTERVAL = 60_000;

/**
 * Busca dados da API e, se `interval` for informado, repete a busca periodicamente.
 *
 *   const { data, error, loading, reload } = useApi(
 *     (signal) => api.server(id, { signal }), ["server", id], { interval: LIVE_INTERVAL });
 *
 * `key` identifica a consulta: quando muda, os dados antigos são descartados e a busca
 * recomeça. Em atualizações periódicas os dados anteriores continuam na tela.
 */
export function useApi(fetcher, key, { interval } = {}) {
  const keyStr = JSON.stringify(key);
  const fetcherRef = useRef(fetcher);
  const [state, setState] = useState({ key: null, data: undefined, error: null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    const controller = new AbortController();
    let timer;
    let active = true;

    async function run() {
      try {
        const data = await fetcherRef.current(controller.signal);
        if (active) setState({ key: keyStr, data, error: null });
      } catch (err) {
        if (!active || err.name === "AbortError") return;
        setState((s) => ({ key: keyStr, data: s.key === keyStr ? s.data : undefined, error: err }));
      }
      if (active && interval) timer = setTimeout(run, interval);
    }

    run();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [keyStr, interval, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const current = state.key === keyStr;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : null,
    loading: !current,
    reload,
  };
}
