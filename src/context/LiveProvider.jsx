import { useMemo } from "react";
import { api } from "../api/client";
import { LIVE_INTERVAL, useApi } from "../hooks/useApi";
import { LiveContext } from "./live";

export default function LiveProvider({ children }) {
  const { data, error, reload } = useApi((signal) => api.overview("24h", { signal }), ["overview", "24h"], {
    interval: LIVE_INTERVAL,
  });
  const value = useMemo(() => ({ overview: data, error, reload }), [data, error, reload]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}
