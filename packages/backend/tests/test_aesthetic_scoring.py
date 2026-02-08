from __future__ import annotations

import asyncio

from app.agents.validator import AestheticValidator
from app.config import Settings
from app.schemas.validation import AestheticScore, AutoChecks, DimensionScores
from app.utils.validation import run_auto_checks


def _make_score(total: int) -> AestheticScore:
    base = max(1, min(5, total // 5))
    remainder = total - base * 5
    values = [base] * 5
    idx = 0
    while remainder > 0 and idx < 5:
        values[idx] = min(5, values[idx] + 1)
        remainder -= 1
        idx += 1
    dims = DimensionScores(
        typography=values[0],
        contrast=values[1],
        layout=values[2],
        color=values[3],
        cta=values[4],
    )
    auto_checks = AutoChecks(wcag_contrast="pass", line_height="pass", type_scale="pass")
    return AestheticScore(dimensions=dims, auto_checks=auto_checks)


def test_aesthetic_score_total_and_threshold() -> None:
    score = AestheticScore(
        dimensions=DimensionScores(typography=4, contrast=4, layout=4, color=3, cta=3),
        auto_checks=AutoChecks(wcag_contrast="pass", line_height="pass", type_scale="pass"),
    )
    assert score.total == 18
    assert score.passes_threshold is True


def test_auto_checks_pass() -> None:
    html = """
    <html>
      <head>
        <style>
          body { color: #111111; background: #ffffff; font-size: 16px; line-height: 1.5; }
          h1 { font-size: 32px; }
          button { font-size: 18px; }
        </style>
      </head>
      <body>
        <h1>Title</h1>
        <p>Body text</p>
        <button>CTA</button>
      </body>
    </html>
    """
    checks = run_auto_checks(html)
    assert checks.wcag_contrast == "pass"
    assert checks.line_height == "pass"
    assert checks.type_scale == "pass"


def test_auto_checks_contrast_fail() -> None:
    html = """
    <html>
      <head>
        <style>
          body { color: #888888; background: #888888; font-size: 16px; line-height: 1.5; }
          h1 { font-size: 28px; }
          button { font-size: 18px; }
        </style>
      </head>
      <body>
        <h1>Title</h1>
        <p>Body text</p>
        <button>CTA</button>
      </body>
    </html>
    """
    checks = run_auto_checks(html)
    assert checks.wcag_contrast == "fail"


def test_aesthetic_validator_comparison(monkeypatch) -> None:
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    validator = AestheticValidator(None, "session-1", settings)

    async def fake_score(html: str, *, product_type: str | None = None) -> AestheticScore:
        if html == "orig":
            return _make_score(15)
        if html == "ref1":
            return _make_score(17)
        return _make_score(16)

    async def fake_refine(html: str, *, score=None, product_type: str | None = None) -> str:
        if html == "orig":
            return "ref1"
        return "ref2"

    monkeypatch.setattr(validator.scorer, "score", fake_score)
    monkeypatch.setattr(validator.style_refiner, "refine", fake_refine)

    async def run():
        return await validator.validate_and_refine("orig", product_type="landing")

    final_html, final_score, attempts = asyncio.run(run())

    assert final_html == "ref1"
    assert final_score.total == 17
    assert [attempt.version for attempt in attempts] == [0, 1, 2]
