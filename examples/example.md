# Example Service

The Example Service is a small HTTP API used to demonstrate documentation RAG.

## Deployment

The service is deployed with Docker Compose. Start dependencies first, then run
the application container. Health checks should pass before routing traffic.

## Operations

Operators should monitor request latency, error rate, and queue depth. If the
service cannot reach its database, it should fail readiness checks.
