from __future__ import annotations

from sqlalchemy import select

from .database import Database
from .models import Page, PageVersion, ProductDoc, ProductDocStatus, Session, Version
from .utils import transaction_scope


def migrate_existing_sessions(database: Database | None = None) -> dict:
    counts = {
        "sessions": 0,
        "product_docs_created": 0,
        "pages_created": 0,
        "page_versions_created": 0,
    }
    with transaction_scope(database) as db_session:
        sessions = db_session.execute(select(Session)).scalars().all()
        counts["sessions"] = len(sessions)
        for session in sessions:
            product_doc = db_session.execute(
                select(ProductDoc).where(ProductDoc.session_id == session.id)
            ).scalar_one_or_none()
            if product_doc is None:
                db_session.add(
                    ProductDoc(
                        session_id=session.id,
                        status=ProductDocStatus.CONFIRMED,
                        content="",
                        structured={},
                    )
                )
                counts["product_docs_created"] += 1

            page = db_session.execute(
                select(Page).where(Page.session_id == session.id, Page.slug == "index")
            ).scalar_one_or_none()
            if page is None:
                page = Page(
                    session_id=session.id,
                    title="Home",
                    slug="index",
                    order_index=0,
                    description="",
                )
                db_session.add(page)
                db_session.flush()
                counts["pages_created"] += 1

            latest_version = db_session.execute(
                select(Version)
                .where(Version.session_id == session.id)
                .order_by(Version.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_version is None:
                continue

            page_version = db_session.execute(
                select(PageVersion).where(
                    PageVersion.page_id == page.id,
                    PageVersion.version == 1,
                )
            ).scalar_one_or_none()
            if page_version is None:
                page_version = PageVersion(
                    page_id=page.id,
                    version=1,
                    html=latest_version.html,
                    description=latest_version.description,
                )
                db_session.add(page_version)
                db_session.flush()
                counts["page_versions_created"] += 1

            if page.current_version_id != page_version.id:
                page.current_version_id = page_version.id
    return counts


__all__ = ["migrate_existing_sessions"]
