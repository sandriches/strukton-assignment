"""Command-line entry point: `eisen extract` and `eisen evaluate`.

Everything printed here is read by the user, so it is in Dutch.
"""

import argparse
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from eisen import evaluation
from eisen.excel import DocumentResult, write_workbook
from eisen.extraction import DEFAULT_MODEL, ExtractionError, extract
from eisen.pdf_text import load_document
from eisen.verification import verify

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
WORKBOOK = OUTPUT_DIR / "eisen_voorstellen.xlsx"
REFERENCE = DATA_DIR / "Referentielijst_oefendocumenten.xlsx"
REPORT = OUTPUT_DIR / "evaluatie.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eisen",
        description="Haalt eisen en wensen uit contract-pdf's en zet ze klaar in Excel.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract_cmd = sub.add_parser("extract", help="Eisen uit de pdf's halen en naar Excel schrijven.")
    extract_cmd.add_argument(
        "pdfs",
        nargs="*",
        type=Path,
        help=f"Te verwerken pdf's (standaard: alle pdf's in {DATA_DIR}/).",
    )
    extract_cmd.add_argument(
        "--refresh",
        action="store_true",
        help="Het model opnieuw aanroepen, ook als er een opgeslagen antwoord is.",
    )

    sub.add_parser("evaluate", help="Excel-uitvoer vergelijken met de referentielijst.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv()
    if args.command == "extract":
        return run_extract(args.pdfs or sorted(DATA_DIR.glob("*.pdf")), refresh=args.refresh)
    return run_evaluate(WORKBOOK, REFERENCE, REPORT)


def run_extract(pdfs: list[Path], refresh: bool = False) -> int:
    if not pdfs:
        print(f"Geen pdf's gevonden in {DATA_DIR}/.", file=sys.stderr)
        return 1

    model = os.environ.get("EISEN_MODEL") or DEFAULT_MODEL
    failed = False
    results = []
    for pdf in pdfs:
        doc = load_document(pdf)
        if len(doc.pages_without_text) == len(doc.pages):
            print(f"{doc.name}: geen tekstlaag gevonden (gescande pdf?); overgeslagen.", file=sys.stderr)
            failed = True
            continue
        if doc.pages_without_text:
            pages = ", ".join(map(str, doc.pages_without_text))
            print(f"{doc.name}: let op, pagina {pages} zonder tekstlaag wordt overgeslagen.", file=sys.stderr)

        try:
            result = extract(doc, OUTPUT_DIR / "responses", model=model, refresh=refresh)
        except (ExtractionError, anthropic.AnthropicError) as error:
            print(f"{doc.name}: {_describe(error)}", file=sys.stderr)
            failed = True
            continue

        proposals = verify(doc, result.candidates)
        results.append(DocumentResult(doc, result, proposals))
        found = sum(p.found for p in proposals)
        review = sum(p.needs_review for p in proposals)
        source = "opgeslagen antwoord" if result.from_cache else f"nieuw antwoord van {result.meta['model_served']}"
        print(f"{doc.name} ({source}, {result.path})")
        print(f"  {len(proposals)} voorstellen, waarvan {found} letterlijk in het document gevonden")
        print(f"  {len(proposals) - review} op tabblad Voorstellen, {review} op tabblad Te controleren")

    if results:
        try:
            write_workbook(WORKBOOK, results)
        except PermissionError:
            print(f"Kan {WORKBOOK} niet opslaan; is het bestand nog geopend in Excel?", file=sys.stderr)
            return 1
        print(f"Excel-bestand opgeslagen: {WORKBOOK}")
    return 1 if failed else 0


def run_evaluate(workbook: Path, reference: Path, report: Path) -> int:
    if not workbook.exists():
        print(f"{workbook} bestaat niet; draai eerst 'eisen extract'.", file=sys.stderr)
        return 1
    if not reference.exists():
        print(f"Referentielijst {reference} niet gevonden.", file=sys.stderr)
        return 1

    references = evaluation.load_reference(reference)
    documents, rows = evaluation.load_output(workbook)
    scores, skipped = [], []
    for document in documents:
        items = references.get(evaluation.document_number(document))
        if items is None:
            skipped.append(f"{document} (geen referentielijst)")
            continue
        scores.append(evaluation.score(document, items, rows))
    evaluated = {evaluation.document_number(s.document) for s in scores}
    skipped += [f"referentielijst Doc {n} (document niet in de uitvoer)" for n in sorted(references) if n not in evaluated]

    for s in scores:
        print(evaluation.summary_line(s))
    for item in skipped:
        print(f"Niet geëvalueerd: {item}", file=sys.stderr)
    evaluation.write_report(report, scores, workbook, reference, skipped)
    print(f"Rapport opgeslagen: {report}")
    return 0


def _describe(error: Exception) -> str:
    if isinstance(error, ExtractionError):
        return str(error)
    if isinstance(error, anthropic.AuthenticationError):
        return "de API-sleutel is ongeldig. Controleer ANTHROPIC_API_KEY in .env."
    if isinstance(error, anthropic.RateLimitError):
        return "te veel verzoeken aan de API; probeer het over een minuut opnieuw."
    if isinstance(error, anthropic.APIStatusError):
        return f"fout van de API ({error.status_code}): {error.message}"
    if isinstance(error, anthropic.APIConnectionError):
        return "geen verbinding met de API. Controleer de internetverbinding."
    return f"het model kon niet worden aangeroepen ({error}). Staat ANTHROPIC_API_KEY in .env?"
