import { useEffect, useState } from "react";

import {
  getRuntimeConfigSnapshot,
  loadRuntimeConfig,
  subscribeRuntimeConfig,
} from "../services/runtimeConfigService";

export function useRuntimeConfig() {
  const [config, setConfig] = useState(getRuntimeConfigSnapshot);

  useEffect(() => {
    const sync = () => setConfig(getRuntimeConfigSnapshot());
    const unsubscribe = subscribeRuntimeConfig(sync);
    loadRuntimeConfig().then(sync);
    return unsubscribe;
  }, []);

  return config;
}
