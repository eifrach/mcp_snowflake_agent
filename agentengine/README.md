# AgentEngine Deployment

This directory contains files for deploying the JIRA MCP Snowflake agent directly to Vertex AI Agent Engine.

## Files

- `src/` - Agent source code
  - `root_agent.py` - Full MCP-enabled agent
  - `simple_agent.py` - Minimal working agent (currently deployed)
- `deploy.py` - Deployment script
- `pyproject.toml` - Python dependencies
- `test_agent.py` - Test script for deployed agent
- `.env` - Environment configuration

## Configuration

Copy `.env.template` to `.env` and update with your GCP settings:

```bash
cp .env.template .env
```

Required variables:
- `PROJECT_ID` - Your GCP project ID
- `LOCATION` - GCP region (e.g., us-east4)
- `BUCKET_NAME` - GCS bucket for staging
- `SERVICE_ACCOUNT` - Service account email for the agent
- `JIRA_MCP_SSE_URL` - URL of your JIRA MCP server SSE endpoint
- `REASONING_ENGINE_ID` - ID of deployed reasoning engine (for testing)

## Deployment

```bash
cd agentengine
uv run deploy.py
```

## Testing

After deployment, test your agent:
```bash
# Make sure your .env has REASONING_ENGINE_ID set
uv run test_agent.py
```

You can also check deployment status:
```bash
uv run check_status.py
```

## Next Steps

1. Test the simple agent
2. Gradually add MCP functionality
3. Replace mock tools with real MCP integration