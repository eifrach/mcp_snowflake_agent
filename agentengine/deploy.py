# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os

import vertexai
from dotenv import load_dotenv
from google.oauth2 import credentials as oauth2_credentials
from vertexai import agent_engines

logging.getLogger("google_adk").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
SERVICE_ACCOUNT = os.getenv("SERVICE_ACCOUNT")
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")
JIRA_MCP_SSE_URL = os.getenv("JIRA_MCP_SSE_URL")

if OAUTH_TOKEN:
    creds = oauth2_credentials.Credentials(token=OAUTH_TOKEN)
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=f"gs://{BUCKET_NAME}",
        credentials=creds,
    )
else:
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=f"gs://{BUCKET_NAME}",
    )


if __name__ == "__main__":
    remote_app = agent_engines.create(
        display_name="jira_mcp_snowflake_agent",
        description="A JIRA analysis agent with MCP integration to Snowflake database",
        agent_engine=agent_engines.ModuleAgent(
            module_name="src.root_agent",
            agent_name="agent_app",
            register_operations={
                "": [
                    "get_session",
                    "list_sessions",
                    "create_session",
                    "delete_session",
                ],
                "async": [
                    "async_get_session",
                    "async_list_sessions",
                    "async_create_session",
                    "async_delete_session",
                ],
                "stream": ["stream_query", "streaming_agent_run_with_events"],
                "async_stream": ["async_stream_query"],
            },
        ),
        requirements=[
            "google-cloud-aiplatform[agent_engines,adk]>=1.101.0",
            "aiohttp>=3.8.0",
            "python-dotenv>=1.0.0",
        ],
        extra_packages=[
            "pyproject.toml",
            "src/__init__.py",
            "src/root_agent.py",
        ],
        env_vars={
            "PROJECT_ID": PROJECT_ID,
            "LOCATION": LOCATION,
            "JIRA_MCP_SSE_URL": JIRA_MCP_SSE_URL,
        },
        service_account=SERVICE_ACCOUNT,
    )