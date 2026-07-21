from __future__ import annotations

import ast
from pathlib import Path


def _literal_text(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            for value in node.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return ""


def test_exception_messages_and_error_logs_use_english() -> None:
    source_root = Path(__file__).parents[1] / "src"
    messages: list[tuple[Path, int, str]] = []

    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                for argument in node.exc.args:
                    messages.append(
                        (path, node.lineno, _literal_text(argument))
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "error"
                and node.args
            ):
                messages.append(
                    (path, node.lineno, _literal_text(node.args[0]))
                )

    non_english = [
        (path, line, message)
        for path, line, message in messages
        if any("\u4e00" <= char <= "\u9fff" for char in message)
    ]
    assert non_english == []
