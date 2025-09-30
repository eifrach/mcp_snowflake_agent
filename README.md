# JIRA MCP Snowflake Agent

This project demonstrates two deployment approaches for a JIRA analysis agent that connects to a Snowflake database through MCP (Model Context Protocol) integration.

## Project Structure

```
├── agentengine/          # Direct Vertex AI Agent Engine deployment
│   ├── src/             # Agent source code
│   ├── deploy.py        # Deployment script
│   ├── pyproject.toml   # Dependencies
│   └── README.md        # AgentEngine-specific docs
├── agentspace/          # AgentSpace deployment via Discovery Engine
│   ├── agent_manager.sh # Management script
│   ├── jira_agent.json  # Agent definition
│   └── README.md        # AgentSpace-specific docs
└── README.md           # This file
```

## Deployment Approaches

### 1. AgentEngine (Direct)
- **Directory**: `agentengine/`
- **Method**: Direct deployment to Vertex AI Agent Engine
- **Use Case**: Backend reasoning engine, testing, development
- **Documentation**: See [`agentengine/README.md`](agentengine/README.md)

### 2. AgentSpace (User-Facing)
- **Directory**: `agentspace/`
- **Method**: AgentSpace via Discovery Engine API
- **Use Case**: User-facing agent with UI, production deployment
- **Documentation**: See [`agentspace/README.md`](agentspace/README.md)

## Quick Start

### 1. Deploy AgentEngine

```bash
cd agentengine
# Copy and configure environment
cp .env.template .env
# Edit .env with your GCP settings

# Deploy the agent
uv run deploy.py

# Test the deployed agent
uv run test_agent.py
```

### 2. Deploy to AgentSpace (Optional)

```bash
cd agentspace
# Copy and configure environment
cp .env.template .env
# Edit .env with your AgentSpace settings

# Update jira_agent.json with your values
# Then create the agent
./agent_manager.sh create jira_agent.json
```

## Agent Capabilities

The agent provides comprehensive JIRA data analysis through:

- **Issue Search**: Filter by project, status, priority, components, versions
- **Issue Details**: Get full issue information including comments and attachments
- **Project Analytics**: Statistical summaries across all projects
- **Sprint Analysis**: Sprint details, issue assignments, and metrics
- **Relationship Mapping**: Issue links and dependencies

## MCP Integration

The agent connects to a remote JIRA MCP server that provides access to JIRA data stored in Snowflake:
- **Protocol**: HTTP Server-Sent Events (SSE)
- **Configuration**: Set `JIRA_MCP_SSE_URL` in your `.env` file
- **Authentication**: Configured via environment variables

## Configuration

Both deployment approaches require environment configuration:

1. **Copy template files**: Each directory has a `.env.template` file
2. **Create `.env` files**: Copy and fill in your specific values
3. **Update JSON configs**: For AgentSpace, update `jira_agent.json` placeholders

See the README files in each directory for detailed configuration instructions.

## Prerequisites

- Google Cloud Platform project with required APIs enabled:
  - Vertex AI API
  - Cloud Storage API
  - Discovery Engine API (for AgentSpace)
- `gcloud` CLI authenticated
- `uv` package manager installed
- Python 3.12+

## Next Steps

1. Deploy the AgentEngine (see [`agentengine/README.md`](agentengine/README.md))
2. Test the deployed agent
3. Optionally deploy to AgentSpace (see [`agentspace/README.md`](agentspace/README.md))
4. Integrate with your JIRA MCP server