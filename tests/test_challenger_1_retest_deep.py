"""
Deep Adversarial Retest for Challenger 1 - Book Search Punctuation Delimiters
"""
import pytest
from services import book_service

def test_mandatory_retest_conditions():
    """Verify specific conditions demanded in dispatch mission."""
    alkimyogar_results = book_service.search_books('Alkimyogar!')
    assert len(alkimyogar_results) >= 1, f"Expected len >= 1, got {len(alkimyogar_results)}"
    
    otkan_results = book_service.get_catalog(query="«O'tkan kunlar»")['items']
    assert len(otkan_results) >= 1, f"Expected len >= 1, got {len(otkan_results)}"

@pytest.mark.parametrize("query", [
    "«O'tkan kunlar»",
    "\"O'tkan kunlar\"",
    "O'tkan kunlar!",
    "O'tkan kunlar?",
    "O'tkan kunlar.",
    "«Alkimyogar»",
    "Alkimyogar!",
    "(Alkimyogar)",
    "[Alkimyogar]",
    "{Alkimyogar}",
    "Alkimyogar?",
    "Alkimyogar...",
    "«O‘tkan kunlar»",
    "„O‘tkan kunlar“",
    "“Oʻtkan kunlar”",
    "Alkimyogar: Paulo",
    "Alkimyogar; Paulo",
    "Alkimyogar / Paulo",
    "Alkimyogar - Paulo",
    "Alkimyogar — Paulo",
    "Alkimyogar, Paulo",
    "*Alkimyogar*",
    "#Alkimyogar",
    "@Alkimyogar",
    "~Alkimyogar~",
    "_Alkimyogar_",
    "<Alkimyogar>",
    "|Alkimyogar|",
    "«O'tkan kunlar» - Abdulla Qodiriy",
    "Alkimyogar (Paulo Koelo)",
    "\"Alkimyogar\"!",
    "««Alkimyogar»»",
    "?!Alkimyogar!?",
])
def test_adversarial_punctuation_matrix(query):
    cat_res = book_service.get_catalog(query=query)
    assert cat_res["ok"] is True
    assert len(cat_res["items"]) >= 1, f"get_catalog failed for {query!r}"

    search_res = book_service.search_books(query)
    assert len(search_res) >= 1, f"search_books failed for {query!r}"
