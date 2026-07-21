"""SRP 领域模型。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .errors import InvalidURIError


@dataclass(frozen=True, slots=True)
class ParsedURI:
    """结构化 SRP URI。"""

    scheme: str
    userinfo: str | None
    host: str | None
    port: int | None
    path: str
    query: str
    fragment: str

    @classmethod
    def parse(cls, value: str) -> ParsedURI:
        """解析 SRP URI。

        Args:
            value: 待解析 URI。

        Returns:
            结构化 URI。

        Raises:
            InvalidURIError: URI 缺少 scheme 或端口不合法。
        """
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise InvalidURIError(
                "SRP URI has an invalid authority or port"
            ) from exc
        if not parsed.scheme:
            raise InvalidURIError("SRP URI must include a scheme")
        userinfo = (
            parsed.netloc.rpartition("@")[0] if "@" in parsed.netloc else None
        )
        return cls(
            scheme=parsed.scheme.lower(),
            userinfo=userinfo,
            host=parsed.hostname,
            port=port,
            path=parsed.path,
            query=parsed.query,
            fragment=parsed.fragment,
        )

    def to_uri(
        self, *, include_userinfo: bool = True, include_query: bool = True
    ) -> str:
        """重建 URI。

        Args:
            include_userinfo: 是否包含 userinfo。
            include_query: 是否包含 query。

        Returns:
            重建后的 URI 字符串。
        """
        host = self.host or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        authority = f"{host}:{self.port}" if self.port is not None else host
        if include_userinfo and self.userinfo:
            authority = f"{self.userinfo}@{authority}"
        parts = SplitResult(
            self.scheme,
            authority,
            self.path,
            self.query if include_query else "",
            self.fragment,
        )
        return urlunsplit(parts)

    def redacted(self) -> str:
        """返回适合日志和错误文本的去敏 URI。

        Returns:
            不含 userinfo 与 query 的 URI。
        """
        return self.to_uri(include_userinfo=False, include_query=False)


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    """SRP 仓库引用。"""

    id: str
    uri: ParsedURI


@dataclass(frozen=True, slots=True)
class SkillIndexEntry:
    """skill_list.json 中的规范化条目。"""

    name: str
    description: str
    path: str
    version: str = "v1.0.0"
    addition_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillRef:
    """包含仓库身份的 skill 引用。"""

    repository: RepositoryRef
    name: str
    description: str
    path: str
    version: str = "v1.0.0"
    addition_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Skill:
    """已经加载的 skill 内容。"""

    ref: SkillRef
    manifest: Mapping[str, Any] = field(default_factory=dict)
    markdown: str = ""

    def __post_init__(self) -> None:
        """冻结有效 manifest，避免调用者修改共享元数据。

        Returns:
            无返回值。
        """
        object.__setattr__(
            self, "manifest", MappingProxyType(dict(self.manifest))
        )
