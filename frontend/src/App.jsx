import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  FileText,
  Send,
  Paperclip,
  X,
  Copy,
  Check,
  FileCheck2,
  FolderOpen,
  Layers,
  Trash2,
  Loader2,
  Eye,
  Maximize2,
  Image as ImageIcon
} from 'lucide-react';
import './App.css';

// Helper to categorize document formats
const getFormatCategory = (filename) => {
  const ext = filename.split('.').pop().toLowerCase();
  if (['pdf'].includes(ext)) return { type: 'pdf', label: 'PDF', color: 'badge-pdf' };
  if (['doc', 'docx'].includes(ext)) return { type: 'doc', label: 'DOCX', color: 'badge-doc' };
  if (['ppt', 'pptx'].includes(ext)) return { type: 'ppt', label: 'PPT', color: 'badge-ppt' };
  if (['xls', 'xlsx', 'csv'].includes(ext)) return { type: 'xls', label: 'SHEET', color: 'badge-xls' };
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(ext)) return { type: 'img', label: 'IMAGE', color: 'badge-img' };
  if (['py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'json', 'yaml', 'yml', 'xml', 'sql', 'cpp', 'c', 'java', 'go', 'rs', 'sh'].includes(ext)) {
    return { type: 'code', label: 'CODE', color: 'badge-code' };
  }
  return { type: 'other', label: ext.toUpperCase() || 'FILE', color: 'badge-other' };
};

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

// Clean SVG diagram data for demonstration
const SAMPLE_DIAGRAM_SVG = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='600' height='360' viewBox='0 0 600 360'><rect width='100%' height='100%' fill='%23faf7f2'/><rect x='20' y='20' width='560' height='320' rx='12' fill='%23ffffff' stroke='%23d2c7b9' stroke-width='2'/><text x='300' y='55' font-family='sans-serif' font-size='17' font-weight='bold' fill='%2328211d' text-anchor='middle'>Multimodal Processing Architecture</text><rect x='50' y='90' width='140' height='70' rx='8' fill='%23eff6ff' stroke='%233b82f6' stroke-width='1.5'/><text x='120' y='122' font-family='sans-serif' font-size='13' font-weight='bold' fill='%231d4ed8' text-anchor='middle'>Document Ingestion</text><text x='120' y='142' font-family='sans-serif' font-size='11' fill='%233b82f6' text-anchor='middle'>PDF / Office / Images</text><rect x='230' y='90' width='140' height='70' rx='8' fill='%23fef3c7' stroke='%23d97706' stroke-width='1.5'/><text x='300' y='122' font-family='sans-serif' font-size='13' font-weight='bold' fill='%23b45309' text-anchor='middle'>Format Router</text><text x='300' y='142' font-family='sans-serif' font-size='11' fill='%23d97706' text-anchor='middle'>raganything.py</text><rect x='410' y='90' width='140' height='70' rx='8' fill='%23ecfdf5' stroke='%2310b981' stroke-width='1.5'/><text x='480' y='122' font-family='sans-serif' font-size='13' font-weight='bold' fill='%23047857' text-anchor='middle'>Vision LLM / OCR</text><text x='480' y='142' font-family='sans-serif' font-size='11' fill='%2310b981' text-anchor='middle'>nex-n2.5-mini</text><rect x='140' y='210' width='320' height='90' rx='8' fill='%23f5f3ff' stroke='%238b5cf6' stroke-width='1.5'/><text x='300' y='245' font-family='sans-serif' font-size='14' font-weight='bold' fill='%236d28d9' text-anchor='middle'>Knowledge Graph & Vector Index</text><text x='300' y='270' font-family='sans-serif' font-size='12' fill='%237c3aed' text-anchor='middle'>Linked Visual Entities & Text Chunks</text><path d='M 190 125 L 230 125' stroke='%2382756a' stroke-width='2' marker-end='url(%23arrow)'/><path d='M 370 125 L 410 125' stroke='%2382756a' stroke-width='2'/><path d='M 300 160 L 300 210' stroke='%2382756a' stroke-width='2'/></svg>";

export default function App() {
  const [uploadedDocs, setUploadedDocs] = useState(() => {
    try {
      const saved = sessionStorage.getItem('active_session_docs');
      if (saved !== null) {
        return JSON.parse(saved);
      }
    } catch {}
    return [];
  });
  const [queryAttachments, setQueryAttachments] = useState([]);
  const [queryInput, setQueryInput] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [lightboxImage, setLightboxImage] = useState(null);

  // Results History (starts empty)
  const [history, setHistory] = useState([]);
  const [activeResultId, setActiveResultId] = useState(null);
  const fileUploadInputRef = useRef(null);
  const queryAttachmentInputRef = useRef(null);
  const textareaRef = useRef(null);

  // Persist session documents
  useEffect(() => {
    try {
      sessionStorage.setItem('active_session_docs', JSON.stringify(uploadedDocs));
    } catch {}
  }, [uploadedDocs]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
    }
  }, [queryInput]);

  // Sync Knowledge Base from backend catalog on mount
  const syncCatalog = async () => {
    try {
      const res = await fetch('http://127.0.0.1:5000/catalog');
      if (res.ok) {
        const data = await res.json();
        if (data.items && Array.isArray(data.items)) {
          const savedRaw = sessionStorage.getItem('active_session_docs');
          if (savedRaw !== null) {
            const savedList = JSON.parse(savedRaw);
            const savedNames = new Set(savedList.map(d => d.name));
            // Only show documents that belong to this session
            const synced = data.items
              .filter(item => savedNames.has(item.filename))
              .map((item) => ({
                id: `kb-${item.filename}`,
                name: item.filename,
                size: item.size || 0,
                category: getFormatCategory(item.filename),
                previewUrl: item.type === 'image' ? item.url : null,
                timestamp: 'Active Session',
                summary: item.summary
              }));
            setUploadedDocs(synced);
          } else {
            // First visit before explicit session interaction: sync current valid catalog
            const synced = data.items.map((item) => ({
              id: `kb-${item.filename}`,
              name: item.filename,
              size: item.size || 0,
              category: getFormatCategory(item.filename),
              previewUrl: item.type === 'image' ? item.url : null,
              timestamp: 'Active Session',
              summary: item.summary
            }));
            setUploadedDocs(synced);
          }
        }
      }
    } catch {
      // Backend not yet reachable
    }
  };

  useEffect(() => {
    syncCatalog();
  }, []);

  // Handle Document Repository Upload
  const handleDocUpload = async (files) => {
    if (!files || files.length === 0) return;
    const newDocs = Array.from(files).map((f) => {
      const isImg = f.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(f.name);
      return {
        id: `doc-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
        name: f.name,
        size: f.size,
        category: getFormatCategory(f.name),
        previewUrl: isImg ? URL.createObjectURL(f) : null,
        timestamp: 'Just now',
        fileObj: f
      };
    });

    setUploadedDocs((prev) => {
      const existing = new Set(prev.map(d => d.name));
      const toAdd = newDocs.filter(d => !existing.has(d.name));
      return [...toAdd, ...prev];
    });

    // Send to Flask backend
    try {
      const formData = new FormData();
      Array.from(files).forEach((f) => formData.append('files', f));
      await fetch('http://127.0.0.1:5000/upload', {
        method: 'POST',
        body: formData
      });
    } catch (e) {
      console.error('Upload failed:', e);
    }
  };

  // Handle Query Attachments (jpg, image, docx, ppt, png, pdf, xls, coding files)
  const handleQueryAttachment = (files) => {
    if (!files || files.length === 0) return;
    const newAttachments = Array.from(files).map((f) => {
      const isImg = f.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(f.name);
      return {
        id: `att-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
        name: f.name,
        size: f.size,
        file: f,
        isImage: isImg,
        previewUrl: isImg ? URL.createObjectURL(f) : null,
        category: getFormatCategory(f.name)
      };
    });

    setQueryAttachments((prev) => [...prev, ...newAttachments]);
  };

  const removeQueryAttachment = (id) => {
    setQueryAttachments((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target?.previewUrl && !target.previewUrl.startsWith('data:')) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return prev.filter((item) => item.id !== id);
    });
  };

  const removeDoc = async (id, docName) => {
    const targetDoc = uploadedDocs.find(item => item.id === id || item.name === docName);
    const filename = docName || targetDoc?.name;

    if (targetDoc?.previewUrl && !targetDoc.previewUrl.startsWith('data:')) {
      URL.revokeObjectURL(targetDoc.previewUrl);
    }

    setUploadedDocs((prev) => prev.filter((d) => d.id !== id && d.name !== filename));

    if (filename) {
      try {
        await fetch(`http://127.0.0.1:5000/documents/${encodeURIComponent(filename)}`, {
          method: 'DELETE'
        });
      } catch (err) {
        console.error('[Storage] Error removing document from backend:', err);
      }
    }
  };

  const clearAllDocs = async () => {
    uploadedDocs.forEach(d => {
      if (d?.previewUrl && !d.previewUrl.startsWith('data:')) {
        URL.revokeObjectURL(d.previewUrl);
      }
    });
    setUploadedDocs([]);
    sessionStorage.setItem('active_session_docs', JSON.stringify([]));

    try {
      await fetch('http://127.0.0.1:5000/clear', {
        method: 'POST'
      });
    } catch (err) {
      console.error('[Storage] Error clearing all documents:', err);
    }
  };

  // Execute Query
  const handleRunQuery = async () => {
    if (!queryInput.trim() && queryAttachments.length === 0) return;

    const currentQuery = queryInput.trim() || 'Review attached files';
    const attachedFileNames = queryAttachments.map((a) => a.name);
    setIsQuerying(true);

    let answerText = '';
    let sourcesList = [];
    let returnedImages = [];
    let isLive = false;

    // Try Flask backend on port 5000
    try {
      // 1. If query has attached files, convert images to base64 and upload to server
      const payloadAttachments = await Promise.all(
        queryAttachments.map(async (att) => {
          const fileObj = att.file || att.fileObj;
          let dataUrl = att.dataUrl;
          if (!dataUrl && fileObj && att.isImage) {
            dataUrl = await new Promise((resolve) => {
              const reader = new FileReader();
              reader.onload = (e) => resolve(e.target.result);
              reader.onerror = () => resolve(null);
              reader.readAsDataURL(fileObj);
            });
          }
          return {
            name: att.name,
            data: dataUrl || null
          };
        })
      );

      if (queryAttachments.length > 0) {
        const formData = new FormData();
        queryAttachments.forEach((att) => {
          const fileObj = att.file || att.fileObj;
          if (fileObj) {
            formData.append('files', fileObj);
          }
        });
        await fetch('http://127.0.0.1:5000/upload', {
          method: 'POST',
          body: formData
        }).catch(() => {});
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minute timeout

      const res = await fetch('http://127.0.0.1:5000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: currentQuery,
          attachments: payloadAttachments,
          active_documents: uploadedDocs.map((d) => d.name)
        }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        answerText = data.answer || data.result || data.response || JSON.stringify(data);
        sourcesList = data.sources || [];
        if (data.images && Array.isArray(data.images)) {
          returnedImages = data.images.map((img) => ({
            filename: img.filename,
            url: img.url,
            caption: `Matched file: ${img.filename}`
          }));
        }
        isLive = true;
      } else {
        const err = await res.json().catch(() => ({}));
        console.error('[Query] Backend returned error:', res.status, err);
      }
    } catch (err) {
      console.error('[Query] Backend not reachable or timed out:', err.message);
    }

    if (!isLive) {
      // Backend is not reachable — show a text-only fallback.
      // NEVER guess or pick an arbitrary image from the repository.
      const docList = uploadedDocs.map((d) => d.name).join(', ') || 'workspace repository';
      answerText = `### Results for: "${currentQuery}"\n\n` +
        `Analyzed against active documents (\`${docList}\`).\n\n` +
        `#### Note:\n` +
        `* The backend is not reachable. Connect to \`http://127.0.0.1:5000\` to enable live RAG retrieval and image matching.`;

      sourcesList = [];
      returnedImages = [];
    }

    const newResult = {
      id: `res-${Date.now()}`,
      query: currentQuery,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachments: attachedFileNames,
      images: returnedImages,
      answer: answerText,
      sources: sourcesList
    };

    setHistory((prev) => [newResult, ...prev]);
    setActiveResultId(newResult.id);
    setQueryInput('');
    setQueryAttachments([]);
    setIsQuerying(false);
  };

  const activeResult = history.find((h) => h.id === activeResultId) || history[0];

  const handleCopyAnswer = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo">
            <FolderOpen size={20} />
          </div>
          <div>
            <h1 className="brand-title">Document & Data Portal</h1>
            <p className="brand-subtitle">Multi-format file inspection and query workspace</p>
          </div>
        </div>

        <div className="header-status">
          <span className="status-dot"></span>
          <span>Workspace Active</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-content">
        {/* Left Column: Document Upload Section */}
        <aside className="sidebar-panel">
          <div className="beige-card">
            <div className="card-title">
              <span>Document Repository</span>
              <FileText size={15} />
            </div>

            <div
              className={`dropzone ${isDragging ? 'active' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                handleDocUpload(e.dataTransfer.files);
              }}
              onClick={() => fileUploadInputRef.current?.click()}
            >
              <input
                ref={fileUploadInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.png,.jpg,.jpeg,.webp,.py,.js,.jsx,.ts,.tsx,.html,.css,.json,.yaml,.yml,.xml,.cpp,.java,.txt,.md"
                onChange={(e) => handleDocUpload(e.target.files)}
              />
              <div className="upload-icon-wrapper">
                <UploadCloud size={24} />
              </div>
              <p className="dropzone-text">Upload documents here</p>
              <p className="dropzone-subtext">Drag & drop or click to browse files</p>

              <div className="formats-taglist">
                <span className="format-pill">PDF</span>
                <span className="format-pill">DOCX</span>
                <span className="format-pill">PPT</span>
                <span className="format-pill">XLS</span>
                <span className="format-pill">IMAGES</span>
                <span className="format-pill">CODE</span>
              </div>
            </div>

            {/* Uploaded Documents List */}
            <div style={{ marginTop: '1.25rem' }}>
              <div className="card-title" style={{ fontSize: '0.78rem', marginBottom: '0.45rem' }}>
                <span>Loaded Documents ({uploadedDocs.length})</span>
                {uploadedDocs.length > 0 && (
                  <button
                    className="icon-btn"
                    title="Clear All Documents"
                    onClick={clearAllDocs}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>

              <div className="uploaded-docs-list">
                {uploadedDocs.length === 0 ? (
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
                    No documents loaded. Upload files above to begin.
                  </p>
                ) : (
                  uploadedDocs.map((doc) => (
                    <div key={doc.id} className="doc-item animate-fade-in">
                      <div className="doc-info">
                        {doc.previewUrl ? (
                          <img
                            src={doc.previewUrl}
                            alt={doc.name}
                            style={{ width: '28px', height: '28px', objectFit: 'cover', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}
                          />
                        ) : (
                          <span className={`doc-badge ${doc.category.color}`}>
                            {doc.category.label}
                          </span>
                        )}
                        <div>
                          <div className="doc-name" title={doc.name}>
                            {doc.name}
                          </div>
                          <div className="doc-size">
                            {formatFileSize(doc.size)}
                          </div>
                        </div>
                      </div>
                      <button
                        className="icon-btn"
                        title="Remove"
                        onClick={() => removeDoc(doc.id, doc.name)}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Repository Summary */}
          <div className="beige-card">
            <div className="card-title">
              <span>Repository Overview</span>
            </div>
            <div className="summary-grid">
              <div className="summary-item">
                <div className="summary-val">{uploadedDocs.length}</div>
                <div className="summary-label">Total Documents</div>
              </div>
              <div className="summary-item">
                <div className="summary-val">
                  {formatFileSize(uploadedDocs.reduce((acc, d) => acc + d.size, 0))}
                </div>
                <div className="summary-label">Total Size</div>
              </div>
            </div>
          </div>
        </aside>

        {/* Right Column: Query & Results Section */}
        <section className="main-stage">
          {/* Query Box */}
          <div className="query-container">
            {/* Attached files bar inside query box */}
            {queryAttachments.length > 0 && (
              <div className="query-attachments-bar">
                {queryAttachments.map((att) => (
                  <div key={att.id} className="attachment-chip">
                    {att.isImage ? (
                      <img src={att.previewUrl} alt={att.name} className="attachment-thumb" />
                    ) : (
                      <span className={`doc-badge ${att.category.color}`}>
                        {att.category.label}
                      </span>
                    )}
                    <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {att.name}
                    </span>
                    <button
                      className="remove-attachment-btn"
                      onClick={() => removeQueryAttachment(att.id)}
                      title="Remove attachment"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Query Input */}
            <textarea
              ref={textareaRef}
              className="query-textarea"
              placeholder="Type your query here or attach files to inspect (Enter to search)..."
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleRunQuery();
                }
              }}
            />

            {/* Query Toolbar */}
            <div className="query-toolbar">
              <input
                ref={queryAttachmentInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                accept=".jpg,.jpeg,.png,.webp,.gif,.bmp,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.py,.js,.jsx,.ts,.tsx,.html,.css,.json,.yaml,.yml,.xml,.cpp,.java,.go,.rs,.sql,.sh,.txt,.md"
                onChange={(e) => handleQueryAttachment(e.target.files)}
              />
              <button
                type="button"
                className="attach-btn"
                title="Attach images, docx, ppt, pdf, xls, or coding files to this query"
                onClick={() => queryAttachmentInputRef.current?.click()}
              >
                <Paperclip size={14} />
                <span>Attach Files</span>
              </button>

              <button
                className="send-btn"
                disabled={isQuerying || (!queryInput.trim() && queryAttachments.length === 0)}
                onClick={handleRunQuery}
              >
                {isQuerying ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <span>Submit Query</span>
                    <Send size={14} />
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Results Section */}
          <div className="result-section">
            {isQuerying ? (
              <div className="result-card">
                <div className="result-header">
                  <div className="result-title-group">
                    <span className="result-title">Searching repository and parsing results...</span>
                  </div>
                </div>
                <div className="loading-box">
                  <div className="loading-line" style={{ width: '85%' }}></div>
                  <div className="loading-line" style={{ width: '92%' }}></div>
                  <div className="loading-line" style={{ width: '70%' }}></div>
                  <div className="loading-line" style={{ width: '88%' }}></div>
                </div>
              </div>
            ) : activeResult ? (
              <div className="result-card animate-fade-in">
                <div className="result-header">
                  <div className="result-title-group">
                    <FileCheck2 size={18} color="var(--accent-primary)" />
                    <div>
                      <h2 className="result-title">{activeResult.query}</h2>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {activeResult.timestamp}
                      </span>
                    </div>
                  </div>

                  <button
                    className="action-pill-btn"
                    onClick={() => handleCopyAnswer(activeResult.answer, activeResult.id)}
                  >
                    {copiedId === activeResult.id ? (
                      <>
                        <Check size={13} color="#2e7d32" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={13} />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Render Result Content */}
                <div className="result-body">
                  {activeResult.answer.split('\n\n').map((paragraph, idx) => {
                    if (paragraph.startsWith('### ')) {
                      return <h3 key={idx}>{paragraph.replace('### ', '')}</h3>;
                    }
                    if (paragraph.startsWith('#### ')) {
                      return <h4 key={idx}>{paragraph.replace('#### ', '')}</h4>;
                    }
                    if (paragraph.startsWith('```')) {
                      const lines = paragraph.split('\n');
                      const lang = lines[0].replace('```', '') || 'code';
                      const codeContent = lines.slice(1, -1).join('\n');
                      return (
                        <pre key={idx}>
                          <div style={{ fontSize: '0.68rem', color: '#a69a8f', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
                            {lang}
                          </div>
                          <code>{codeContent}</code>
                        </pre>
                      );
                    }
                    if (paragraph.startsWith('* ') || paragraph.startsWith('- ')) {
                      return (
                        <ul key={idx}>
                          {paragraph.split('\n').map((item, itemIdx) => (
                            <li key={itemIdx}>{item.replace(/^[*|-]\s+/, '')}</li>
                          ))}
                        </ul>
                      );
                    }
                    return <p key={idx}>{paragraph}</p>;
                  })}
                </div>

                {/* Matched Image Names (Text-only display, no image preview) */}
                {activeResult.images && activeResult.images.length > 0 && (
                  <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: 'var(--beige-100)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <FileText size={14} color="var(--accent-primary)" />
                      <span>Identified Image File(s):</span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {activeResult.images.map((img, imgIdx) => (
                        <span key={imgIdx} style={{ fontSize: '0.82rem', fontFamily: 'monospace', background: 'var(--card-bg)', padding: '0.25rem 0.6rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', color: 'var(--text-main)', fontWeight: 600 }}>
                          {img.filename}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Source Excerpts / References */}
                {activeResult.sources && activeResult.sources.length > 0 && (
                  <div className="citations-box">
                    <div className="citations-header">
                      <Layers size={14} />
                      <span>Referenced Documents & Excerpts ({activeResult.sources.length})</span>
                    </div>
                    <div className="sources-grid">
                      {activeResult.sources.map((src, srcIdx) => (
                        <div key={srcIdx} className="source-card">
                          <div className="source-meta">
                            <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{src.doc}</span>
                            <span style={{ color: 'var(--accent-primary)', fontSize: '0.7rem' }}>
                              {src.ref}
                            </span>
                          </div>
                          <div className="source-snippet">
                            "{src.snippet}"
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="result-card animate-fade-in" style={{ textAlign: 'center', padding: '3.5rem 2rem' }}>
                <div style={{ display: 'inline-flex', padding: '1rem', borderRadius: '50%', background: 'var(--beige-200)', color: 'var(--accent-primary)', marginBottom: '1rem' }}>
                  <FolderOpen size={30} />
                </div>
                <h3 style={{ fontSize: '1.1rem', color: 'var(--text-main)', marginBottom: '0.4rem', fontWeight: 600 }}>Workspace Ready</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', maxWidth: '380px', margin: '0 auto', lineHeight: '1.5' }}>
                  Upload files to the repository on the left or enter a query above to start inspecting documents.
                </p>
              </div>
            )}

            {/* Query History */}
            {history.length > 1 && (
              <div style={{ marginTop: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Previous Queries:</span>
                <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', marginTop: '0.4rem' }}>
                  {history.map((item) => (
                    <button
                      key={item.id}
                      className={`history-button-chip ${item.id === activeResultId ? 'active' : ''}`}
                      onClick={() => setActiveResultId(item.id)}
                    >
                      {item.query.length > 35 ? `${item.query.slice(0, 35)}...` : item.query}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* Lightbox Modal for Full Size Image Viewing */}
      {lightboxImage && (
        <div className="lightbox-overlay" onClick={() => setLightboxImage(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-header">
              <span className="lightbox-title">{lightboxImage.filename}</span>
              <button className="icon-btn" onClick={() => setLightboxImage(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="lightbox-body">
              <img src={lightboxImage.url} alt={lightboxImage.filename} className="lightbox-img" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
