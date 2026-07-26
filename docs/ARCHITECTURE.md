# SRP Python 代码结构与接口

本文档描述 `skill_repository_protocol` Python 包的模块边界、公共接口、输入输出、主要调用链和扩展机制。README 面向使用者介绍协议与常见用法；本文档面向维护者解释代码如何协作。

## 整体结构

```text
调用者
  │
  ▼
SRPParser                         parser.py
  ├── 读取并合并仓库索引          parse_skill_list()
  ├── 查找与 repository 消歧      SkillRef
  ├── 加载 manifest/SKILL.md      Skill
  └── 读取已声明 addition_files
          │
          ▼
TransportRegistry                transports.py
  ├── 按 scheme 选择 Transport
  └── 可选 resolver 自定义路由
          │
          ├── FileTransport
          ├── HTTPTransport
          ├── S3Transport
          ├── GitTransport
          └── Custom Transport
                  │
                  ▼
                bytes
```

核心分层原则：

- `SRPParser` 理解 SRP 领域语义，包括清单、skill 身份、元数据和多仓库查找。
- `Transport` 只理解如何从某种 scheme 读取原始资源，不解析 JSON、YAML 或 Markdown。
- `ParsedURI` 和路径函数负责在 I/O 前完成 URI 结构化与安全相对路径处理。
- 所有预期失败通过公共异常层级表达，调用者不需要依赖底层库的异常类型。

## 模块职责

| 模块 | 职责 | 主要公共对象 |
|---|---|---|
| `models.py` | URI、仓库、索引条目和 skill 领域模型 | `ParsedURI`、`RepositoryRef`、`SkillRef`、`Skill` |
| `paths.py` | 相对路径校验、拼接和 URI path 叠加 | `normalize_relative_path`、`join_relative_paths`、`append_uri_path` |
| `transports.py` | Transport 契约、注册表、路由和内置读取实现 | `Transport`、`TransportRegistry`、4 个内置 Transport |
| `parser.py` | 清单解析、多仓库索引、查找消歧和 skill 内容加载 | `SRPParser`、`parse_skill_list` |
| `errors.py` | 稳定的公共业务异常层级 | `SRPError` 及其子类 |
| `__init__.py` | 定义包顶层公共导出面 | 上述公共类型与函数 |

模块依赖保持单向：

```text
errors
  ▲
models ◀── paths
  ▲        ▲
  └── transports
         ▲
       parser
```

`parser` 可以依赖所有底层模块；Transport 不得反向依赖 `SRPParser` 或解析 skill 领域内容。

## 数据模型

### ParsedURI

结构化保存仓库 URI：

```python
@dataclass(frozen=True, slots=True)
class ParsedURI:
    scheme: str
    userinfo: str | None
    host: str | None
    port: int | None
    path: str
    query: str
    fragment: str
```

主要接口：

```python
ParsedURI.parse(value: str) -> ParsedURI
uri.to_uri(
    *,
    include_userinfo: bool = True,
    include_query: bool = True,
) -> str
uri.redacted() -> str
```

`redacted()` 用于日志和错误文本，移除 userinfo 与 query。fragment 会被结构化保留，但 SRP 核心不解释其业务含义。

### RepositoryRef

```python
@dataclass(frozen=True, slots=True)
class RepositoryRef:
    id: str
    uri: ParsedURI
```

`id` 是调用者提供的 repository alias，或根据去敏 URI 生成的稳定内部标识。多仓库消歧使用 `id`，不直接暴露可能带凭证的原 URI。

### SkillIndexEntry 与 SkillRef

`SkillIndexEntry` 是单个 `skill_list.json` 条目的规范化结果。`SkillRef` 在此基础上增加所属 repository：

```text
SkillIndexEntry
  name
  description
  path
  version = "v1.0.0"
  addition_files = ()

SkillRef
  repository
  name
  description
  path
  version = "v1.0.0"
  addition_files = ()
```

同一仓库内 `(name, version)` 必须唯一。`version` 是逻辑身份，不用于推导或修改 `path`。

### Skill

```python
@dataclass(frozen=True, slots=True)
class Skill:
    ref: SkillRef
    manifest: Mapping[str, Any]
    markdown: str
```

`manifest` 是 `SKILL.md` frontmatter 与 `manifest.json` 字段级合并后的只读映射，其中 manifest 字段优先。

## Transport 接口

### 统一契约

```python
class Transport(Protocol):
    schemes: frozenset[str]

    def read(
        self,
        repository: ParsedURI,
        relative_path: str,
    ) -> bytes: ...
```

输入：

- `repository`：仓库根 URI 的结构化表示。
- `relative_path`：相对于仓库根目录的安全资源路径，例如 `skill_list.json` 或 `example/SKILL.md`。

输出：

- 成功时返回原始 `bytes`。Transport 不解析内容格式。
- 资源不存在时抛出 `ResourceNotFoundError`。
- 超时时抛出 `TransportTimeoutError`。
- 其他底层读取失败抛出 `TransportError`，并通过异常链保留原始原因。
- URI scheme 与 Transport 不匹配时抛出 `SchemeMismatchError`。

### FileTransport

职责：将 `file://` 仓库 URI 映射为本地文件系统根目录，并安全读取仓库内文件。

```python
transport = FileTransport()
repository = ParsedURI.parse("file:///srv/skills")

content = transport.read(
    repository,
    "example-skill/SKILL.md",
)
```

映射结果：

```text
repository.path  /srv/skills
relative_path    example-skill/SKILL.md
                 │
                 ▼
实际目标          /srv/skills/example-skill/SKILL.md
                 │
                 ▼
输出              bytes
```

读取步骤：

1. 校验 URI scheme 必须为 `file`。
2. 默认只接受空 host 或 `localhost`。
3. 校验 `relative_path` 不包含绝对路径、反斜杠、scheme 或点路径段。
4. 解析仓库根目录和目标文件的真实路径。
5. 检查符号链接解析后的目标仍位于仓库根目录内。
6. 读取文件并返回 bytes。

当目标为 `manifest.json` 且本地文件不存在时，FileTransport 会读取同目录
`SKILL.md` 的 YAML frontmatter，转换为 UTF-8 JSON bytes 返回。若显式的
`manifest.json` 已存在，则直接读取该文件。

### HTTPTransport

职责：将 `http` 或 `https` 仓库 URI 与相对路径组合为 URL，通过 HTTP GET 返回响应 body。

```python
HTTPTransport(
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    max_redirects: int = 5,
    max_response_bytes: int = 10 * 1024 * 1024,
    verify: bool = True,
    trust_env: bool = False,
    client: httpx.Client | None = None,
)
```

它保留 query、在发出请求前移除 fragment，并限制超时、重定向和最大响应大小。注入 `client` 时，client 自身的重定向、TLS 和代理配置由调用者负责。

### S3Transport

职责：将 `s3://bucket/prefix` 映射为 S3 GetObject 请求。

```text
repository     s3://skill-bucket/production
relative_path  example/SKILL.md

Bucket         skill-bucket
Key            production/example/SKILL.md
```

构造参数允许注入兼容客户端、endpoint 和 region。未注入 client 时延迟加载可选的 boto3 依赖。

### GitTransport

职责：将 Git repository 物化到受控缓存目录，checkout 指定 ref，然后读取可选 subdir 下的资源。

```text
git://host/team/skills.git?ref=v1.2.0&subdir=repository
```

- `ref` 默认 `HEAD`，并在执行 Git 前校验安全字符。
- `subdir` 默认仓库根目录，按安全相对路径处理。
- checkout 禁用 hooks，Git 命令使用参数数组而非 shell 字符串。
- 资源读取完成后返回 bytes。

### 自定义 Transport

自定义实现只需满足 `Transport` Protocol：

```python
class IPFSTransport:
    schemes = frozenset({"ipfs"})

    def read(
        self,
        repository: ParsedURI,
        relative_path: str,
    ) -> bytes:
        return ipfs_client.read(repository.host, relative_path)
```

自定义 Transport 在调用者进程权限内运行，框架不提供代码沙箱。

## TransportRegistry 与路由

`TransportRegistry` 是每个 `SRPParser` 实例独立持有的注册表，避免全局状态污染。

```python
registry.register(
    scheme: str,
    transport: Transport,
    *,
    replace_existing: bool = False,
) -> None

registry.resolve(repository: ParsedURI) -> Transport
```

默认注册：

| scheme | Transport |
|---|---|
| `file` | `FileTransport` |
| `http`、`https` | `HTTPTransport` |
| `s3` | `S3Transport` |
| `git` | `GitTransport` |

覆盖已有 scheme 必须显式传入 `replace_existing=True`。可选 resolver 的签名为：

```python
TransportResolver = Callable[
    [ParsedURI, Mapping[str, Transport]],
    Transport | None,
]
```

resolver 返回 Transport 时优先使用该结果；返回 `None` 时回退到默认 scheme 映射。这样可以按 host 等结构化 URI 字段进行特殊路由。

## SRPParser 公共接口

### 构造

```python
SRPParser(
    repositories: Mapping[str, str] | Sequence[str],
    *,
    transports: Mapping[str, Transport] | None = None,
    resolver: TransportResolver | None = None,
)
```

- Mapping 形式允许调用者提供 repository alias。
- Sequence 形式根据去敏 URI 生成 repository id。
- `transports` 用于注册新的 scheme，不能无声覆盖内置 scheme。
- `resolver` 用于覆盖默认路由决策。

### list_skills

```python
list_skills(*, refresh: bool = False) -> list[SkillRef]
```

对每个 repository 读取 `skill_list.json`，校验字段与仓库内唯一性，再合并为带 repository 身份的列表。默认缓存索引；`refresh=True` 强制重新读取。

### find_skills

```python
find_skills(
    name: str,
    version: str | None = None,
) -> list[SkillRef]
```

返回所有匹配项。version 为 `None` 时匹配该名称的所有版本；不同 repository 的同名同版本结果都会保留。

### get_skill_ref

```python
get_skill_ref(
    name: str,
    version: str | None = None,
    repository: str | None = None,
) -> SkillRef
```

要求结果唯一：没有匹配时抛出 `SkillNotFoundError`；匹配多个时抛出 `AmbiguousSkillError`；指定 repository id 可进行消歧。

### get_skill

```python
get_skill(
    name: str,
    version: str | None = None,
    repository: str | None = None,
) -> Skill
```

先获取唯一 `SkillRef`，然后读取：

```text
{path}/manifest.json
{path}/SKILL.md
```

解析器解析 frontmatter，以 manifest 字段覆盖同名字段，并校验有效 name 与可选 version 是否和索引一致。

### read_additional_file

```python
read_additional_file(
    name: str,
    relative_path: str,
    version: str | None = None,
    repository: str | None = None,
) -> bytes
```

只允许读取 `addition_files` 已声明的路径。实际 transport 路径为 `{skill.path}/{relative_path}`；未声明时抛出 `UndeclaredResourceError`。

### register_transport

```python
register_transport(
    scheme: str,
    transport: Transport,
    *,
    replace_existing: bool = False,
) -> None
```

注册只作用于当前 parser。覆盖内置或已有 scheme 必须显式允许。

## 主要调用链

### 加载仓库索引

```text
SRPParser.list_skills()
  └── 对每个 RepositoryRef
      ├── registry.resolve(repository.uri)
      ├── transport.read(uri, "skill_list.json") -> bytes
      └── parse_skill_list(bytes, repository) -> list[SkillRef]
```

### 加载 skill

```text
SRPParser.get_skill(name, version, repository)
  ├── find_skills() / get_skill_ref()
  ├── transport.read(uri, "{path}/manifest.json")
  ├── transport.read(uri, "{path}/SKILL.md")
  ├── 解析 YAML 与 frontmatter
  ├── manifest 字段级覆盖
  ├── 校验 name/version
  └── Skill(ref, effective_manifest, markdown)
```

### 读取附加文件

```text
SRPParser.read_additional_file(...)
  ├── 获取唯一 SkillRef
  ├── 校验 relative_path 在 addition_files 中
  ├── 拼接 "{path}/{relative_path}"
  └── transport.read(...) -> bytes
```

## 路径安全边界

所有仓库资源路径必须先经过 `normalize_relative_path()`：

- 拒绝空路径和绝对路径。
- 拒绝 `.`、`..`、空路径段和反斜杠。
- `skill_list.json` 中目录型 `path` 是输入边界例外：解析器先移除一个
  或多个末尾正斜杠，再执行上述通用校验；中间空路径段仍然非法。
- `addition_files` 与 transport 资源路径不应用该例外。
- 拒绝包含 `://` 的 scheme 注入。
- URL path 按段 percent-encode，不使用可能覆盖 base path 的通用 URL join。
- File/Git 在解析真实路径后再次检查目标仍位于仓库根目录。

## 异常层级

所有公共异常继承 `SRPError`：

```text
SRPError
├── InvalidArgumentError
│   ├── InvalidURIError
│   └── InvalidPathError
├── UnsupportedSchemeError
├── SchemeMismatchError
├── SchemeAlreadyRegisteredError
├── ManifestError
│   ├── DuplicateSkillError
│   └── MetadataMismatchError
├── SkillNotFoundError
├── AmbiguousSkillError
├── UndeclaredResourceError
├── ResourceNotFoundError
├── TransportTimeoutError
└── TransportError
```

Transport 应将底层异常作为 `__cause__` 保留，但日志和公共错误文本必须使用 repository id 或 `ParsedURI.redacted()`，不能泄露 userinfo、认证 header、S3 凭证或敏感 query。

## 架构文档维护规则

以下修改必须在同一个 OpenSpec change 中同步更新本文档：

- 新增、删除或重命名包模块。
- 修改包顶层公共导出或公共方法签名。
- 修改 `SRPParser`、Transport、registry 或 resolver 的职责边界。
- 修改核心领域模型、唯一键或 manifest 合并规则。
- 修改主要调用链、路径安全边界或公共异常分类。
- 新增或移除内置 scheme。

仅修复内部实现且不改变上述结构时，不要求修改本文档。更新后应对照 `src/skill_repository_protocol/__init__.py`、公共类型注解和相关测试进行复核。
