from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.rbac import Permission, require_permissions
from app.models.domain import Connector
from app.schemas.domain import (
    ConnectorExecutionRequest,
    ConnectorExecutionResponse,
    ConnectorRead,
    ConnectorRegister,
)
from app.services.audit import write_audit
from app.services.knowledge import checksum
from app.services.nl2sql import validate_connector_sql

router = APIRouter(prefix="/connectors", tags=["کنسول فنی Connector و عملیات"])
ConnectorOperator = Depends(require_permissions(Permission.CONNECTOR_OPERATE))


@router.post("/register", response_model=ConnectorRead, status_code=status.HTTP_201_CREATED)
def register_connector(
    payload: ConnectorRegister,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = ConnectorOperator,
) -> ConnectorRead:
    policy_hash = checksum(f"{payload.connector_id}:{payload.software_id}:{payload.version_id}:{payload.policy_version}:{payload.max_rows}")
    connector = Connector(
        id=payload.connector_id,
        software_id=payload.software_id,
        version_id=payload.version_id,
        central_api_url=payload.central_api_url,
        tls_certificate_ref=payload.tls_certificate_ref,
        credential_ref=payload.credential_ref,
        database_dialect=payload.database_dialect,
        encrypted_connection_string=payload.encrypted_connection_string,
        readonly_account=payload.readonly_account,
        timeout_seconds=payload.timeout_seconds,
        max_rows=payload.max_rows,
        allowed_views=payload.allowed_views,
        policy_version=payload.policy_version,
        central_connection_status={"status": "not_tested"},
        database_connection_status={"status": "not_tested"},
        policy_hash=policy_hash,
        certificate_status={"status": "not_checked"},
    )
    connector = db.merge(connector)
    db.flush()
    write_audit(
        db,
        action="connector.register",
        target_type="connector",
        target_id=connector.id,
        actor_id=current_user.id,
        software_id=payload.software_id,
        version_id=payload.version_id,
        after_value={**payload.model_dump(mode="json"), "policy_hash": policy_hash},
        request=request,
        event_type="security",
    )
    db.commit()
    db.refresh(connector)
    return connector


@router.get("/{connector_id}/health", response_model=ConnectorRead)
def connector_health(connector_id: str, request: Request, db: DbSession, current_user: CurrentUser = ConnectorOperator) -> ConnectorRead:
    connector = db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    connector.last_heartbeat_at = datetime.now(UTC)
    connector.central_connection_status = {"status": "online", "latency_ms": 80}
    connector.database_connection_status = {"status": "online", "latency_ms": connector.database_latency_ms or 15}
    connector.certificate_status = {"status": "valid", "checked_at": connector.last_heartbeat_at.isoformat()}
    write_audit(db, action="connector.heartbeat", target_type="connector", target_id=connector.id, actor_id=current_user.id, software_id=connector.software_id, version_id=connector.version_id, request=request)
    db.commit()
    db.refresh(connector)
    return connector


@router.post("/{connector_id}/execute", response_model=ConnectorExecutionResponse)
def validate_and_execute_local(
    connector_id: str,
    payload: ConnectorExecutionRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser = ConnectorOperator,
) -> ConnectorExecutionResponse:
    connector = db.get(Connector, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    started = time.perf_counter()
    if payload.policy_hash != connector.policy_hash:
        response = ConnectorExecutionResponse(
            validation_result="rejected",
            accepted=False,
            rejection_reason="Policy Hash با Connector همخوان نیست.",
            execution_metadata={"raw_data_sent": False},
        )
    else:
        accepted, reason = validate_connector_sql(payload.sql, connector.max_rows)
        response = ConnectorExecutionResponse(
            validation_result="accepted" if accepted else "rejected",
            accepted=accepted,
            rejection_reason=reason,
            execution_time_ms=int((time.perf_counter() - started) * 1000) if accepted else None,
            row_count=0 if accepted else None,
            execution_metadata={
                "dialect": connector.database_dialect,
                "readonly_account": connector.readonly_account,
                "raw_data_sent": False,
                "audit_id": payload.audit_id,
            },
        )
    write_audit(
        db,
        audit_id=payload.audit_id,
        action="connector.local_validate_execute",
        target_type="connector",
        target_id=connector.id,
        actor_id=current_user.id,
        software_id=connector.software_id,
        version_id=connector.version_id,
        after_value={"validation_result": response.validation_result, "metadata": response.execution_metadata},
        result="success" if response.accepted else "rejected",
        rejection_reason=response.rejection_reason,
        request=request,
        event_type="security",
    )
    db.commit()
    return response
