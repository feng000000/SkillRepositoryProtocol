"""SRP transport 契约、路由与内置实现。"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs, unquote

import httpx
import yaml

from .errors import (
    InvalidURIError,
    ResourceNotFoundError,
    SchemeAlreadyRegisteredError,
    SchemeMismatchError,
    TransportError,
    TransportTimeoutError,
    UnsupportedSchemeError,
)
from .models import ParsedURI
from .paths import append_uri_path, join_relative_paths, normalize_relative_path

LOGGER = logging.getLogger("skill_repository_protocol.transports")


@runtime_checkable
class Transport(Protocol):
    """同步资源读取器契约。"""

    schemes: frozenset[str]

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        """读取仓库中的相对资源。

        Args:
            repository: 结构化仓库 URI。
            relative_path: 安全相对资源路径。

        Returns:
            原始资源字节。
        """
        raise NotImplementedError


TransportResolver = Callable[
    [ParsedURI, Mapping[str, Transport]], Transport | None
]


def _validate_scheme(repository: ParsedURI, schemes: frozenset[str]) -> None:
    if repository.scheme not in schemes:
        expected = ", ".join(sorted(schemes))
        raise SchemeMismatchError(
            f"URI scheme {repository.scheme!r} does not match transport; "
            f"expected one of: {expected}"
        )


class TransportRegistry:
    """parser 实例级 transport 注册表。"""

    def __init__(
        self,
        transports: Mapping[str, Transport] | None = None,
        resolver: TransportResolver | None = None,
    ) -> None:
        """初始化注册表。

        Args:
            transports: 初始自定义 transport 映射。
            resolver: 可选的结构化 URI 路由钩子。

        Returns:
            无返回值。
        """
        self._transports: dict[str, Transport] = {
            "file": FileTransport(),
            "http": HTTPTransport(),
            "https": HTTPTransport(),
            "s3": S3Transport(),
            "git": GitTransport(),
        }
        self._resolver = resolver
        for scheme, transport in (transports or {}).items():
            self.register(scheme, transport)

    @property
    def transports(self) -> Mapping[str, Transport]:
        """返回注册项的只读语义视图。

        Returns:
            scheme 到 transport 的浅拷贝。
        """
        return dict(self._transports)

    def register(
        self,
        scheme: str,
        transport: Transport,
        *,
        replace_existing: bool = False,
    ) -> None:
        """注册 transport。

        Args:
            scheme: URI scheme。
            transport: 资源读取器。
            replace_existing: 是否显式覆盖已有项。

        Returns:
            无返回值。

        Raises:
            SchemeAlreadyRegisteredError: scheme 已存在且未允许覆盖。
        """
        normalized = scheme.lower()
        if normalized in self._transports and not replace_existing:
            raise SchemeAlreadyRegisteredError(
                f"Scheme is already registered: {normalized}"
            )
        self._transports[normalized] = transport

    def resolve(self, repository: ParsedURI) -> Transport:
        """为结构化 URI 选择 transport。

        Args:
            repository: 结构化仓库 URI。

        Returns:
            匹配的 transport。

        Raises:
            UnsupportedSchemeError: 没有匹配项。
        """
        if self._resolver is not None:
            selected = self._resolver(repository, self.transports)
            if selected is not None:
                return selected
        try:
            return self._transports[repository.scheme]
        except KeyError as exc:
            raise UnsupportedSchemeError(
                f"Unsupported scheme: {repository.scheme}"
            ) from exc


class FileTransport:
    """本地文件系统 transport。"""

    schemes = frozenset({"file"})

    @staticmethod
    def _frontmatter_as_json(skill_path: Path) -> bytes:
        """将 SKILL.md 的 YAML frontmatter 转换为 JSON。

        Args:
            skill_path: SKILL.md 的安全本地路径。

        Returns:
            UTF-8 JSON 字节。
        """
        try:
            text = skill_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ResourceNotFoundError(
                "SKILL.md required to generate manifest.json was not found: "
                f"{skill_path}"
            ) from exc
        except OSError as exc:
            raise TransportError(
                f"Failed to read SKILL.md: {skill_path}"
            ) from exc
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise TransportError("SKILL.md is missing YAML frontmatter")
        try:
            end = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise TransportError("SKILL.md frontmatter is not closed") from exc
        try:
            manifest = yaml.safe_load("\n".join(lines[1:end]))
        except yaml.YAMLError as exc:
            raise TransportError(
                "SKILL.md frontmatter is not valid YAML"
            ) from exc
        if not isinstance(manifest, dict) or not all(
            isinstance(key, str) for key in manifest
        ):
            raise TransportError(
                "SKILL.md frontmatter must be a mapping with string keys"
            )
        return json.dumps(
            manifest,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        """从本地仓库根目录安全读取文件。

        Args:
            repository: file 仓库 URI。
            relative_path: 仓库相对资源路径。

        Returns:
            文件内容。
        """
        _validate_scheme(repository, self.schemes)
        if repository.host not in {None, "", "localhost"}:
            raise InvalidURIError(
                "FileTransport only accepts an empty host or localhost"
            )
        safe_path = normalize_relative_path(relative_path)
        root = Path(unquote(repository.path)).resolve()
        target = root.joinpath(*safe_path.split("/")).resolve()
        if not target.is_relative_to(root):
            raise TransportError(
                f"File resource escapes repository root: {safe_path}"
            )
        try:
            if target.name == "manifest.json" and not target.exists():
                data = self._frontmatter_as_json(target.with_name("SKILL.md"))
            else:
                data = target.read_bytes()
        except FileNotFoundError as exc:
            raise ResourceNotFoundError(
                f"Resource not found: {repository.redacted()} / {safe_path}"
            ) from exc
        except OSError as exc:
            LOGGER.error(
                "File transport read failed: repository=%s path=%s",
                repository.redacted(),
                safe_path,
            )
            raise TransportError(
                "Failed to read file resource: "
                f"{repository.redacted()} / {safe_path}"
            ) from exc
        LOGGER.info(
            "读取 file 资源: repository=%s path=%s",
            repository.redacted(),
            safe_path,
        )
        return data


class HTTPTransport:
    """HTTP 与 HTTPS transport。"""

    schemes = frozenset({"http", "https"})

    def __init__(
        self,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
        max_redirects: int = 5,
        max_response_bytes: int = 10 * 1024 * 1024,
        verify: bool = True,
        trust_env: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        """初始化 HTTP transport。

        Args:
            headers: 默认请求头，可用于认证。
            timeout: 连接与读取超时秒数。
            max_redirects: 最大重定向次数。
            max_response_bytes: 最大响应字节数。
            verify: 是否验证 TLS 证书。
            trust_env: 是否继承环境代理与证书配置。
            client: 可注入的 httpx 客户端。

        Returns:
            无返回值。
        """
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._max_response_bytes = max_response_bytes
        self._client = client or httpx.Client(
            timeout=timeout,
            verify=verify,
            follow_redirects=True,
            max_redirects=max_redirects,
            trust_env=trust_env,
        )

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        """通过 HTTP(S) GET 读取资源。

        Args:
            repository: HTTP(S) 仓库 URI。
            relative_path: 仓库相对资源路径。

        Returns:
            响应字节。
        """
        _validate_scheme(repository, self.schemes)
        resource = append_uri_path(repository, relative_path)
        url = replace(resource, fragment="").to_uri()
        try:
            with self._client.stream(
                "GET", url, headers=self._headers, timeout=self._timeout
            ) as response:
                if response.status_code == 404:
                    raise ResourceNotFoundError(
                        f"Resource not found: {resource.redacted()}"
                    )
                response.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._max_response_bytes:
                        raise TransportError(
                            "HTTP response exceeds the size limit: "
                            f"{resource.redacted()}"
                        )
                    chunks.append(chunk)
        except ResourceNotFoundError:
            raise
        except httpx.TimeoutException as exc:
            raise TransportTimeoutError(
                f"HTTP read timed out: {resource.redacted()}"
            ) from exc
        except httpx.HTTPError as exc:
            LOGGER.error(
                "HTTP transport read failed: resource=%s",
                resource.redacted(),
            )
            raise TransportError(
                f"HTTP read failed: {resource.redacted()}"
            ) from exc
        LOGGER.info("读取 HTTP 资源: resource=%s", resource.redacted())
        return b"".join(chunks)


class S3Transport:
    """S3 及兼容对象存储 transport。"""

    schemes = frozenset({"s3"})

    def __init__(
        self,
        *,
        client: Any | None = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
    ) -> None:
        """初始化 S3 transport。

        Args:
            client: 可注入的 S3 兼容客户端。
            endpoint_url: S3 兼容端点。
            region_name: AWS region。

        Returns:
            无返回值。
        """
        self._client = client
        self._endpoint_url = endpoint_url
        self._region_name = region_name

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            boto3 = importlib.import_module("boto3")
        except ImportError as exc:
            raise TransportError("S3Transport requires the s3 extra") from exc
        self._client = boto3.client(
            "s3", endpoint_url=self._endpoint_url, region_name=self._region_name
        )
        return self._client

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        """通过 GetObject 读取 S3 对象。

        Args:
            repository: s3 仓库 URI，host 为 bucket。
            relative_path: 仓库相对对象路径。

        Returns:
            对象内容。
        """
        _validate_scheme(repository, self.schemes)
        if not repository.host:
            raise InvalidURIError("S3 URI must include a bucket")
        safe_path = normalize_relative_path(relative_path)
        prefix = repository.path.strip("/")
        key = join_relative_paths(prefix, safe_path) if prefix else safe_path
        try:
            response = self._get_client().get_object(
                Bucket=repository.host, Key=key
            )
            data = response["Body"].read()
        except TimeoutError as exc:
            raise TransportTimeoutError(
                f"S3 read timed out: {repository.host}/{key}"
            ) from exc
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise ResourceNotFoundError(
                    f"S3 resource not found: {repository.host}/{key}"
                ) from exc
            LOGGER.error(
                "S3 transport read failed: bucket=%s key=%s",
                repository.host,
                key,
            )
            raise TransportError(
                f"S3 read failed: {repository.host}/{key}"
            ) from exc
        if not isinstance(data, bytes):
            raise TransportError(
                f"S3 client returned non-bytes content: {repository.host}/{key}"
            )
        LOGGER.info("读取 S3 资源: bucket=%s key=%s", repository.host, key)
        return data


class GitTransport:
    """将 git 仓库物化后读取文件的 transport。"""

    schemes = frozenset({"git"})

    def __init__(
        self, *, cache_dir: Path | None = None, timeout: float = 60.0
    ) -> None:
        """初始化 Git transport。

        Args:
            cache_dir: 受控 checkout 缓存目录。
            timeout: Git 命令超时秒数。

        Returns:
            无返回值。
        """
        default_cache = (
            Path(tempfile.gettempdir()) / "skill-repository-protocol-git"
        )
        self._cache_dir = (cache_dir or default_cache).resolve()
        self._timeout = timeout

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        """从指定 Git ref/subdir 读取资源。

        Args:
            repository: git 仓库 URI；query 可包含 ref 与 subdir。
            relative_path: 仓库相对资源路径。

        Returns:
            文件内容。
        """
        _validate_scheme(repository, self.schemes)
        safe_path = normalize_relative_path(relative_path)
        options = parse_qs(repository.query, keep_blank_values=False)
        ref = options.get("ref", ["HEAD"])[-1]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}", ref) or any(
            marker in ref for marker in ("..", "@{")
        ):
            raise InvalidURIError("Git ref contains unsafe characters")
        subdir = options.get("subdir", [""])[-1]
        safe_subdir = normalize_relative_path(subdir) if subdir else ""
        clone_uri = (
            unquote(repository.path)
            if not repository.host
            else replace(repository, query="", fragment="").to_uri()
        )
        digest = hashlib.sha256(repository.redacted().encode()).hexdigest()[:20]
        checkout = self._cache_dir / digest
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            if not checkout.exists():
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--no-checkout",
                        "--",
                        clone_uri,
                        str(checkout),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=self._timeout,
                    env=env,
                )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "checkout",
                    "--force",
                    ref,
                ],
                cwd=checkout,
                check=True,
                capture_output=True,
                timeout=self._timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransportTimeoutError(
                f"Git repository read timed out: {repository.redacted()}"
            ) from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            LOGGER.error(
                "Git transport failed to prepare repository: repository=%s",
                repository.redacted(),
            )
            raise TransportError(
                f"Failed to prepare Git repository: {repository.redacted()}"
            ) from exc
        root = (
            checkout.joinpath(*safe_subdir.split("/")).resolve()
            if safe_subdir
            else checkout
        )
        target = root.joinpath(*safe_path.split("/")).resolve()
        if not target.is_relative_to(root):
            raise TransportError(
                f"Git resource escapes repository root: {safe_path}"
            )
        try:
            data = target.read_bytes()
        except FileNotFoundError as exc:
            raise ResourceNotFoundError(
                f"Git resource not found: {repository.redacted()} / {safe_path}"
            ) from exc
        except OSError as exc:
            raise TransportError(
                "Failed to read Git resource: "
                f"{repository.redacted()} / {safe_path}"
            ) from exc
        LOGGER.info(
            "读取 Git 资源: repository=%s path=%s",
            repository.redacted(),
            safe_path,
        )
        return data
