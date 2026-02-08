import asyncio
from unittest.mock import AsyncMock

from app.agents.validator import AestheticValidator
from app.schemas.validation import AestheticScore, AutoChecks, DimensionScores


class TestAestheticScoringE2E:
    def _make_score(self, total: int) -> AestheticScore:
        if total >= 20:
            dims = DimensionScores(typography=4, contrast=4, layout=4, color=4, cta=4)
        else:
            dims = DimensionScores(typography=2, contrast=2, layout=2, color=2, cta=2)
        return AestheticScore(
            dimensions=dims,
            auto_checks=AutoChecks(wcag_contrast="pass", line_height="pass", type_scale="pass"),
        )

    def test_refiner_triggered_on_low_score(self, test_db, test_settings):
        validator = AestheticValidator(test_db, "e2e-aesthetic", test_settings)

        low_score = self._make_score(10)
        high_score = self._make_score(20)

        validator.scorer.score = AsyncMock(side_effect=[low_score, high_score])
        validator.style_refiner.refine = AsyncMock(return_value="<html>refined</html>")

        html, score, attempts = asyncio.run(
            validator.validate_and_refine(
                "<html>original</html>",
                product_type="landing",
            )
        )

        assert html == "<html>refined</html>"
        assert score.total >= 18
        assert len(attempts) == 2
        assert validator.style_refiner.refine.call_count == 1

    def test_max_two_refiner_iterations(self, test_db, test_settings):
        validator = AestheticValidator(test_db, "e2e-aesthetic-max", test_settings)

        low_score = self._make_score(10)
        validator.scorer.score = AsyncMock(side_effect=[low_score, low_score, low_score])
        validator.style_refiner.refine = AsyncMock(return_value="<html>refined</html>")

        html, score, attempts = asyncio.run(
            validator.validate_and_refine(
                "<html>original</html>",
                product_type="landing",
            )
        )

        assert len(attempts) == 3
        assert validator.style_refiner.refine.call_count == 2
        assert html
        assert score.total is not None
