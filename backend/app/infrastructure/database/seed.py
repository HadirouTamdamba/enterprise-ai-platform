"""Idempotent seed: schema (dev), admin user, demo organization/workspace/project.

Run with: python -m app.infrastructure.database.seed
"""

import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.domain.entities.identity import Role
from app.infrastructure.database.models import (
    Base,
    OrganizationModel,
    ProjectModel,
    UserModel,
    WorkspaceModel,
)
from app.infrastructure.database.repositories.identity import (
    OrganizationRepository,
    UserRepository,
)
from app.infrastructure.database.session import get_engine, get_session_factory

logger = get_logger(__name__)


async def seed() -> None:
    settings = get_settings()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        users = UserRepository(session)
        orgs = OrganizationRepository(session)

        if await users.find_by_email(settings.admin_email):
            logger.info("seed_skipped", reason="admin already exists")
            return

        org = await orgs.find_by_slug("default")
        if org is None:
            org = await orgs.add(OrganizationModel(name="Default Organization", slug="default"))

        workspace = WorkspaceModel(name="Default Workspace", organization_id=org.id)
        session.add(workspace)
        await session.flush()

        project = ProjectModel(
            name="Getting Started",
            description="Demo project seeded at first startup",
            workspace_id=workspace.id,
        )
        session.add(project)

        admin = UserModel(
            email=settings.admin_email.lower(),
            full_name="Platform Administrator",
            hashed_password=hash_password(settings.admin_password),
            role=Role.PLATFORM_ADMIN.value,
            organization_id=org.id,
        )
        session.add(admin)
        await session.commit()
        logger.info("seed_completed", admin=settings.admin_email, project=str(project.id))


if __name__ == "__main__":
    configure_logging()
    asyncio.run(seed())
