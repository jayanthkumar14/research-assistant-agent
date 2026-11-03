"""
Research Assistant – FastAPI backend

Endpoints:
  POST /api/research   – run the agent on a topic (returns the report)
  GET  /api/health     – health check
  GET  /               – serves the frontend (index.html)
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent import create_agent

load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(
    title="Research Assistant Agent",
    description="Multi-step research agent using LLM + tools (web search, browse, Wikipedia)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


class ResearchRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=3,
        max_length=500,
        examples=["Recent advances in solid-state batteries for electric vehicles"],
    )
    provider: str = Field(
        default="gemini",
        description="LLM provider: openai | xai | groq | gemini | together | openrouter",
    )
    model: Optional[str] = Field(default=None, description="Optional model override")
    max_turns: int = Field(default=12, ge=4, le=20)
    verbose: bool = Field(default=False, description="Include intermediate steps in response")


class ResearchResponse(BaseModel):
    topic: str
    report: str
    provider: str
    model: Optional[str] = None
    steps: Optional[list[str]] = None


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "research-assistant-agent",
        "providers": ["openai", "xai", "groq", "gemini", "together", "openrouter"],
    }


@app.post("/api/research", response_model=ResearchResponse)
def research(req: ResearchRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    has_key = any(
        os.getenv(k)
        for k in (
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "GROQ_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "TOGETHER_API_KEY",
            "OPENROUTER_API_KEY",
        )
    )
    if not has_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "No API key configured. Set GEMINI_API_KEY (or another provider key) "
                "in the environment."
            ),
        )

    try:
        agent = create_agent(
            provider=req.provider,
            model=req.model,
            max_turns=req.max_turns,
            verbose=req.verbose,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {e}")

    steps: list[str] = []
    if req.verbose:
        original_print = print

        def capture(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            steps.append(msg)
            original_print(*args, **kwargs)

        import builtins
        builtins.print = capture

    try:
        report = agent.run(topic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
    finally:
        if req.verbose:
            import builtins
            builtins.print = original_print

    return ResearchResponse(
        topic=topic,
        report=report,
        provider=req.provider,
        model=req.model or agent.model,
        steps=steps if req.verbose else None,
    )


@app.get("/")
def serve_index():
    path = os.path.join(_FRONTEND_DIR, "index.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(path)


@app.get("/styles.css")
def serve_css():
    path = os.path.join(_FRONTEND_DIR, "styles.css")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="styles.css not found")
    return FileResponse(path, media_type="text/css")


@app.get("/app.js")
def serve_js():
    path = os.path.join(_FRONTEND_DIR, "app.js")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="app.js not found")
    return FileResponse(path, media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
