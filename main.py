"""
Zone 1 Entity Graph Explorer — FastAPI Server
===============================================
Serves the API (extraction, graph state, reset) and static frontend files.

Run:
  uvicorn main:app --reload --port 8000

Environment variables:
  LLM_API_KEY   — Your API key (Groq / OpenAI / etc.)
  LLM_BASE_URL  — API base URL (default: https://api.groq.com/openai/v1)
  LLM_MODEL     — Model name (default: llama-3.3-70b-versatile)
"""

from __future__ import annotations

import os
import traceback

from dotenv import load_dotenv
load_dotenv()  # Load .env before other imports that read env vars

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from graph_store import GraphStore, IngestionStore
from extraction import call_llm
from ingestion import extract_text_from_pdf, generate_golden_chunk
from fastapi import UploadFile, File
import shutil
import uuid
import json


# ────────────────────────────────────────────────────────────────────────
# APP SETUP
# ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Zone 1 Entity Graph Explorer",
    description="Interactive Zone 1 (Entity Zone) knowledge graph builder for investment analysis",
    version="1.0.0",
)

# Global graph store (persistent)
DB_PATH = "graph.db"
store = GraphStore(DB_PATH)
ingest_store = IngestionStore()

# Seed the database on startup within the server process (avoids locks)
@app.on_event("startup")
def startup_seed():
    print("SERVER STARTUP: Checking ontology updates...")
    try:
        store.db.seed_ontology()
        store.ontology = store.db.get_ontology()
        from validators import LogicGuard
        store.guard = LogicGuard(store.ontology)
        print("SERVER STARTUP: Ontology updated successfully.")
    except Exception as e:
        print(f"SERVER STARTUP ERROR: {e}")

@app.post("/api/admin/reseed")
async def reseed_ontology():
    """Administrative endpoint to force refresh the ontology without restarting."""
    try:
        store.db.seed_ontology()
        store.ontology = store.db.get_ontology()
        from validators import LogicGuard
        store.guard = LogicGuard(store.ontology)
        return {"success": True, "message": "Ontology re-seeded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


# ────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ────────────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str
    document_name: str = "User Input"
    section_ref: str = "chunk"
    source_authority: int = 5
    metadata: dict = {}


# ────────────────────────────────────────────────────────────────────────
# API ROUTES
# ────────────────────────────────────────────────────────────────────────

@app.post("/api/extract")
async def extract_entities(req: ExtractRequest):
    """
    Accept a text chunk, extract Zone 1 entities/relations via LLM,
    ingest into graph store, and return the diff + full graph.
    """
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="LLM_API_KEY not configured. Set it in your .env file."
        )

    try:
        # Call LLM for extraction
        payload = await call_llm(
            text=req.text,
            document_name=req.document_name,
            section_ref=req.section_ref,
            metadata=req.metadata
        )

        # Ingest into graph store
        diff = store.ingest_extraction(payload, source_authority=req.source_authority)

        # Return diff + full graph state
        return {
            "success": True,
            "diff": diff,
            "graph": store.get_graph_data(),
            "extraction": {
                "entities_extracted": len(payload.entities),
                "relations_extracted": len(payload.relations),
                "abstentions": payload.abstentions,
            },
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph")
async def get_graph():
    """Return the current full graph state."""
    return store.get_graph_data()


@app.get("/api/log")
async def get_log():
    """Return the extraction history log."""
    return store.get_extraction_log()


@app.delete("/api/graph")
async def reset_graph():
    """Clear the entire graph store."""
    store.reset()
    return {"success": True, "message": "Graph reset successfully."}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": bool(os.getenv("LLM_API_KEY")),
        "llm_model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        "llm_base_url": os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    }


# ────────────────────────────────────────────────────────────────────────
# INGESTION ROUTES
# ────────────────────────────────────────────────────────────────────────

@app.post("/api/ingest/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF and return a temporary document ID."""
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "success": True, 
        "doc_id": doc_id, 
        "filename": file.filename, 
        "file_path": file_path
    }

@app.post("/api/ingest/process")
async def process_document(req: dict):
    """
    Process a PDF doc_id with metadata.
    1. Extract text page-by-page.
    2. Convert to Golden Chunks using LLM.
    3. Store in IngestionStore.
    """
    doc_id = req.get("doc_id")
    file_path = req.get("file_path")
    metadata = req.get("metadata", {})
    metadata["doc_id"] = doc_id
    metadata["filename"] = file_path
    
    if not doc_id or not file_path:
        raise HTTPException(status_code=400, detail="Missing doc_id or file_path")

    # Step 1: Extract Text
    pages = await extract_text_from_pdf(file_path)
    ingest_store.add_document(doc_id, metadata)
    
    # Step 2: Generate Golden Chunks (First 5 pages for brevity in MVP)
    processed_chunks = []
    for page in pages[:5]:
        chunk = await generate_golden_chunk(page["content"], metadata, page["page_number"])
        ingest_store.add_chunk(doc_id, chunk)
        processed_chunks.append(chunk.model_dump())
        
    return {
        "success": True,
        "doc_id": doc_id,
        "total_pages": len(pages),
        "chunks_processed": len(processed_chunks),
        "chunks": processed_chunks
    }

@app.get("/api/ingest/chunks/{doc_id}")
async def get_chunks(doc_id: str):
    """Retrieve processed chunks for a document."""
    chunks = ingest_store.get_document_chunks(doc_id)
    return {"success": True, "chunks": [c.model_dump() for c in chunks]}

# ────────────────────────────────────────────────────────────────────────
# STATIC FILES — serve the frontend
# ────────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


# Mount static files AFTER specific routes
app.mount("/static", StaticFiles(directory="static"), name="static")
