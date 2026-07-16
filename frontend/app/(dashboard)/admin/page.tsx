"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Button, Card, Input } from "@/components/ui";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}
interface Workspace {
  id: string;
  name: string;
  organization_id: string;
}
interface Project {
  id: string;
  name: string;
  workspace_id: string;
}

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [projectName, setProjectName] = useState("");

  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/users") });
  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api<Workspace[]>("/workspaces"),
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
  });

  const createProject = useMutation({
    mutationFn: () =>
      api("/projects", {
        method: "POST",
        body: JSON.stringify({
          name: projectName,
          workspace_id: workspaces.data?.[0]?.id,
        }),
      }),
    onSuccess: () => {
      setProjectName("");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Administration</h1>
        <p className="text-sm text-zinc-500">Users, workspaces, projects and platform settings</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Users">
          {users.isError ? (
            <p className="text-sm text-zinc-500">Requires org admin role</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {(users.data ?? []).map((u) => (
                <li key={u.id} className="flex items-center justify-between">
                  <span>
                    <span className="font-medium">{u.full_name}</span>
                    <span className="ml-2 text-xs text-zinc-500">{u.email}</span>
                  </span>
                  <span className="flex gap-2">
                    <Badge tone="info">{u.role}</Badge>
                    <Badge tone={u.is_active ? "success" : "danger"}>
                      {u.is_active ? "active" : "disabled"}
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Projects">
          <div className="space-y-3">
            <ul className="space-y-2 text-sm">
              {(projects.data ?? []).map((p) => (
                <li key={p.id} className="flex justify-between">
                  <span className="font-medium">{p.name}</span>
                  <span className="font-mono text-xs text-zinc-400">{p.id.slice(0, 8)}</span>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <Input
                placeholder="New project name"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
              />
              <Button
                onClick={() => createProject.mutate()}
                disabled={projectName.length < 2 || !workspaces.data?.length}
              >
                Create
              </Button>
            </div>
            {createProject.isError && (
              <p className="text-xs text-red-600">{(createProject.error as Error).message}</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
