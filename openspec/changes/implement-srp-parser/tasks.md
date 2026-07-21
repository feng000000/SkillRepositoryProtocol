## 1. Backend：Python 项目与公共模型（Spec 04）

- [x] 1.1 使用 `uv` 初始化 `pyproject.toml`、`src/skill_repository_protocol/` 与测试目录，配置核心及 S3/Git 可选依赖；验证：执行 `uv sync --all-extras` 成功。（Spec 04；模块：backend/src、testing）
- [x] 1.2 实现 ParsedURI、RepositoryRef、SkillIndexEntry、SkillRef、Skill 等类型化领域模型及中文 Google Style Docstring；验证：执行静态类型检查并构造包含 query/fragment 的模型。（Spec 03/04；模块：backend/src）
- [x] 1.3 实现以 SRPError 为根的公共异常层级、错误上下文与敏感 URI 去敏；验证：运行异常层级单元测试并检查错误文本不含 userinfo/敏感 query。（Spec 01/02/03/04；模块：backend/src、testing）
- [x] 1.4 将最低 Python 版本放宽到 3.10，并同步构建、静态检查、文档与 lockfile；验证：使用 Python 3.10 执行完整测试。（Spec 04：最低 Python 版本兼容；模块：backend/src、testing、docs）
- [x] 1.5 配置并修复 BasedPyright LSP 诊断，按 80 字符 Ruff 限制重新格式化；验证：BasedPyright、Ruff、mypy 与测试全部通过。（Spec 04：Python 项目质量约束；模块：backend/src、testing）

## 2. Backend：仓库索引（Spec 01，依赖任务 1）

- [x] 2.1 实现 `skill_list.json` 数据解析、字段校验、`version=v1.0.0` 与 `addition_files=[]` 默认值；验证：运行合法、缺省字段及非法 JSON/字段测试。（Spec 01：读取仓库清单、应用清单默认值；模块：backend/src、testing）
- [x] 2.2 实现单仓库 `(name, version)` 唯一性校验并保留 repository 身份；验证：运行同仓库重复和跨仓库同名测试。（Spec 01：校验仓库内唯一性、合并多个仓库；模块：backend/src、testing）
- [x] 2.3 实现多仓库列表合并、`find_skills` 与带 repository 消歧的精确匹配逻辑；验证：运行零匹配、唯一匹配、多匹配歧义和指定仓库测试。（Spec 01：区分查找与精确获取；模块：backend/src、testing）

## 3. Backend：资源解析（Spec 02，依赖任务 1-2）

- [x] 3.1 实现 SRP 相对路径解析与 URI path 分段拼接，拒绝绝对路径、scheme/authority 注入及点路径逃逸；验证：运行斜杠组合、percent-encoding 与恶意路径参数化测试。（Spec 02：相对路径安全拼接；模块：backend/src、testing）
- [x] 3.2 实现基于清单 path 的 manifest、SKILL.md 和 addition_files 寻址，确保 version 不参与隐式拼接；验证：运行无版本目录、版本目录、自定义 stable path 和未声明附加文件测试。（Spec 02：基于声明路径定位、读取附加文件；模块：backend/src、testing）
- [x] 3.3 实现 SKILL.md frontmatter 解析、manifest 字段级优先合并及身份一致性校验；验证：运行字段覆盖、字段保留、缺失/损坏 manifest 和身份冲突测试。（Spec 02：合并 manifest 与 frontmatter；模块：backend/src、testing）

## 4. Backend：scheme 路由核心（Spec 03，依赖任务 1、3.1）

- [x] 4.1 实现 URI 结构化解析与重建，完整保留 query/fragment 且不由 SRP 核心解释 fragment；验证：运行完整 URI、缺少 scheme、IPv6 host 和编码路径测试。（Spec 03：结构化 URI；模块：backend/src、testing）
- [x] 4.2 定义同步 Transport protocol、实例级 registry、内置 scheme 映射和 scheme 匹配校验；验证：使用内存 transport 运行成功、unsupported scheme 与 scheme mismatch 测试。（Spec 03：路由内置 scheme、统一契约；模块：backend/src、testing）
- [x] 4.3 实现自定义 scheme 注册、显式覆盖开关及接收 ParsedURI 的 resolver hook；验证：运行自定义 `ipfs`、禁止无声覆盖和按 file host 分流测试。（Spec 03：注册自定义 scheme、支持自定义路由决策；模块：backend/src、testing）

## 5. Backend：内置 transport（Spec 03/04，依赖任务 4）

- [x] 5.1 实现 FileTransport，包括 repository root、符号链接解析后边界校验、not-found 与 I/O 错误映射；验证：运行临时目录正常读取、路径逃逸和符号链接逃逸测试。（Spec 03/04；模块：backend/src、testing）
- [x] 5.2 实现共享 http/https 的 HttpTransport，包括 TLS 校验、认证 header 配置、超时、重定向及响应大小限制；验证：运行本地 mock server 的成功、404、超时、重定向和超限测试。（Spec 03/04；模块：backend/src、testing）
- [x] 5.3 实现可选依赖 S3Transport，包括 bucket/prefix 解析、client/endpoint/region 注入及错误映射；验证：使用 fake client 运行成功、missing object 与 timeout 测试。（Spec 03/04；模块：backend/src、testing）
- [x] 5.4 实现可选依赖 GitTransport，将 `git://` repository 物化到受控缓存/临时目录，禁用 hooks 后复用安全文件读取；验证：运行本地 bare repository 的 ref/subdir、资源不存在及恶意参数测试。（Spec 03/04；模块：backend/src、testing）

## 6. Backend：统一 Python API（Spec 04，依赖任务 2-5）

- [x] 6.1 实现 SRPParser 构造、repository alias/稳定非敏感 id、列表/查找/获取与附加文件读取的端到端组合；验证：使用 file 与内存 transport 运行多仓库端到端测试。（Spec 01-04；模块：backend/src、testing）
- [x] 6.2 从包顶层导出公共模型、parser、transport 与异常，并验证内置 transport 可独立调用且错误类型稳定；验证：运行公共 import surface 和独立 transport contract 测试。（Spec 04：公共 API、scheme 专用读取器、公共错误；模块：backend/src、testing）
- [x] 6.3 在关键加载、路由和失败路径加入 `[skill_repository_protocol.模块名]` 日志并确保敏感字段去敏；验证：使用日志捕获测试检查关键事件、error level 与无凭证泄漏。（Spec 04：Python 项目质量约束；模块：backend/src、testing）

## 7. Testing：质量与验收（Spec 01-04，依赖任务 1-6）

- [x] 7.1 建立覆盖四个 specs 全部 Gherkin 场景的单元/集成测试追踪表并补齐边界测试；验证：执行 `uv run pytest` 全部通过。（Spec 01-04；模块：testing）
- [x] 7.2 配置并执行格式、lint、静态类型和覆盖率检查；验证：执行 `uv run ruff format --check .`、`uv run ruff check .`、项目类型检查命令及覆盖率命令全部通过。（Spec 04：Python 项目质量约束；模块：testing）
- [x] 7.3 对生产代码执行静态验收，禁止 `print` 和用于运行时校验的 `assert`；验证：通过 Ruff 规则及 `rg -n '\b(print|assert)\b' src` 人工复核零违规。（Spec 04：Python 项目质量约束；模块：backend/src、testing）
- [x] 7.4 执行 file、HTTP、S3 fake client 与本地 Git 的完整验收矩阵，确认单个 transport 失败不影响其他仓库；验证：执行标记后的集成测试集合并保存测试结果。（Spec 03/04；模块：testing）

## 8. Docs：协议与使用文档（Spec 01-04，依赖任务 6）

- [x] 8.1 更新 README 的 Python 安装、单/多仓库、repository 消歧、资源路径和 version/path 解耦示例；验证：逐项对照 Spec 01/02 并运行文档示例测试。（Spec 01/02/04；模块：docs）
- [x] 8.2 编写 file、HTTP(S)、S3、Git 和自定义 scheme/resolver 的配置与安全说明；验证：逐项对照 Spec 03 并由示例测试执行关键代码片段。（Spec 03/04；模块：docs）
- [x] 8.3 更新 TODO 中 Python 支持状态与明确 Go 独立仓库边界；验证：人工核对 proposal Non-goals，确保不声明未实现能力。（Spec 04；模块：docs）
- [x] 8.4 创建代码接口与模块结构文档，并配置后续大修改的同步更新规则；验证：复核 docs/ARCHITECTURE.md 与公共 API 一致并通过 OpenSpec 校验。（Spec 03/04；模块：docs、openspec）
- [x] 8.5 精简 README，在原协议说明基础上仅增加 Quick Start、Usage 与代码结构文档入口；验证：复核示例与公共 API 一致并运行文档示例测试。（Spec 01-04；模块：docs、testing）
- [x] 8.6 将 manifest 资源改为 JSON，并使 FileTransport 在文件缺失时从 SKILL.md YAML frontmatter 生成 JSON；验证：运行 manifest 合并、转换、错误和全量质量测试。（Spec 02/03；模块：backend/src、testing、docs）
- [x] 8.7 将公共异常消息和 error 日志统一为英文；验证：扫描生产代码的 raise/error 路径并运行完整质量测试。（Spec 04：公共错误；模块：backend/src、testing）

## 9. Frontend / Database / DevOps：范围确认

- [x] 9.1 确认本 change 未引入 frontend、database、migration 或部署资源变更；验证：检查最终 diff 仅包含 Python backend、testing、docs 与项目依赖配置。（Proposal Non-goals；模块：frontend、database、devops）
