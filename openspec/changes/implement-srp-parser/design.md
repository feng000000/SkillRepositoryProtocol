## Context

当前仓库只有 SRP 协议说明和解析器待办，没有 Python 包、公共 API 或 transport 实现。协议已确认：仓库入口为 `skill_list.json`；每个条目使用可选单值 `version`（默认 `v1.0.0`）和独立的相对 `path`；资源位于 `${repository URI}/{path}/`；manifest 字段优先于 SKILL.md frontmatter；不同仓库允许同名同版本，单值获取时需要消歧；URI fragment 被结构化但不由 SRP 核心解释。

本 change 是当前 Python 根项目的首次实现。Go 版本将来在独立仓库实现，不共享本仓库构建系统。项目使用 `uv + pyproject.toml`，生产代码需要完整类型注解、中文 Google Style Docstring 和项目命名日志。

## Goals / Non-Goals

**Goals:**

- 提供稳定、类型化且可扩展的 Python SRP 公共 API。
- 将 scheme 无关的清单、元数据、查找逻辑与底层资源读取分离。
- 支持 file、HTTP(S)、S3、Git 与自定义 scheme。
- 对路径逃逸、重复身份、查找歧义和底层读取失败给出可测试的确定行为。

**Non-Goals:**

- 不实现 Go 包、仓库服务端、发布写入或同步。
- 不从 version 推导目录，也不解释 query/fragment 的业务语义。
- 不引入数据库、后台服务或全局可变的 scheme 注册表。

## Architecture

```text
调用者
  │
  ▼
SRPParser ── RepositoryIndex ── SkillResolver
  │                │                   │
  │                └─ 清单/冲突         └─ manifest/frontmatter/additions
  ▼
TransportResolver
  │
  ├─ FileTransport
  ├─ HttpTransport (http + https)
  ├─ S3Transport
  ├─ GitTransport
  └─ CustomTransport
```

依赖与执行顺序为 `01-repository-index → 02-skill-resource-resolution → 03-scheme-routing → 04-python-public-api`。01 建立身份与清单模型；02 使用该模型定位内容；03 为前两者提供字节读取边界；04 组合并稳定公开接口。实现时可以先以测试内存 transport 驱动 01/02，再接入 03，避免外部服务阻塞核心行为验证。某个 transport 不可用时只影响使用对应 scheme 的仓库，不降低其他 scheme 或已加载仓库的能力。

## Components

- **URI model**：保存 scheme、userinfo、host、port、path、query、fragment；提供不覆盖 base path 的 SRP 相对路径拼接。
- **Transport protocol**：最小读取契约，输入结构化 repository URI 和已校验相对路径，输出 bytes。实例持有认证、客户端、超时与缓存配置。
- **Transport resolver/registry**：parser 实例级注册表；默认按 scheme 选择，也允许自定义 resolver 根据完整结构化 URI 决策。覆盖内置项必须显式授权。
- **Repository index**：读取并校验 `skill_list.json`，应用默认值，生成含 repository identity 的 `SkillRef`，执行仓库内唯一性检查与多仓库合并。
- **Skill resolver**：读取 manifest、SKILL.md 和已声明附加文件，字段级合并元数据并校验身份一致性。
- **Git workspace/cache**：将远程仓库物化到受控缓存目录，再复用文件读取边界；禁止执行 hooks，初版不承诺 submodule/LFS。
- **Public API and errors**：导出领域对象、transport 接口、内置实现和稳定异常层级。

与现有仓库的集成点仅为 README/TODO 所定义协议与新建的 Python 包。新模块替代 TODO 中尚未实现的抽象，不替换任何既有运行时代码。

## APIs

建议的公共形态（名称可在实现中按 Python 命名规范微调，但行为由 specs 固定）：

```python
class SRPParser:
    def __init__(
        self,
        repositories: Mapping[str, str] | Sequence[str],
        *,
        transports: Mapping[str, Transport] | None = None,
        resolver: TransportResolver | None = None,
    ) -> None: ...

    def list_skills(self) -> list[SkillRef]: ...
    def find_skills(self, name: str, version: str | None = None) -> list[SkillRef]: ...
    def get_skill(
        self,
        name: str,
        version: str | None = None,
        repository: str | None = None,
    ) -> Skill: ...
```

内置 transport 同时公开，允许调用者独立使用。所有同步/异步选择必须保持一致；最小实现优先提供同步 API，因为 file、Git 工作区和多数简单消费场景无需事件循环。未来若增加 async API，应作为独立能力，避免当前接口返回类型双态化。

## Data Model

```text
ParsedURI
  scheme, userinfo, host, port, path, query, fragment

RepositoryRef
  id/alias, original_uri, parsed_uri

SkillIndexEntry
  name, description, version="v1.0.0", path, addition_files=[]

SkillRef
  repository, name, version, path, description, addition_files

Skill
  ref, effective_manifest, skill_markdown
```

唯一键是单仓库范围内规范化后的 `(name, version)`；path 不是身份字段，也不由身份字段推导。若调用者提供 alias，则 alias 是公开 repository id；仅传 URI 序列时生成稳定的非敏感内部 id，不将包含 userinfo/query 的 URI 暴露在错误文本中。

## Decisions

1. **领域层与 transport 分层。** 选择单一清单/skill 解析实现叠加最小 bytes transport，避免五种 scheme 复制校验逻辑。替代方案是每个 scheme 提供完整 parser，但会产生行为漂移。
2. **使用实例级注册表。** 自定义 scheme 与 resolver 绑定到 SRPParser 实例，避免全局状态污染测试和并发调用。替代方案是模块级注册表，使用更短但隔离性差。
3. **version 与 path 解耦。** version 只参与逻辑身份和查找，path 完全服从清单。这样同时支持无版本目录、版本目录和 stable 指针布局。
4. **跨仓库重复延迟到获取阶段消歧。** 列表与查找保留所有候选；仅要求单值的 get 操作报 AmbiguousSkillError。替代方案是加载时报错或静默优先级覆盖，前者削弱组合能力，后者可能读取错误来源。
5. **manifest 字段级覆盖。** manifest 中存在的字段覆盖 frontmatter，其余字段保留；身份冲突报错。整体替换会无谓丢失元数据，静默接受冲突会破坏索引一致性。
6. **SRP 自定义路径拼接。** 对相对路径分段校验并重建 URI，不采用会让前导斜杠替换 base path 的 RFC URL join 结果。
7. **最小同步 API。** 初版以同步调用为稳定合同；网络 transport 自行执行带超时的同步读取。异步版本不在本 change 范围。

## Error Handling

公共异常以 `SRPError` 为根，至少区分 `InvalidURIError`、`UnsupportedSchemeError`、`SchemeMismatchError`、`InvalidPathError`、`ManifestError`、`DuplicateSkillError`、`AmbiguousSkillError`、`MetadataMismatchError`、`ResourceNotFoundError`、`TransportTimeoutError` 与 `TransportError`。transport 将底层异常链入 `__cause__`，错误消息包含去敏后的 repository id 和资源相对路径。关键读取与失败使用 `[项目名.模块名]` logger；不得通过 print 输出或以 assert 进行运行时校验。

## Security Design

- path/addition_files 在任何 I/O 前拒绝绝对路径、scheme/authority 注入、点路径段和归一化逃逸。
- file transport 在解析符号链接后仍校验目标位于 repository root。
- HTTP transport 配置连接/读取超时、重定向上限和响应大小上限；默认验证 TLS。
- userinfo、认证 header、S3 凭证和敏感 query 不写日志或异常文本。
- Git transport 使用参数数组调用 Git、禁止 shell 拼接与 hooks，并将 checkout 限制在受控临时/缓存目录。
- 自定义 transport 在调用者进程权限内运行；框架只保证注册显式性，不提供代码沙箱。

## Risks / Trade-offs

- **[多种外部 transport 增加可选依赖体积]** → 使用依赖 extras，让核心/file/HTTP 与 S3、Git 能力按需安装。
- **[Git URI 的 ref、subdir 表达仍可能演进]** → 初版将其封装在 Git transport 配置与结构化 query 中，不让 SRP 核心解释。
- **[远端内容在清单和资源读取之间变化]** → 当前不保证跨资源快照一致性；未来可增加 hash/etag manifest 能力。
- **[同步网络 I/O 会阻塞调用线程]** → 要求超时并记录为已知边界；异步 API 另立 change。
- **[manifest 优先可能隐藏 frontmatter 差异]** → 身份字段严格一致，其他覆盖行为在结果中可追踪来源并用测试固定。

## Migration Plan

这是首次实现，无数据库 migration。按核心模型、路径与元数据、transport、公开 API 的顺序交付；先发布预览版本并用 file/HTTP fixtures 验证，再启用可选 S3/Git extras。回滚方式是撤回新包版本及依赖配置，不涉及数据回滚。若单个外部 transport 失败，调用者可不注册/不安装该 extra，核心与其他 transport 保持可用。

## Open Questions

- Python distribution/import package 的最终名称。
- `git` scheme 的规范 URI 形式以及 ref/subdir query 命名，是否在首版支持 `git+https` 与 `git+ssh`。
- HTTP 与 S3 的默认响应/对象大小上限及 Git 缓存失效策略。
