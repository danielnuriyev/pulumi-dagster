import pulumi
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from pulumi_kubernetes.core.v1 import Namespace

# Load configuration
config = pulumi.Config()
postgresql_password = config.require_secret("postgresqlPassword")
s3_secret_key = config.get_secret("s3SecretKey") or ""

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
    # User code deployments
    "dagster-user-deployments": {
        "enabled": True,
        "enableSubchart": True,
        "deployments": [
            {
                "name": "pipelines-dagster",
                "image": {
                    "repository": "pipelines-dagster",
                    "tag": "latest",
                    "pullPolicy": "IfNotPresent"
                },
                "dagsterApiGrpcArgs": [
                    "-m", "pipelines_dagster.definitions"
                ],
                "port": 4000,
                "env": {
                    "PIPELINES_CONFIG_DIR": "/app/pipelines",
                    "S3_SECRET_KEY": s3_secret_key,
                },
            }
        ]
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