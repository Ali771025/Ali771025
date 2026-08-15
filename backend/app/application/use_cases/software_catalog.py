from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.common.context import ActorContext
from app.application.common.exceptions import ConflictError, NotFoundError
from app.application.ports.unit_of_work import UnitOfWorkPort
from app.services.knowledge import checksum


@dataclass(slots=True)
class CreateSoftwareUseCase:
    uow: UnitOfWorkPort

    def execute(self, data: dict[str, Any], actor: ActorContext) -> Any:
        if self.uow.software.code_exists(data["code"]):
            raise ConflictError(
                code="SOFTWARE_CODE_EXISTS",
                message="کد یکتای نرم‌افزار قبلاً ثبت شده است.",
                details={"code": data["code"]},
            )
        product = self.uow.software.add_product(data)
        self.uow.audit.record(
            actor=actor,
            action="software.create",
            target_type="software",
            target_id=product.id,
            tenant_id=data.get("tenant_id"),
            after_value=data,
        )
        self.uow.commit()
        return product


@dataclass(slots=True)
class CreateVersionUseCase:
    uow: UnitOfWorkPort

    def execute(self, data: dict[str, Any], actor: ActorContext) -> Any:
        software_id = data["software_id"]
        if not self.uow.software.get_product(software_id):
            raise NotFoundError(
                code="SOFTWARE_NOT_FOUND",
                message="نرم‌افزار برای ثبت نسخه یافت نشد.",
                details={"software_id": software_id},
            )
        version_hash = checksum(f"{software_id}:{data['version_number']}")
        version = self.uow.software.add_version(data, version_hash=version_hash)
        self.uow.audit.record(
            actor=actor,
            action="software.version_create",
            target_type="software_version",
            target_id=version.id,
            software_id=software_id,
            after_value={**data, "version_hash": version_hash},
        )
        self.uow.commit()
        return version
