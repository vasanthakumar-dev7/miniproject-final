import os
import json
import csv
from pathlib import Path
from typing import Dict, Any, List

class CustomParserPipeline:
    """
    Custom pipeline for text, code, markdown, and structured data files.
    Extracts structured content, code definitions (classes/functions),
    and metadata for indexing.
    """

    @staticmethod
    def is_code_file(filename: str) -> bool:
        code_exts = {'.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json',
                     '.yaml', '.yml', '.xml', '.sql', '.cpp', '.c', '.java', '.go',
                     '.rs', '.sh', '.bat', '.ps1'}
        return Path(filename).suffix.lower() in code_exts

    @staticmethod
    def is_text_file(filename: str) -> bool:
        text_exts = {'.txt', '.md', '.markdown', '.rst', '.log', '.csv', '.tsv'}
        return Path(filename).suffix.lower() in text_exts

    @classmethod
    def parse_file(cls, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        ext = path.suffix.lower()
        filename = path.name

        if not path.exists():
            return {"error": f"File not found: {file_path}", "filename": filename}

        file_size = path.stat().st_size

        if ext == '.csv':
            return cls._parse_csv(path)
        elif ext == '.json':
            return cls._parse_json(path)
        elif cls.is_code_file(filename):
            return cls._parse_code(path)
        else:
            return cls._parse_text(path)

    @classmethod
    def _parse_text(cls, path: Path) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            lines = content.splitlines()
            return {
                "type": "text",
                "filename": path.name,
                "extension": path.suffix.lower(),
                "line_count": len(lines),
                "word_count": len(content.split()),
                "preview": content[:1000],
                "content": content
            }
        except Exception as e:
            return {"type": "text", "filename": path.name, "error": str(e), "content": ""}

    @classmethod
    def _parse_csv(cls, path: Path) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                rows = list(reader)

            headers = rows[0] if rows else []
            row_count = max(0, len(rows) - 1)
            sample_rows = rows[:6]

            summary_text = f"CSV File with {row_count} rows and columns: {', '.join(headers)}.\n"
            summary_text += "Sample data:\n"
            for r in sample_rows:
                summary_text += " | ".join(r) + "\n"

            return {
                "type": "structured_data",
                "subtype": "csv",
                "filename": path.name,
                "columns": headers,
                "row_count": row_count,
                "preview": summary_text,
                "content": summary_text
            }
        except Exception as e:
            return {"type": "structured_data", "filename": path.name, "error": str(e), "content": ""}

    @classmethod
    def _parse_json(cls, path: Path) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)

            if isinstance(data, list):
                summary = f"JSON Array containing {len(data)} items."
            elif isinstance(data, dict):
                summary = f"JSON Object with keys: {', '.join(list(data.keys())[:20])}."
            else:
                summary = "JSON Primitive Data"

            content_str = json.dumps(data, indent=2)[:3000]
            return {
                "type": "structured_data",
                "subtype": "json",
                "filename": path.name,
                "summary": summary,
                "preview": content_str,
                "content": content_str
            }
        except Exception as e:
            return {"type": "structured_data", "filename": path.name, "error": str(e), "content": ""}

    @classmethod
    def _parse_code(cls, path: Path) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                code = f.read()

            lines = code.splitlines()
            symbols = []

            # Extract basic functions and classes
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("function ") or "const " in stripped and "=>" in stripped:
                    symbols.append(stripped[:80])

            summary = f"Code file ({path.suffix}) with {len(lines)} lines. Defined structures: {len(symbols)} definitions."
            return {
                "type": "code",
                "filename": path.name,
                "extension": path.suffix.lower(),
                "line_count": len(lines),
                "symbols": symbols[:30],
                "preview": code[:1500],
                "content": code
            }
        except Exception as e:
            return {"type": "code", "filename": path.name, "error": str(e), "content": ""}
