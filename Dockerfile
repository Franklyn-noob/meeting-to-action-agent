# AgentCore runtime container (container deployment type; CodeBuild builds it for arm64).
#
# The container must serve the BedrockAgentCore runtime over HTTP on 0.0.0.0:8080 so the
# AgentCore gateway can POST invoke payloads to it. The contract comes straight from
# meeting_agent/agent.py:
#   app = BedrockAgentCoreApp()                 # agent.py:87
#   @app.entrypoint                             # agent.py:90
#   def handler(event, context): ...            # agent.py:91  <- where invoke payloads land
#   if __name__ == "__main__" and os.getenv("AGENTCORE_DEPLOY") == "1":
#       app.run()                               # agent.py:107-109
# app.run() starts uvicorn on 0.0.0.0:8080
# (runtime/runtime/ag_ui.py:129  ->  port: int = 8080, host forced to "0.0.0.0"), and routes
# each request to `handler`. So the correct container command is `python -m meeting_agent.agent`
# with AGENTCORE_DEPLOY=1 (set via ENV below). Running as a module (rather than `python
# meeting_agent/agent.py`) puts /workspace on sys.path so the package's absolute imports
# (`from meeting_agent.tools import ...`) resolve — running the script directly would only put
# /workspace/meeting_agent on sys.path and fail with `ModuleNotFoundError: No module named
# 'meeting_agent'`. The `agentcore configure --entrypoint
# meeting_agent/agent.py` we already ran points at this same file; the toolkit auto-discovers
# the @app.entrypoint-decorated `handler` from it.

# multi-arch image (amd64 + arm64); CodeBuild bedrock-agentcore-arm64 resolves the arm64 variant.
FROM public.ecr.aws/docker/library/python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Makes `python -m meeting_agent.agent` enter the __main__ branch and call app.run() (agent.py:107).
    AGENTCORE_DEPLOY=1

WORKDIR /workspace

# Install dependencies first -> cached layer across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The agent runtime is self-contained: meeting_agent imports only strands + meeting_agent.*
# (backend/ is the separate FastAPI dashboard; frontend/dist is its static assets — not needed here).
COPY meeting_agent/ ./meeting_agent/

# AgentCore gateway expects HTTP on the runtime default port (8080).
EXPOSE 8080

# With AGENTCORE_DEPLOY=1 this becomes: app.run() -> uvicorn on 0.0.0.0:8080 -> handler.
ENTRYPOINT ["python", "-m", "meeting_agent.agent"]
