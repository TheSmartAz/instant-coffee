from app.services.scenario_detector import detect_scenario


def test_detect_scenario_ecommerce():
    result = detect_scenario("我要做一个电商网站，有商品和购物车")
    assert result.product_type == "ecommerce"
    assert result.confidence >= 0.5


def test_detect_scenario_travel():
    result = detect_scenario("旅行行程规划，包含行程和景点 itinerary")
    assert result.product_type == "travel"
    assert result.confidence >= 0.5


def test_detect_scenario_manual():
    result = detect_scenario("产品说明书 文档 手册")
    assert result.product_type == "manual"
    assert result.confidence >= 0.5


def test_detect_scenario_kanban():
    result = detect_scenario("团队看板任务管理 board task")
    assert result.product_type == "kanban"
    assert result.confidence >= 0.5


def test_detect_scenario_landing():
    result = detect_scenario("做一个落地页，带 hero 和 cta")
    assert result.product_type == "landing"
    assert result.confidence >= 0.5


def test_detect_scenario_fallback():
    result = detect_scenario("Just build a website")
    assert result.product_type == "unknown"
    assert result.confidence < 0.5
