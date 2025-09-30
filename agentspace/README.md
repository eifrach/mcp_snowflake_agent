# AgentSpace Deployment

This directory contains files for deploying the JIRA MCP Snowflake agent to Google Cloud AgentSpace using the Discovery Engine API.

## Files

- `agent_manager.sh` - AgentSpace management script
- `jira_agent.json` - Agent definition for AgentSpace
- `.env` - AgentSpace configuration

## Configuration

Copy `.env.template` to `.env` and update with your AgentSpace settings:

```bash
cp .env.template .env
```

Required variables:
- `PROJECT_ID` - Your GCP project ID
- `GCP_PROJECT_NUMBER` - Your GCP project number
- `LOCATION` - AgentSpace location (typically `global`)
- `COLLECTION_ID` - Collection ID (typically `default_collection`)
- `ENGINE_ID` - Your AgentSpace engine ID (find in AgentSpace console)
- `ASSISTANT_ID` - Assistant ID (typically `default_assistant`)
- `REASONING_ENGINE_ID` - ID from agentengine deployment
- `REASONING_ENGINE_LOCATION` - Location of reasoning engine (e.g., us-east4)

**Note**: 
- Find your `ENGINE_ID` from the AgentSpace console
- `REASONING_ENGINE_ID` comes from the agentengine deployment
- Update `jira_agent.json` with these values before creating the agent

## Usage

Make the script executable:
```bash
chmod +x agent_manager.sh
```

### List existing agents
```bash
./agent_manager.sh list
```

### Create the JIRA agent

First, update `jira_agent.json` with your values:
1. Replace `{GCP_PROJECT_NUMBER}` with your project number
2. Replace `{REASONING_ENGINE_LOCATION}` with your reasoning engine location
3. Replace `{REASONING_ENGINE_ID}` with your deployed reasoning engine ID

Then create the agent:
```bash
./agent_manager.sh create jira_agent.json
```

### Update an agent
```bash
./agent_manager.sh update <agent_id> jira_agent.json
```

### Delete an agent
```bash
./agent_manager.sh delete <agent_id>
```

## Prerequisites

- AgentEngine must be deployed first (see `../agentengine/`)
- AgentSpace engine must be created in your GCP project
- Discovery Engine API must be enabled

## Agent Definition

The `jira_agent.json` references your deployed AgentEngine. You must update the placeholders:
- `{GCP_PROJECT_NUMBER}` - Your GCP project number
- `{REASONING_ENGINE_LOCATION}` - Location where reasoning engine is deployed (e.g., us-east4)
- `{REASONING_ENGINE_ID}` - ID from your agentengine deployment

This creates an AgentSpace agent that uses the deployed reasoning engine as its backend.