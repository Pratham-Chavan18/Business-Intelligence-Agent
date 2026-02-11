import os
from pathlib import Path
from dotenv import load_dotenv  # type: ignore

# Load .env from the backend directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

from fastapi import FastAPI, HTTPException  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore
from fastapi.responses import HTMLResponse  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from pydantic import BaseModel  # type: ignore
import uvicorn  # type: ignore

from agent import BIAgent  # type: ignore
from monday_client import health_check  # type: ignore

# --- App setup ---
app = FastAPI(title="Monday.com BI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global agent instance ---
agent = BIAgent()


# --- Request/Response models ---

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    status: str = "ok"


# --- API Routes ---

@app.get("/api/health")
async def api_health():
    """Health check — verifies Monday.com connection."""
    monday_status = health_check()
    gemini_key = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "healthy",
        "monday": monday_status,
        "gemini_configured": gemini_key,
        "work_orders_board": agent.work_orders_id or "not configured",
        "deals_board": agent.deals_id or "not configured",
    }


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """Main chat endpoint — process a user question."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        result = agent.chat(req.message.strip())
        return {"response": result, "status": "ok"}
    except Exception as e:
        return {
            "response": f"❌ An error occurred: {str(e)}",
            "status": "error",
        }


@app.post("/api/report")
async def api_report():
    """Generate a leadership update report."""
    try:
        report = agent.get_leadership_report()
        return {"report": report, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def api_refresh():
    """Force refresh cached data from Monday.com."""
    result = agent.refresh_data()
    return {"message": result, "status": "ok"}


# --- Static files & Frontend ---
# Frontend is in the sibling 'frontend' directory
frontend_dir = str(Path(__file__).resolve().parent.parent / "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend page."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>Monday.com BI Agent</h1><p>Frontend not found. Place index.html in /frontend/</p>"
    )


# --- Entry point ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
