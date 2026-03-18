import os
import uuid
import json
from typing import List, Dict, Any
from pypdf import PdfReader
from models import GoldenChunk, DocSpecificAttributes, AnalysisAttributes
import httpx
from extraction import _get_llm_config

INGESTION_SYSTEM_PROMPT = """
You are a Senior Financial Analyst and Data Engineer. Your task is to analyze a text chunk from a financial document and convert it into a 'Golden Schema' JSON.

=== GOLDEN SCHEMA RULES ===
1. CHUNK CONTENT: Summarize or preserve the key financial narrative. If tables are present, represent them clearly.
2. SIGNAL TYPE: Identify if this chunk is 'historical', 'forward_looking', 'neutral', or 'risk_factor'.
3. METRICS: Extract specific financial metrics and normalize them (e.g., 'Total Revenue' -> 'revenue').
4. SENTIMENT: Determine the tone (positive, negative, neutral).
5. DOC SPECIFIC: Note if there are tables or image placeholders in the text.

=== OUTPUT FORMAT ===
Return ONLY valid JSON matching this structure:
{
    "analysis_attributes": {
        "signal_type": "forward_looking",
        "time_horizon": "FY2026",
        "metric_type": ["revenue", "ebitda"],
        "sentiment": "positive"
    },
    "normalized_metrics": {
       "revenue": ["topline growth of 20%"],
       "ebitda": ["554 Crore"]
    },
    "llm_analysis_summary": "Detailed summary of the financial signal found in this chunk."
}
"""

async def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Extracts text page by page from a PDF."""
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages.append({"page_number": i + 1, "content": text})
    return pages

async def generate_golden_chunk(
    text: str, 
    metadata: Dict[str, Any], 
    page_number: int
) -> GoldenChunk:
    """Uses LLM to enrich a raw text chunk into a GoldenChunk."""
    cfg = _get_llm_config()
    endpoint = cfg['base_url']
    if not endpoint.endswith("/chat/completions"):
        endpoint = endpoint.rstrip("/") + "/chat/completions"

    prompt = f"DOCUMENT METADATA: {json.dumps(metadata)}\n\nCHUNK CONTENT:\n{text}"
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
                json={
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": INGESTION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            analysis = json.loads(content)
        
        return GoldenChunk(
            chunk_id=str(uuid.uuid4()),
            doc_id=metadata.get("doc_id", "unknown"),
            company_ticker=metadata.get("company_ticker", "N/A"),
            company_name=metadata.get("company_name", "N/A"),
            sector=metadata.get("sector", "N/A"),
            fiscal_year=metadata.get("fiscal_year", 2024),
            fiscal_period=metadata.get("fiscal_period", "Annual"),
            date_iso=metadata.get("date_iso", "2024-01-01"),
            filename=metadata.get("filename", "unknown"),
            page_number=page_number,
            content=text[:2000],  # Embedded content
            doc_specific_attributes=DocSpecificAttributes(
                has_tables="|" in text or "+" in text,
                has_images=False
            ),
            analysis_attributes=AnalysisAttributes(**analysis.get("analysis_attributes", {})),
            normalized_metrics=analysis.get("normalized_metrics", {}),
            llm_analysis_summary=analysis.get("llm_analysis_summary")
        )
    except Exception as e:
        print(f"Error generating golden chunk: {e}")
        # Return a shell if LLM fails
        return GoldenChunk(
            chunk_id=str(uuid.uuid4()),
            doc_id=metadata.get("doc_id", "unknown"),
            company_ticker=metadata.get("company_ticker", "N/A"),
            company_name=metadata.get("company_name", "N/A"),
            sector=metadata.get("sector", "N/A"),
            fiscal_year=metadata.get("fiscal_year", 2024),
            fiscal_period=metadata.get("fiscal_period", "Annual"),
            date_iso=metadata.get("date_iso", "2024-01-01"),
            filename=metadata.get("filename", "unknown"),
            page_number=page_number,
            content=text[:500],
            doc_specific_attributes=DocSpecificAttributes(),
            analysis_attributes=AnalysisAttributes(),
            normalized_metrics={}
        )
