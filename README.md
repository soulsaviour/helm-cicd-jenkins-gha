# helm-cicd-jenkins-gha

One service, two CI/CD setups: a Jenkins pipeline that pushes to ECR, and
GitHub Actions workflows that push to GHCR. Both test the code, validate the
Helm chart, build the image tagged with the commit SHA, and deploy it with
`helm upgrade --install --atomic`, so a release whose pods never become ready
is rolled back automatically.

The service, `inventory-api`, is a small Flask app with separate liveness
(`/healthz`) and readiness (`/readyz`) endpoints. It's there to give the
pipelines something real to build and deploy.

## Layout

```
app/                       Flask service and its tests
Dockerfile                 multi-stage build, non-root user
chart/inventory-api/       Helm chart
deploy/values-dev.yaml     per-environment overrides
deploy/values-prod.yaml
Jenkinsfile                Jenkins pipeline (ECR)
.github/workflows/ci.yml   tests, chart checks, image build (GHCR)
.github/workflows/deploy.yml  manual deploy to dev or prod
```

## The Helm chart

- Rolling updates with `maxUnavailable: 0`, so capacity never drops during a
  deploy, plus readiness and liveness probes.
- Optional HorizontalPodAutoscaler on CPU, with a 5-minute scale-down
  stabilisation window to avoid flapping.
- PodDisruptionBudget so node drains and cluster upgrades never take out every
  replica at once.
- Topology spread across zones and nodes.
- Hardened pods: non-root UID, read-only root filesystem (with a small
  in-memory `/tmp` for gunicorn), all capabilities dropped, `RuntimeDefault`
  seccomp, no service account token mounted.
- Ingress for dev; ingress with cert-manager TLS and autoscaling for prod.

```bash
helm template inventory-api chart/inventory-api -f deploy/values-prod.yaml
```

## Jenkins

`Jenkinsfile` stages: **Test** (ruff and pytest in a virtualenv) → **Lint chart**
→ **Build image** (tag = short commit SHA) → **Push to ECR** → **Deploy to
dev** → **Approve production** (manual input, restricted to the
`release-managers` group) → **Deploy to production**. Branches other than
`main` stop after the build.

It expects an agent with docker, helm, kubectl and the AWS CLI, these
credentials:

| ID | Kind | Used for |
|----|------|----------|
| `aws-ci` | AWS credentials | `docker push` to ECR |
| `kubeconfig-dev` | secret file | Deploying to dev |
| `kubeconfig-prod` | secret file | Deploying to production |

and a global `AWS_ACCOUNT_ID` environment variable for the registry address.

## GitHub Actions

**ci.yml** runs on pushes and pull requests: app tests, `helm lint` and
`kubeconform` against the rendered manifests for both environments, hadolint,
then a Buildx image build. On `main` the image is pushed to
`ghcr.io/<owner>/<repo>` tagged with the full commit SHA and `latest`, using
the workflow's own `GITHUB_TOKEN`, with layer caching.

**deploy.yml** is started by hand with an environment and an image tag. Each
GitHub environment (`dev`, `prod`) holds its own `KUBECONFIG_B64` secret
(a base64-encoded kubeconfig), so a dev deploy can't reach production
credentials. Add required reviewers to the `prod` environment in the
repository settings to get the same approval gate as in Jenkins. Deploys to
the same environment are queued, never run in parallel.

## Running it locally

```bash
cd app && pip install -r requirements.txt -r requirements-dev.txt && pytest
docker build -t inventory-api:local --build-arg APP_VERSION=local .
docker run --rm -p 8080:8080 inventory-api:local
curl localhost:8080/items
```

Deploy to a local cluster (kind, minikube):

```bash
kind load docker-image inventory-api:local
helm upgrade --install inventory-api chart/inventory-api \
  --set image.repository=inventory-api --set image.tag=local --wait
kubectl port-forward svc/inventory-api 8080:80
```

## Rolling back

Every deploy is a Helm revision:

```bash
helm -n inventory history inventory-api
helm -n inventory rollback inventory-api <revision> --wait
```

Or redeploy an earlier commit's image through either pipeline.
