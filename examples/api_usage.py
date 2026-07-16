#!/usr/bin/env python3
"""End-to-end API walkthrough: login → project → knowledge base → upload → RAG query.

Requires the Docker Compose stack (make up) and httpx: pip install httpx
"""

import io
import os
import sys
from pathlib import Path

import httpx

API = "http://localhost:8000/api/v1"


def _credentials() -> dict[str, str]:
    """ADMIN_EMAIL / ADMIN_PASSWORD from the environment, falling back to ../.env."""
    email = os.getenv("ADMIN_EMAIL", "")
    password = os.getenv("ADMIN_PASSWORD", "")
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.strip().partition("=")
            if key == "ADMIN_EMAIL" and not email:
                email = value
            if key == "ADMIN_PASSWORD" and not password:
                password = value
    return {"username": email or "admin@example.com", "password": password or "ChangeMe123!"}


ADMIN = _credentials()


def main() -> int:
    client = httpx.Client(base_url=API, timeout=60)

    # 1. Authenticate
    tokens = client.post("/auth/login", data=ADMIN).raise_for_status().json()
    client.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    print("✓ authenticated")

    # 2. Reuse the seeded workspace/project
    projects = client.get("/projects").raise_for_status().json()
    project = projects[0]
    print(f"✓ project: {project['name']}")

    # 3. Create a knowledge base
    kb = client.post(
        "/rag/knowledge-bases",
        json={
            "name": "Demo KB",
            "project_id": project["id"],
            "workspace_id": project["workspace_id"],
            "similarity_threshold": 0.0,
        },
    )
    if kb.status_code == 409:
        kb_id = next(
            k["id"]
            for k in client.get("/rag/knowledge-bases").json()
            if k["name"] == "Demo KB"
        )
    else:
        kb_id = kb.raise_for_status().json()["id"]
    print(f"✓ knowledge base: {kb_id}")

    # 4. Upload a document (ingestion runs async via Celery)
    content = (
        b"Enterprise AI Policy: all high-risk models require human approval. "
        b"Token budgets are reviewed monthly by the platform team."
    )
    doc = client.post(
        f"/rag/knowledge-bases/{kb_id}/documents",
        files={"file": ("policy.txt", io.BytesIO(content), "text/plain")},
    ).raise_for_status().json()
    print(f"✓ uploaded: {doc['filename']} (status: {doc['status']})")

    # 5. Ask a grounded question
    answer = client.post(
        "/rag/query",
        json={"knowledge_base_id": kb_id, "question": "Who approves high-risk models?"},
    ).raise_for_status().json()
    print(f"\nAnswer: {answer['answer']}")
    print(f"Confidence: {answer['confidence']}")
    for i, citation in enumerate(answer["citations"], 1):
        print(f"  [{i}] {citation['filename']} (score {citation['score']})")

    # 6. Check the cost dashboard
    usage = client.get("/monitoring/usage").raise_for_status().json()
    print(f"\nUsage last 30 days: {usage['requests']} requests, ${usage['cost_usd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
