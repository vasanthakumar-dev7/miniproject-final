import os
import re
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import RAG engine directly from raganything_processor
from raganything_processor import (
    get_engine,
    is_supported_by_raganything,
    RAGANYTHING_EXTENSIONS
)
from custom_parsers import CustomParserPipeline

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin requests for React frontend

UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_DIR", "./uploads"))
OUTPUT_FOLDER = os.path.abspath(os.getenv("OUTPUT_DIR", "./output"))
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# Core Engine instance
rag_engine = get_engine()
rag_engine.scan_directory(UPLOAD_FOLDER)

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "service": "Multimodal Document & Data Portal",
        "engine": "RAGAnything Grounded Engine",
        "indexed_items": len(rag_engine.catalog),
        "supported_multimodal_formats": sorted(list(RAGANYTHING_EXTENSIONS))
    })

@app.route("/catalog", methods=["GET"])
def get_catalog():
    """Return current indexed files and images."""
    items = []
    for fname, meta in rag_engine.catalog.items():
        items.append({
            "filename": fname,
            "type": meta.get("type"),
            "size": meta.get("size", 0),
            "summary": meta.get("summary") or meta.get("analysis", "")[:120],
            "url": f"http://127.0.0.1:5000/files/{fname}" if meta.get("type") == "image" else None
        })
    return jsonify({
        "status": "success",
        "count": len(items),
        "items": items
    })

@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    """Serves uploaded or extracted images and document assets directly to frontend."""
    upload_file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(upload_file_path):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    output_file_path = os.path.join(app.config["OUTPUT_FOLDER"], filename)
    if os.path.exists(output_file_path):
        return send_from_directory(app.config["OUTPUT_FOLDER"], filename)

    return jsonify({"error": f"File '{filename}' not found"}), 404

@app.route("/upload", methods=["POST"])
def upload_files():
    """
    Endpoint for uploading documents and routing to grounded ingestion.
    """
    if "files" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return jsonify({"error": "No files provided"}), 400

    results = []

    for file in files:
        if file.filename == "":
            continue

        filename = Path(file.filename).name
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        # Route by format category
        if is_supported_by_raganything(save_path):
            print(f"[Router] Routing '{filename}' to RAGAnything pipeline...")
            try:
                meta = rag_engine.index_document(save_path)
                results.append({
                    "filename": filename,
                    "pipeline": "raganything",
                    "status": "indexed",
                    "type": meta.get("type"),
                    "summary": meta.get("summary") or meta.get("analysis", "")[:100]
                })
            except Exception as e:
                print(f"[Router] Error processing {filename}: {e}")
                results.append({
                    "filename": filename,
                    "pipeline": "raganything",
                    "status": "error",
                    "error": str(e)
                })
        else:
            print(f"[Router] Routing '{filename}' to custom text/code pipeline...")
            try:
                meta = rag_engine.index_code_or_text(save_path)
                results.append({
                    "filename": filename,
                    "pipeline": "custom_parser",
                    "status": "indexed",
                    "type": meta.get("type"),
                    "summary": meta.get("summary", "")[:100]
                })
            except Exception as e:
                print(f"[Router] Error parsing code/text {filename}: {e}")
                results.append({
                    "filename": filename,
                    "pipeline": "custom_parser",
                    "status": "error",
                    "error": str(e)
                })

    return jsonify({
        "status": "success",
        "message": f"Successfully processed and indexed {len(results)} file(s)",
        "results": results
    })

@app.route("/documents/<path:filename>", methods=["DELETE"])
def delete_document(filename):
    """
    Deletes a document from the uploads directory and clears its record from the engine catalog.
    """
    clean_name = Path(filename).name
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], clean_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[Storage] Deleted file from disk: {file_path}")
        except Exception as e:
            print(f"[Storage Error] Failed to delete {file_path}: {e}")

    rag_engine.remove_document(clean_name)
    return jsonify({
        "status": "success",
        "message": f"Document '{clean_name}' successfully removed",
        "remaining_count": len(rag_engine.catalog)
    })

@app.route("/clear", methods=["POST"])
def clear_documents():
    """
    Clears all documents from the uploads folder and catalog.
    """
    upload_dir = app.config["UPLOAD_FOLDER"]
    for f in os.listdir(upload_dir):
        p = os.path.join(upload_dir, f)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except Exception:
                pass

    rag_engine.clear_all()
    print("[Storage] Cleared all documents and catalog.")
    return jsonify({
        "status": "success",
        "message": "All session documents and catalog entries have been cleared"
    })

@app.route("/query", methods=["POST"])
def handle_query():
    """
    Grounded RAG query endpoint.
    Retrieves matching grounded context and returns exact verified images and synthesis.
    """
    data = request.get_json(force=True, silent=True) or {}
    query_text = data.get("query", "").strip()
    attachments = data.get("attachments", [])
    active_documents = data.get("active_documents", None)

    if not query_text and not attachments:
        return jsonify({"error": "Please provide a query or at least one attachment"}), 400

    try:
        scope_info = f"scoped to {len(active_documents)} active doc(s)" if active_documents is not None else "all catalog items"
        print(f"[Query] Executing grounded query: '{query_text}' ({scope_info}) with {len(attachments)} attachment(s)...")
        result = rag_engine.query(query_text=query_text, query_attachments=attachments, active_documents=active_documents)

        return jsonify({
            "status": "success",
            "query": query_text,
            "answer": result.get("answer", ""),
            "images": result.get("images", []),
            "sources": result.get("sources", [])
        })
    except Exception as e:
        print(f"[Query Error] {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == "__main__":
    print(f"=== Multimodal Document & Data Portal Server ===")
    print(f"Engine: RAGAnything Grounded Engine ({rag_engine.model_signature})")
    print(f"Knowledge Catalog: {len(rag_engine.catalog)} item(s) indexed")
    print(f"Serving at http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
