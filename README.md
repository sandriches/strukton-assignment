# Requirement extraction from contract PDFs

A small Python tool that extracts requirements and wishes from PDFs with a text layer and prepares them in Excel for review by a system engineer. The language model (Claude Sonnet 5.5) finds and classifies the requirements; the code checks that every requirement text appears verbatim in the source and determines the page or page range itself.

Technical case Generative AI Engineer, Strukton. The approach and its trade-offs were planned before any code was written. The tool's output (Excel, evaluation report, command-line messages) is in Dutch, like the source documents.

> **Status:** complete - see [Results](#results) for the scores and [What's missing](#whats-missing) for what a production version needs.

## Requirements

- [uv](https://docs.astral.sh/uv/), which downloads the right Python version (3.15) by itself. Tested with uv 0.13.5; older versions may not know Python 3.15 yet. Update with `uv self update`, or `brew upgrade uv` if you installed it with Homebrew.
- An Anthropic API key, only needed to run the extraction again. Tests, evaluation and the existing output work without a key.

## Installation

```bash
uv sync
```

```bash
cp .env.example .env
```

Then fill in your own `ANTHROPIC_API_KEY` in `.env`. The `.env` file is listed in `.gitignore` and is never committed.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes, for extraction | Key for the Anthropic API |
| `EISEN_MODEL` | No | Use a different model; default `claude-sonnet-5-5` |

### Keys in production

The API key in `.env` is meant for running this case locally. A production application in Azure should not hold a long-lived API key. Two options, neither of which changes the extraction code:

- **Workload identity federation:** the application proves its identity with a short-lived token from Microsoft Entra ID (for example an Azure managed identity), which the Anthropic SDK exchanges for a temporary access token. The SDK switches to this automatically when `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`, `ANTHROPIC_SERVICE_ACCOUNT_ID` and `ANTHROPIC_IDENTITY_TOKEN_FILE` are set. It needs a one-time setup by an Anthropic organisation admin (identity provider, federation rule, service account).
- **Claude via Microsoft Foundry:** call the model inside Strukton's own Azure tenant, which also settles data location and billing through Azure.

Note: an `ANTHROPIC_API_KEY` variable, even an empty one, takes priority over federation, so remove it from the environment when switching.

## Usage

Extract requirements from the PDFs in `data/`, check every quote against the source and write the result to `output/eisen_voorstellen.xlsx`:

```bash
uv run eisen extract
```

The workbook has three sheets (in Dutch, like the documents):

| Sheet | Contents |
|---|---|
| Voorstellen | Proposals whose text was found verbatim in the PDF: code, text, page (range), section, type, signals, the model's explanation, and an empty *Beoordeling SE* column with a dropdown for the system engineer |
| Te controleren | Proposals that need a human decision, with the reason: text not found verbatim (shown next to the closest source passage), marked as doubtful by the model, duplicate, or contained in another proposal |
| Run-info | Per document: which model and prompt produced the output, when, how many quotes were found verbatim, and which header/footer lines were removed |

Each model response is saved in `output/responses/`. A rerun with the same model, prompt and document reads the saved response instead of calling the model, so it works without an API key and gives the same result. To call the model again anyway:

```bash
uv run eisen extract --refresh
```

You can also pass specific PDFs: `uv run eisen extract path/to/document.pdf`.

Compare the workbook with the reference list in `data/` and write the report to `output/evaluatie.md`:

```bash
uv run eisen evaluate
```

The evaluation reads the workbook, so it needs no API key. It follows the scoring rules of the assignment:

- A reference item is found when a proposal on *Voorstellen* has the same text and the same document and page (range). Whitespace, line breaks and Unicode form are ignored; section, code and type don't count.
- Several proposals count together as one found item when they cover its full text in order, add nothing, and together have the same page range. These splits are listed separately.
- Every other proposal on *Voorstellen* is a duplicate or wrong (*onterecht*), with the reason, such as the wrong page or only part of a requirement.
- *Te controleren* doesn't count towards the found rate; the report says how many of its rows are reference items.

Run the tests:

```bash
uv run pytest
```

## Folder structure

| Folder | Contents |
|---|---|
| `data/` | The two source PDFs and the reference list |
| `docs/` | The assignment brief |
| `prompts/` | Versioned prompts for the language model |
| `src/eisen/` | Source code |
| `tests/` | Tests; run without a model connection |
| `output/` | Excel output (`eisen_voorstellen.xlsx`), evaluation report (`evaluatie.md`) and saved model responses (`responses/`) |

## Time estimate

The assignment has a maximum of four hours. Each step was estimated in advance; the actual time per step was not recorded. The estimate includes code generation, usage and review.

| # | Step | Estimate |
|---|---|---|
| 0 | Scaffold: git, uv project, folders, `.env.example`, `.gitignore` | 15 min |
| 1 | PDF to text: per page, remove headers and footers, index back to the page | 40 min |
| 2 | Extraction with the language model: prompt, JSON schema, saved responses | 50 min |
| 3 | Verification and enrichment: map quotes to the source, page range, requirement codes, duplicates, type check | 40 min |
| 4 | Excel output with the sheets Voorstellen, Te controleren and Run-info | 25 min |
| 5 | Evaluation against the reference list | 40 min |
| 6 | README, results, what's missing, AI usage | 30 min |
| | **Total** | **4 hours** |

## Results

With Claude Sonnet 5.5, prompt `extract_v1.md` and the saved responses in `output/responses/` (details per item in [output/evaluatie.md](output/evaluatie.md)):

| Document | Found | Wrong | Duplicates | Splits | Type as in reference | *Te controleren* (of which reference items) |
|---|---|---|---|---|---|---|
| 01 Vraagspecificatie Kolkbrug | 14/14 (100%) | 0 | 0 | 0 | 14/14 | 2 (0) |
| 02 Programma van Eisen Dorpsstraat | 13/13 (100%) | 0 | 0 | 1 | 13/13 | 2 (0) |

- All 32 quotes from the model were found verbatim in the source.
- The split is PvE-2-02: the model proposed its two sentences (the lime trees and the crown projection) separately. Together they cover the item exactly, on the same page.
- The four rows on *Te controleren* are sentences the model itself marked as doubtful; none is in the reference list. The system engineer decides on them.
- The reference list has 27 items in two documents, so these scores are indicative. The prompt was not tuned to this list.

## What's missing

The scope was kept small on purpose to fit in four hours. What's missing, roughly in the order it should be added:

**Quality**

1. **A completeness check.** The code proves that every text on *Voorstellen* is in the source, but not that every requirement was found. Without a reference list, a requirement the model skips is invisible. First step: put sentences with requirement words ("dient", "moet", "wenst", "bij voorkeur") that no proposal covers on *Te controleren*.
2. **A larger evaluation set.** 27 items in two short documents make the scores indicative, not reliable. The *Beoordeling SE* column could feed approved proposals back as new reference data. The evaluation should run on every prompt or model change, for example in CI with a minimum found rate.
3. **Stable derived codes.** Codes like `D02-3.3-01` are numbered within one run, so a different model response can renumber them. In production a code should be fixed once a requirement is approved.
4. **Section and type are the model's judgement.** The text and page are proven by code; the section isn't checked and isn't scored, and the type check only catches clear contradictions with cue words.

**Documents**

5. **Long documents.** Each document goes to the model in one call. A document with many requirements can hit the output limit; the tool then stops with a message instead of returning half a list. Larger documents need splitting by page window with overlap, still verified against the full text.
6. **Scanned PDFs.** These are detected and skipped. OCR (for example Azure Document Intelligence) would come first, with the same verification against the OCR text.
7. **Other layouts and languages.** Only two Dutch documents were tested. Header and footer removal is a heuristic, and line breaks inside a requirement become spaces.

**Production in Azure**

8. **No deployment.** There is no upload screen, storage, or shared review workflow; the review happens in Excel.
9. **Keys.** The long-lived API key in `.env` should become workload identity federation or Claude via Microsoft Foundry (see [Keys in production](#keys-in-production)).
10. **Data.** Documents are sent to the Anthropic API. For real contracts, data processing and data location must be arranged first.
11. **Licence.** PyMuPDF is AGPL-licensed; review this before production use, or switch libraries.
12. **Operations.** Run-info records model, prompt and token use per document, but there is no central logging, monitoring or cost tracking, and no batching or prompt caching for large volumes.

## AI usage

**In the tool.** Claude Sonnet 5.5 finds the requirements and classifies them; it does not decide the text, page or code. The prompt is versioned in [prompts/extract_v1.md](prompts/extract_v1.md) and its hash is recorded on Run-info. The prompt was written from the brief and the documents, not tuned to the traps in the reference list.

**Building the tool.** The code, tests and documentation were written with Claude Code (Claude Opus 5.5) as a pair programmer:

- **Plan first.** The brief and documents were analysed and the approach agreed in a plan before any code was written. Decisions such as the language rule, the *Te controleren* sheet for doubtful cases and the position-based header removal were made by the author.
- **Step by step.** Each step was reviewed before the next one started, and the author made every commit.
- **Checked, not trusted.** Every step has tests, including tests on the real PDFs: all 27 reference texts are located exactly once, on their reference pages, independently of the model. The Excel output was opened and read, the live model run was checked, and the evaluation scores the end result.

The manual checks modified the AI's proposals several times, including:

- pdfplumber mixed up the table columns of document 1, so PyMuPDF was chosen.
- A fixed margin band for headers and footers was replaced by the position-based rule.
- PyMuPDF 2.0 pulled in a dependency without a Python 3.15 build, so it is pinned below 2.0.
- A first version of the verification let a doubtful proposal push a sound one to *Te controleren*; it was rewritten.
- The claim that a rerun gives an identical Excel file turned out to be false (openpyxl stores the save time), and was corrected.

The API key was put in `.env` by the author. That file is ignored by git, so no key is in the repository.
