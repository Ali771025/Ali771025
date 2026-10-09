"""Policy-gated, allow-listed tools [TECH] (ARCHITECTURE §4.15).

Registry records metadata only. Arbitrary code is never accepted from HTTP/DB; every
executable handler is reviewed Python code in BUILTIN_HANDLERS.
"""
import ast
import math
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.runtime.models import ToolInvocation, ToolRegistration
from app.shared.errors import CONFLICT, NOT_FOUND, AppError


BUILTIN_SCHEMAS = {
    "text.word_count": {
        "description": "Count words and characters in supplied text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "maxLength": 4000}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"word_count": {"type": "integer"}, "char_count": {"type": "integer"}},
            "required": ["word_count", "char_count"],
            "additionalProperties": False,
        },
    },
    "math.calculate": {
        "description": "Evaluate a simple arithmetic expression without code execution.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "maxLength": 160}},
            "required": ["expression"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"value": {"type": "number"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    },
    "date.today": {
        "description": "Return the current UTC date.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {
            "type": "object",
            "properties": {"date": {"type": "string"}},
            "required": ["date"],
            "additionalProperties": False,
        },
    },
}


def _safe_calculate(expression: str) -> float:
    """Evaluate arithmetic only; names, attributes, calls and exponent bombs are rejected."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid arithmetic expression") from exc

    operators = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
    }

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            value = float(node.value)
            if not math.isfinite(value) or abs(value) > 1_000_000_000:
                raise ValueError("Number outside allowed range")
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, (ast.Mult, ast.Mod, ast.FloorDiv, ast.Div)) and abs(left) > 1e9:
                raise ValueError("Number outside allowed range")
            if abs(right) > 1e9:
                raise ValueError("Number outside allowed range")
            value = operators[type(node.op)](left, right)
            if not math.isfinite(value) or abs(value) > 1_000_000_000:
                raise ValueError("Result outside allowed range")
            return value
        raise ValueError("Only basic arithmetic is allowed")

    return visit(tree)


def _validate(value, schema: dict, path: str = "$", errors: list[str] | None = None) -> list[str]:
    errors = errors if errors is not None else []
    expected = schema.get("type")
    valid_type = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
    }
    if expected in valid_type and not valid_type[expected](value):
        errors.append(f"{path} must be {expected}")
        return errors

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key} is not allowed")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path} is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path} is too long")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} is above maximum")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} is not an allowed value")
    return errors


def _handler(name: str, data: dict) -> dict:
    if name == "text.word_count":
        text = data["text"]
        return {"word_count": len(text.split()), "char_count": len(text)}
    if name == "math.calculate":
        return {"value": _safe_calculate(data["expression"])}
    if name == "date.today":
        return {"date": datetime.now(timezone.utc).date().isoformat()}
    raise ValueError("No trusted handler is registered")


class ToolService:
    @staticmethod
    def ensure_builtins(db: Session) -> None:
        """Install safe read-only tools once. Admins can still narrow their allow-list."""
        for name, config in BUILTIN_SCHEMAS.items():
            if db.scalar(select(ToolRegistration).where(ToolRegistration.name == name)):
                continue
            db.add(ToolRegistration(
                name=name,
                description=config["description"],
                input_schema=config["input_schema"],
                output_schema=config["output_schema"],
                auth_requirement="none",
                risk_class="LOW",
                allowed_services=["*"],
                timeout_ms=1000,
                enabled=True,
            ))
        db.commit()

    @staticmethod
    def register(db: Session, data: dict, actor_id: int | None = None) -> ToolRegistration:
        name = data["name"]
        if name not in BUILTIN_SCHEMAS:
            raise AppError(CONFLICT, "Only platform-reviewed handlers can be registered", 409)
        row = db.scalar(select(ToolRegistration).where(ToolRegistration.name == name))
        if row is None:
            row = ToolRegistration(name=name)
            db.add(row)
        defaults = BUILTIN_SCHEMAS[name]
        row.description = data.get("description") or defaults["description"]
        row.input_schema = data.get("input_schema") or defaults["input_schema"]
        row.output_schema = data.get("output_schema") or defaults["output_schema"]
        row.auth_requirement = data.get("auth_requirement", "none")
        row.risk_class = data.get("risk_class", "LOW")
        row.allowed_services = data.get("allowed_services", [])
        row.timeout_ms = min(max(int(data.get("timeout_ms", 1000)), 50), 5000)
        row.enabled = bool(data.get("enabled", True))
        db.add(row)
        from app.shared.audit import record

        record(db, actor_id, "tool.registered", name, {"enabled": row.enabled, "risk_class": row.risk_class})
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_tools(db: Session) -> list[dict]:
        rows = db.scalars(select(ToolRegistration).order_by(ToolRegistration.name)).all()
        return [ToolService.serialize(row) for row in rows]

    @staticmethod
    def serialize(row: ToolRegistration) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "input_schema": row.input_schema,
            "output_schema": row.output_schema,
            "auth_requirement": row.auth_requirement,
            "risk_class": row.risk_class,
            "allowed_services": row.allowed_services,
            "timeout_ms": row.timeout_ms,
            "enabled": row.enabled,
        }

    @staticmethod
    def invocation_log(db: Session, limit: int = 50, session_id: int | None = None) -> list[dict]:
        query = select(ToolInvocation).order_by(ToolInvocation.id.desc()).limit(min(max(limit, 1), 200))
        if session_id is not None:
            query = query.where(ToolInvocation.session_id == session_id)
        return [
            {
                "id": row.id,
                "session_id": row.session_id,
                "tool_name": row.tool_name,
                "input": row.input or {},
                "output": row.output or {},
                "status": row.status,
                "latency_ms": row.latency_ms,
            }
            for row in db.scalars(query).all()
        ]

    @staticmethod
    def execute(
        db: Session,
        session_id: int,
        service_id: int,
        name: str,
        arguments: dict,
        granted_context: dict | None = None,
    ) -> dict:
        from app.modules.service.service import ServiceRegistry

        started = time.monotonic()
        row = db.scalar(select(ToolRegistration).where(ToolRegistration.name == name))
        status = "error"
        output: dict = {}
        reason = ""
        result: dict | None = None
        try:
            if row is None:
                status, reason = "denied", "Tool is not registered"
                return {"ok": False, "status": status, "error": reason}
            if not row.enabled:
                status, reason = "denied", "Tool is disabled"
                return {"ok": False, "status": status, "error": reason}
            allowlist = row.allowed_services or []
            if "*" not in allowlist and service_id not in allowlist and str(service_id) not in allowlist:
                status, reason = "denied", "Service is not allow-listed for this tool"
                return {"ok": False, "status": status, "error": reason}
            if row.auth_requirement != "none":
                grants = (granted_context or {}).get("tool_permissions", [])
                if name not in grants:
                    status, reason = "denied", "Explicit permission is required for this tool"
                    return {"ok": False, "status": status, "error": reason}
            service = ServiceRegistry.get(db, service_id)
            allowed_risk = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "RESTRICTED": 3}
            if allowed_risk.get(row.risk_class, 3) > allowed_risk.get(service.risk_level, 0):
                status, reason = "denied", "Tool risk exceeds the service risk allowance"
                return {"ok": False, "status": status, "error": reason}
            problems = _validate(arguments, row.input_schema or {})
            if problems:
                status, reason = "error", "; ".join(problems[:5])
                return {"ok": False, "status": status, "error": reason}
            result = _handler(name, arguments)
            latency_ms = int((time.monotonic() - started) * 1000)
            if latency_ms > row.timeout_ms:
                status, reason = "timeout", "Tool execution exceeded its time limit"
                return {"ok": False, "status": status, "error": reason}
            problems = _validate(result, row.output_schema or {})
            if problems:
                status, reason = "error", "Invalid tool result: " + "; ".join(problems[:5])
                return {"ok": False, "status": status, "error": reason}
            status = "ok"
            output = result
            return {"ok": True, "status": status, "result": result, "latency_ms": latency_ms}
        except Exception as exc:
            status, reason = "error", str(exc)[:240]
            return {"ok": False, "status": status, "error": reason}
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            db.add(ToolInvocation(
                session_id=session_id,
                tool_name=name[:80],
                input=arguments if isinstance(arguments, dict) else {},
                output=output or ({"error": reason[:240]} if reason else result or {}),
                status=status,
                latency_ms=latency_ms,
            ))
            from app.modules.runtime.service import RuntimeService

            RuntimeService.record_event(db, session_id, "tool_call", {
                "tool": name,
                "status": status,
                "latency_ms": latency_ms,
            })
