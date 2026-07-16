"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Stat } from "@/components/ui";
import { formatNumber, formatUsd } from "@/lib/utils";

interface Costs {
  total_cost_usd: number;
  total_requests: number;
  avg_latency_ms: number;
  by_model: { provider: string; model: string; requests: number; cost_usd: number }[];
}

export default function MonitoringPage() {
  const costs = useQuery({
    queryKey: ["costs"],
    queryFn: () => api<Costs>("/monitoring/costs?days=30"),
  });
  const maxCost = Math.max(...(costs.data?.by_model.map((m) => m.cost_usd) ?? [0]), 0.0001);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Monitoring Center</h1>
        <p className="text-sm text-zinc-500">
          AI usage, cost and latency — 30 days. Infrastructure metrics live in Grafana (:3001)
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Stat label="Total requests" value={formatNumber(costs.data?.total_requests ?? 0)} />
        <Stat label="Total cost" value={formatUsd(costs.data?.total_cost_usd ?? 0)} />
        <Stat label="Avg latency" value={`${Math.round(costs.data?.avg_latency_ms ?? 0)} ms`} />
      </div>

      <Card title="Cost by model">
        {(costs.data?.by_model ?? []).length === 0 ? (
          <p className="text-sm text-zinc-500">No usage recorded yet</p>
        ) : (
          <div className="space-y-3">
            {costs.data!.by_model.map((m) => (
              <div key={`${m.provider}/${m.model}`}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>
                    {m.provider}/{m.model}
                    <span className="ml-2 text-xs text-zinc-500">
                      {formatNumber(m.requests)} req
                    </span>
                  </span>
                  <span className="font-medium">{formatUsd(m.cost_usd)}</span>
                </div>
                <div className="h-2 rounded-full bg-zinc-100 dark:bg-zinc-800">
                  <div
                    className="h-2 rounded-full bg-brand-500"
                    style={{ width: `${(m.cost_usd / maxCost) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
