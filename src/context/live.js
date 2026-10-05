import { createContext, useContext } from "react";

// Dados "ao vivo" compartilhados pelo layout: a Visão Geral (GET /overview), atualizada a
// cada 10 s. Sidebar, Topbar e Dashboard leem daqui em vez de cada um consultar a API.
export const LiveContext = createContext({ overview: undefined, error: null, reload: () => {} });

export function useLive() {
  return useContext(LiveContext);
}
