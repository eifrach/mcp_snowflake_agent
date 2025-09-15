# ADK Agent - JIRA MCP Integration

A Google ADK agent that integrates with JIRA data through a Model Context Protocol (MCP) server connected to Snowflake.

## Features

- **JIRA Issue Details**: Get detailed information about JIRA issues
- **JIRA Issue Listing**: Search and filter JIRA issues
- **Project Summaries**: Get overview of JIRA projects
- **Issue Links**: Explore relationships between JIRA issues
- **Sprint Information**: Get details about sprints and their issues

## Setup

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Environment Configuration

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# JIRA MCP SSE URL - The Server-Sent Events endpoint for the JIRA MCP server
JIRA_MCP_SSE_URL=https://your-jira-mcp-server.example.com/sse

# Snowflake Token - Your authentication token for Snowflake access
JIRA_MCP_SNOWFLAKE_TOKEN=your_snowflake_token_here
```

### 3. Run the Agent

```bash
python main.py
```

## Architecture

The agent uses:
- **Google ADK**: For the agent framework and natural language processing
- **MCP Protocol**: For communication with the JIRA data server
- **Server-Sent Events (SSE)**: For real-time communication with the MCP server
- **Snowflake**: As the backend data source for JIRA information

## Available Tools

- `list_jira_issues`: Search and filter JIRA issues with various criteria
- `get_jira_issue_details`: Get comprehensive details for specific JIRA issues
- `get_jira_project_summary`: Get statistics and overview of JIRA projects
- `get_jira_issue_links`: Explore issue relationships and dependencies
- `get_jira_sprint_details`: Get information about sprints

## Example Queries

- "Please describe JIRA issue TELCOV10N-682"
- "Show me all open issues in the SMQE project"
- "What's the summary of all JIRA projects?"
- "Find issues created in the last 7 days"

## Security

- Environment variables are used for sensitive configuration
- The `.env` file is excluded from version control
- All communications use HTTPS with proper SSL validation