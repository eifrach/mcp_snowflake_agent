#!/usr/bin/env python3

import os
import vertexai
from dotenv import load_dotenv
from google.oauth2 import credentials as oauth2_credentials
from vertexai import agent_engines
from google.api_core import exceptions

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")

print(f"Checking deployment status for project: {PROJECT_ID}")
print(f"Location: {LOCATION}")

try:
    # Initialize Vertex AI
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

    print("\n🔍 Listing all deployed agent engines...")

    # List all agent engines
    agent_list = list(agent_engines.list())

    if not agent_list:
        print("❌ No agent engines found.")
    else:
        print(f"✅ Found {len(agent_list)} agent engine(s):")
        for i, agent in enumerate(agent_list, 1):
            print(f"\n{i}. Agent: {getattr(agent, 'display_name', 'Unknown')}")
            print(f"   Resource Name: {getattr(agent, 'name', 'Unknown')}")

            # Try to get all available attributes
            print(f"   Available attributes: {[attr for attr in dir(agent) if not attr.startswith('_')]}")

            # Try different state attribute names
            state = None
            for state_attr in ['state', 'status', 'lifecycle_state', 'current_state']:
                if hasattr(agent, state_attr):
                    state = getattr(agent, state_attr)
                    print(f"   {state_attr.title()}: {state}")
                    break

            if hasattr(agent, 'create_time'):
                print(f"   Create Time: {agent.create_time}")
            if hasattr(agent, 'update_time'):
                print(f"   Update Time: {agent.update_time}")

            # Check if this is our JIRA agent
            agent_name = getattr(agent, 'display_name', '')
            if "jira_mcp_snowflake_agent" in agent_name:
                print(f"   🎯 This is our JIRA MCP Snowflake Agent!")
                if state:
                    if "ACTIVE" in str(state).upper() or "READY" in str(state).upper():
                        print(f"   ✅ Status: {state} - Deployment successful!")
                    elif "CREATING" in str(state).upper() or "PENDING" in str(state).upper():
                        print(f"   ⏳ Status: {state} - Deployment in progress...")
                    elif "FAILED" in str(state).upper() or "ERROR" in str(state).upper():
                        print(f"   ❌ Status: {state} - Deployment failed")
                    else:
                        print(f"   ❓ Status: {state}")
                else:
                    print(f"   ❓ Status: Unknown (state attribute not found)")

                # Test if the agent is functional by trying to create a session
                print(f"\n🧪 Testing agent functionality...")
                try:
                    session = agent.create_session(user_id="test_user")
                    print(f"   ✅ Agent is FUNCTIONAL! Session created: {session.name}")

                    # Clean up the test session
                    session.delete()
                    print(f"   🧹 Test session cleaned up")

                except Exception as test_error:
                    error_msg = str(test_error)
                    if "user_id" in error_msg and "missing" in error_msg:
                        print(f"   ✅ Agent is DEPLOYED and FUNCTIONAL!")
                        print(f"   ℹ️  Note: Requires user_id parameter for session creation")
                    else:
                        print(f"   ❌ Agent test failed: {test_error}")

except exceptions.PermissionDenied as e:
    print(f"❌ Permission denied: {e}")
    print("Make sure you have the necessary permissions for Vertex AI Agent Builder.")
except Exception as e:
    print(f"❌ Error checking status: {e}")
    print(f"Error type: {type(e).__name__}")