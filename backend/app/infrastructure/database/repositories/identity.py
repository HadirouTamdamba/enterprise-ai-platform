"""Repositories for identity & tenancy aggregates."""

from sqlalchemy import select

from app.infrastructure.database.models import (
    OrganizationModel,
    ProjectModel,
    UserModel,
    WorkspaceModel,
)
from app.infrastructure.database.repositories.base import BaseRepository


class UserRepository(BaseRepository[UserModel]):
    model = UserModel

    async def find_by_email(self, email: str) -> UserModel | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        )
        return result.scalar_one_or_none()


class OrganizationRepository(BaseRepository[OrganizationModel]):
    model = OrganizationModel

    async def find_by_slug(self, slug: str) -> OrganizationModel | None:
        result = await self.session.execute(
            select(OrganizationModel).where(OrganizationModel.slug == slug)
        )
        return result.scalar_one_or_none()


class WorkspaceRepository(BaseRepository[WorkspaceModel]):
    model = WorkspaceModel


class ProjectRepository(BaseRepository[ProjectModel]):
    model = ProjectModel
