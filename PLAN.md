# Plan: requirement extraction from contract PDFs

Technical case Generative AI Engineer, Strukton. This document records what we build, why, and which trade-offs we make deliberately. It was written before building and guides the four hours.

## Goal

A small Python tool that extracts requirements and wishes from PDFs with a text layer and writes them to Excel, ready for review by a system engineer. Per proposal: requirement code, verbatim requirement text, document, page (range), section and type (binding or wish). In addition, an evaluation against the reference list and a README that lets a colleague run the tool without help.

## Decisions made

| Topic | Choice |
|---|---|
| Language model | Claude Sonnet 5.5 (`claude-sonnet-5-5`) via the Anthropic API |
| Model call | One call per document with structured output (`messages.parse` with a pydantic schema), effort `high`, adaptive thinking (the model default). No `temperature`: the API rejects sampling parameters since 2026-10-21, so reproducibility comes from the saved responses. No server-side refusal fallback: it only retries cyber and AI-development declines, which don't apply to contract texts, and a silent switch to another model would muddy the evaluation. A refusal stops with a clear message instead. |
| Execution | Locally as a Python command; the model is called over the internet. No local model, nothing deployed. |
| Language | Everything code-related is in English: identifiers, comments, docstrings, config files, commit messages, the README and this plan. The tool's output is in Dutch, like the source PDFs: Excel sheets and columns, evaluation report, CLI help and messages. The prompt is in Dutch, matching the documents. |
| Python | 3.15, pinned in `.python-version`; uv downloads it, so no system Python is needed |
| Doubtful cases | On the *Te controleren* sheet, counted separately in the evaluation |
| PDF library | PyMuPDF: keeps table cells together (pdfplumber interleaves the columns of document 1 line by line). Pinned below 2.0: version 2.0 bundles an AI layout stack (onnxruntime, numpy, networkx) we don't need, and onnxruntime has no Python 3.15 build. |
| Dependencies | `uv` with a lockfile; `pymupdf`, `openpyxl`, `anthropic`, `pydantic`, `python-dotenv` (loads `.env`), `pytest` |

## What the documents test

| | Doc 1 Kolkbrug (14 reference items) | Doc 2 Dorpsstraat (13 reference items) |
|---|---|---|
| Layout | Tables with code, text, explanation, type, verification | Free prose, no codes, no type |
| Traps | The *Toelichting* column is explicitly not a requirement; the typo "aangemeldt" must be kept | Description of the current situation, the engineering firm's advice ("maakt geen deel uit van de eisen"), "De gemeente streeft ernaar …", bullet markers |
| Page boundary | Not in the reference | PvE-3.2-01 runs from page 1 to 2, with the running header in the middle of the sentence |
| Text layer | Clean | Justified text gives per-word line breaks; "DWG-⏎en" must not be de-hyphenated |

## Architecture: the model proposes, the code proves

```
PDF ──► page text + char→page index ──► LLM (whole document, JSON) ──► verification ──► Excel
        (deterministic)                  finds, classifies, quotes      (deterministic)
                                                                            │
                                              reference list ──► evaluation ◄┘
```

The model is only trusted to **find and classify**. Everything that must be verbatim or exact is decided by code:

- **Requirement text** comes from the source, not from the model. The model's quote is located in the source text (whitespace and Unicode form ignored). Found: the source passage goes to Excel. Not found: the proposal goes to *Te controleren*, with the closest source passage next to it.
- **Page (range)** follows from the matched passage, so a requirement across a page break automatically gets "1-2".
- **Requirement code** from the model is only accepted if it appears in the document on the same page(s) as the requirement; otherwise it is derived as `<documentprefix>-<section>-<sequence>`, for example `D02-3.3-01` (document 02, section 3.3, first item), numbered in document order.

### Excel layout (Dutch)

Written to `output/eisen_voorstellen.xlsx`.

- **Voorstellen**: Document, Eiscode, Codebron (bron/afgeleid), Eistekst, Pagina, Paragraaf, Type (Bindend/Wens), Signalering, Toelichting model, Beoordeling SE (empty dropdown: Goedgekeurd/Afgekeurd).
- **Te controleren**: the same plus Reden, Letterlijk gevonden (ja/nee) and Dichtstbijzijnde brontekst; quotes not found in the source, items the model marks as doubtful, duplicates and nested proposals.
- **Run-info**: one row per document: requested and serving model, effort, prompt file and checksum, when the response was made, the saved response file, proposal counts, percentage of quotes found verbatim, tokens, removed header/footer lines and pages without a text layer.

Requirement text is always written as text: a value starting with "=" is never interpreted as an Excel formula.

Placement rule: verification failed or the model is in doubt → *Te controleren*. Among the remaining proposals, an identical duplicate or a proposal that lies entirely within another → *Te controleren*, with the code of the other proposal; a partial overlap stays and is flagged on both. Disagreement between the model's type and cue words ("wenst", "bij voorkeur") → stays in *Voorstellen*, flagged in Signalering. Nothing the model proposes is silently dropped.

### Evaluation

Follows the scoring rules in the brief: verbatim text (whitespace, line breaks and Unicode normalisation ignored) plus the correct page or page range; splits allowed and reported separately. Per document:

- *Voorstellen*: found rate, incorrect proposals, duplicate proposals, splits.
- *Te controleren*: reported separately, with the number of items and how many match a reference item.

Choices made in the implementation:

- The evaluation reads the workbook, not the model responses: it scores what the system engineer receives and runs without a model connection. Text comparison reuses the normalisation of the source index, so extraction and evaluation compare the same way.
- A split counts when its parts cover the reference text in order without gaps, overlap or extra text, and their combined page range equals the reference's. A requirement split at a page break (part on page 1, part on page 2) therefore counts for a "1-2" item.
- A proposal matching an item that is already found is a duplicate; anything else that doesn't count is wrong, with the reason (wrong page, incomplete, extra text, not in the reference list).
- Type agreement with the reference is reported but doesn't count, as in the brief.
- The report (`output/evaluatie.md`) is Markdown without a timestamp, so it reads well on GitHub and only changes in git when the scores change.

## Steps

Each step ends with a review before the next one starts; the author makes the commits after reviewing.

| # | Step | Time | Review |
|---|---|---|---|
| 0 | Scaffold: git, uv project, folders (`data/`, `docs/`, `prompts/`, `src/`, `tests/`, `output/`), `.env.example`, `.gitignore` | 15m | Structure, dependencies |
| 1 | PDF to text: per page, generic header/footer removal (outermost lines whose text recurs at the same position on another page, digits masked, 2pt tolerance), index back to page and offset | 40m | Tests: header removed, page boundary gives "1-2", typo kept |
| 2 | Extraction with the model: versioned prompt, whole document with page markers, JSON schema, responses saved to `output/responses/` (key: model + effort + prompt + schema + document) | 50m | The prompt and the raw responses |
| 3 | Verification and enrichment: map quotes to source passages, page range, validate or derive codes, merge overlapping duplicates, cue-word type check | 40m | Tests on matching and rejection |
| 4 | Excel output with the three sheets | 25m | The Excel file itself |
| 5 | Evaluation against the reference list | 40m | Tests with synthetic cases, then the real scores |
| 6 | README, results, "What's missing", "AI usage" | 30m | Can a colleague run it without help? |

**Cut order if we overrun**: (1) cue-word type check, (2) dropdown in the review column, (3) evaluation edge-case tests. Verification, evaluation and the README are never cut.

## How this meets the brief

| The brief asks for | The plan delivers |
|---|---|
| Python tool with an LLM of choice | Python CLI with Claude Sonnet 5.5 behind one replaceable function |
| Requirements and wishes from both PDFs to Excel | Steps 2 to 4; one document-agnostic prompt for both table and prose |
| Code from the source or a traceable self-made one | Source code checked for presence; otherwise derived from document and section |
| Verbatim text, including typos | Text comes from the PDF, not from the model |
| Document, page (range), section | Page range computed from the matched passage |
| Type: binding or wish | Classification by the model plus a cue-word check |
| Doubtful cases, explanation, manual review | Signalering, Toelichting model, *Te controleren*, Beoordeling SE |
| Found rate per document, incorrect and duplicate proposals | Evaluation step following the scoring rules; *Te controleren* counted separately |
| Code, prompts, dependencies, Excel | Repo with `prompts/`, `pyproject.toml` + `uv.lock`, `output/` |
| README for a colleague | English README: install, key in `.env`, run, read the results |
| No keys or secrets | `.env` in `.gitignore`; `.env.example` describes what is needed |
| Four hours maximum, describe what is missing | Time box per step, cut order, "What's missing" section |
| Explain how AI tools were used and checked | "AI usage" section in the README |
| Explain results without a working model connection | Saved model responses, Excel and evaluation report in the repo |

| What they assess | The plan's answer |
|---|---|
| Preventing the model from rewriting, summarising or inventing | Text comes from the source; quotes not found are set aside, never presented as verbatim |
| Document structures, page boundaries, long requirements, doubtful cases | No layout-specific parsers, computed page range, *Te controleren* sheet |
| Noticing quality drops with another model or document type | The verbatim-match rate works on any document, even without a reference list; the evaluation is the regression test |
| Keys, data, configuration, handover | `.env`, lockfile, versioned prompts, Run-info |
| Deliberate choices within four hours | Small scope, omitted parts recorded explicitly |

## Trade-offs

What we deliberately don't do with this approach, and what it costs.

### Verification guards correctness, not completeness

The biggest trade-off. The code guarantees that every requirement text in *Voorstellen* really appears in the source, but not that all requirements were found. A requirement the model misses is invisible. We only measure completeness where a reference list exists. First improvement: a safety net that puts sentences containing "dient", "moet", "wordt", "wenst" or "bij voorkeur" that no proposal covers on *Te controleren*.

### What we don't use

| Not chosen | Why not | What it costs |
|---|---|---|
| Giving the PDF directly to the model (image or document input) | No control over text and pagination; verbatim text can't be proven | The model sees no layout cues (bold, table borders); we rely entirely on the text layer |
| Rules or regular expressions without a model | The brief asks for an LLM; rules don't generalise to unknown documents | Doc 1 would probably score perfectly with rules |
| Layout-specific parsers (table detection, Camelot) | Only work for a known layout | Table structure isn't used explicitly |
| Chunking, RAG, embeddings, vector database | Documents are three pages; the whole document gives context and solves page boundaries | Untested on long documents, where the approach hits context and attention limits |
| Frameworks (LangChain, LlamaIndex, LiteLLM, Instructor) | Small, readable code; one own function is enough | Other providers need their own adapter |
| Multiple passes, multi-model voting, model-as-judge | Time and simplicity | Completeness depends on one model call; a fresh run can turn out differently (saved responses keep results reproducible) |
| Automatic correction to the closest source text | A silent correction is a hidden rewrite | Small quoting mistakes by the model cost found rate; they land on *Te controleren* |
| OCR for scanned PDFs | Out of scope; the tool reports a missing text layer | Scanned documents aren't processed |
| Web UI, Azure deployment, database, authentication, Key Vault | The brief asks for a small tool; the final application is built elsewhere | Review happens in Excel; no multi-user workflow |
| Async or batched calls, prompt caching | Two documents, negligible cost | Doesn't scale efficiently to hundreds of documents |

### Other risks we accept

- **Section and type can't be proven the way the text can.** The section comes from the model and may be wrong (not scored, but visible). Type in doc 2 is an interpretation; the cue-word check only catches clear contradictions.
- **Derived codes depend on the section the model gives** and may differ between runs. Traceability remains through document, page and section.
- **Line breaks become spaces in the Excel text.** We treat line breaks in the PDF as layout, not content. A requirement spanning several paragraphs loses its paragraph structure.
- **Header/footer detection is a heuristic.** Running headers and footers are printed by the page template at the same spot on every page. A line is removed when its text (digits masked, so "Pagina 1" and "Pagina 2" match) recurs at the same vertical position on another page (within 2 points, for rounding) and it belongs to the outermost rows at the top or bottom of the page. There is no fixed margin, so headers are found wherever the template puts them. Body lines that recur on every page, such as doc 1's table header row and its "Bindend" type cells, are kept because they sit at different heights or have text above and below them. It misses headers that vary per page (such as the current chapter title, although a page number on the same row is still removed), does nothing on one-page documents, and could in theory remove a genuine line that happens to be outermost at the same height on two pages. A table that repeats its column header at the top of each page would have that row removed, which is harmless and keeps a page-crossing table row intact. It fails safely: a miss causes a verification failure, so the item lands on *Te controleren* rather than producing wrong text.
- **PyMuPDF is AGPL-licensed.** Fine for this case; before production, review the licence or switch to pdfplumber with table detection.
- **Documents are sent to an external API.** Fictional here; for real contracts, data processing and location must be arranged (for example via a provider within Strukton's own Azure environment).
- **A long-lived API key in `.env`.** Fine for running the case locally; workload identity federation (for example an Azure managed identity via Entra ID) would remove the long-lived secret, but needs Anthropic organisation admin setup and a workload identity, and makes local runs by a colleague harder. Production should use federation or Claude via Microsoft Foundry; see "Keys in production" in the README. The SDK already picks up federation from environment variables, so no code change is needed.
- **The evaluation set is small** (27 items, two documents). Scores are indicative, not statistically solid. We don't tune the prompt to the reference list's specific traps, to avoid overfitting.
- **The prompt and test documents are Dutch.** English-language documents are untested.

## Deliberately omitted, and what comes first

1. Completeness safety net (sentences with requirement words that no proposal covers).
2. Chunking by page window with overlap for long documents.
3. OCR for scanned PDFs (for example Azure Document Intelligence), with the same verification.
4. Comparing models with the evaluation, as a standard step when switching models.
5. Feeding the system engineer's approvals back as new evaluation data.
