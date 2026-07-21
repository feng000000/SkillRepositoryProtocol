"""SRP 安全相对路径处理。"""

from __future__ import annotations

from urllib.parse import quote, unquote

from .errors import InvalidPathError
from .models import ParsedURI


def normalize_relative_path(value: str) -> str:
    """校验并规范化 SRP 相对路径。

    Args:
        value: path 或 addition_file。

    Returns:
        使用正斜杠连接的规范化相对路径。

    Raises:
        InvalidPathError: 路径为空、为绝对路径或包含逃逸语义。
    """
    if not isinstance(value, str) or not value:
        raise InvalidPathError("Resource relative path must not be empty")
    decoded = unquote(value)
    if decoded.startswith(("/", "\\")) or "://" in decoded or "\\" in decoded:
        raise InvalidPathError(
            f"Resource path must be a safe relative path: {value!r}"
        )
    parts = decoded.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InvalidPathError(
            f"Resource path contains an invalid path segment: {value!r}"
        )
    return "/".join(parts)


def join_relative_paths(*values: str) -> str:
    """安全拼接多个相对路径。

    Args:
        *values: 需要依次拼接的路径。

    Returns:
        规范化后的相对路径。
    """
    return "/".join(normalize_relative_path(value) for value in values)


def append_uri_path(repository: ParsedURI, relative_path: str) -> ParsedURI:
    """将相对路径叠加到仓库 URI path，并保留 query 与 fragment。

    Args:
        repository: 结构化仓库 URI。
        relative_path: 已声明的资源相对路径。

    Returns:
        拼接资源路径后的新 URI。
    """
    safe_path = normalize_relative_path(relative_path)
    encoded = "/".join(
        quote(part, safe="~:@!$&'()*+,;=") for part in safe_path.split("/")
    )
    base = repository.path.rstrip("/")
    return ParsedURI(
        scheme=repository.scheme,
        userinfo=repository.userinfo,
        host=repository.host,
        port=repository.port,
        path=f"{base}/{encoded}" if base else f"/{encoded}",
        query=repository.query,
        fragment=repository.fragment,
    )
