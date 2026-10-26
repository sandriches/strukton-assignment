# Requirement extraction from contract PDFs

A small Python tool that extracts requirements and wishes from PDFs with a text layer and prepares them in Excel for review by a system engineer. The language model (Claude Sonnet 5.5) finds and classifies the requirements; the code checks that every requirement text appears verbatim in the source and determines the page or page range itself.

Technical case Generative AI Engineer, Strukton. The full approach and its trade-offs are in [PLAN.md](PLAN.md). The tool's output (Excel, evaluation report, command-line messages) is in Dutch, like the source documents.

> **Status:** in progress. Steps 0 (scaffold), 1 (PDF to text) and 2 (extraction with the language model) are done; verification, Excel output and evaluation follow.

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

### Keys in production

The API key in `.env` is meant for running this case locally. A production application in Azure should not hold a long-lived API key. Two options, neither of which changes the extraction code:

- **Workload identity federation:** the application proves its identity with a short-lived token from Microsoft Entra ID (for example an Azure managed identity), which the Anthropic SDK exchanges for a temporary access token. The SDK switches to this automatically when `ANTHROPIC_FEDERATION_RULE_ID`, `ANTHROPIC_ORGANIZATION_ID`, `ANTHROPIC_SERVICE_ACCOUNT_ID` and `ANTHROPIC_IDENTITY_TOKEN_FILE` are set. It needs a one-time setup by an Anthropic organisation admin (identity provider, federation rule, service account).
- **Claude via Microsoft Foundry:** call the model inside Strukton's own Azure tenant, which also settles data location and billing through Azure.

Note: an `ANTHROPIC_API_KEY` variable, even an empty one, takes priority over federation, so remove it from the environment when switching.

## Usage

Extract requirements from the PDFs in `data/` (writing them to Excel follows in steps 3 and 4):

```bash
uv run eisen extract
```

Each model response is saved in `output/responses/`. A rerun with the same model, prompt and document reads the saved response instead of calling the model, so it works without an API key and gives the same result. To call the model again anyway:

```bash
uv run eisen extract --refresh
```

You can also pass specific PDFs: `uv run eisen extract path/to/document.pdf`.

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
