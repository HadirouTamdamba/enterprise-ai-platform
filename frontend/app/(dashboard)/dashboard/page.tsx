"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Stat, Badge } from "@/components/ui";
import { formatNumber, formatUsd } from "@/lib/utils";

interface Usage {
  requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  avg_latency_ms: number;
}
interface Inventory {
  models: number;
  prompts: number;
  knowledge_bases: number;
  pending_approvals: number;
}

export default function DashboardPage() {
  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: () => api<Usage>("/monitoring/usage?days=30"),
  });
  const inventory = useQuery({
    queryKey: ["inventory"],
    queryFn: () => api<Inventory>("/governance/inventory"),
  });
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api<{ configured: string[] }>("/gateway/providers"),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Overview</h1>
        <p className="text-sm text-zinc-500">Platform activity over the last 30 days</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="LLM requests" value={formatNumber(usage.data?.requests ?? 0)} />
        <Stat
          label="Tokens"
          value={formatNumber(
            (usage.data?.prompt_tokens ?? 0) + (usage.data?.completion_tokens ?? 0),
          )}
        />
        <Stat label="Cost" value={formatUsd(usage.data?.cost_usd ?? 0)} />
        <Stat
          label="Avg latency"
          value={`${Math.round(usage.data?.avg_latency_ms ?? 0)} ms`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="AI Inventory">
          <ul className="space-y-3 text-sm">
            <li className="flex justify-between">
              <span>Registered models</span>
              <Badge tone="info">{inventory.data?.models ?? 0}</Badge>
            </li>
            <li className="flex justify-between">
              <span>Prompts</span>
              <Badge tone="info">{inventory.data?.prompts ?? 0}</Badge>
            </li>
            <li className="flex justify-between">
              <span>Knowledge bases</span>
              <Badge tone="info">{inventory.data?.knowledge_bases ?? 0}</Badge>
            </li>
            <li className="flex justify-between">
              <span>Pending approvals</span>
              <Badge tone={inventory.data?.pending_approvals ? "warning" : "success"}>
                {inventory.data?.pending_approvals ?? 0}
              </Badge>
            </li>
          </ul>
        </Card>
        <Card title="Configured LLM providers">
          <div className="flex flex-wrap gap-2">
            {(providers.data?.configured ?? []).map((p) => (
              <Badge key={p} tone="success">
                {p}
              </Badge>
            ))}
            {providers.data?.configured.length === 0 && (
              <p className="text-sm text-zinc-500">
                No provider configured — add an API key in .env
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
