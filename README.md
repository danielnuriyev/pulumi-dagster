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

### 5. Use the Trino Kind Cluster

This project deploys to the existing `trino` kind cluster. Make sure it's running:

```bash
kind get clusters
# Should show 'trino' in the list

kubectl get nodes
# Should show 4 nodes (1 control-plane + 3 workers)
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
kubectl port-forward -n dagster svc/dagster-dagster-webserver 3000:80
```

Then open http://localhost:3000

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

## User Code Deployments

This project loads user code deployment configuration from the sibling `pipelines-dagster` project.

### Required Project Structure

```
projects/
├── pulumi-dagster/          # This project
│   └── __main__.py
└── pipelines-dagster/       # Required sibling project
    └── dagster-deployment.yaml
```

### dagster-deployment.yaml Format

The `pipelines-dagster` project must contain a `dagster-deployment.yaml` file with this format:

```yaml
# Docker image configuration
image:
  repository: pipelines-dagster    # Image name
  tag: latest                      # Image tag
  pullPolicy: IfNotPresent         # Always, IfNotPresent, or Never

# List of deployments (each runs as a separate pod)
deployments:
  - name: my-deployment            # Unique deployment name
    module: my_package.definitions # Python module with Dagster definitions
    port: 4000                     # gRPC port (usually 4000)
    env:                           # Optional environment variables
      MY_VAR: my_value

# Secrets to inject (loaded from Pulumi config)
secrets:
  - S3_SECRET_KEY                  # Maps to Pulumi config "s3secretkey"
```

### Building and Loading the Image

Since Kind can't pull from your local Docker daemon, you must load images manually:

```bash
# Build the image
cd ../pipelines-dagster
docker build -t pipelines-dagster:latest .

# Load into the trino cluster
kind load docker-image pipelines-dagster:latest --name trino
```

### Setting Secrets

For each secret listed in `dagster-deployment.yaml`, set it in Pulumi config:

```bash
# S3_SECRET_KEY -> s3secretkey
pulumi config set --secret s3secretkey "your-secret-value"
```

The secret name is converted to lowercase with underscores removed for the Pulumi config key.

## Cleanup

Destroy all resources:

```bash
pulumi destroy --yes --stack dev
```

**Note**: The trino cluster is shared with other services and should not be deleted.

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

### User code deployment failing

If your user code pod is crash looping:

1. Check the logs: `kubectl logs -n dagster deployment/dagster-<deployment-name>`
2. Verify the image was loaded into Kind: `docker exec dagster-control-plane crictl images | grep pipelines`
3. Ensure `dagster-deployment.yaml` has the correct module path

