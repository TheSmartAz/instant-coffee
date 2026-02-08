from app.services.product_doc import ProductDocService


def test_select_doc_tier_static_types():
    assert ProductDocService.select_doc_tier("landing", "complex") == "checklist"
    assert ProductDocService.select_doc_tier("card", "medium") == "checklist"
    assert ProductDocService.select_doc_tier("invitation", "simple") == "checklist"


def test_select_doc_tier_flow_by_complexity():
    assert ProductDocService.select_doc_tier("ecommerce", "simple") == "checklist"
    assert ProductDocService.select_doc_tier("ecommerce", "medium") == "standard"
    assert ProductDocService.select_doc_tier("ecommerce", "complex") == "extended"


def test_select_doc_tier_accepts_doc_tier_complexity_values():
    assert ProductDocService.select_doc_tier("booking", "checklist") == "checklist"
    assert ProductDocService.select_doc_tier("booking", "standard") == "standard"
    assert ProductDocService.select_doc_tier("booking", "extended") == "extended"


def test_select_doc_tier_override_takes_precedence():
    assert ProductDocService.select_doc_tier("landing", "simple", override="extended") == "extended"
