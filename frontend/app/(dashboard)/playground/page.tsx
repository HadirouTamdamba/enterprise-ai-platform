"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Button, Card, Input, Textarea } from "@/components/ui";
import { formatUsd } from "@/lib/utils";

interface ChatResponse {
  content: string;
  provider: string;
  model: string;
  usage: {
    total_tokens: number;
    cost_usd: number;
    latency_ms: number;
    cached: boolean;
  };
}

export default function PlaygroundPage() {
  const [system, setSystem] = useState("You are a helpful enterprise assistant.");
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState(0.2);
  const [result, setResult] = useState<ChatResponse | null>(null);

  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api<{ configured: string[] }>("/gateway/providers"),
  });

  const run = useMutation({
    mutationFn: () =>
      api<ChatResponse>("/gateway/chat", {
        method: "POST",
        body: JSON.stringify({
          messages: [
            { role: "system", content: system },
            { role: "user", content: prompt },
          ],
          provider: provider || null,
          model: model || null,
          temperature,
        }),
      }),
    onSuccess: setResult,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Prompt Playground</h1>
        <p className="text-sm text-zinc-500">
          Test any prompt against any configured provider — cost and latency included
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Configuration">
          <div className="space-y-3 text-sm">
            <div>
              <label className="mb-1 block font-medium">Provider (empty = default)</label>
              <select
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="">platform default</option>
                {(providers.data?.configured ?? []).map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block font-medium">Model (empty = default)</label>
              <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. claude-sonnet-5" />
            </div>
            <div>
              <label className="mb-1 block font-medium">Temperature: {temperature}</label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full"
              />
            </div>
          </div>
        </Card>

        <Card title="Prompt" className="lg:col-span-2">
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium">System</label>
              <Textarea rows={2} value={system} onChange={(e) => setSystem(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">User</label>
              <Textarea
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Write your prompt…"
              />
            </div>
            <Button onClick={() => run.mutate()} disabled={!prompt || run.isPending}>
              {run.isPending ? "Running…" : "Run"}
            </Button>
            {run.isError && (
              <p className="text-sm text-red-600">{(run.error as Error).message}</p>
            )}
          </div>
        </Card>
      </div>

      {result && (
        <Card
          title="Response"
          actions={
            <div className="flex gap-2">
              <Badge tone="info">
                {result.provider}/{result.model}
              </Badge>
              <Badge>{result.usage.total_tokens} tokens</Badge>
              <Badge>{formatUsd(result.usage.cost_usd)}</Badge>
              <Badge>{Math.round(result.usage.latency_ms)} ms</Badge>
              {result.usage.cached && <Badge tone="success">cached</Badge>}
            </div>
          }
        >
          <p className="whitespace-pre-wrap text-sm">{result.content}</p>
        </Card>
      )}
    </div>
  );
}
