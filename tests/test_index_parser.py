from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_repository_protocol import (
    AmbiguousSkillError,
    DuplicateSkillError,
    MetadataMismatchError,
    ParsedURI,
    RepositoryRef,
    SkillNotFoundError,
    SRPParser,
    UndeclaredResourceError,
    parse_skill_list,
)
from skill_repository_protocol.errors import ManifestError


def _write_repository(
    root: Path,
    *,
    name: str = "example",
    version: str | None = None,
    path: str = "example",
    manifest_description: str = "manifest description",
) -> None:
    entry: dict[str, object] = {
        "name": name,
        "description": "index description",
        "path": path,
        "addition_files": ["scripts/tool.py"],
    }
    if version is not None:
        entry["version"] = version
    root.mkdir(parents=True)
    (root / "skill_list.json").write_text(
        json.dumps({"version": "1", "skill_list": [entry]}), encoding="utf-8"
    )
    skill_root = root / path
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "manifest.json").write_text(
        json.dumps({"name": name, "description": manifest_description}),
        encoding="utf-8",
    )
    markdown = (
        f"---\nname: {name}\ndescription: frontmatter\n"
        f"license: MIT\n---\n\n# {name}\n"
    )
    (skill_root / "SKILL.md").write_text(
        markdown,
        encoding="utf-8",
    )
    (skill_root / "scripts" / "tool.py").write_bytes(b"tool")


def test_parse_skill_list_applies_defaults() -> None:
    repository = RepositoryRef("repo", ParsedURI.parse("file:///tmp/repo"))
    data = json.dumps(
        {
            "version": "1",
            "skill_list": [
                {"name": "x", "description": "desc", "path": "stable/x"}
            ],
        }
    ).encode()

    skill = parse_skill_list(data, repository)[0]

    assert skill.version == "v1.0.0"
    assert skill.path == "stable/x"
    assert skill.addition_files == ()


def test_parse_skill_list_rejects_invalid_and_duplicate_entries() -> None:
    repository = RepositoryRef("repo", ParsedURI.parse("file:///tmp/repo"))
    with pytest.raises(ManifestError):
        parse_skill_list(b"not json", repository)
    duplicate = {
        "skill_list": [
            {"name": "x", "description": "d", "path": "x"},
            {
                "name": "x",
                "description": "d2",
                "path": "elsewhere",
                "version": "v1.0.0",
            },
        ]
    }
    with pytest.raises(DuplicateSkillError):
        parse_skill_list(json.dumps(duplicate).encode(), repository)


def test_parser_loads_skill_and_manifest_overrides_frontmatter(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    _write_repository(root)
    parser = SRPParser({"official": root.as_uri()})

    refs = parser.list_skills()
    skill = parser.get_skill("example")

    assert refs[0].repository.id == "official"
    assert refs[0].version == "v1.0.0"
    assert skill.manifest["description"] == "manifest description"
    assert skill.manifest["license"] == "MIT"
    assert parser.read_additional_file("example", "scripts/tool.py") == b"tool"
    with pytest.raises(UndeclaredResourceError):
        parser.read_additional_file("example", "private.txt")


def test_parser_keeps_version_and_path_independent(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write_repository(root, version="v1.2.0", path="stable/example")

    skill = SRPParser([root.as_uri()]).get_skill("example", "v1.2.0")

    assert skill.ref.path == "stable/example"


def test_file_parser_generates_missing_manifest_from_skill_frontmatter(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    _write_repository(root)
    (root / "example" / "manifest.json").unlink()

    skill = SRPParser([root.as_uri()]).get_skill("example")

    assert skill.manifest["name"] == "example"
    assert skill.manifest["description"] == "frontmatter"


def test_cross_repository_duplicates_require_disambiguation(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_repository(first)
    _write_repository(second)
    parser = SRPParser(
        {"official": first.as_uri(), "internal": second.as_uri()}
    )

    assert len(parser.find_skills("example", "v1.0.0")) == 2
    with pytest.raises(AmbiguousSkillError) as caught:
        parser.get_skill("example", "v1.0.0")
    assert set(caught.value.repositories) == {"official", "internal"}
    assert (
        parser.get_skill("example", repository="official").ref.repository.id
        == "official"
    )
    with pytest.raises(SkillNotFoundError):
        parser.get_skill("missing")


def test_metadata_identity_conflict_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write_repository(root)
    (root / "example" / "manifest.json").write_text(
        '{"name":"other"}', encoding="utf-8"
    )

    with pytest.raises(MetadataMismatchError):
        SRPParser([root.as_uri()]).get_skill("example")


@pytest.mark.parametrize(
    ("manifest", "markdown"),
    [
        ("{broken", "---\nname: example\n---\n"),
        ('{"name":"example"}', "# no frontmatter\n"),
        ('{"name":"example"}', "---\nname: [broken\n---\n"),
    ],
)
def test_invalid_manifest_or_frontmatter_is_rejected(
    tmp_path: Path, manifest: str, markdown: str
) -> None:
    root = tmp_path / "repo"
    _write_repository(root)
    (root / "example" / "manifest.json").write_text(manifest, encoding="utf-8")
    (root / "example" / "SKILL.md").write_text(markdown, encoding="utf-8")

    with pytest.raises(ManifestError):
        SRPParser([root.as_uri()]).get_skill("example")
