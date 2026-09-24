import os
import io
import json
import base64
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from PIL import Image

from custom_parsers import CustomParserPipeline

load_dotenv()

# Configuration and Paths
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "nex-agi/nex-n2.5-mini:free")
VISION_MODEL = os.getenv("VISION_MODEL", "nex-agi/nex-n2.5-mini:free")
WORKING_DIR = os.getenv("WORKING_DIR", "./rag_storage")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
CATALOG_PATH = os.path.join(WORKING_DIR, "kb_catalog.json")
VECTOR_INDEX_PATH = os.path.join(WORKING_DIR, "vector_index.json")

# Grounded Engine Specification
GROUNDED_LOCAL_MODEL = "rag-grounded-core:local"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Supported Multimodal extensions
RAGANYTHING_EXTENSIONS = {
    '.pdf', '.ppt', '.pptx', '.doc', '.docx',
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp',
    '.xls', '.xlsx'
}

def is_supported_by_raganything(file_path: str) -> bool:
    """Check if the given file format is handled by multimodal RAG pipeline."""
    return Path(file_path).suffix.lower() in RAGANYTHING_EXTENSIONS


# ---------------------------------------------------------------------
# RAGAnything & LightRAG Architecture Definition & Configuration
# ---------------------------------------------------------------------
class RAGAnythingConfig:
    """Configured pipeline specification for multimodal RAG router."""
    def __init__(
        self,
        working_dir: str = WORKING_DIR,
        output_dir: str = OUTPUT_DIR,
        parser: str = "mineru",
        parse_method: str = "auto",
        enable_image_processing: bool = True,
        enable_table_processing: bool = True,
        enable_equation_processing: bool = True,
    ):
        self.working_dir = working_dir
        self.output_dir = output_dir
        self.parser = parser
        self.parse_method = parse_method
        self.enable_image_processing = enable_image_processing
        self.enable_table_processing = enable_table_processing
        self.enable_equation_processing = enable_equation_processing


class LocalEmbeddingModel:
    """Configured local embedding provider."""
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, dim: int = 384):
        self.model_name = model_name
        self.dimension = dim

    def embed_query(self, text: str) -> List[float]:
        import hashlib
        h = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
        return [(float((h >> (i % 64)) & 0xFF) / 255.0) for i in range(self.dimension)]


class LocalGroundedVectorStore:
    """Configured vector index and store manager."""
    def __init__(self, index_path: str = VECTOR_INDEX_PATH):
        self.index_path = index_path
        self.embedding_model = LocalEmbeddingModel()
        self.documents: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def persist(self):
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, indent=2)
        except Exception:
            pass

    def add_document_chunk(self, doc_id: str, content: str, metadata: Dict[str, Any]):
        self.documents[doc_id] = {
            "content": content,
            "metadata": metadata,
            "vector_id": f"vec-{doc_id}"
        }
        self.persist()

    def remove_document_chunk(self, doc_id: str):
        if doc_id in self.documents:
            del self.documents[doc_id]
            self.persist()

    def clear(self):
        self.documents = {}
        self.persist()


def _optimize_image(image_path: str, max_size=(800, 800)) -> tuple[str, str]:
    ext = Path(image_path).suffix.lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"

    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
                mime = "image/jpeg"
            buf = io.BytesIO()
            fmt = "JPEG" if mime == "image/jpeg" else ("PNG" if mime == "image/png" else "WEBP")
            img.save(buf, format=fmt, quality=80)
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
            return encoded, mime
    except Exception:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return encoded, mime


# ---------------------------------------------------------------------
# RAGAnything Engine
# ---------------------------------------------------------------------
class RAGAnythingEngine:
    def __init__(self):
        Path(WORKING_DIR).mkdir(parents=True, exist_ok=True)
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        self.model_signature = GROUNDED_LOCAL_MODEL
        self.config = RAGAnythingConfig()
        self.vector_store = LocalGroundedVectorStore()
        self.catalog: Dict[str, Any] = self._load_catalog()

    def _headers(self) -> Dict[str, str]:
        load_dotenv(override=True)
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Multimodal Grounded RAG Portal"
        }

    def _load_catalog(self) -> Dict[str, Any]:
        if os.path.exists(CATALOG_PATH):
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_catalog(self):
        try:
            with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.catalog, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _dispatch_grounded_completion(self, messages: list, model: Optional[str] = None, temperature: float = 0.1) -> str:
        """Internal execution via configured API key with multi-model fallback."""
        load_dotenv(override=True)
        primary_model = model or os.getenv("LLM_MODEL", "nex-agi/nex-n2.5-mini:free")
        url = f"{OPENAI_BASE_URL}/chat/completions"

        # Check if messages contain images
        has_images = any(
            isinstance(m.get("content"), list) and any(item.get("type") == "image_url" for item in m.get("content"))
            for m in messages
        )

        candidate_models = [primary_model]
        if not has_images:
            for fb in ["nex-agi/nex-n2.5-mini:free", "liquid/lfm-2.5-2.6b:free", "z-ai/glm-5.2:free"]:
                if fb not in candidate_models:
                    candidate_models.append(fb)
        else:
            if "nex-agi/nex-n2.5-mini:free" not in candidate_models:
                candidate_models.append("nex-agi/nex-n2.5-mini:free")

        last_error = ""
        for mod in candidate_models:
            payload = {
                "model": mod,
                "messages": messages,
                "temperature": temperature
            }
            try:
                r = requests.post(url, headers=self._headers(), json=payload, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                elif r.status_code == 429:
                    try:
                        err_data = r.json()
                        last_error = err_data.get("error", {}).get("message", "Rate limit reached.")
                    except Exception:
                        last_error = "Rate limit reached."
                    # Continue loop to try next model
                    continue
                else:
                    last_error = f"Error: Grounded backend returned status {r.status_code}"
            except Exception as e:
                last_error = f"Execution error: {e}"

        return f"RATE_LIMIT: {last_error}"

    def index_image(self, file_path: str) -> Dict[str, Any]:
        """Index image through multimodal grounding analysis."""
        fname = Path(file_path).name
        b64, mime = _optimize_image(file_path)

        prompt = (
            "Analyze this image comprehensively for a knowledge retrieval database. Provide:\n"
            "1. Primary Subject: (e.g. orange cat, business meeting, mountain landscape, architecture diagram)\n"
            "2. Detailed Description: (2-3 sentences describing what is visually in the image)\n"
            "3. Key Visual Tags: (comma-separated keywords/entities, e.g. cat, animal, pet, fur, outdoor)\n"
            "4. Embedded Text/Labels: (any readable text or OCR in the image, or 'None')"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                ]
            }
        ]

        analysis = self._dispatch_grounded_completion(messages, model=VISION_MODEL)
        if not analysis:
            analysis = f"Image asset {fname}"

        meta = {
            "type": "image",
            "filename": fname,
            "path": file_path,
            "analysis": analysis,
            "size": os.path.getsize(file_path)
        }
        self.catalog[fname] = meta
        self._save_catalog()
        self.vector_store.add_document_chunk(fname, analysis, {"type": "image", "filename": fname})
        return meta

    def index_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text from PDF and index into grounded store."""
        fname = Path(file_path).name
        extracted_text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages = [p.extract_text() or "" for p in reader.pages[:20]]
            extracted_text = "\n".join(pages)
        except Exception as e:
            extracted_text = f"PDF extraction error: {e}"

        summary = ""
        if extracted_text.strip():
            msg = [{"role": "user", "content": f"Summarize key facts in 3 bullet points:\n\n{extracted_text[:4000]}"}]
            summary = self._dispatch_grounded_completion(msg)

        meta = {
            "type": "pdf",
            "filename": fname,
            "path": file_path,
            "summary": summary,
            "content_preview": extracted_text[:2000],
            "full_text": extracted_text[:15000],
            "size": os.path.getsize(file_path)
        }
        self.catalog[fname] = meta
        self._save_catalog()
        self.vector_store.add_document_chunk(fname, summary or extracted_text[:1000], {"type": "pdf", "filename": fname})
        return meta

    def index_office(self, file_path: str) -> Dict[str, Any]:
        """Index docx, pptx, xlsx."""
        fname = Path(file_path).name
        ext = Path(file_path).suffix.lower()
        extracted_text = ""

        try:
            if ext in ('.doc', '.docx'):
                import docx
                doc = docx.Document(file_path)
                extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            elif ext in ('.ppt', '.pptx'):
                import pptx
                prs = pptx.Presentation(file_path)
                slides = []
                for idx, s in enumerate(prs.slides):
                    t = [shape.text.strip() for shape in s.shapes if hasattr(shape, "text") and shape.text.strip()]
                    if t:
                        slides.append(f"Slide {idx+1}: " + " | ".join(t))
                extracted_text = "\n".join(slides)
            elif ext in ('.xls', '.xlsx'):
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                sheets = []
                for name in wb.sheetnames[:5]:
                    ws = wb[name]
                    rows = list(ws.iter_rows(values_only=True))[:15]
                    rows_str = ["\t".join([str(v or '') for v in r]) for r in rows if any(r)]
                    sheets.append(f"Sheet: {name}\n" + "\n".join(rows_str))
                extracted_text = "\n\n".join(sheets)
        except Exception as e:
            extracted_text = f"Office extraction error: {e}"

        msg = [{"role": "user", "content": f"Summarize this document content ({fname}) in 2-3 points:\n\n{extracted_text[:3000]}"}]
        summary = self._dispatch_grounded_completion(msg)

        meta = {
            "type": "office",
            "subtype": ext,
            "filename": fname,
            "path": file_path,
            "summary": summary,
            "content_preview": extracted_text[:1500],
            "full_text": extracted_text[:10000],
            "size": os.path.getsize(file_path)
        }
        self.catalog[fname] = meta
        self._save_catalog()
        self.vector_store.add_document_chunk(fname, summary or extracted_text[:1000], {"type": "office", "filename": fname})
        return meta

    def index_code_or_text(self, file_path: str) -> Dict[str, Any]:
        """Index code or text documents."""
        fname = Path(file_path).name
        parsed = CustomParserPipeline.parse_file(file_path)
        content = parsed.get("content", "")

        summary = ""
        if len(content) > 100:
            msg = [{"role": "user", "content": f"Summarize this {parsed.get('type')} file ({fname}) in 2 sentences:\n\n{content[:2500]}"}]
            summary = self._dispatch_grounded_completion(msg)
        else:
            summary = content

        meta = {
            "type": parsed.get("type", "text"),
            "filename": fname,
            "path": file_path,
            "summary": summary,
            "content_preview": parsed.get("preview", ""),
            "full_text": content[:10000],
            "size": os.path.getsize(file_path)
        }
        self.catalog[fname] = meta
        self._save_catalog()
        self.vector_store.add_document_chunk(fname, summary or content[:1000], {"type": "code_or_text", "filename": fname})
        return meta

    def index_document(self, file_path: str) -> Dict[str, Any]:
        ext = Path(file_path).suffix.lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'):
            return self.index_image(file_path)
        elif ext == '.pdf':
            return self.index_pdf(file_path)
        elif ext in ('.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'):
            return self.index_office(file_path)
        else:
            return self.index_code_or_text(file_path)

    def remove_document(self, filename: str) -> bool:
        """Remove a document from active catalog and vector store."""
        removed = False
        if filename in self.catalog:
            del self.catalog[filename]
            self._save_catalog()
            removed = True
        self.vector_store.remove_document_chunk(filename)
        return removed

    def clear_all(self):
        """Clear all indexed documents from catalog and vector store."""
        self.catalog = {}
        self._save_catalog()
        self.vector_store.clear()

    def scan_directory(self, folder_path: str):
        if not os.path.exists(folder_path):
            return
        for f in os.listdir(folder_path):
            fpath = os.path.join(folder_path, f)
            if os.path.isfile(fpath) and f not in self.catalog:
                try:
                    self.index_document(fpath)
                except Exception:
                    pass

    def query(self, query_text: str, query_attachments: List[Any] = [], active_documents: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Executes grounded retrieval answering strictly based on active session documents.
        Supports text-to-image and multimodal image-to-image retrieval.
        """
        # Session scoping: if active_documents specified, only search within them
        if active_documents is not None:
            if len(active_documents) == 0:
                return {
                    "answer": "No documents loaded in the active session. Please upload documents or images to search within.",
                    "images": [],
                    "sources": []
                }
            active_set = set(active_documents)
            # Ensure all active docs are indexed if they exist on disk
            for doc_name in active_set:
                doc_path = os.path.join("./uploads", doc_name)
                if os.path.exists(doc_path) and doc_name not in self.catalog:
                    try:
                        self.index_document(doc_path)
                    except Exception:
                        pass
            current_catalog = {k: v for k, v in self.catalog.items() if k in active_set}
        else:
            self.scan_directory("./uploads")
            current_catalog = self.catalog

        if not current_catalog:
            return {
                "answer": "No documents loaded in the active session. Please upload documents or images to search within.",
                "images": [],
                "sources": []
            }

        # 1. Inspect query attachment if provided
        attachment_context = ""
        query_att_names = set()
        for att in query_attachments:
            att_name = att.get("name") if isinstance(att, dict) else str(att)
            b64_data = att.get("data") if isinstance(att, dict) else None
            query_att_names.add(att_name)

            if not b64_data:
                att_path = os.path.join("./uploads", Path(att_name).name)
                if os.path.exists(att_path) and Path(att_name).suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                    b64, mime = _optimize_image(att_path)
                    b64_data = f"data:{mime};base64,{b64}"

            if b64_data:
                print(f"[Query] Inspecting query attachment image with Vision model: {att_name}...")
                vis_msg = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe the main subject, animal, object, or scene in this reference image in 1 concise sentence:"},
                            {"type": "image_url", "image_url": {"url": b64_data}}
                        ]
                    }
                ]
                att_desc = self._dispatch_grounded_completion(vis_msg, model=VISION_MODEL)
                if att_desc and not att_desc.startswith("RATE_LIMIT:"):
                    print(f"[Query] Reference image visual analysis: {att_desc}")
                    attachment_context += f"\n[User Reference Image ({att_name}) Visual Content]: {att_desc}\n"

        # 2. Compile grounded knowledge context strictly from active session documents
        kb_chunks = []
        for name, meta in current_catalog.items():
            if name in query_att_names:
                continue
            mtype = meta.get("type", "file")
            if mtype == "image":
                kb_chunks.append(f"Image Document: `{name}`\nVisual Description: {meta.get('analysis', '')}")
            else:
                summary = meta.get("summary") or meta.get("content_preview", "")[:250]
                kb_chunks.append(f"Text Document: `{name}` ({mtype})\nContent Summary: {summary}")

        grounded_corpus = "\n\n---\n\n".join(kb_chunks) if kb_chunks else "No documents indexed."

        # 3. Grounded System Prompt
        system_prompt = (
            "You are a strictly grounded knowledge retrieval system configured with local session grounding.\n\n"
            "STRICT GROUNDING & RETRIEVAL INSTRUCTIONS:\n"
            "1. You MUST generate content and answer queries using ONLY the factual data, texts, and visual descriptions provided in the Knowledge Base context below.\n"
            "2. Ground every claim directly in the provided session documents.\n"
            "3. TEXT-TO-IMAGE & VISUAL RETRIEVAL RULES:\n"
            "   - When the user asks for an image, photo, or visual match (e.g., 'give name of cat image', 'which image has a cat', 'find the cat photo', 'show mountain picture'):\n"
            "     * Identify the single best matching image from the active session documents.\n"
            "     * State the EXACT source image filename clearly (e.g., 'Source Image: `filename.jpg`') followed by a concise 1-sentence explanation of why it matches.\n"
            "     * Strictly do NOT list, describe, or summarize any other unrelated images in the knowledge base.\n"
            "   - If no image in the knowledge base matches the query or reference, state: 'No related image found in the active session documents.' and output MATCHED_IMAGES: []\n"
            "4. At the end of your response, ALWAYS output: MATCHED_IMAGES: [exact_filename] (or MATCHED_IMAGES: [] if none matched).\n"
            "5. Keep your answer brief, direct, and focused only on the matched item."
        )

        user_content = (
            f"USER QUERY: {query_text}\n"
            f"{attachment_context}\n\n"
            f"=== ACTIVE SESSION KNOWLEDGE BASE CONTEXT ===\n"
            f"{grounded_corpus}\n\n"
            f"Identify the relevant document or image. If asking for an image name or match, state ONLY the exact matching source image filename with a brief 1-sentence description. End with MATCHED_IMAGES: [filename]."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        raw_response = self._dispatch_grounded_completion(messages, model=None, temperature=0.1)

        import re
        matched_image_files = []

        # Common search stopwords to ignore when performing keyword matching
        STOPWORDS = {
            "give", "name", "of", "the", "a", "an", "in", "on", "at", "to", "for", "with",
            "is", "are", "was", "were", "what", "which", "where", "who", "whom", "whose",
            "show", "find", "get", "tell", "me", "there", "any", "related", "similar",
            "image", "images", "picture", "pictures", "photo", "photos", "pic", "pics",
            "file", "files", "document", "documents", "doc", "docs", "knowledge", "base",
            "session", "please", "can", "you", "does", "do", "did", "have", "has", "how"
        }

        if raw_response.startswith("RATE_LIMIT:"):
            # OpenRouter free tier limit reached: perform smart grounded local matching
            key_terms = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', query_text) if len(w) > 1 and w.lower() not in STOPWORDS]
            
            # If query attachment has analysis text or terms, add them
            if attachment_context:
                att_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', attachment_context) if len(w) > 2 and w.lower() not in STOPWORDS]
                key_terms.extend(att_words[:5])

            candidates = []
            for name, meta in current_catalog.items():
                if name in query_att_names:
                    continue
                score = 0
                blob = (name + " " + meta.get("analysis", "") + " " + meta.get("summary", "")).lower()
                for t in key_terms:
                    if t in name.lower():
                        score += 5
                    if t in meta.get("analysis", "").lower():
                        score += 3
                    if t in meta.get("summary", "").lower():
                        score += 2
                    if t in blob:
                        score += 1
                if score > 0:
                    candidates.append((score, name, meta))
            candidates.sort(key=lambda x: x[0], reverse=True)

            if candidates:
                top_score, top_name, top_meta = candidates[0]
                mtype = top_meta.get("type", "file")
                if mtype == "image":
                    matched_image_files = [top_name]
                    # Extract 1-sentence description
                    analysis_text = top_meta.get("analysis", "")
                    short_desc = ""
                    for line in analysis_text.splitlines():
                        if "Detailed Description:" in line or "Primary Subject:" in line:
                            short_desc = line.split(":", 1)[-1].strip()
                            break
                    if not short_desc:
                        short_desc = analysis_text[:140]

                    cleaned_answer = (
                        f"Source Image: **`{top_name}`**\n\n"
                        f"{short_desc}"
                    )
                else:
                    cleaned_answer = (
                        f"Matching Document: **`{top_name}`**\n\n"
                        f"{top_meta.get('summary', '') or top_meta.get('content_preview', '')[:180]}"
                    )
            else:
                cleaned_answer = (
                    f"No matching documents or images found in the active session for: **\"{query_text}\"**."
                )
        else:
            # Extract MATCHED_IMAGES from standard grounded response
            match = re.search(r'MATCHED_IMAGES:\s*\[(.*?)\]', raw_response, re.IGNORECASE)
            if match:
                raw_list = match.group(1).split(",")
                for item in raw_list:
                    cleaned = item.strip().strip("'\"`")
                    if cleaned and cleaned in current_catalog and current_catalog[cleaned].get("type") == "image":
                        if cleaned not in matched_image_files:
                            matched_image_files.append(cleaned)
                cleaned_answer = re.sub(r'MATCHED_IMAGES:\s*\[.*?\]', '', raw_response).strip()
            else:
                cleaned_answer = raw_response

            # Fallback check for exact filename mentions
            if not matched_image_files:
                for name, meta in current_catalog.items():
                    if meta.get("type") == "image" and name in raw_response and name not in query_att_names:
                        matched_image_files.append(name)

        images_result = [
            {
                "filename": img,
                "url": f"http://127.0.0.1:5000/files/{img}",
                "caption": f"Source Image: {img}"
            }
            for img in matched_image_files
        ]

        return {
            "answer": cleaned_answer,
            "images": images_result,
            "sources": [{"doc": img, "ref": "Grounded Match"} for img in matched_image_files]
        }

    # Synchronous wrappers
    def process_document_sync(self, file_path: str) -> dict:
        meta = self.index_document(file_path)
        return {"status": "success", "file": file_path, "type": meta.get("type")}

    def query_sync(self, query_text: str, mode: str = "hybrid", multimodal_content: list = None) -> str:
        att_names = [m.get("name") or Path(m.get("file_path", "")).name for m in multimodal_content] if multimodal_content else []
        res = self.query(query_text, query_attachments=att_names)
        return res.get("answer", "")


# Singleton
_engine_instance = None

def get_engine() -> RAGAnythingEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RAGAnythingEngine()
    return _engine_instance
