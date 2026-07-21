## Why

SRP 已定义通过统一 URI 访问 skill 仓库资源的协议，但当前仓库尚无 Python 解析器实现，使用者无法统一读取 `file`、HTTP(S)、S3、Git 或自定义 scheme 的仓库。现在需要将已确认的 URI、版本、路径、清单优先级及多仓库冲突规则固化为可测试的 Python 能力，为后续实现和独立语言版本提供稳定的行为基线。

## What Changes

- 新增 Python SRP 公共 API，支持输入一个或多个仓库 URI，解析结构化 URI，并按 scheme 分发资源读取。
- 新增 `skill_list.json` 解析与校验：`version` 可选且默认 `v1.0.0`，`path` 为仓库相对路径；同一仓库内重复的 `(name, version)` 必须报错。
- 新增 skill 资源寻址：`manifest.json`、`SKILL.md` 和 `addition_files` 均在 `${URI}/{path}/` 下解析，版本仅作为逻辑元数据，不参与隐式路径拼接。
- 新增 `manifest.json` 与 `SKILL.md` frontmatter 的字段级合并，并以 manifest 字段为高优先级来源；FileTransport 可从 frontmatter 生成缺失的 manifest.json。
- 新增多仓库查找规则：不同仓库允许存在同名同版本 skill；精确获取遇到多个匹配时返回歧义错误，并允许通过 repository 标识消歧。
- 新增内置 `file`、`http`、`https`、`s3`、`git` scheme 解析器，以及可注册、可覆盖路由的自定义 scheme 扩展机制。
- 新增统一错误分类、安全路径校验、日志、类型注解、中文 Google Style Docstring、自动化测试和使用文档。
- 本 change 仅交付 Python 包，并使用 `uv` 与 `pyproject.toml` 管理依赖。

关键假设与取舍：

- `path` 和 `addition_files` 是 SRP 定义的相对路径，由解析器执行安全的分段拼接，不使用会覆盖 URI base path 的通用 URL join 语义。
- `version` 不决定目录布局；相同版本可以位于任意合法 `path`，缺省版本规范化为 `v1.0.0`。
- fragment 必须被结构化保留，但 SRP 核心不解释其业务含义。
- 跨仓库重名在加载阶段合法，在无 repository 限定的单值获取阶段才判定歧义，以保留多仓库组合能力。
- 最小改动路径是将通用 SRP 领域逻辑与 scheme 资源读取分层，而不是为每个 scheme 重复实现清单和 skill 解析。

## Capabilities

### New Capabilities

- `01-repository-index`: 定义 `skill_list.json` 的读取、默认值、校验、多仓库合并、重复与歧义处理。
- `02-skill-resource-resolution`: 定义 skill 基于 `path` 的资源寻址、manifest/frontmatter 合并、附加文件访问及路径安全。
- `03-scheme-routing`: 定义结构化 URI、内置 scheme 分发、scheme 专用资源读取和自定义 scheme 注册/路由。
- `04-python-public-api`: 定义 Python 包对外暴露的 parser、scheme parser、查找与错误行为。

### Modified Capabilities

无。当前没有已归档的主规格。

## Impact

- **创建日期**：2026-07-20
- **状态**：active
- **需求来源**：README.md 中的 SRP 协议与 TODO.md 中的解析器需求，以及本次探索中确认的版本、路径、manifest 优先级和多仓库冲突决策。
- **受影响模块**：`src/<python-package>`、`testing`、`docs`、根目录 `pyproject.toml`；不涉及 frontend、database 或 devops。
- **API 兼容性**：仓库当前没有 Python 公共 API，因此不存在已有代码的破坏性变更；本 change 将建立首个公开 API 合同。
- **配置风险**：S3、Git 和 HTTP 认证、端点、超时等 transport 配置将作为显式构造参数处理，不把敏感凭证固化到仓库清单。
- **数据迁移风险**：不引入数据库或持久化数据迁移。已有 SRP 仓库若不符合相对路径、唯一性或元数据一致性规则，将在解析时显式失败。
- **依赖影响**：引入 Python 构建、HTTP、YAML、S3/Git 支持及测试所需依赖，具体选型在 design 中约束。

## Non-goals

- 不在当前仓库实现 Go 版本；Go 版本将在后续独立仓库中规划。
- 不提供 SRP 仓库发布、写入、同步或服务端托管能力。
- 不让 SRP 核心解释 query 或 fragment 的业务语义；它们仅作为结构化 URI 信息交给对应 scheme parser。
- 不自动根据 `name` 或 `version` 推导、改写 `path`。
- 不定义 skill 自身如何发布或管理历史版本，只读取清单中声明的单个 `version` 与 `path`。
