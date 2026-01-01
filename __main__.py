import pulumi
import yaml
from pathlib import Path
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from pulumi_kubernetes.core.v1 import Namespace

# Load configuration
config = pulumi.Config()
postgresql_password = config.require_secret("postgresqlPassword")

# Load deployment config from pipelines-dagster
pipelines_dagster_path = Path(__file__).parent.parent / "pipelines-dagster"
deployment_config_path = pipelines_dagster_path / "dagster-deployment.yaml"

with open(deployment_config_path) as f:
    deployment_config = yaml.safe_load(f)

# Build secrets map from Pulumi config
secrets = {}
for secret_name in deployment_config.get("secrets", []):
    # Convert SECRET_NAME to secretName for Pulumi config lookup
    config_key = secret_name.lower().replace("_", "")
    secret_value = config.get_secret(config_key) or ""
    secrets[secret_name] = secret_value

# Build Helm deployments from config
def build_deployments(cfg: dict, secrets: dict) -> list:
    image = cfg["image"]
    deployments = []
    for dep in cfg["deployments"]:
        env = dict(dep.get("env", {}))
        # Inject secrets into env
        for secret_name, secret_value in secrets.items():
            env[secret_name] = secret_value
        deployments.append({
            "name": dep["name"],
            "image": {
                "repository": image["repository"],
                "tag": image["tag"],
                "pullPolicy": image["pullPolicy"]
            },
            "dagsterApiGrpcArgs": ["-m", dep["module"]],
            "port": dep["port"],
            "env": env,
        })
    return deployments

user_deployments = build_deployments(deployment_config, secrets)

# 1. Create a Kubernetes Namespace for Dagster
dagster_ns = Namespace(
    "dagster",
    metadata={
        "name": "dagster"
    }
)

# 2. Define Helm Chart Values
# These override default values to make the deployment suitable for local dev.
# We disable the persistent volume claims for simplicity in some local envs,
# though Docker Desktop handles them fine usually.
dagster_values = {
    "postgresql": {
        "enabled": True,
        "postgresqlUsername": "dagster",
        "postgresqlPassword": postgresql_password,
        "postgresqlDatabase": "dagster",
    },
    "dagsterWebserver": {
        "service": {
            "type": "ClusterIP",  # Use LoadBalancer if you want direct access via localhost on Docker Desktop
            "port": 80
        }
    },
    # In a local environment, you might want to adjust resource limits if your machine is constrained
    "dagsterDaemon": {
        "resources": {
            "limits": {"cpu": "1", "memory": "512Mi"},
            "requests": {"cpu": "1", "memory": "256Mi"}
        }
    },
    # User code deployments - loaded from pipelines-dagster/dagster-deployment.yaml
    "dagster-user-deployments": {
        "enabled": True,
        "enableSubchart": True,
        "deployments": user_deployments
    }
}

# 3. Deploy the Dagster Helm Chart
dagster_chart = Chart(
    "dagster",
    ChartOpts(
        chart="dagster",
        version="1.12.8",  # Pin a version for stability
        fetch_opts=FetchOpts(
            repo="https://dagster-io.github.io/helm"
        ),
        namespace=dagster_ns.metadata["name"],
        values=dagster_values,
    )
)

# 4. Export the Webserver Service Name
# We verify the service name so we know what to port-forward to.
webserver_svc = dagster_chart.get_resource(
    "v1/Service", 
    "dagster/dagster-dagster-webserver" 
)

pulumi.export("dagster_namespace", dagster_ns.metadata["name"])
pulumi.export("webserver_service_name", webserver_svc.metadata["name"])