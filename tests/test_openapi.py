"""Validate that all OpenAPI operations have camelCase IDs and tags."""

import re

from src.main import app


def _is_camel_case(s: str) -> bool:
    return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", s))


def test_all_operations_have_camel_case_id_and_tags() -> None:
    spec = app.openapi()
    errors: list[str] = []

    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId")
            tags = operation.get("tags", [])

            if not op_id:
                errors.append(f"{method.upper()} {path}: missing operationId")
            elif not _is_camel_case(op_id):
                errors.append(
                    f"{method.upper()} {path}: operationId '{op_id}' is not camelCase",
                )

            if not tags:
                errors.append(f"{method.upper()} {path}: missing tags")

    assert not errors, "OpenAPI spec issues:\n" + "\n".join(errors)
