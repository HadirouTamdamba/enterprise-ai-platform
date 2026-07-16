# Deployment Guide

## 1. Docker Compose (evaluation / single host)

```bash
git clone https://github.com/HadirouTamdamba/enterprise-ai-platform.git
cd enterprise-ai-platform
cp .env.example .env
# Edit .env: set SECRET_KEY (openssl rand -hex 32), ADMIN_PASSWORD,
# and at least one LLM provider API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, …)
docker compose up -d --build
```

The `seed` service creates the schema, admin user, and a default org/workspace/project on
first start. Services: frontend :3000 · API :8000 (`/api/v1/docs`) · NGINX edge :8080 ·
Grafana :3001 · Prometheus :9090 · Qdrant :6333 · MLflow :5000.

Verify: `curl http://localhost:8000/api/v1/health/ready` → `{"status":"ready",…}`, then
run `python examples/api_usage.py` for an end-to-end smoke test.

## 2. Kubernetes (production)

Prereqs: cluster ≥1.29, ingress-nginx, cert-manager, a StorageClass with RWX support
(for the uploads PVC), images published by the `docker.yml` workflow.

```bash
# 1. Real secrets — never apply the template in config.yaml
kubectl create namespace eap
kubectl create secret generic eap-secrets -n eap \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=POSTGRES_USER=eap \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 24) \
  --from-literal=POSTGRES_DB=eap \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-...

# 2. Point config.yaml PUBLIC_API_URL + ingress.yaml host at your domain, then:
kubectl apply -k kubernetes/

# 3. Migrations + seed (one-off)
kubectl -n eap run seed --rm -i --restart=Never \
  --image=ghcr.io/hadiroutamdamba/eap-backend:latest \
  --overrides='{"spec":{"containers":[{"name":"seed","image":"ghcr.io/hadiroutamdamba/eap-backend:latest","command":["python","-m","app.infrastructure.database.seed"],"envFrom":[{"configMapRef":{"name":"eap-config"}},{"secretRef":{"name":"eap-secrets"}}]}]}}'

# 4. Verify
kubectl -n eap rollout status deployment/backend
```

Prefer managed Postgres (RDS/CloudSQL) in production: set `POSTGRES_HOST` in the ConfigMap
and drop the postgres StatefulSet from `kustomization.yaml`.

## 3. Cloud provisioning (Terraform, AWS reference)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # adjust region/env/sizing
terraform init -backend-config=backend.hcl     # S3 state bucket
terraform plan
terraform apply
aws eks update-kubeconfig --name eap-production
```

Outputs include the EKS endpoint, RDS endpoint (wire into `eap-config`) and ECR URLs
(point the `docker.yml` workflow or retag GHCR images).

## 4. CI/CD deployment

`Actions → Deploy → Run workflow` with `staging` or `production`. The GitHub environment
holds `KUBECONFIG_B64` and enforces reviewer approval for production. The workflow applies
manifests, waits for rollout, and smoke-tests `/health/ready`.

## 5. Rollback

- **App:** `kubectl -n eap rollout undo deployment/backend` (images are immutably tagged by SHA).
- **Models:** `POST /api/v1/governance/models/{id}/rollback` (previous production version).
- **Prompts:** `POST /api/v1/prompts/{id}/versions/{n}/activate`.
- **Database:** restore from `scripts/backup.sh` output; migrations are Alembic-versioned.
