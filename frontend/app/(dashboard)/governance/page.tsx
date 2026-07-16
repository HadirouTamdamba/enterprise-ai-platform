"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui";

interface Model {
  id: string;
  name: string;
  version: string;
  stage: string;
  risk_level: string;
  approval_status: string;
}
interface Approval {
  id: string;
  resource_type: string;
  resource_id: string;
  status: string;
  justification: string;
}
interface AuditEvent {
  id: string;
  created_at: string;
  action: string;
  resource_type: string;
  entry_hash: string;
}

const riskTone = (risk: string) =>
  risk === "high" ? "danger" : risk === "limited" ? "warning" : "success";

export default function GovernancePage() {
  const queryClient = useQueryClient();
  const models = useQuery({
    queryKey: ["gov-models"],
    queryFn: () => api<Model[]>("/governance/models"),
  });
  const approvals = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<Approval[]>("/governance/approvals?status=pending_review"),
  });
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<AuditEvent[]>("/governance/audit?limit=15"),
  });

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api(`/governance/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ approve, comment: approve ? "Approved" : "Rejected" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["gov-models"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Governance Center</h1>
        <p className="text-sm text-zinc-500">
          Model registry, human approvals, risk levels, tamper-evident audit trail
        </p>
      </div>

      <Card title="Model registry">
        {(models.data ?? []).length === 0 ? (
          <p className="text-sm text-zinc-500">No models registered yet</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs uppercase text-zinc-500 dark:border-zinc-800">
                <th className="py-2">Model</th>
                <th>Version</th>
                <th>Stage</th>
                <th>Risk</th>
                <th>Approval</th>
              </tr>
            </thead>
            <tbody>
              {models.data!.map((m) => (
                <tr key={m.id} className="border-b border-zinc-100 dark:border-zinc-800/50">
                  <td className="py-2 font-medium">{m.name}</td>
                  <td>{m.version}</td>
                  <td>
                    <Badge tone={m.stage === "production" ? "success" : "neutral"}>{m.stage}</Badge>
                  </td>
                  <td>
                    <Badge tone={riskTone(m.risk_level)}>{m.risk_level}</Badge>
                  </td>
                  <td>
                    <Badge tone={m.approval_status === "approved" ? "success" : "warning"}>
                      {m.approval_status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pending approvals (human-in-the-loop)">
          {(approvals.data ?? []).length === 0 ? (
            <p className="text-sm text-zinc-500">Nothing awaiting review</p>
          ) : (
            <ul className="space-y-3">
              {approvals.data!.map((a) => (
                <li key={a.id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                  <p className="font-medium">
                    {a.resource_type} — {a.resource_id.slice(0, 8)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">{a.justification || "No justification"}</p>
                  <div className="mt-2 flex gap-2">
                    <Button onClick={() => decide.mutate({ id: a.id, approve: true })}>
                      Approve
                    </Button>
                    <Button variant="danger" onClick={() => decide.mutate({ id: a.id, approve: false })}>
                      Reject
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Audit trail (hash-chained)">
          <ul className="space-y-2 text-xs">
            {(audit.data ?? []).map((e) => (
              <li key={e.id} className="flex items-center justify-between border-b border-zinc-100 py-1.5 dark:border-zinc-800/50">
                <span>
                  <span className="font-medium">{e.action}</span>
                  <span className="ml-2 text-zinc-500">{e.resource_type}</span>
                </span>
                <span className="font-mono text-zinc-400">{e.entry_hash.slice(0, 10)}…</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
