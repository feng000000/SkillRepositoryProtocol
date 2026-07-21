"""SRP 清单、skill 内容与统一解析器。"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import yaml

from .errors import (
    AmbiguousSkillError,
    DuplicateSkillError,
    InvalidArgumentError,
    ManifestError,
    MetadataMismatchError,
    ResourceNotFoundError,
    SkillNotFoundError,
    UndeclaredResourceError,
)
from .models import ParsedURI, RepositoryRef, Skill, SkillIndexEntry, SkillRef
from .paths import join_relative_paths, normalize_relative_path
from .transports import Transport, TransportRegistry, TransportResolver

LOGGER = logging.getLogger("skill_repository_protocol.parser")


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(
            f"skill_list field {field!r} must be a non-empty string"
        )
    return value


def parse_skill_list(data: bytes, repository: RepositoryRef) -> list[SkillRef]:
    """解析并校验单仓库 skill_list.json。

    Args:
        data: 清单 JSON 字节。
        repository: 清单所属仓库。

    Returns:
        包含仓库身份的 skill 引用。
    """
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(
            f"Repository {repository.id} has an invalid skill_list.json"
        ) from exc
    if not isinstance(document, dict) or not isinstance(
        document.get("skill_list"), list
    ):
        raise ManifestError("skill_list.json must contain a skill_list array")
    protocol_version = document.get("version", "1")
    if protocol_version != "1":
        raise ManifestError(
            f"Unsupported skill_list version: {protocol_version!r}"
        )
    result: list[SkillRef] = []
    identities: set[tuple[str, str]] = set()
    for raw in document["skill_list"]:
        if not isinstance(raw, dict):
            raise ManifestError("Each skill_list item must be an object")
        additions = raw.get("addition_files", [])
        if not isinstance(additions, list) or not all(
            isinstance(item, str) for item in additions
        ):
            raise ManifestError("addition_files must be an array of strings")
        entry = SkillIndexEntry(
            name=_required_string(raw.get("name"), "name"),
            description=_required_string(raw.get("description"), "description"),
            path=normalize_relative_path(
                _required_string(raw.get("path"), "path")
            ),
            version=_required_string(raw.get("version", "v1.0.0"), "version"),
            addition_files=tuple(
                normalize_relative_path(item) for item in additions
            ),
        )
        identity = (entry.name, entry.version)
        if identity in identities:
            detail = f"{entry.name}@{entry.version}"
            raise DuplicateSkillError(
                f"Repository {repository.id} contains duplicate skill: {detail}"
            )
        identities.add(identity)
        result.append(
            SkillRef(
                repository=repository,
                name=entry.name,
                description=entry.description,
                path=entry.path,
                version=entry.version,
                addition_files=entry.addition_files,
            )
        )
    return result


def _parse_yaml_mapping(data: bytes, resource: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ManifestError(f"{resource} is not valid UTF-8 YAML") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) for key in loaded
    ):
        raise ManifestError(f"{resource} must be a mapping with string keys")
    return dict(loaded)


def _parse_json_mapping(data: bytes, resource: str) -> dict[str, Any]:
    try:
        loaded = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{resource} is not valid UTF-8 JSON") from exc
    if not isinstance(loaded, dict):
        raise ManifestError(f"{resource} must contain a top-level object")
    return loaded


def _parse_frontmatter(markdown: bytes) -> tuple[dict[str, Any], str]:
    try:
        text = markdown.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestError("SKILL.md must be UTF-8 encoded") from exc
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ManifestError("SKILL.md is missing YAML frontmatter")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            yaml_bytes = "".join(lines[1:index]).encode()
            return _parse_yaml_mapping(yaml_bytes, "SKILL.md frontmatter"), text
    raise ManifestError("SKILL.md frontmatter is not closed")


class SRPParser:
    """统一 SRP Python 解析器。"""

    def __init__(
        self,
        repositories: Mapping[str, str] | Sequence[str],
        *,
        transports: Mapping[str, Transport] | None = None,
        resolver: TransportResolver | None = None,
    ) -> None:
        """初始化解析器。

        Args:
            repositories: repository alias 到 URI 的映射，或 URI 序列。
            transports: 初始自定义 transport 映射。
            resolver: 接收结构化 URI 的自定义路由钩子。

        Returns:
            无返回值。
        """
        if isinstance(repositories, Mapping):
            raw_repositories = list(repositories.items())
        else:
            raw_repositories = []
            for value in repositories:
                parsed = ParsedURI.parse(value)
                digest = hashlib.sha256(parsed.redacted().encode()).hexdigest()[
                    :12
                ]
                raw_repositories.append((f"repo-{digest}", value))
        if not raw_repositories:
            raise InvalidArgumentError(
                "At least one repository URI is required"
            )
        ids: set[str] = set()
        self.repositories: list[RepositoryRef] = []
        for repository_id, uri in raw_repositories:
            if not repository_id or repository_id in ids:
                raise InvalidArgumentError(
                    f"Repository ID is empty or duplicated: {repository_id!r}"
                )
            ids.add(repository_id)
            self.repositories.append(
                RepositoryRef(repository_id, ParsedURI.parse(uri))
            )
        self.registry = TransportRegistry(transports, resolver)
        self._index: list[SkillRef] | None = None

    def register_transport(
        self,
        scheme: str,
        transport: Transport,
        *,
        replace_existing: bool = False,
    ) -> None:
        """向当前 parser 注册 transport。

        Args:
            scheme: URI scheme。
            transport: 自定义资源读取器。
            replace_existing: 是否显式覆盖已有项。

        Returns:
            无返回值。
        """
        self.registry.register(
            scheme, transport, replace_existing=replace_existing
        )

    def _read(self, repository: RepositoryRef, relative_path: str) -> bytes:
        transport = self.registry.resolve(repository.uri)
        try:
            return transport.read(repository.uri, relative_path)
        except Exception:
            LOGGER.error(
                "Failed to read repository resource: repository=%s path=%s",
                repository.id,
                relative_path,
            )
            raise

    def list_skills(self, *, refresh: bool = False) -> list[SkillRef]:
        """读取并合并所有仓库清单。

        Args:
            refresh: 是否忽略实例缓存重新加载。

        Returns:
            所有仓库的 skill 引用列表。
        """
        if self._index is not None and not refresh:
            return list(self._index)
        merged: list[SkillRef] = []
        for repository in self.repositories:
            LOGGER.info("加载仓库清单: repository=%s", repository.id)
            merged.extend(
                parse_skill_list(
                    self._read(repository, "skill_list.json"), repository
                )
            )
        self._index = merged
        return list(merged)

    def find_skills(
        self, name: str, version: str | None = None
    ) -> list[SkillRef]:
        """查找全部匹配 skill 引用。

        Args:
            name: skill 名称。
            version: 可选的精确版本。

        Returns:
            所有匹配项。
        """
        return [
            item
            for item in self.list_skills()
            if item.name == name
            and (version is None or item.version == version)
        ]

    def get_skill_ref(
        self,
        name: str,
        version: str | None = None,
        repository: str | None = None,
    ) -> SkillRef:
        """获取唯一 skill 引用。

        Args:
            name: skill 名称。
            version: 可选的精确版本。
            repository: 可选 repository id。

        Returns:
            唯一匹配引用。
        """
        matches = self.find_skills(name, version)
        if repository is not None:
            matches = [
                item for item in matches if item.repository.id == repository
            ]
        if not matches:
            identity = f"{name}@{version or '*'}"
            source = repository or "*"
            raise SkillNotFoundError(
                f"Skill not found: {identity} repository={source}"
            )
        if len(matches) > 1:
            raise AmbiguousSkillError(
                name, version or "*", [item.repository.id for item in matches]
            )
        return matches[0]

    def get_skill(
        self,
        name: str,
        version: str | None = None,
        repository: str | None = None,
    ) -> Skill:
        """加载唯一匹配 skill 的 manifest 与 SKILL.md。

        Args:
            name: skill 名称。
            version: 可选的精确版本。
            repository: 可选 repository id。

        Returns:
            已加载 skill。
        """
        ref = self.get_skill_ref(name, version, repository)
        manifest_path = join_relative_paths(ref.path, "manifest.json")
        markdown_path = join_relative_paths(ref.path, "SKILL.md")
        try:
            manifest = _parse_json_mapping(
                self._read(ref.repository, manifest_path), "manifest.json"
            )
            markdown_bytes = self._read(ref.repository, markdown_path)
        except ResourceNotFoundError:
            raise
        frontmatter, markdown = _parse_frontmatter(markdown_bytes)
        effective = {**frontmatter, **manifest}
        if effective.get("name") != ref.name:
            actual_name = effective.get("name")
            raise MetadataMismatchError(
                f"Skill name mismatch: index={ref.name!r}, "
                f"metadata={actual_name!r}"
            )
        metadata_version = effective.get("version")
        if metadata_version is not None and metadata_version != ref.version:
            raise MetadataMismatchError(
                f"Skill version mismatch: index={ref.version!r}, "
                f"metadata={metadata_version!r}"
            )
        LOGGER.info(
            "加载 skill: repository=%s name=%s version=%s",
            ref.repository.id,
            ref.name,
            ref.version,
        )
        return Skill(ref=ref, manifest=effective, markdown=markdown)

    def read_additional_file(
        self,
        name: str,
        relative_path: str,
        version: str | None = None,
        repository: str | None = None,
    ) -> bytes:
        """读取清单声明的附加文件。

        Args:
            name: skill 名称。
            relative_path: 相对于 skill path 的附加文件路径。
            version: 可选的精确版本。
            repository: 可选 repository id。

        Returns:
            附加文件字节。
        """
        ref = self.get_skill_ref(name, version, repository)
        safe_path = normalize_relative_path(relative_path)
        if safe_path not in ref.addition_files:
            raise UndeclaredResourceError(
                f"Additional file is not declared in skill_list: {safe_path}"
            )
        return self._read(
            ref.repository, join_relative_paths(ref.path, safe_path)
        )
