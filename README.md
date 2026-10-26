# Requirement extraction from contract PDFs

A small Python tool that extracts requirements and wishes from PDFs with a text layer and prepares them in Excel for review by a system engineer. The language model (Claude Sonnet 5.5) finds and classifies the requirements; the code checks that every requirement text appears verbatim in the source and determines the page or page range itself.

Technical case Generative AI Engineer, Strukton. The full approach and its trade-offs are in [PLAN.md](PLAN.md). The tool's output (Excel, evaluation report, command-line messages) is in Dutch, like the source documents.

> **Status:** in progress. Steps 0 (scaffold) and 1 (PDF to text) are done; extraction and evaluation follow.

## Requirements

- [uv](https://docs.astral.sh/uv/) (downloads the right Python version, 3.15, by itself)
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

## Usage

Extract requirements from the PDFs and write them to Excel (follows in steps 2 to 4):

```bash
uv run eisen extract
```

Compare the output with the reference list (follows in step 5):

```bash
uv run eisen evaluate
```

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
| `output/` | Excel output, evaluation report and saved model responses |

## Time estimate

The assignment has a maximum of four hours. Each step was estimated in advance; the actual time per step was not recorded.

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

Follows after step 5.

## What's missing

Follows after step 6.

## AI usage

Follows after step 6.
