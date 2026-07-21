"""SRP 公共异常。"""

from __future__ import annotations

from collections.abc import Sequence


class SRPError(Exception):
    """所有 SRP 业务异常的基类。"""


class InvalidArgumentError(SRPError, ValueError):
    """调用参数不合法。"""


class InvalidURIError(InvalidArgumentError):
    """SRP URI 不合法。"""


class UnsupportedSchemeError(SRPError):
    """URI scheme 没有可用的 transport。"""


class SchemeMismatchError(SRPError):
    """URI scheme 与指定 transport 不匹配。"""


class SchemeAlreadyRegisteredError(SRPError):
    """scheme 已注册且调用者未允许覆盖。"""


class InvalidPathError(InvalidArgumentError):
    """资源相对路径不安全或格式不合法。"""


class ManifestError(SRPError):
    """仓库清单或 skill manifest 无法解析。"""


class DuplicateSkillError(ManifestError):
    """同一仓库包含重复的 skill 身份。"""


class SkillNotFoundError(SRPError):
    """索引中不存在匹配的 skill。"""


class AmbiguousSkillError(SRPError):
    """精确获取匹配多个仓库。"""

    def __init__(
        self, name: str, version: str, repositories: Sequence[str]
    ) -> None:
        """初始化歧义错误。

        Args:
            name: skill 名称。
            version: 规范化后的版本。
            repositories: 匹配的仓库标识。

        Returns:
            无返回值。
        """
        self.name = name
        self.version = version
        self.repositories = tuple(repositories)
        choices = ", ".join(self.repositories)
        super().__init__(
            f"Skill {name}@{version} matches multiple repositories: {choices}"
        )


class MetadataMismatchError(ManifestError):
    """skill 元数据与索引身份不一致。"""


class UndeclaredResourceError(SRPError):
    """调用者请求了清单未声明的附加资源。"""


class ResourceNotFoundError(SRPError):
    """底层资源不存在。"""


class TransportTimeoutError(SRPError, TimeoutError):
    """底层 transport 读取超时。"""


class TransportError(SRPError):
    """底层 transport 读取失败。"""
