import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import refresh_settings
from app.db.base import Base
from app.db.database import reset_database
from app.events.emitter import EventEmitter


@pytest.fixture()
def test_settings(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("MODEL_LIGHT", "test-light")
    monkeypatch.setenv("MODEL_MID", "test-mid")
    monkeypatch.setenv("MODEL_HEAVY", "test-heavy")
    reset_database()
    return refresh_settings()


@pytest.fixture()
def test_db(test_settings):
    engine = create_engine(
        test_settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def test_client(test_db, test_settings):
    from app.main import create_app
    from app.api import chat as chat_api

    app = create_app()

    def _override_get_db():
        yield test_db

    app.dependency_overrides[chat_api._get_db_session] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def event_emitter():
    return EventEmitter()


@pytest.fixture()
def output_dir(tmp_path):
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    return str(output)


@pytest.fixture()
def sample_png_base64():
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/"
        "5+hHgAHggJ/P9i2ZQAAAABJRU5ErkJggg=="
    )


@pytest.fixture()
def sample_style_reference_image(tmp_path, sample_png_base64):
    data = sample_png_base64.split(",", 1)[1]
    raw = base64.b64decode(data)
    path = tmp_path / "style-ref.png"
    path.write_bytes(raw)
    return path


@pytest.fixture()
def sample_ecommerce_images(tmp_path, sample_png_base64):
    data = sample_png_base64.split(",", 1)[1]
    raw = base64.b64decode(data)
    images = []
    for idx in range(2):
        path = tmp_path / f"product{idx + 1}.png"
        path.write_bytes(raw)
        images.append(path)
    return images
