
FROM python:3.11-slim
WORKDIR /app

# Create a non-root user
RUN adduser --disabled-password --gecos "" myuser

# Switch to the non-root user
USER myuser

# Set up environment variables - Start
ENV PATH="/home/myuser/.local/bin:$PATH"

ENV GOOGLE_GENAI_USE_ENTERPRISE=1
ENV GOOGLE_CLOUD_PROJECT=cowork-aset-6tnf0w
ENV GOOGLE_CLOUD_LOCATION=us-central1

# Set up environment variables - End

# Install ADK - Start
RUN pip install "google-adk[a2a]==2.3.0"
# Install ADK - End

# Copy agent - Start

# Set permission
COPY --chown=myuser:myuser "agents/agent/" "/app/agents/agent/"

# Copy agent - End

# Install Agent Deps - Start
RUN pip install -r "/app/agents/agent/requirements.txt"
# Install Agent Deps - End

EXPOSE 8080

CMD adk api_server --port=8080 --host=0.0.0.0 --session_service_uri=agentengine://projects/645694706016/locations/us-central1/reasoningEngines/1536670304154157056 --memory_service_uri=agentengine://projects/645694706016/locations/us-central1/reasoningEngines/1536670304154157056    --a2a  --gemini_enterprise_app_name=agent "/app/agents"
