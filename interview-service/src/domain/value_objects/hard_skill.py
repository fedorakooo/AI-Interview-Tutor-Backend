from enum import StrEnum


class HardSkill(StrEnum):
    # Languages
    PYTHON = "Python"
    JAVA_SCRIPT = "JavaScript"

    # Frameworks
    REACT = "React"
    ANGULAR = "Angular"
    DJANGO = "Django"
    DRF = "Django Rest Framework"
    FLASK = "Flask"
    FAST_API = "FastAPI"

    # Web
    HTML = "HTML"
    CSS = "CSS"
    REST_API = "REST API"
    GRAPHQL = "GraphQL"
    SOAP = "SOAP"

    # SQL
    SQL = "SQL"
    POSTGRESQL = "PostgreSQL"
    MYSQL = "MySQL"
    ORACLE_DB = "Oracle DB"
    SQLITE = "SQLite"

    # NoSQL
    NOSQL = "NoSQL"
    MONGO = "MongoDB"
    REDIS = "Redis"
    DYNAMO = "DynamoDB"
    ELASTICSEARCH = "Elasticsearch"
    CASSANDRA = "Cassandra"

    # Message Brokers
    RABBIT = "RabbitMQ"
    KAFKA = "Kafka"
    AWS_SQS = "AWS SQS"

    # DevOps
    DOCKER = "Docker"
    KUBERNETES = "Kubernetes"
    TERRAFORM = "Terraform"
    DOCKER_SWARM = "Docker Swarm"
    PROMETHEUS = "Prometheus"
    GRAFANA = "Grafana"
    CI_CD = "CI/CD"

    # Cloud
    AWS = "AWS Cloud"
    AZURE = "Azure Cloud"
    GOOGLE_CLOUD = "Google Cloud"
    ORACLE_CLOUD = "Oracle Cloud"

    # Methodologies
    SCRUM = "SCRUM"
    KANBAN = "KANBAN"
    AGILE = "AGILE"
