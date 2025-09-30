#!/usr/bin/env python3

import os
import vertexai
from dotenv import load_dotenv
from vertexai.preview.reasoning_engines import ReasoningEngine

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
REASONING_ENGINE_ID = os.getenv("REASONING_ENGINE_ID")

if not all([PROJECT_ID, LOCATION, REASONING_ENGINE_ID]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

# Initialize Vertex AI
vertexai.init(
    project=PROJECT_ID,
    location=LOCATION
)

# Get the deployed agent
agent = ReasoningEngine(REASONING_ENGINE_ID)

# Test the agent
def test_agent():
    print("Testing deployed JIRA agent...")

    try:
        # Check what's available
        print("Available methods:", [m for m in dir(agent) if not m.startswith('_')])

        # The agent should be accessible via API call
        from google.cloud import aiplatform_v1

        client = aiplatform_v1.ReasoningEngineExecutionServiceClient()

        # Make a query request
        request = aiplatform_v1.QueryReasoningEngineRequest(
            name=f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}",
            class_method="stream_query",
            input={
                "message": "Hello, can you help me with JIRA queries?",
                "user_id": "test_user"
            }
        )

        print("Calling reasoning engine...")
        response = client.query_reasoning_engine(request=request)

        print("Response:")
        print(response.output)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agent()