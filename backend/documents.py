"""The policy wording and the claims manual, read one section at a time."""

import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException

DOCUMENT_PATHS = {
    "policy_wording": Path("data/policy_wording.md"),
    "claims_manual": Path("data/claims_manual.md"),
}
SECTION_HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)

Document = Literal["policy_wording", "claims_manual"]

router = APIRouter(prefix="/api/documents/{document}")


def sections(document: Document) -> dict[str, dict[str, str]]:
    """Split a document into its numbered sections, each with its title and text."""
    text = DOCUMENT_PATHS[document].read_text(encoding="utf-8")
    headings = list(SECTION_HEADING.finditer(text))
    ends = [heading.start() for heading in headings[1:]] + [len(text)]
    return {
        heading.group(1): {
            "title": heading.group(2),
            "text": text[heading.start() : end].strip(),
        }
        for heading, end in zip(headings, ends, strict=True)
    }


@router.get("", operation_id="get_document_contents")
def get_document_contents(document: Document) -> list[dict[str, str]]:
    """List a document's sections by number and title."""
    return [
        {"section": number, "title": section["title"]}
        for number, section in sections(document).items()
    ]


@router.get("/sections/{section}", operation_id="get_document_section")
def get_document_section(document: Document, section: str) -> dict[str, str]:
    """Get one section of a document in full."""
    found = sections(document)
    if section not in found:
        raise HTTPException(404, f"No section {section} in {document}")
    return {"document": document, "section": section, **found[section]}
