"use client";

import { useState, useEffect } from "react";
import { getPortfolio, getDrift, getOpportunities } from "@/lib/api";
import type { PortfolioResponse, DriftAnalysis } from "@/lib/types";

export function usePortfolio(clientId: string | null) {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    setError(null);
    getPortfolio(clientId)
      .then(setPortfolio)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [clientId]);

  return { portfolio, loading, error };
}

export function useDrift(clientId: string | null) {
  const [drift, setDrift] = useState<DriftAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    getDrift(clientId)
      .then(setDrift)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [clientId]);

  return { drift, loading, error };
}

export function useOpportunities(clientId: string | null) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    getOpportunities(clientId)
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [clientId]);

  return { data, loading, error };
}
