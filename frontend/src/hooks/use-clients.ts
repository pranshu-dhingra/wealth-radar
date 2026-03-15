"use client";

import { useState, useEffect, useCallback } from "react";
import { listClients, getClient, getClientTriggers, type ListClientsParams } from "@/lib/api";
import type { Client, TriggerScanResult } from "@/lib/types";

// ─── useClients ───────────────────────────────────────────────────────────────

export function useClients(params?: ListClientsParams) {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(params ?? {});

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listClients(params);
      setClients(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { clients, loading, error, refetch: fetch_ };
}

// ─── useClient ────────────────────────────────────────────────────────────────

export function useClient(clientId: string | null) {
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    getClient(clientId)
      .then(setClient)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [clientId]);

  return { client, loading, error };
}

// ─── useClientTriggers ────────────────────────────────────────────────────────

export function useClientTriggers(clientId: string | null) {
  const [result, setResult] = useState<TriggerScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getClientTriggers(clientId);
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  return { result, loading, error, run };
}
