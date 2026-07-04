"""Ingest DOCS_PATH into the Chroma vectorstore used by RAG_BACKEND=vector.

Chunks .md/.txt (and .pdf via PyMuPDF) files under DOCS_PATH, embeds each
chunk with the configured EMBEDDINGS_PROVIDER (local | hash | stub), and
upserts them into a persistent Chroma collection at VECTORSTORE_PATH.
Re-running is idempotent: chunk ids are derived from file path + offset.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Prefer ./docs as the corpus root by default
DOCS_PATH = os.getenv("DOCS_PATH", "./docs")


def extract_pdf_text(path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError(
            "PyMuPDF (pymupdf) is required for PDF ingestion. Install with `pip install pymupdf`."
        ) from e
    text_parts = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def chunk_text(text: str, size: int = 1000, overlap: int = 200):
    if size <= 0:
        yield 0, text
        return
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        yield start, text[start:end]
        if end == n:
            break
        start = max(0, end - overlap)


def iter_documents(docs_path: str):
    for root, _, files in os.walk(docs_path):
        for fn in sorted(files):
            path = os.path.join(root, fn)
            low = fn.lower()
            try:
                if low.endswith((".md", ".txt")):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        yield path, f.read()
                elif low.endswith(".pdf"):
                    yield path, extract_pdf_text(path)
            except Exception as e:
                print(f"skip {path}: {e}")


def main() -> int:
    from app.services.vector_retriever import get_collection, get_embedder

    docs_path = os.getenv("DOCS_PATH", DOCS_PATH)
    if not os.path.isdir(docs_path):
        raise SystemExit(f"Docs path not found: {docs_path}")

    embedder = get_embedder()
    collection = get_collection(create=True)

    ids, docs, metas = [], [], []
    for path, text in iter_documents(docs_path):
        rel = os.path.relpath(path, docs_path)
        for offset, chunk in chunk_text(text):
            if not chunk.strip():
                continue
            ids.append(f"{rel}:{offset}")
            docs.append(chunk)
            metas.append({"source": rel, "offset": offset})

    if not ids:
        print(f"No ingestible documents under {docs_path}")
        return 0

    batch = 64
    for i in range(0, len(ids), batch):
        j = i + batch
        collection.upsert(
            ids=ids[i:j],
            documents=docs[i:j],
            metadatas=metas[i:j],
            embeddings=embedder.embed(docs[i:j]),
        )
    print(
        f"Ingested {len(ids)} chunks from {docs_path} "
        f"into collection '{collection.name}' (count={collection.count()})"
    )
    return len(ids)


if __name__ == "__main__":
    main()
