"""Load test profile (Locust) — run against a staging deployment, never production.

Usage:
    pip install locust
    locust -f tests/load/locustfile.py --host http://localhost:8000 \
           -u 50 -r 5 --run-time 5m --headless
"""

import os
import uuid

from locust import HttpUser, between, task


class PlatformUser(HttpUser):
    wait_time = between(0.5, 3)

    def on_start(self) -> None:
        email = f"load-{uuid.uuid4().hex[:8]}@test.local"
        password = os.getenv("LOAD_TEST_PASSWORD", "LoadTest123!!")
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": "Load Test", "password": password},
        )
        response = self.client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        token = response.json().get("access_token", "")
        self.client.headers["Authorization"] = f"Bearer {token}"

    @task(5)
    def health(self) -> None:
        self.client.get("/api/v1/health")

    @task(3)
    def usage_dashboard(self) -> None:
        self.client.get("/api/v1/monitoring/usage")

    @task(2)
    def list_projects(self) -> None:
        self.client.get("/api/v1/projects")

    @task(1)
    def agents_catalog(self) -> None:
        self.client.get("/api/v1/agents")
