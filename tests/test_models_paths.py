from __future__ import annotations

import pytest

from skill_repository_protocol import (
    InvalidPathError,
    InvalidURIError,
    ParsedURI,
    append_uri_path,
    normalize_relative_path,
)


def test_parsed_uri_preserves_all_structured_parts() -> None:
    uri = ParsedURI.parse(
        "https://user:secret@[2001:db8::1]:8443/base?q=token#section"
    )

    assert uri.scheme == "https"
    assert uri.userinfo == "user:secret"
    assert uri.host == "2001:db8::1"
    assert uri.port == 8443
    assert uri.path == "/base"
    assert uri.query == "q=token"
    assert uri.fragment == "section"
    assert (
        uri.to_uri()
        == "https://user:secret@[2001:db8::1]:8443/base?q=token#section"
    )
    assert "secret" not in uri.redacted()
    assert "token" not in uri.redacted()


def test_parsed_uri_rejects_missing_scheme_and_bad_port() -> None:
    with pytest.raises(InvalidURIError):
        ParsedURI.parse("example.com/skills")
    with pytest.raises(InvalidURIError):
        ParsedURI.parse("https://example.com:bad/skills")


def test_append_uri_path_preserves_base_query_and_fragment() -> None:
    repository = ParsedURI.parse("https://example.com/base/?mirror=one#opaque")

    resource = append_uri_path(repository, "example skill/SKILL.md")

    assert resource.path == "/base/example%20skill/SKILL.md"
    assert resource.query == "mirror=one"
    assert resource.fragment == "opaque"


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "../escape",
        "a/../escape",
        "a/./file",
        "https://evil/x",
        "a\\b",
        "a//b",
    ],
)
def test_relative_path_rejects_unsafe_inputs(path: str) -> None:
    with pytest.raises(InvalidPathError):
        normalize_relative_path(path)


def test_relative_path_accepts_versioned_and_stable_layouts() -> None:
    assert normalize_relative_path("example/v1.2.0") == "example/v1.2.0"
    assert normalize_relative_path("stable/example") == "stable/example"
