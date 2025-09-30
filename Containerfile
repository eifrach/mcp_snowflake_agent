# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Install build dependencies and UV
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV (much faster than pip)
RUN uv sync --frozen

# Copy source code
COPY snowflake_adk_agent/ ./snowflake_adk_agent/

# Set environment variables for the application
ENV PYTHONPATH=/app
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE
ENV GOOGLE_CLOUD_LOCATION=global

# Expose port for Cloud Run
EXPOSE 8080

# Use UV to run the application
CMD ["uv", "run", "python", "-m", "snowflake_adk_agent.agent"]