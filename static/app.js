/**
 * Zone 1 Entity Graph Explorer — Application Logic
 * ===================================================
 * Handles API calls, UI state, extraction workflow, and legend rendering.
 */

// ── Entity type colors (must match backend models.py) ──────────────
const ENTITY_TYPE_COLORS = {
    "LegalEntity":          "#4A90D9",
    "ExternalOrganization": "#E67E22",
    "BusinessUnit":         "#27AE60",
    "Sector":               "#8E44AD",
    "Industry":             "#2C3E50",
    "SubIndustry":          "#16A085",
    "EndMarket":            "#D35400",
    "Channel":              "#C0392B",
    "ProductDomain":        "#2980B9",
    "ProductFamily":        "#3498DB",
    "ProductLine":          "#1ABC9C",
    "Site":                 "#E74C3C",
    "Geography":            "#F39C12",
    "Person":               "#9B59B6",
    "Role":                 "#7F8C8D",
    "Technology":           "#00BCD4",
    "Capability":           "#FF5722",
    "Brand":                "#FF9800",
    "Initiative":           "#795548",
    "Financial":            "#4CAF50",
    "Program":              "#607D8B",
    "Management":           "#FFD700",
    "Competitors":          "#C0392B",
    "ProductPortfolio":     "#3b82f6",
};

// ── State ──────────────────────────────────────────────────────────
let graph;
let chunkCount = 0;

// ── Initialize ─────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    graph = new GraphVisualization("#graph-svg", "#node-tooltip");

    // Render legend
    renderLegend();

    // Check health
    checkHealth();

    // Button handlers
    document.getElementById("btn-extract").addEventListener("click", handleExtract);
    document.getElementById("btn-reset").addEventListener("click", handleReset);

    // Ctrl+Enter shortcut
    document.getElementById("text-input").addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            handleExtract();
        }
    });

    // Tab switch logic
    initTabs();

    // Ingestion logic
    initIngestion();

    // Sharing logic
    initSharing();
});

// ── Sharing Logic ───────────────────────────────────────────────
function initSharing() {
    const btnShare = document.getElementById("btn-share");
    const shareModal = document.getElementById("share-modal");
    const btnCloseShare = document.getElementById("btn-close-share");
    const btnCopyLink = document.getElementById("btn-copy-link");
    const shareUrlInput = document.getElementById("share-url-input");
    const btnDownloadState = document.getElementById("btn-download-state");

    if (!btnShare) return;

    btnShare.addEventListener("click", () => {
        // Update the input with the current URL
        shareUrlInput.value = window.location.href;
        shareModal.style.display = "flex";
    });

    btnCloseShare.addEventListener("click", () => {
        shareModal.style.display = "none";
    });

    // Close on click outside
    shareModal.addEventListener("click", (e) => {
        if (e.target === shareModal) {
            shareModal.style.display = "none";
        }
    });

    btnCopyLink.addEventListener("click", () => {
        shareUrlInput.select();
        document.execCommand("copy");
        
        const originalText = btnCopyLink.textContent;
        btnCopyLink.textContent = "Copied!";
        btnCopyLink.classList.remove("btn-primary");
        btnCopyLink.style.background = "var(--accent-green)";
        
        setTimeout(() => {
            btnCopyLink.textContent = originalText;
            btnCopyLink.classList.add("btn-primary");
            btnCopyLink.style.background = "";
        }, 2000);
    });

    btnDownloadState.addEventListener("click", () => {
        if (!graph || !graph.nodes || graph.nodes.length === 0) {
            alert("The graph is currently empty.");
            return;
        }

        const state = {
            nodes: graph.nodes,
            links: graph.links,
            timestamp: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `zone1_graph_state_${new Date().getTime()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

// ── Legend ──────────────────────────────────────────────────────────
function renderLegend() {
    const legendEl = document.getElementById("graph-legend");
    let html = "";
    for (const [type, color] of Object.entries(ENTITY_TYPE_COLORS)) {
        // Add spaces before capital letters for readability
        const label = type.replace(/([A-Z])/g, " $1").trim();
        html += `<div class="legend-item">
            <div class="legend-dot" style="background:${color}"></div>
            <span>${label}</span>
        </div>`;
    }
    legendEl.innerHTML = html;
}

// ── Health Check ───────────────────────────────────────────────────
async function checkHealth() {
    try {
        const res = await fetch("/api/health");
        const data = await res.json();

        const llmInfo = document.getElementById("llm-info");
        if (data.llm_configured) {
            llmInfo.textContent = `LLM: ${data.llm_model} via ${new URL(data.llm_base_url).hostname}`;
            setStatus("Ready — LLM configured");
        } else {
            llmInfo.textContent = "⚠ LLM_API_KEY not set";
            setStatus("Warning: Set LLM_API_KEY in .env file", true);
        }
    } catch (e) {
        setStatus("Error: Cannot connect to server", true);
    }
}

// ── Extract Handler ────────────────────────────────────────────────
async function handleExtract() {
    const textInput = document.getElementById("text-input");
    const docName = document.getElementById("doc-name").value.trim() || "User Input";
    const sectionRef = document.getElementById("section-ref").value.trim() || "chunk";
    const text = textInput.value.trim();

    const metadata = {
        company_name: document.getElementById("doc-company").value,
        company_ticker: document.getElementById("doc-ticker").value,
        fiscal_year: parseInt(document.getElementById("doc-year").value),
        fiscal_period: document.getElementById("doc-period").value
    };

    if (!text) {
        setStatus("Please paste some text to extract from", true);
        return;
    }

    const btn = document.getElementById("btn-extract");
    const btnText = btn.querySelector(".btn-text");
    const btnLoading = btn.querySelector(".btn-loading");

    // UI: loading state
    btn.disabled = true;
    btnText.style.display = "none";
    btnLoading.style.display = "inline-flex";
    setStatus("Extracting entities...");

    try {
        const res = await fetch("/api/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: text,
                document_name: docName,
                section_ref: sectionRef,
                metadata: metadata
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Extraction failed");
        }

        const data = await res.json();

        // Update graph visualization
        graph.update(data.graph);

        const detailPanel = document.getElementById("detail-panel");
        if (detailPanel) detailPanel.style.display = "none";

        // Update stats
        document.getElementById("entity-count").textContent = data.graph.stats.total_entities;
        document.getElementById("relation-count").textContent = data.graph.stats.total_relations;

        // Update chunk count
        chunkCount++;
        document.getElementById("chunk-count").textContent = `${chunkCount} chunk${chunkCount !== 1 ? "s" : ""} processed`;

        // Show extraction result
        showExtractionResult(data);

        // Add to log
        addLogEntry(docName, data.diff);

        // Reset input for next chunk
        textInput.value = "";
        setStatus(`Extracted ${data.extraction.entities_extracted} entities, ${data.extraction.relations_extracted} relations`);

    } catch (e) {
        setStatus(`Error: ${e.message}`, true);
        showError(e.message);
    } finally {
        btn.disabled = false;
        btnText.style.display = "inline";
        btnLoading.style.display = "none";
    }
}

// ── Reset Handler ──────────────────────────────────────────────────
async function handleReset() {
    console.log("Reset button clicked");
    // if (!confirm("Reset the entire graph? This cannot be undone.")) return;

    try {
        console.log("Sending DELETE request to /api/graph");
        const res = await fetch("/api/graph", { method: "DELETE" });
        if (!res.ok) throw new Error("Server reset failed");
        
        console.log("Server reset success, resetting UI");
        graph.reset();
        chunkCount = 0;

        const detailPanel = document.getElementById("detail-panel");
        if (detailPanel) detailPanel.style.display = "none";

        document.getElementById("entity-count").textContent = "0";
        document.getElementById("relation-count").textContent = "0";
        document.getElementById("chunk-count").textContent = "0 chunks processed";
        document.getElementById("extraction-result").style.display = "none";
        document.getElementById("log-entries").innerHTML = "";

        setStatus("Graph reset successfully");
    } catch (e) {
        console.error("Reset error:", e);
        setStatus(`Error during reset: ${e.message}`, true);
    }
}

// ── Show Extraction Result ─────────────────────────────────────────
function showExtractionResult(data) {
    const resultEl = document.getElementById("extraction-result");
    const contentEl = document.getElementById("result-content");

    const diff = data.diff;
    const ext = data.extraction;

    let html = `
        <div class="result-stat">
            <span class="label">Entities extracted</span>
            <span class="value">${ext.entities_extracted}</span>
        </div>
        <div class="result-stat">
            <span class="label">Relations extracted</span>
            <span class="value">${ext.relations_extracted}</span>
        </div>
        <div class="result-stat">
            <span class="label">New entities added</span>
            <span class="value">${diff.new_entity_ids.length}</span>
        </div>
        <div class="result-stat">
            <span class="label">New relations added</span>
            <span class="value">${diff.new_relation_ids.length}</span>
        </div>
        <div class="result-stat">
            <span class="label">Total graph entities</span>
            <span class="value">${diff.total_entities}</span>
        </div>
        <div class="result-stat">
            <span class="label">Total graph relations</span>
            <span class="value">${diff.total_relations}</span>
        </div>

        ${ext.thought_process ? `
        <div class="result-warnings" style="border-color:var(--accent-blue); background:rgba(59, 130, 246, 0.05); margin-top:20px;">
            <div style="font-size:10px; color:var(--accent-blue); margin-bottom:6px; text-transform:uppercase; font-weight:600; letter-spacing:0.05em;">AI Logical Grouping & Intent</div>
            <div style="font-size:11px; color:var(--text-secondary); line-height:1.5; font-style:italic;">"${ext.thought_process}"</div>
        </div>
        ` : ''}

        ${data.extraction.analysis_attributes ? `
        <div class="chunk-card" style="margin-top: 20px; border-color: var(--accent-teal);">
            <div class="chunk-header">
                <span class="chunk-title">ANALYSIS: ${data.extraction.analysis_attributes.signal_type.toUpperCase()}</span>
                <span class="chunk-page">Sentiment: ${data.extraction.analysis_attributes.sentiment}</span>
            </div>
            <div class="chunk-summary">${data.extraction.llm_analysis_summary || 'No summary provided.'}</div>
            <div class="chunk-metrics">
                ${(data.extraction.analysis_attributes.metric_type || []).map(m => `<span class="metric-tag">${m}</span>`).join('')}
            </div>
        </div>
        ` : ''}
    `;

    // Warnings
    if (diff.warnings && diff.warnings.length > 0) {
        html += `<div class="result-warnings">`;
        for (const w of diff.warnings) {
            html += `<div class="warning-item">${w}</div>`;
        }
        html += `</div>`;
    }

    // Abstentions
    if (ext.abstentions && ext.abstentions.length > 0) {
        html += `<div class="result-warnings" style="border-color:#334155">`;
        html += `<div style="font-size:10px;color:#4a5568;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em;font-weight:500;">Abstentions</div>`;
        for (const a of ext.abstentions) {
            html += `<div style="font-size:11px;color:#6b7280;padding:1px 0;">${a}</div>`;
        }
        html += `</div>`;
    }

    // Discoveries
    if (ext.discoveries && ext.discoveries.length > 0) {
        html += `<div class="result-warnings" style="border-color:var(--accent-purple); background:rgba(139, 92, 246, 0.05);">`;
        html += `<div style="font-size:10px;color:var(--accent-purple);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600;">Ontology Expansion Discoveries</div>`;
        for (const d of ext.discoveries) {
            html += `<div class="warning-item" style="color:var(--text-primary); border-left: 2px solid var(--accent-purple); padding-left:8px; margin-bottom:8px;">
                <span class="discovery-badge">${d.type}</span> <strong>${d.suggested_label}</strong><br>
                <small style="color:var(--text-secondary); font-style:italic;">"${d.context}"</small>
            </div>`;
        }
        html += `</div>`;
    }

    contentEl.innerHTML = html;
    resultEl.style.display = "block";

    // Show JSON output for debugging
    const jsonEl = document.getElementById("json-output");
    if (jsonEl) {
        jsonEl.textContent = JSON.stringify(data, null, 2);
    }
}

// ── Show Error ─────────────────────────────────────────────────────
function showError(message) {
    const resultEl = document.getElementById("extraction-result");
    const contentEl = document.getElementById("result-content");

    contentEl.innerHTML = `
        <div style="color:#ef4444;font-size:12px;line-height:1.5;word-break:break-word;">
            ${message}
        </div>
    `;
    resultEl.style.display = "block";
}

// ── Log Entry ──────────────────────────────────────────────────────
function addLogEntry(docName, diff) {
    const logEl = document.getElementById("log-entries");

    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `
        <span class="log-doc" title="${docName}">${docName}</span>
        <span class="log-stats">+${diff.new_entity_ids.length}E +${diff.new_relation_ids.length}R</span>
    `;

    // Prepend (newest first)
    logEl.insertBefore(entry, logEl.firstChild);
}

// ── Status Bar ─────────────────────────────────────────────────────
function setStatus(text, isError = false) {
    const statusEl = document.getElementById("status-text");
    statusEl.textContent = text;
    statusEl.style.color = isError ? (isError === true ? "#ef4444" : isError) : "#4a5568";
}

// ────────────────────────────────────────────────────────────────────────
// NEW: TABS & INGESTION
// ────────────────────────────────────────────────────────────────────────

function initTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            const contentId = `tab-${tab.dataset.tab}`;
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            document.getElementById(contentId).classList.add("active");
        });
    });
}

let activeDoc = null; // { doc_id, file_path, filename }

function initIngestion() {
    const dropZone = document.getElementById("file-drop-zone");
    const fileInput = document.getElementById("pdf-upload");
    const processBtn = document.getElementById("btn-process-doc");

    dropZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
    });

    // Drag and Drop
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragging"); });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragging");
        if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
    });

    processBtn.addEventListener("click", handleDocProcessing);
}

async function handleFileUpload(file) {
    if (file.type !== "application/pdf") {
        setStatus("Please upload a valid PDF file", true);
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setStatus(`Uploading ${file.name}...`);
    
    try {
        const res = await fetch("/api/ingest/upload", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        
        if (data.success) {
            activeDoc = data;
            document.getElementById("metadata-config").style.display = "block";
            document.querySelector(".upload-placeholder span").textContent = `Selected: ${file.name}`;
            setStatus("File uploaded. Please configure metadata.");
            
            // Auto-fill company if possible
            document.getElementById("meta-company").value = file.name.split(".")[0];
        }
    } catch (e) {
        setStatus("Upload failed: " + e.message, true);
    }
}

async function handleDocProcessing() {
    if (!activeDoc) return;

    const metadata = {
        company_name: document.getElementById("meta-company").value,
        company_ticker: document.getElementById("meta-ticker").value,
        fiscal_year: parseInt(document.getElementById("meta-year").value),
        fiscal_period: document.getElementById("meta-period").value,
        date_iso: new Date().toISOString().split("T")[0]
    };

    const btn = document.getElementById("btn-process-doc");
    btn.disabled = true;
    btn.querySelector(".btn-loading").style.display = "inline";
    
    document.getElementById("ingestion-status").style.display = "block";
    const statusText = document.getElementById("ingestion-status-text");
    const progressFill = document.querySelector(".progress-fill");
    
    statusText.textContent = "Processing PDF and generating Golden Chunks...";
    progressFill.style.width = "40%";

    try {
        const res = await fetch("/api/ingest/process", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                doc_id: activeDoc.doc_id,
                file_path: activeDoc.file_path,
                metadata: metadata
            })
        });
        const data = await res.json();

        if (data.success) {
            progressFill.style.width = "100%";
            statusText.textContent = `Completed! Generated ${data.chunks_processed} Golden Chunks.`;
            renderGoldenChunks(data.chunks);
            setStatus("Document ingested successfully.");
        }
    } catch (e) {
        setStatus("Processing failed: " + e.message, true);
    } finally {
        btn.disabled = false;
        btn.querySelector(".btn-loading").style.display = "none";
    }
}

function renderGoldenChunks(chunks) {
    const listEl = document.getElementById("golden-chunks-list");
    listEl.innerHTML = `<h3>Golden Chunks (${chunks.length})</h3>`;

    chunks.forEach(chunk => {
        const card = document.createElement("div");
        card.className = "chunk-card";
        
        // Build metric tags
        const metrics = chunk.analysis_attributes.metric_type || [];
        const metricHtml = metrics.map(m => `<span class="metric-tag">${m}</span>`).join("");

        card.innerHTML = `
            <div class="chunk-header">
                <span class="chunk-title">${chunk.analysis_attributes.signal_type.toUpperCase()}</span>
                <span class="chunk-page">Page ${chunk.page_number}</span>
            </div>
            <div class="chunk-summary">${chunk.llm_analysis_summary}</div>
            <div class="chunk-metrics">
                <span class="metric-tag" style="background:rgba(59, 130, 246, 0.1); color:var(--accent-blue);">Sentiment: ${chunk.analysis_attributes.sentiment}</span>
                ${metricHtml}
            </div>
        `;
        listEl.appendChild(card);
    });
}
