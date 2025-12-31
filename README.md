# Dagster on Kubernetes with Pulumi

Deploy Dagster to a local Kubernetes cluster using Pulumi and the official Dagster Helm chart.

## Architecture

- **Dagster Webserver** - Web UI for monitoring pipelines and runs
- **Dagster Daemon** - Background process for schedules, sensors, and run queuing
- **PostgreSQL** - Metadata storage for Dagster

## Prerequisites

### 1. Install Homebrew (macOS)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 2. Install Docker Desktop

Download and install from [docker.com](https://www.docker.com/products/docker-desktop/)

### 3. Install Required Tools

```bash
brew install kind kubectl helm pulumi uv
```

### 4. Configure Pulumi for Local State

```bash
pulumi login file://~
```

This stores Pulumi state locally instead of in Pulumi Cloud.

Set your Pulumi passphrase as an environment variable (add to your `~/.zshrc` or `~/.bashrc`):

```bash
export PULUMI_CONFIG_PASSPHRASE="your-secure-passphrase"
```

This passphrase encrypts your Pulumi secrets. Use the same passphrase consistently.

### 5. Create a Kind Cluster

Create a file `kind-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: dagster
nodes:
  - role: control-plane
  - role: worker
```

Create the cluster:

```bash
kind create cluster --config kind-config.yaml
```

Verify the cluster is running:

```bash
kubectl get nodes
```

### 6. Install Python Dependencies

```bash
cd pulumi-dagster
uv sync
```

### 7. Initialize Pulumi Stack

If this is a fresh clone, initialize the dev stack:

```bash
pulumi stack init dev
```

### 8. Set Required Secrets

Before deploying, set the PostgreSQL password. This is stored as an encrypted secret in `Pulumi.dev.yaml`.

```bash
pulumi config set --secret postgresqlPassword "your-postgres-password"
```

To verify your secret is set:

```bash
pulumi config
```

You should see `postgresqlPassword` listed as `[secret]`.

## Deploy

```bash
pulumi up --yes --stack dev
```

## Access Dagster UI

Port-forward the webserver service:

```bash
kubectl port-forward -n dagster svc/dagster-dagster-webserver 8080:80
```

Then open http://localhost:8080

## Configuration

The deployment uses these default settings:

| Setting | Value |
|---------|-------|
| Namespace | `dagster` |
| PostgreSQL Username | `dagster` |
| PostgreSQL Database | `dagster` |
| Webserver Service Type | `ClusterIP` |
| Webserver Port | `80` |
| Helm Chart Version | `1.12.8` |

To customize, modify the `dagster_values` dictionary in `__main__.py`.

## Adding User Code Deployments

The default chart includes an example user code deployment that will fail since it's a placeholder. To add your own:

1. Build and push your Dagster code to a container registry
2. Update `dagster_values` in `__main__.py`:

```python
dagster_values = {
    # ... existing config ...
    "dagster-user-deployments": {
        "enabled": True,
        "deployments": [
            {
                "name": "my-user-code",
                "image": {
                    "repository": "your-registry/your-dagster-code",
                    "tag": "latest",
                    "pullPolicy": "Always"
                },
                "dagsterApiGrpcArgs": [
                    "-m", "your_module"
                ],
                "port": 3030
            }
        ]
    }
}
```

## Cleanup

Destroy all resources:

```bash
pulumi destroy --yes --stack dev
```

Delete the Kind cluster:

```bash
kind delete cluster --name dagster
```

## Troubleshooting

### Check pod status

```bash
kubectl get pods -n dagster
```

### View logs

```bash
kubectl logs -n dagster deployment/dagster-dagster-webserver
kubectl logs -n dagster deployment/dagster-daemon
kubectl logs -n dagster statefulset/dagster-postgresql
```

### Restart a deployment

```bash
kubectl rollout restart deployment/dagster-dagster-webserver -n dagster
```

### Example user code failing

The chart includes an example user code deployment that will crash loop. This is expected if you haven't added your own code. The webserver and daemon will still function.

