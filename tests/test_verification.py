import pytest
from conftest import DORPSSTRAAT, KOLKBRUG

from eisen.extraction import Candidate
from eisen.pdf_text import load_document
from eisen.verification import verify

LINDEBOMEN = "De bestaande lindebomen langs de Lindelaan (36 stuks, zie bijlage B) dienen behouden te blijven."
KROONPROJECTIE = (
    "Werkzaamheden binnen de kroonprojectie zijn uitsluitend toegestaan onder begeleiding "
    "van een gecertificeerd boomtechnisch adviseur."
)
SCHEEPVAART = (
    "De scheepvaart dient gedurende de uitvoering te allen tijde doorgang te hebben, met "
    "uitzondering van stremmingen die minimaal tien werkdagen vooraf zijn aangemeldt bij de "
    "vaarwegbeheerder en die niet langer duren dan 48 uur."
)


@pytest.fixture(scope="module")
def kolkbrug():
    return load_document(KOLKBRUG)


@pytest.fixture(scope="module")
def dorpsstraat():
    return load_document(DORPSSTRAAT)


def candidate(text, code=None, section="2", type="Bindend", doubt=False):
    return Candidate(code=code, text=text, section=section, type=type, doubt=doubt, reason="Test.")


def test_found_quote_carries_source_text_and_pages(dorpsstraat):
    # The model's line breaks and spacing differ from the PDF; the source wins.
    quote = LINDEBOMEN.replace(" (36 stuks", "\n(36  stuks")
    [proposal] = verify(dorpsstraat, [candidate(quote)])
    assert proposal.found and not proposal.needs_review
    assert proposal.text == LINDEBOMEN
    assert proposal.pages == "1"


def test_page_crossing_requirement_gets_full_range(dorpsstraat):
    text = (
        "Het kruispunt Dorpsstraat - Lindelaan dient te worden uitgevoerd als een verhoogd plateau "
        "met een hoogte van 12 centimeter en sinusvormige hellingen conform de CROW-richtlijn voor "
        "verkeersdrempels en -plateaus."
    )
    [proposal] = verify(dorpsstraat, [candidate(text, section="3.2")])
    assert proposal.pages == "1-2"


def test_corrected_typo_goes_to_review_with_closest_passage(kolkbrug):
    corrected = SCHEEPVAART.replace("aangemeldt", "aangemeld")
    [proposal] = verify(kolkbrug, [candidate(corrected, code="VS-3.2-01", section="3.2")])
    assert not proposal.found
    assert proposal.review_reason == "Eistekst niet letterlijk in het document gevonden"
    assert proposal.text == corrected  # shown as the model wrote it, next to the source
    assert "aangemeldt" in proposal.closest
    assert proposal.pages == ""


def test_invented_text_has_no_closest_passage(kolkbrug):
    [proposal] = verify(kolkbrug, [candidate("De aannemer levert drie gouden sleutels op.")])
    assert proposal.needs_review and proposal.closest is None


def test_doubtful_proposal_goes_to_review_even_when_found(dorpsstraat):
    [proposal] = verify(dorpsstraat, [candidate(LINDEBOMEN, doubt=True)])
    assert proposal.found
    assert proposal.review_reason == "Twijfelgeval volgens het model"


def test_source_code_is_kept_when_it_stands_on_the_same_page(kolkbrug):
    [proposal] = verify(kolkbrug, [candidate(SCHEEPVAART, code="VS-3.2-01", section="3.2")])
    assert (proposal.code, proposal.code_source) == ("VS-3.2-01", "bron")
    assert proposal.signals == []


def test_invented_code_is_replaced_by_a_derived_code(kolkbrug):
    [proposal] = verify(kolkbrug, [candidate(SCHEEPVAART, code="VS-9.9-99", section="3.2")])
    assert (proposal.code, proposal.code_source) == ("D01-3.2-01", "afgeleid")
    assert "Eiscode 'VS-9.9-99' van het model staat niet bij deze eis" in proposal.signals


def test_code_from_another_page_is_not_accepted(kolkbrug):
    # VS-1.1-01 exists, but on page 1; the requirement is on page 2.
    [proposal] = verify(kolkbrug, [candidate(SCHEEPVAART, code="VS-1.1-01", section="3.2")])
    assert proposal.code_source == "afgeleid"


def test_derived_codes_are_numbered_per_section(dorpsstraat):
    proposals = verify(
        dorpsstraat,
        [
            candidate(LINDEBOMEN, section="2"),
            candidate("Bij elke laadplaats wordt een laadpaal met een laadvermogen van minimaal 11 kW geplaatst.", section="3.3"),
            candidate(KROONPROJECTIE, section="2"),
        ],
    )
    assert [p.code for p in proposals] == ["D02-2-01", "D02-3.3-01", "D02-2-02"]


def test_derived_code_has_no_spaces(dorpsstraat):
    [proposal] = verify(dorpsstraat, [candidate(LINDEBOMEN, section="Bijlage B")])
    assert proposal.code == "D02-Bijlage_B-01"


def test_split_requirement_stays_as_two_proposals(dorpsstraat):
    proposals = verify(dorpsstraat, [candidate(LINDEBOMEN), candidate(KROONPROJECTIE)])
    assert [p.needs_review for p in proposals] == [False, False]
    assert all(p.signals == [] for p in proposals)


def test_duplicate_goes_to_review(dorpsstraat):
    first, second = verify(dorpsstraat, [candidate(LINDEBOMEN), candidate(LINDEBOMEN)])
    assert not first.needs_review
    assert second.review_reason == f"Dubbel voorstel: zelfde tekst als {first.code}"


def test_nested_proposal_goes_to_review(dorpsstraat):
    short, full = verify(
        dorpsstraat, [candidate("dienen behouden te blijven."), candidate(LINDEBOMEN)]
    )
    assert short.review_reason == f"Valt volledig binnen {full.code}"
    assert not full.needs_review


def test_doubtful_proposal_does_not_push_a_sound_one_off_the_main_sheet(dorpsstraat):
    whole = f"{LINDEBOMEN} {KROONPROJECTIE}"
    doubtful, sound = verify(dorpsstraat, [candidate(whole, doubt=True), candidate(LINDEBOMEN)])
    assert doubtful.needs_review
    assert not sound.needs_review


def test_partial_overlap_is_flagged_on_both(dorpsstraat):
    first, second = verify(
        dorpsstraat,
        [candidate(LINDEBOMEN), candidate("dienen behouden te blijven. Werkzaamheden binnen de kroonprojectie")],
    )
    assert not first.needs_review and not second.needs_review
    assert f"Overlapt gedeeltelijk met {second.code}" in first.signals
    assert f"Overlapt gedeeltelijk met {first.code}" in second.signals


def test_type_that_contradicts_cue_words_is_flagged(dorpsstraat):
    wish = "Bij voorkeur worden de hellingen van het plateau uitgevoerd in natuursteen, om aan te sluiten bij het materiaalgebruik in de historische kern."
    [wrong] = verify(dorpsstraat, [candidate(wish, type="Bindend", section="3.2")])
    [right] = verify(dorpsstraat, [candidate(wish, type="Wens", section="3.2")])
    assert any("bij voorkeur" in s for s in wrong.signals)
    assert not wrong.needs_review  # a signal, not a reason to move it
    assert right.signals == []


def test_wish_with_binding_word_is_flagged(dorpsstraat):
    [proposal] = verify(dorpsstraat, [candidate(LINDEBOMEN, type="Wens")])
    assert any("dienen" in s for s in proposal.signals)


def test_repeated_text_is_signalled(kolkbrug):
    [proposal] = verify(kolkbrug, [candidate("De Opdrachtnemer dient")])
    assert any("4 keer" in s for s in proposal.signals)
