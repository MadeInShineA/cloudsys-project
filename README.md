# IoT Edge to Cloud Pipeline Group 8

![Made with: Docker](https://badgemaxxing.com/badge/v1/Made_with-Docker-blue.svg?logo=docker&anim=shine)
![Made with: Kind](https://badgemaxxing.com/badge/v1/Made_with-Kind-blue.svg?logo=kubernetes&anim=shine)
![Made with: Nix](https://badgemaxxing.com/badge/v1/Made_with-Nix-blue.svg?logo=nixos&anim=shine)

Simulated coffee machines run on a local Kubernetes cluster (kind) acting as an edge gateway. Telemetry is stored in SQLite, analysed at the edge, then batched and sent over MQTT/TLS to **AWS IoT Core**, where Lambdas write it to DynamoDB, predict memory failures and send email alerts. Grafana reads the results.

```
simulator → SQLite → edge-analyser → iot-controller ──MQTT/TLS──▶ AWS IoT Core ──▶ Lambda ──▶ DynamoDB ──▶ Grafana
```

## Repository layout

| Path | Content |
|---|---|
| `edge-device/` | kind cluster config and Kubernetes manifests |
| `edge-device/deployment/simulator/` | Device simulator + log parser (worker image) |
| `edge-device/deployment/edge-analyser/` | Edge anomaly detection |
| `edge-device/deployment/iot-controller/` | MQTT gateway to AWS IoT Core |
| `cloud/lambda/` | Lambdas: `telemetry-parser`, `memory-predictor`, `alert-notifier` |
| `docs/` | Architecture, analysis and AWS setup documentation |

## Prerequisites

| Tool | Purpose |
|---|---|
| [Docker](https://docs.docker.com/get-docker/) or [Podman](https://podman.io/docs/installation) | Container runtime for kind and image builds |
| [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) | Local Kubernetes cluster |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | Cluster management |
| [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | Lambda deployment and AWS inspection |
| [Python 3](https://www.python.org/downloads/) + [uv](https://docs.astral.sh/uv/getting-started/installation/) | Local development and tests |

**Using Nix?** Everything except the container runtime is provided by the flake:

```sh
nix develop          # or `direnv allow` (an .envrc with `use flake` is included)
```

## Credentials

Secrets are **not** committed (see `.gitignore`). Place them as follows:

| Files | Location | Used by |
|---|---|---|
| `AmazonRootCA1.pem`, `device.pem.crt`, `private.pem.key` (downloaded when creating the IoT Thing `group-8-iot-gateway-01`) | `edge-device/deployment/certs/` | Kubernetes Secret `iot-core-certs`, mounted at `/certs` in the `iot-controller` pod |
| Personal AWS credentials | `aws configure` (`~/.aws/`), region `eu-central-1` | AWS CLI (Lambda deployment) |


## Running the pipeline

First, create the cluster from `edge-device/`:

```sh
cd edge-device
kind create cluster --config kind-config.yaml --name iot-cluster
```

Then deploy using **either** option below.

**Option A: script.** Creates or updates the Secret and ConfigMap, then (re)deploys every component. It also works on an existing cluster, for example after editing `simulator/config.yaml`.

```sh
cd deployment
./rebuild-and-deploy.sh
```

**Option B: step by step**, from `edge-device/`:

```sh
# 1. Inject the IoT Core certificates and the simulator configuration
kubectl create secret generic iot-core-certs \
  --from-file=deployment/certs/AmazonRootCA1.pem \
  --from-file=deployment/certs/device.pem.crt \
  --from-file=deployment/certs/private.pem.key
kubectl create configmap simulator-config \
  --from-file=config.yaml=deployment/simulator/config.yaml

# 2. Deploy the simulators, the edge analyser and the controller
kubectl apply -f deployment/statefulset-worker.yaml
kubectl apply -f deployment/deployment-edge-analyser.yaml
kubectl apply -f deployment/pod-iot-controller.yaml
```

Follow the controller's progress with:

```sh
kubectl logs -f iot-controller
```

Tear down with:

```sh
kind delete cluster --name iot-cluster
```

## Deploying a Lambda

From the Lambda's folder, e.g. `cloud/lambda/telemetry-parser/`:

```sh
uv run python -m zipfile -c function.zip lambda_function.py
aws lambda update-function-code --function-name group-8-telemetry-parser \
  --zip-file fileb://function.zip --region eu-central-1
```

Full architecture and AWS setup: [`docs/aws-iot-pipeline.md`](docs/aws-iot-pipeline.md).
