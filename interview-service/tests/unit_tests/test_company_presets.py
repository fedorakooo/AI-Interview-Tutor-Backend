from src.services.company_presets import load_company_presets, preset_context


def test_load_company_presets_contains_amazon():
    presets = load_company_presets()
    assert "amazon_lp" in presets


def test_preset_context_unknown_returns_empty():
    assert preset_context(None) == ""
    assert preset_context("missing") == ""


def test_preset_context_renders_hints():
    text = preset_context("startup")
    assert "Startup" in text or "startup" in text.lower()
