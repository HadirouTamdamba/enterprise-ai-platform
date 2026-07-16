"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Button, Card, Input, Spinner, Textarea } from "@/components/ui";

interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  chunking_strategy: string;
}
interface Doc {
  id: string;
  filename: string;
  status: string;
  version: number;
  chunk_count: number;
}
interface Citation {
  filename: string;
  page: number | null;
  score: number;
  excerpt: string;
}
interface RagAnswer {
  answer: string;
  citations: Citation[];
  confidence: number;
}
interface Project {
  id: string;
  name: string;
  workspace_id: string;
}

export default function RagStudioPage() {
  const queryClient = useQueryClient();
  const [selectedKb, setSelectedKb] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [newKbName, setNewKbName] = useState("");

  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
  });
  const kbs = useQuery({
    queryKey: ["kbs"],
    queryFn: () => api<KnowledgeBase[]>("/rag/knowledge-bases"),
  });
  const docs = useQuery({
    queryKey: ["docs", selectedKb],
    queryFn: () => api<Doc[]>(`/rag/knowledge-bases/${selectedKb}/documents`),
    enabled: !!selectedKb,
    refetchInterval: 5000,
  });

  const createKb = useMutation({
    mutationFn: async () => {
      const project = projects.data?.[0];
      if (!project) throw new Error("Create a project first (Administration)");
      return api("/rag/knowledge-bases", {
        method: "POST",
        body: JSON.stringify({
          name: newKbName,
          project_id: project.id,
          workspace_id: project.workspace_id,
        }),
      });
    },
    onSuccess: () => {
      setNewKbName("");
      queryClient.invalidateQueries({ queryKey: ["kbs"] });
    },
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api(`/rag/knowledge-bases/${selectedKb}/documents`, {
        method: "POST",
        body: form,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["docs", selectedKb] }),
  });

  const ask = useMutation({
    mutationFn: () =>
      api<RagAnswer>("/rag/query", {
        method: "POST",
        body: JSON.stringify({ knowledge_base_id: selectedKb, question }),
      }),
    onSuccess: setAnswer,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">RAG Studio</h1>
        <p className="text-sm text-zinc-500">
          Build knowledge bases, upload documents, ask grounded questions with citations
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Knowledge bases" className="lg:col-span-1">
          <div className="space-y-2">
            {(kbs.data ?? []).map((kb) => (
              <button
                key={kb.id}
                onClick={() => setSelectedKb(kb.id)}
                className={`w-full rounded-lg border p-3 text-left text-sm ${
                  selectedKb === kb.id
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-900/30"
                    : "border-zinc-200 dark:border-zinc-800"
                }`}
              >
                <p className="font-medium">{kb.name}</p>
                <p className="text-xs text-zinc-500">{kb.chunking_strategy} chunking</p>
              </button>
            ))}
            <div className="flex gap-2 pt-2">
              <Input
                placeholder="New knowledge base name"
                value={newKbName}
                onChange={(e) => setNewKbName(e.target.value)}
              />
              <Button
                onClick={() => createKb.mutate()}
                disabled={newKbName.length < 2 || createKb.isPending}
              >
                Create
              </Button>
            </div>
            {createKb.isError && (
              <p className="text-xs text-red-600">{(createKb.error as Error).message}</p>
            )}
          </div>
        </Card>

        <Card title="Documents" className="lg:col-span-2">
          {!selectedKb ? (
            <p className="text-sm text-zinc-500">Select a knowledge base</p>
          ) : (
            <div className="space-y-3">
              <label className="flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-zinc-300 p-6 text-sm text-zinc-500 hover:border-brand-500 dark:border-zinc-700">
                {upload.isPending ? <Spinner /> : "Click to upload (PDF, DOCX, PPTX, XLSX, MD, CSV, HTML…)"}
                <input
                  type="file"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])}
                />
              </label>
              <ul className="divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
                {(docs.data ?? []).map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between py-2">
                    <span>
                      {doc.filename}{" "}
                      <span className="text-xs text-zinc-400">v{doc.version}</span>
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs text-zinc-500">{doc.chunk_count} chunks</span>
                      <Badge
                        tone={
                          doc.status === "indexed"
                            ? "success"
                            : doc.status === "failed"
                              ? "danger"
                              : "warning"
                        }
                      >
                        {doc.status}
                      </Badge>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <Card title="Ask the knowledge base">
        <div className="space-y-3">
          <Textarea
            rows={2}
            placeholder="Ask a question grounded in your documents…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Button
            onClick={() => ask.mutate()}
            disabled={!selectedKb || question.length < 3 || ask.isPending}
          >
            {ask.isPending ? "Thinking…" : "Ask"}
          </Button>
          {ask.isError && (
            <p className="text-sm text-red-600">{(ask.error as Error).message}</p>
          )}
          {answer && (
            <div className="space-y-3 rounded-lg bg-zinc-50 p-4 dark:bg-zinc-800/50">
              <div className="flex items-center gap-2">
                <Badge tone={answer.confidence >= 0.7 ? "success" : "warning"}>
                  groundedness {(answer.confidence * 100).toFixed(0)}%
                </Badge>
              </div>
              <p className="whitespace-pre-wrap text-sm">{answer.answer}</p>
              {answer.citations.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase text-zinc-500">Sources</p>
                  <ul className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
                    {answer.citations.map((c, i) => (
                      <li key={i}>
                        [{i + 1}] {c.filename}
                        {c.page ? ` — p.${c.page}` : ""} (score {c.score.toFixed(2)})
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
