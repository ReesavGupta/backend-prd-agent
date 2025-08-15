import os
from pathlib import Path
from typing import Any, List, Optional, Dict
from dotenv import load_dotenv
from langchain_nomic.embeddings import NomicEmbeddings
from langchain_groq import ChatGroq
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
import traceback

load_dotenv()
class CompleteRagService:
    """End-to-end RAG service with ingestion and retrieval pipelines."""

    def __init__(self, llm: Optional[ChatGroq], vectorstore: PineconeVectorStore, embedding_model: NomicEmbeddings) -> None:
        self.llm = llm
        self.vectorstore = vectorstore
        self.embedding_model = embedding_model

    # -----------------------
    # Ingestion pipeline
    # -----------------------
    def load_pdf(self, path: str) -> List[Document]:
        loader = PyPDFLoader(file_path=path)
        docs = loader.load()
        return docs

    def save_as_markdown(self, docs: List[Document], output_dir: str, base_name: Optional[str] = None) -> str:
        """Persist raw PDF pages as a single Markdown file for auditing or reuse.

        This is the basic/raw fallback path and will likely not preserve layout well.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        inferred_name = base_name
        if not inferred_name:
            if docs and docs[0].metadata.get("source"):
                inferred_name = Path(docs[0].metadata["source"]).stem
            else:
                inferred_name = "document"
        md_path = Path(output_dir) / f"{inferred_name}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            for i, doc in enumerate(docs, start=1):
                f.write(f"# Page {i}\n\n")
                f.write(doc.page_content)
                f.write("\n\n")
        return str(md_path)

    # -----------------------
    # High-fidelity PDF -> Markdown (primary): pymupdf4llm
    # -----------------------
    def pdf_to_markdown_pymupdf4llm(self, pdf_path: str, output_dir: str, base_name: Optional[str] = None) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        inferred_name = base_name or Path(pdf_path).stem
        md_path = Path(output_dir) / f"{inferred_name}.md"
        try:
            # Import within method so code runs even if dependency isn't installed for other users
            import pymupdf4llm
            md_text: str = pymupdf4llm.to_markdown(pdf_path)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            return str(md_path)
        except Exception as exc:
            print("[pymupdf4llm] Failed to convert PDF to Markdown. Falling back to raw save.")
            traceback.print_exc()
            # Fallback to raw PyPDF save
            docs = self.load_pdf(pdf_path)
            return self.save_as_markdown(docs, output_dir=output_dir, base_name=inferred_name)

    # -----------------------
    # Structured extraction via Unstructured (fallback)
    # -----------------------
    def pdf_to_markdown_unstructured(self, pdf_path: str, output_dir: str, base_name: Optional[str] = None) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        inferred_name = base_name or Path(pdf_path).stem
        md_path = Path(output_dir) / f"{inferred_name}.md"
        try:
            from unstructured.partition.pdf import partition_pdf
        except Exception:
            print("[unstructured] Library not available. Using raw PDF save instead.")
            docs = self.load_pdf(pdf_path)
            return self.save_as_markdown(docs, output_dir=output_dir, base_name=inferred_name)

        try:
            # Try hi_res strategy first as requested. If it fails, fall back to fast.
            try:
                elements = partition_pdf(filename=pdf_path, strategy="hi_res")
            except Exception:
                print("[unstructured] hi_res strategy failed. Falling back to fast strategy.")
                elements = partition_pdf(filename=pdf_path, strategy="fast")

            # Map elements to Markdown
            lines: List[str] = []
            for el in elements:
                el_type = el.category if hasattr(el, "category") else el.__class__.__name__
                text = (el.text or "").strip() if hasattr(el, "text") else str(el)
                if not text:
                    continue
                if el_type in {"Title", "Header", "Heading", "SectionHeader"}:
                    lines.append(f"# {text}\n")
                elif el_type in {"Subheader", "Subtitle", "Header2"}:
                    lines.append(f"## {text}\n")
                elif el_type in {"Header3"}:
                    lines.append(f"### {text}\n")
                elif el_type in {"ListItem", "BulletedText", "ListItemText"}:
                    # Normalize bullets to markdown '-'
                    for li in text.splitlines():
                        li = li.strip("•·- \t")
                        if li:
                            lines.append(f"- {li}")
                    lines.append("")
                elif el_type in {"Table"}:
                    # Best-effort: keep table text fenced to avoid losing structure
                    lines.append("\ntable")
                    lines.append(text)
                    lines.append("")
                else:
                    lines.append(text + "\n")

            md_text = "\n".join(lines).strip() + "\n"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            return str(md_path)
        except Exception:
            print("[unstructured] Failed to convert PDF to Markdown. Falling back to raw save.")
            traceback.print_exc()
            docs = self.load_pdf(pdf_path)
            return self.save_as_markdown(docs, output_dir=output_dir, base_name=inferred_name)

    # -----------------------
    # Markdown -> Documents (header-aware + size-controlled chunking)
    # -----------------------
    def markdown_to_chunks(self, md_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
        )
        md_docs = header_splitter.split_text(md_text)
        for d in md_docs:
            d.metadata["source"] = md_path

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.split_documents(md_docs)
        return chunks

    def split_docs(self, docs: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = splitter.split_documents(docs)
        return chunks

    def embed_docs(self, docs: List[Document], extra_metadata: Optional[Dict[str, Any]] = None) -> int:
        if not docs:
            return 0
        if extra_metadata:
            for d in docs:
                try:
                    d.metadata.update(extra_metadata)
                except Exception:
                    d.metadata = {**getattr(d, "metadata", {}), **extra_metadata}
        self.vectorstore.add_documents(docs)
        return len(docs)

    def ingest_pdf(self, pdf_path: str, markdown_dir: str = "ingested", chunk_size: int = 1000, chunk_overlap: int = 200, extra_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str | int]:
        engine = os.getenv("PDF_TO_MD_ENGINE", "pymupdf4llm").lower()
        if engine == "pymupdf4llm":
            md_path = self.pdf_to_markdown_pymupdf4llm(pdf_path, output_dir=markdown_dir, base_name=Path(pdf_path).stem)
        elif engine == "unstructured":
            md_path = self.pdf_to_markdown_unstructured(pdf_path, output_dir=markdown_dir, base_name=Path(pdf_path).stem)
        else:
            docs = self.load_pdf(pdf_path)
            md_path = self.save_as_markdown(docs, output_dir=markdown_dir, base_name=Path(pdf_path).stem)

        chunks = self.markdown_to_chunks(md_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        num_chunks = self.embed_docs(chunks, extra_metadata=extra_metadata)
        return {"pdf_path": pdf_path, "markdown_path": md_path, "num_chunks": num_chunks}

    # -----------------------
    # Retrieval pipeline
    # -----------------------
    def semantic_search(self, query: str, k: int = 5, fetch_k: int = 50, metadata_filter: Optional[Dict[str, Any]] = None) -> List[Document]:
        retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={ "k": k, "fetch_k": fetch_k, **({"filter": metadata_filter} if metadata_filter else {}) },
        )
        retrieved_docs = retriever.invoke(query)
        return retrieved_docs

    # -----------------------
    # Optional generation
    # -----------------------
    def generate_answer(self, query: str, context_docs: List[Document]) -> str:
        if self.llm is None:
            raise ValueError("LLM is not configured; cannot generate answer.")
        context = "\n\n".join([doc.page_content for doc in context_docs])
        prompt = (
            "Answer the question based strictly on the provided context.\n"
            "Be precise and concise. If unknown from context, say you don't know.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )
        result = self.llm.invoke(prompt)
        try:
            return result.content  # type: ignore[attr-defined]
        except Exception:
            return str(result)


if __name__ == "__main__":
    # Environment configuration
    GROQ_API_KEY = os.getenv("GROQ_KEY")
    NOMIC_API_KEY = os.getenv("NOMIC_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "rag-index")

    if not NOMIC_API_KEY:
        raise ValueError("NOMIC_KEY not set")
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_KEY not set")

    # LLM is optional for retrieval-only usage; enforce only if present
    llm: Optional[ChatGroq]
    if GROQ_API_KEY:
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=GROQ_API_KEY)
    else:
        llm = None

    embedding_model = NomicEmbeddings(nomic_api_key=NOMIC_API_KEY, model="nomic-embed-text-v1.5")

    pc = Pinecone(api_key=PINECONE_API_KEY)
    # Ensure index exists (Pinecone v3 SDK)
    try:
        existing_indexes = pc.list_indexes().names()  # type: ignore[attr-defined]
    except Exception:
        try:
            existing_indexes = [idx.name for idx in pc.list_indexes()]  # type: ignore[assignment]
        except Exception:
            existing_indexes = []
    if PINECONE_INDEX_NAME not in existing_indexes:
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    index = pc.Index(PINECONE_INDEX_NAME)
    vectorstore = PineconeVectorStore(embedding=embedding_model, index=index)
    rag = CompleteRagService(llm=llm, vectorstore=vectorstore, embedding_model=embedding_model)

    # Ingestion
    input_pdf = os.getenv("INPUT_PDF_PATH")
    if input_pdf and Path(input_pdf).exists():
        info = rag.ingest_pdf(pdf_path=input_pdf, markdown_dir="ingested")
        print(f"Ingested {info['num_chunks']} chunks → {info['markdown_path']}")
    else:
        print("No ingestion performed (set INPUT_PDF_PATH to ingest a PDF).")

    # Retrieval
    query = os.getenv("RAG_QUERY", "What is this document about?")
    retrieved = rag.semantic_search(query=query, k=5, fetch_k=50)
    print(f"Retrieved {len(retrieved)} chunks for query: {query}")

    # Optional generation if LLM configured
    if llm is not None and retrieved:
        answer = rag.generate_answer(query, retrieved)
        print("\nAnswer:\n")
        print(answer)
    elif llm is None:
        print("LLM not configured; retrieval-only mode.")
    else:
        print("No chunks retrieved to generate an answer.")