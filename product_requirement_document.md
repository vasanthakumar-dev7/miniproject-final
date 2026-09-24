# Product Requirement Document (PRD)

## Project Title
**Multimodal RAG System (raganything + Custom Multi-Format Parsers)**

---

## 1. Executive Summary
The goal of this project is to build an end-to-end Multimodal Retrieval-Augmented Generation (RAG) pipeline capable of ingesting diverse document types, source code, structured datasets, and visual files. 

The system leverages the `raganything` ecosystem for complex binary documents and media types (PDF, Office files, images) while implementing lightweight custom parsers for plain text, structured markup, data tables, and source code.

---

## 2. Installation & Core Setup

### Dependencies
```bash
# Core library with all extended format features
pip install 'raganything[all]'

# Optional specific installations if isolating dependencies
pip install 'raganything[image,text]'
```

---

## 3. Scope & File Format Matrix

| Format Category | File Extensions | Responsible Parser / Library | Processing Approach |
| :--- | :--- | :--- | :--- |
| **Complex Documents** | `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx` | `raganything` | Native structural extraction, page layout analysis, LibreOffice conversion where required. |
| **Images** | `.jpg`, `.jpeg`, `.png` | `raganything` (`[image]`) | Multimodal vision model analysis, OCR, and automated image captioning. |
| **Spreadsheets (Office)** | `.xls`, `.xlsx` | `raganything` | Table structural parsing and sheet-by-sheet text/data indexing. |
| **Plain Text** | `.txt`, `.md` | Custom Parser | UTF-8 text chunking, markdown header-aware splitting. |
| **Tabular & Data** | `.csv`, `.tsv` | Custom Parser | Row/column schema extraction and record-level chunking. |
| **Structured Markup** | `.json`, `.xml`, `.yaml`, `.yml` | Custom Parser | Key-value pair flattening, AST/tree traversal, syntax preservation. |
| **Source Code** | `.py`, `.js`, `.ts`, `.html`, `.css`, `.cpp`, `.java`, etc. | Custom Parser | Code-aware chunking (functions, classes, AST analysis), preserving scope and syntax. |

---

## 4. System Architecture & Functional Requirements

```
                       ┌───────────────────────────────┐
                       │       Document Ingestion      │
                       └───────────────┬───────────────┘
                                       │
                       ┌───────────────┴───────────────┐
                       │     Format Router / Parser    │
                       └───────┬───────────────┬───────┘
                               │               │
        ┌──────────────────────┴┐             ┌┴──────────────────────┐
        │  raganything Engine   │             │ Custom Extensible Engine│
        │                       │             │                       │
        │ • PDF / DOC / PPT     │             │ • TXT / MD            │
        │ • PNG / JPG           │             │ • CSV / TSV           │
        │ • XLS                 │             │ • JSON / XML / YAML   │
        │                       │             │ • Source Code Files   │
        └───────────┬───────────┘             └───────────┬───────────┘
                    │                                     │
                    └───────────────────┬─────────────────┘
                                        │
                       ┌────────────────┴───────────────┐
                       │  Multimodal Knowledge Graph    │
                       │     & Vector Indexing          │
                       └────────────────┬───────────────┘
                                        │
                       ┌────────────────┴───────────────┐
                       │   Hybrid Retrieval & LLM Gen   │
                       └────────────────────────────────┘
```

---

## 5. Functional Specifications

### Module 1: Ingestion & Routing Router
* **Format Identification:** Automatically detects file extension and MIME type to route files to either the `raganything` pipeline or custom extension modules.
* **Batch Processing:** Handles single-file and folder-level recursive directory ingestion asynchronously.

---

### Module 2: `raganything` Ingestion Core
Handles binary, visual, and standard Microsoft Office formats out of the box.

* **PDF (`.pdf`) & Word (`.doc`, `.docx`):**
  * Extracts raw text while maintaining reading order across columns.
  * Preserves embedded figures, captions, and section hierarchy.
* **Presentations (`.ppt`, `.pptx`):**
  * Parses slide titles, bullet points, speaker notes, and embedded diagrams.
* **Images (`.png`, `.jpg`, `.jpeg`):**
  * Uses vision model integration (via `raganything[image]`) to generate high-detailed textual descriptions, optical character recognition (OCR) for text within images, and visual relationship tagging.
* **Excel Files (`.xls`):**
  * Extracts sheet contents, structured tables, and cell relationships.

---

### Module 3: Custom Format Extensions (User-Implemented)

#### 3.1 Plain Text & Markdown Processor (`.txt`, `.md`)
* **Markdown Parsing:** Headers (`#`, `##`), blockquotes, and lists are used as explicit semantic boundaries for chunking.
* **Plain Text Chunking:** Implements recursive character splitting with semantic overlap.

#### 3.2 Tabular Data Processor (`.csv`, `.tsv`)
* **Schema Detection:** Reads headers to infer dataset structure.
* **Row-to-Document Mapping:** Converts tabular records into context-aware key-value text blocks (e.g., `"Column Name: Value"`) to maximize embedding similarity.

#### 3.3 Structured Markup Processor (`.json`, `.xml`, `.yaml`, `.yml`)
* **Hierarchical Flattening:** Flattens deeply nested structures while keeping parent-child context tags.
* **Schema Integrity:** Preserves key-value contexts so LLMs can reason over configurations and payloads.

#### 3.4 Source Code Processor (Multi-Language Source Code)
* **AST / Symbol-Based Chunking:** Splits code by classes, methods, and function boundaries rather than arbitrary token counts.
* **Metadata Extraction:** Captures language context, imports, function signatures, and docstrings.

---

### Module 4: Unified Vector & Knowledge Graph Indexing
* **Multimodal Graph Integration:** Combines chunked text, code metadata, image captions, and structured fields into a single multimodal knowledge graph network.
* **Hybrid Search Index:** Stores dense vector embeddings alongside graph-based entity-relationship indexes for multi-hop reasoning.

---

