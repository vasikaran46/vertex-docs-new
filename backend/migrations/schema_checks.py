"""Read-only validation for the pre-migration ActivityLog table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect, text


def _normalized_default(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    while result.startswith("(") and result.endswith(")"):
        result = result[1:-1].strip()
    if "::" in result:
        result = result.split("::", 1)[0].strip()
    if len(result) >= 2 and result[0] == result[-1] == "'":
        result = result[1:-1].replace("''", "'")
    return result.upper() if result.upper() == "CURRENT_TIMESTAMP" else result


def validate_empty_activity_log_table(connection) -> None:
    """Raise unless activity_logs exactly matches the expected empty model table."""
    inspector = inspect(connection)
    if "activity_logs" not in inspector.get_table_names():
        raise RuntimeError("Expected activity_logs table is missing")

    expected = {
        "id": (sa.Integer, None, False, None, True),
        "user_id": (sa.Integer, None, False, None, False),
        "action": (sa.String, 80, False, None, False),
        "entity_type": (sa.String, 80, False, None, False),
        "entity_id": (sa.Integer, None, True, None, False),
        "metadata": (sa.JSON, None, False, "{}", False),
        "created_at": (sa.DateTime, None, False, "CURRENT_TIMESTAMP", False),
    }
    columns = {column["name"]: column for column in inspector.get_columns("activity_logs")}
    if set(columns) != set(expected):
        raise RuntimeError("activity_logs columns do not match the expected schema")
    primary_key = set(inspector.get_pk_constraint("activity_logs").get("constrained_columns") or ())
    for name, (expected_type, expected_length, nullable, default, is_primary) in expected.items():
        column = columns[name]
        actual_type = column["type"]
        type_matches = isinstance(actual_type, expected_type)
        if expected_length is not None:
            type_matches = type_matches and actual_type.length == expected_length
        if not type_matches or bool(column["nullable"]) != nullable:
            raise RuntimeError("activity_logs column types or nullability do not match the expected schema")
        if (name in primary_key) != is_primary:
            raise RuntimeError("activity_logs primary key does not match the expected schema")
        if _normalized_default(column.get("default")) != default:
            raise RuntimeError("activity_logs column defaults do not match the expected schema")

    indexes = {
        index["name"]: (tuple(index.get("column_names") or ()), bool(index.get("unique")))
        for index in inspector.get_indexes("activity_logs")
    }
    expected_indexes = {
        "ix_activity_logs_user_created_at": (("user_id", "created_at"), False),
        "ix_activity_logs_action_created_at": (("action", "created_at"), False),
    }
    if indexes != expected_indexes:
        raise RuntimeError("activity_logs indexes do not match the expected schema")

    foreign_keys = inspector.get_foreign_keys("activity_logs")
    if len(foreign_keys) != 1:
        raise RuntimeError("activity_logs foreign key does not match the expected schema")
    foreign_key = foreign_keys[0]
    options = foreign_key.get("options") or {}
    ondelete = str(options.get("ondelete") or "NO ACTION").upper()
    if (
        foreign_key.get("constrained_columns") != ["user_id"]
        or foreign_key.get("referred_table") != "users"
        or foreign_key.get("referred_columns") != ["id"]
        or ondelete != "NO ACTION"
    ):
        raise RuntimeError("activity_logs foreign key does not match the expected schema")

    if inspector.get_unique_constraints("activity_logs") or inspector.get_check_constraints("activity_logs"):
        raise RuntimeError("activity_logs has unexpected constraints")
    if connection.execute(text("SELECT count(*) FROM activity_logs")).scalar_one() != 0:
        raise RuntimeError("activity_logs is not empty")
