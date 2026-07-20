# Kubernetes deployment

Kustomize manifests for deploying the full AI-Interview-Tutor backend stack inside a Kubernetes cluster (minikube, kind, k3s).

The layout mirrors [`docker-compose.yaml`](../docker-compose.yaml): five application services, nginx API gateway, and in-cluster infrastructure (Postgres, Redis, RabbitMQ, MongoDB, LocalStack).

## Layout

```
k8s/
├── base/                  # Shared manifests (no secrets)
│   ├── configmaps/
│   ├── infra/
│   └── apps/
└── overlays/
    └── dev/               # Local cluster overlay (NodePort, dev secrets)
```

## Prerequisites

- Kubernetes cluster with a default StorageClass (for PVCs)
- `kubectl` and built-in `kustomize`
- Docker (to build application images)

## 1. Build application images

From the repository root:

```bash
docker build -t ai-interview-tutor/user-management:latest -f user-management-service/Dockerfile .
docker build -t ai-interview-tutor/interview-service:latest -f interview-service/Dockerfile .
docker build -t ai-interview-tutor/practice-service:latest -f practice-service/Dockerfile .
docker build -t ai-interview-tutor/analyze-service:latest -f analyze-service/Dockerfile .
docker build -t ai-interview-tutor/notification-service:latest -f notification-service/Dockerfile .
```

## 2. Load images into the cluster

**minikube:**

```bash
minikube image load ai-interview-tutor/user-management:latest
minikube image load ai-interview-tutor/interview-service:latest
minikube image load ai-interview-tutor/practice-service:latest
minikube image load ai-interview-tutor/analyze-service:latest
minikube image load ai-interview-tutor/notification-service:latest
```

**kind:**

```bash
kind load docker-image ai-interview-tutor/user-management:latest
kind load docker-image ai-interview-tutor/interview-service:latest
kind load docker-image ai-interview-tutor/practice-service:latest
kind load docker-image ai-interview-tutor/analyze-service:latest
kind load docker-image ai-interview-tutor/notification-service:latest
```

## 3. Configure secrets

The dev overlay includes pre-filled secrets in [`overlays/dev/app-secrets.yaml`](overlays/dev/app-secrets.yaml) matching `docker-compose.yaml` defaults. JWT keys use the CI test fixtures from `tests/fixtures/dev_rsa_*.pem`.

For a custom environment, copy the template:

```bash
cp k8s/base/secrets/app-secrets.example.yaml k8s/overlays/dev/app-secrets.yaml
# Edit values, then apply
```

Set LLM API keys (`OPENAI_API_KEY`, etc.) and SES credentials before using interview, analyze, or notification features in production-like setups.

## 4. Deploy

```bash
kubectl apply -k k8s/overlays/dev
```

Preview rendered manifests:

```bash
kubectl kustomize k8s/overlays/dev
```

## 5. Verify

```bash
kubectl -n ai-interview-tutor get pods
kubectl -n ai-interview-tutor get svc
```

Wait until all pods are `Running` and ready. Infrastructure pods (Postgres, RabbitMQ, MongoDB) may take a few minutes on first start while PVCs bind and databases initialize.

**Access the API gateway (nginx NodePort 30080):**

```bash
# minikube
minikube service -n ai-interview-tutor nginx --url

# or direct node IP (nginx → interview-service at /)
curl http://<node-ip>:30080/
```

Interview service health (internal):

```bash
kubectl -n ai-interview-tutor exec deploy/interview-service -- curl -sf http://localhost:8001/health/ready
```

## Architecture notes

| Component | K8s resource | Notes |
|-----------|--------------|-------|
| nginx | Deployment + NodePort Service | API gateway, WebSocket sticky sessions (`ip_hash`) |
| user-management | Deployment + Service :8000 | Runs Alembic migrations on startup |
| interview-service | Deployment + Service :8001 | Readiness: `/health/ready` |
| practice-service | Deployment + Service :8000 | Readiness: `/ready` |
| analyze-service | Deployment (worker) | 4Gi memory limit |
| notification-service | Deployment (worker) | No HTTP probes |
| postgres | StatefulSet | DBs: `user_management`, `interview` |
| redis | Deployment + PVC | ACL users matching Compose |
| rabbitmq | StatefulSet | Management UI on port 15672 (cluster-internal) |
| mongodb | StatefulSet | Database: `ai_interview` |
| localstack | Deployment + PVC | S3 emulator for dev |

### Startup ordering

Application pods use `initContainers` (busybox) to wait for infrastructure TCP ports. Nginx waits for HTTP health endpoints of the three API services.

### What is not included

- Frontend (Next.js) — separate repository
- TLS / Ingress controller — use NodePort for local dev; add cert-manager overlay for production
- Managed cloud databases (RDS, ElastiCache, etc.)
- CI/CD image push to a container registry

## Customization

- **Base manifests:** edit `k8s/base/` for shared configuration
- **Dev overlay:** edit `k8s/overlays/dev/` for local cluster tweaks (NodePort, image pull policy)
- **New environment:** create `k8s/overlays/<env>/` referencing `../../base` with environment-specific secrets and patches

## Teardown

```bash
kubectl delete -k k8s/overlays/dev
```

PVCs are retained unless manually deleted. To remove data volumes:

```bash
kubectl -n ai-interview-tutor delete pvc --all
```
