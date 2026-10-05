"""
Document processor — cleans and chunks raw text from OpenFDA labels and PubMed abstracts.
Medical text is dense, so we use a sentence-aware chunker with overlap.
"""
import re
import textwrap
from typing import Iterator

CHUNK_SIZE = 400      # characters per chunk (not tokens — faster, good enough)
CHUNK_OVERLAP = 80    # characters of overlap between adjacent chunks


def clean_text(text: str) -> str:
    """Remove HTML tags, excessive whitespace, and non-printable chars."""
    text = re.sub(r"<[^>]+>", " ", text)           # strip HTML
    text = re.sub(r"\s+", " ", text)                # collapse whitespace
    text = re.sub(r"[^\x20-\x7E\n]", "", text)     # strip non-ASCII
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks, breaking on sentence boundaries where possible.
    Returns a list of non-empty chunk strings.
    """
    text = clean_text(text)
    if len(text) <= chunk_size:
        return [text] if text else []

    # Split into sentences (crude but fast)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
                # Keep overlap from end of current chunk
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = (overlap_text + " " + sentence).strip()
            else:
                # Single sentence longer than chunk — hard split
                for i in range(0, len(sentence), chunk_size - overlap):
                    chunks.append(sentence[i:i + chunk_size])
                current = ""

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c) > 50]  # discard tiny fragments


def process_openfda_label(label: dict, drug_name: str) -> list[dict]:
    """
    Convert an OpenFDA drug label dict into a list of embeddable document dicts.
    Each section (indications, warnings, interactions, etc.) becomes its own chunk.
    """
    sections = {
        "indications_and_usage": "Indications and Usage",
        "contraindications": "Contraindications",
        "warnings": "Warnings",
        "drug_interactions": "Drug Interactions",
        "adverse_reactions": "Adverse Reactions",
        "precautions": "Precautions",
    }

    openfda = label.get("openfda", {})
    brand_names = openfda.get("brand_name", [])
    generic_names = openfda.get("generic_name", [])
    all_names = list({n.lower() for n in brand_names + generic_names + [drug_name]})

    documents = []
    for field, section_title in sections.items():
        raw = label.get(field, [])
        if not raw:
            continue
        text = " ".join(raw) if isinstance(raw, list) else str(raw)
        for i, chunk in enumerate(chunk_text(text)):
            documents.append({
                "id": f"openfda_{drug_name}_{field}_{i}",
                "text": f"{drug_name.title()} — {section_title}: {chunk}",
                "payload": {
                    "source": "OpenFDA",
                    "document_type": "drug_label",
                    "drug_names": all_names,
                    "title": f"{drug_name.title()} Drug Label — {section_title}",
                    "url": f"https://open.fda.gov/drugs/label/",
                    "source_id": label.get("id", ""),
                    "section": field,
                },
            })
    return documents


def process_pubmed_abstract(pmid: str, title: str, abstract: str, drug_names: list[str]) -> list[dict]:
    """Convert a PubMed abstract into embeddable document chunks."""
    full_text = f"{title}. {abstract}" if abstract else title
    documents = []
    for i, chunk in enumerate(chunk_text(full_text)):
        documents.append({
            "id": f"pubmed_{pmid}_{i}",
            "text": chunk,
            "payload": {
                "source": "PubMed",
                "document_type": "abstract",
                "drug_names": [d.lower() for d in drug_names],
                "title": title,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "source_id": pmid,
            },
        })
    return documents


def process_guideline(guideline: dict) -> list[dict]:
    """Convert a curated guideline dict into an embeddable document."""
    drug_names = [d.lower() for d in guideline.get("drugs", [])]
    text = f"{guideline['title']}: {guideline['guideline']}"
    return [{
        "id": f"guideline_{guideline['title'][:40].replace(' ', '_').lower()}",
        "text": text,
        "payload": {
            "source": guideline.get("source", "Clinical Guideline"),
            "document_type": "guideline",
            "drug_names": drug_names,
            "title": guideline["title"],
            "url": "",
            "source_id": "",
            "severity": guideline.get("severity", "moderate"),
        },
    }]
