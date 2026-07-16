"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Button, Card, Textarea } from "@/components/ui";
import { formatUsd } from "@/lib/utils";

interface AgentInfo {
  name: string;
  role: string;
  description: string;
}
interface AgentRun {
  agent: string;
  output: string;
  steps: { iteration: number; thought: string; action: string; result: string }[];
  usage: { total_tokens: number; cost_usd: number };
}

export default function AgentsPage() {
  const [selected, setSelected] = useState("planner");
  const [task, setTask] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null);

  const agents = useQuery({ queryKey: ["agents"], queryFn: () => api<AgentInfo[]>("/agents") });

  const execute = useMutation({
    mutationFn: () =>
      api<AgentRun>("/agents/run", {
        method: "POST",
        body: JSON.stringify({ agent: selected, task }),
      }),
    onSuccess: setRun,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI Agents</h1>
        <p className="text-sm text-zinc-500">
          Specialized agents with planning, tools, reflection and budget guards
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Agent catalog">
          <div className="space-y-2">
            {(agents.data ?? []).map((agent) => (
              <button
                key={agent.name}
                onClick={() => setSelected(agent.name)}
                className={`w-full rounded-lg border p-3 text-left text-sm ${
                  selected === agent.name
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-900/30"
                    : "border-zinc-200 dark:border-zinc-800"
                }`}
              >
                <p className="font-medium">{agent.role}</p>
                <p className="mt-1 text-xs text-zinc-500">{agent.description}…</p>
              </button>
            ))}
          </div>
        </Card>

        <Card title="Task" className="lg:col-span-2">
          <div className="space-y-3">
            <Textarea
              rows={4}
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder={`Give the ${selected} agent a task…`}
            />
            <Button onClick={() => execute.mutate()} disabled={task.length < 3 || execute.isPending}>
              {execute.isPending ? "Agent working…" : `Run ${selected}`}
            </Button>
            {execute.isError && (
              <p className="text-sm text-red-600">{(execute.error as Error).message}</p>
            )}
          </div>
        </Card>
      </div>

      {run && (
        <Card
          title={`Result — ${run.agent}`}
          actions={
            <div className="flex gap-2">
              <Badge>{run.usage.total_tokens} tokens</Badge>
              <Badge>{formatUsd(run.usage.cost_usd)}</Badge>
              <Badge tone="info">{run.steps.length} steps</Badge>
            </div>
          }
        >
          <p className="whitespace-pre-wrap text-sm">{run.output}</p>
          {run.steps.length > 0 && (
            <details className="mt-4">
              <summary className="cursor-pointer text-xs font-semibold uppercase text-zinc-500">
                Execution trace
              </summary>
              <ol className="mt-2 space-y-2 text-xs text-zinc-600 dark:text-zinc-400">
                {run.steps.map((s) => (
                  <li key={s.iteration} className="rounded bg-zinc-50 p-2 dark:bg-zinc-800/50">
                    <span className="font-semibold">#{s.iteration} {s.action}</span> — {s.thought}
                    <br />
                    <span className="text-zinc-500">{s.result}</span>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </Card>
      )}
    </div>
  );
}
