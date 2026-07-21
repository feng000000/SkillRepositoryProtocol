from __future__ import annotations

from skill_repository_protocol import ParsedURI, SRPParser


class IPFSTransport:
    schemes = frozenset({"ipfs"})

    def read(self, repository: ParsedURI, relative_path: str) -> bytes:
        if relative_path == "skill_list.json":
            return b'{"version":"1","skill_list":[]}'
        return b"resource"


def test_readme_custom_transport_example() -> None:
    parser = SRPParser(
        ["ipfs://content-id/skills"],
        transports={"ipfs": IPFSTransport()},
    )

    assert parser.list_skills() == []


def test_readme_resolver_example() -> None:
    transport = IPFSTransport()

    def resolver(uri: ParsedURI, transports: object) -> IPFSTransport | None:
        del transports
        return (
            transport if uri.scheme == "file" and uri.host == "corp" else None
        )

    parser = SRPParser(["file://corp/skills"], resolver=resolver)  # type: ignore[arg-type]

    assert parser.list_skills() == []
