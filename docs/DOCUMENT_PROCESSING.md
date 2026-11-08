# DOCUMENT PROCESSING (`docs.py`)

## Accepted input
PDF (text-based), DOCX, TXT. Not supported: scans, photos, images, `.doc`, spreadsheets. Say so clearly in the UI and in API errors.

## Validation (`validate_upload(filename, data) -> ext`)
1. Extension must be `.pdf`, `.docx` or `.txt` (case-insensitive).
2. Size ≤ `MAX_UPLOAD_MB` MB, else `file_too_large`.
3. Magic bytes must match: PDF starts with `%PDF`; DOCX starts with `PK` (zip) and contains `word/document.xml`; TXT must decode as UTF-8 (fallback `utf-8-sig`, then `latin-1`). Mismatch gives `unsupported_type`.
4. Use a sanitized filename for display only; never use it as a path.

## Extraction (`extract_text(data, ext) -> ExtractResult`)
```python
@dataclass
class ExtractResult:
    text: str
    pages: int | None
    truncated: bool
    warnings: list[str]
```
- PDF: `pdfplumber.open(io.BytesIO(data))`; join page text with a marker `\n[Page n]\n`. Max 30 pages (set `truncated`, warn).
- DOCX: `docx.Document(io.BytesIO(data))`; include paragraphs and table cell text (rows joined with ` | `).
- Clean text: normalize line endings, collapse runs of blank lines, strip control characters.
- If extracted characters < 200 for a PDF: raise `scanned_pdf_unsupported`. If empty after cleaning: `empty_document`.
- Cap total text at 120,000 characters (set `truncated`).
- Work from memory (`BytesIO`); never write the upload to disk.

## Chunking (`chunk_text(text, size=3500, overlap=300) -> list[str]`)
- Split on paragraph boundaries; pack paragraphs up to `size` characters; when one paragraph exceeds `size`, split on sentence boundaries, then hard-split.
- Keep `overlap` characters from the previous chunk at the start of the next.
- Keep page markers inside chunks so quotes can be located.
- Short documents (≤ `LONG_DOC_CHAR_THRESHOLD`/2, about 6,000 chars) use a single call. Chunks keep prompts under free-tier per-minute token limits.

## Map-reduce flow
**Summary (`summary_service`)**
1. For each chunk: call the summary prompt, validate JSON, verify quotes against the **full document text**.
2. Merge by code: concatenate `parties`, `key_amounts`, `key_dates`, `key_clauses`, `red_flags`; dedupe by normalized quote (or normalized name for parties). `arbitration_clause`: found if found in any chunk; keep the first verified quote.
3. If more than one chunk: one merge call for `plain_summary` only. Otherwise use the chunk's `plain_summary`.
4. Fill `date_iso` with `parse_date`.
5. Store the summary on the document (the chat prompt later receives a compact version).

**Timeline (`timeline_service`)**
1. For each chunk of each selected document, and once for the user's chat messages: call the timeline prompt.
2. Parse dates, lower confidence for ambiguous dates, verify quotes against the right source text, drop failures (`dropped_unverified`).
3. Dedupe on `(date_iso or date_raw, normalized event text)`; if two items collide keep the one with higher confidence and set `source` to `both` only if both are present.
4. Sort by `date_iso`; items with no parseable date go to `undated` in document order.

## Rate-limit friendliness
- Process chunks sequentially. On `LLMRateLimited` wait 5 seconds and retry once; then return what was processed with flag `partial_result`.
- Cache per `(doc_id, task)` in the session so pressing a button twice costs nothing.

## Privacy
No persistence. Delete a document's text from memory when the session expires. Never include document text in logs or error messages.
