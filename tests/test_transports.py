from __future__ import annotations

import io
import logging
import subprocess
from pathlib import Path

import httpx
import pytest

from skill_repository_protocol import (
    FileTransport,
    GitTransport,
    HTTPTransport,
    InvalidURIError,
    ParsedURI,
    ResourceNotFoundError,
    S3Transport,
    SchemeAlreadyRegisteredError,
    SchemeMismatchError,
    SRPParser,
    TransportError,
    TransportRegistry,
    TransportTimeoutError,
    UnsupportedSchemeError,
)


class MemoryTransport:
    schemes = frozenset({"memory", "ipfs", "file"})

    def __init__(self, resources: dict[str, bytes] | None = None) -> None:
        self.resources = resources or {}
        self.reads: list[str] = []

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        self.reads.append(relative_path)
        try:
            return self.resources[relative_path]
        except KeyError as exc:
            raise ResourceNotFoundError(relative_path) from exc


class FailingTransport:
    schemes = frozenset({"broken"})

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        raise TransportError(
            f"broken: {repository.redacted()} / {relative_path}"
        )


def test_registry_custom_scheme_and_explicit_override() -> None:
    registry = TransportRegistry()
    custom = MemoryTransport()
    registry.register("ipfs", custom)

    assert registry.resolve(ParsedURI.parse("ipfs://cid/root")) is custom
    with pytest.raises(SchemeAlreadyRegisteredError):
        registry.register("https", custom)
    registry.register("https", custom, replace_existing=True)
    assert registry.resolve(ParsedURI.parse("https://example.com")) is custom
    with pytest.raises(UnsupportedSchemeError):
        registry.resolve(ParsedURI.parse("unknown://host/root"))


def test_registry_constructor_cannot_silently_override_builtin() -> None:
    with pytest.raises(SchemeAlreadyRegisteredError):
        TransportRegistry({"https": MemoryTransport()})


def test_custom_resolver_can_route_by_file_host() -> None:
    custom = MemoryTransport()
    registry = TransportRegistry(
        resolver=lambda uri, transports: (
            custom if uri.scheme == "file" and uri.host == "corp" else None
        )
    )

    assert registry.resolve(ParsedURI.parse("file://corp/repo")) is custom


def test_parser_uses_custom_transport() -> None:
    memory = MemoryTransport(
        {
            "skill_list.json": b'{"skill_list": []}',
        }
    )
    parser = SRPParser(["memory://repo/root"], transports={"memory": memory})

    assert parser.list_skills() == []
    assert memory.reads == ["skill_list.json"]


def test_failing_transport_does_not_poison_other_registered_transport() -> None:
    memory = MemoryTransport({"resource": b"healthy"})
    registry = TransportRegistry(
        {"memory": memory, "broken": FailingTransport()}
    )

    with pytest.raises(TransportError):
        registry.resolve(ParsedURI.parse("broken://repo/root")).read(
            ParsedURI.parse("broken://repo/root"), "resource"
        )
    assert (
        registry.resolve(ParsedURI.parse("memory://repo/root")).read(
            ParsedURI.parse("memory://repo/root"), "resource"
        )
        == b"healthy"
    )


def test_file_transport_reads_and_blocks_wrong_host(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"data")
    transport = FileTransport()

    assert (
        transport.read(ParsedURI.parse(tmp_path.as_uri()), "data.txt")
        == b"data"
    )
    with pytest.raises(ResourceNotFoundError):
        transport.read(ParsedURI.parse(tmp_path.as_uri()), "missing.txt")
    with pytest.raises(InvalidURIError):
        transport.read(ParsedURI.parse("file://remote/path"), "data.txt")
    with pytest.raises(SchemeMismatchError):
        transport.read(ParsedURI.parse("https://example.com"), "data.txt")


def test_file_transport_generates_json_manifest_from_frontmatter(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "example"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text(
        "---\nname: example\ndescription: 示例\n---\n\n# Example\n",
        encoding="utf-8",
    )

    data = FileTransport().read(
        ParsedURI.parse(tmp_path.as_uri()),
        "example/manifest.json",
    )

    assert data == '{"name":"example","description":"示例"}'.encode()


def test_file_transport_rejects_invalid_frontmatter_for_manifest(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "example"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text(
        "---\nname: [broken\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(TransportError):
        FileTransport().read(
            ParsedURI.parse(tmp_path.as_uri()),
            "example/manifest.json",
        )


def test_file_transport_blocks_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")
    (root / "link.txt").symlink_to(outside)

    with pytest.raises(TransportError):
        FileTransport().read(ParsedURI.parse(root.as_uri()), "link.txt")


def test_http_transport_success_not_found_and_size_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("missing"):
            return httpx.Response(404)
        if request.url.path.endswith("large"):
            return httpx.Response(200, content=b"12345")
        return httpx.Response(200, content=b"ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HTTPTransport(client=client, max_response_bytes=4)
    repository = ParsedURI.parse("https://example.com/base?token=secret#opaque")

    assert transport.read(repository, "ok") == b"ok"
    with pytest.raises(ResourceNotFoundError):
        transport.read(repository, "missing")
    with pytest.raises(TransportError):
        transport.read(repository, "large")


def test_http_transport_follows_redirect_and_does_not_send_fragment() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("start"):
            return httpx.Response(302, headers={"Location": "/base/final"})
        return httpx.Response(200, content=b"redirected")

    client = httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    transport = HTTPTransport(client=client)

    assert (
        transport.read(
            ParsedURI.parse("https://example.com/base#client-only"), "start"
        )
        == b"redirected"
    )
    assert len(requests) == 2
    assert requests[0].url.fragment == ""


def test_http_transport_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    transport = HTTPTransport(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(TransportTimeoutError):
        transport.read(ParsedURI.parse("https://example.com/base"), "resource")


class FakeS3Client:
    def get_object(self, *, Bucket: str, Key: str) -> dict[str, io.BytesIO]:
        if Key.endswith("missing"):
            error = RuntimeError("missing")
            error.response = {"Error": {"Code": "NoSuchKey"}}  # type: ignore[attr-defined]
            raise error
        if Key.endswith("slow"):
            raise TimeoutError
        return {"Body": io.BytesIO(f"{Bucket}/{Key}".encode())}


def test_s3_transport_uses_bucket_prefix_and_maps_errors() -> None:
    transport = S3Transport(client=FakeS3Client())
    repository = ParsedURI.parse("s3://bucket/prefix")

    assert transport.read(repository, "file") == b"bucket/prefix/file"
    with pytest.raises(ResourceNotFoundError):
        transport.read(repository, "missing")
    with pytest.raises(TransportTimeoutError):
        transport.read(repository, "slow")


def test_git_transport_reads_ref_and_subdir(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=source,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=source, check=True
    )
    (source / "skills").mkdir()
    (source / "skills" / "data.txt").write_bytes(b"git-data")
    subprocess.run(["git", "add", "skills/data.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=source, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    bare = tmp_path / "repo.git"
    subprocess.run(
        ["git", "clone", "-q", "--bare", str(source), str(bare)], check=True
    )
    repository = ParsedURI.parse(f"git://{bare}?ref={revision}&subdir=skills")
    transport = GitTransport(cache_dir=tmp_path / "cache")

    assert transport.read(repository, "data.txt") == b"git-data"
    with pytest.raises(ResourceNotFoundError):
        transport.read(repository, "missing.txt")
    with pytest.raises(InvalidURIError):
        transport.read(
            ParsedURI.parse(f"git://{bare}?ref=--upload-pack=evil"), "data.txt"
        )


def test_parser_logs_repository_id_without_uri_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    memory = MemoryTransport({"skill_list.json": b'{"skill_list": []}'})
    parser = SRPParser(
        {"safe-alias": "memory://user:secret@repo/root?token=hidden"},
        transports={"memory": memory},
    )

    with caplog.at_level(
        logging.INFO, logger="skill_repository_protocol.parser"
    ):
        parser.list_skills()

    assert "safe-alias" in caplog.text
    assert "secret" not in caplog.text
    assert "hidden" not in caplog.text


def test_public_api_exports_transport_types() -> None:
    import skill_repository_protocol as srp

    assert srp.SRPParser is SRPParser
    assert srp.FileTransport is FileTransport
    assert srp.HTTPTransport is HTTPTransport
    assert srp.S3Transport is S3Transport
    assert srp.GitTransport is GitTransport
