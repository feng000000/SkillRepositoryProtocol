## Context

`parse_skill_list()` 目前将清单条目的 `path` 与 `addition_files` 都交给通用的 `normalize_relative_path()`。该函数通过拒绝任意空路径段保证资源路径安全，因此 `example/` 会因为末尾空段而失败。清单 `path` 表示 skill 目录，而 `addition_files` 和 transport 参数表示具体资源路径，两者对末尾斜杠的语义并不相同。

约束是兼容目录型清单 path，但不能让通用资源路径校验接受中间双斜杠、绝对路径或逃逸段，也不能改变规范化后的 `SkillRef.path` 契约。

## Goals / Non-Goals

**Goals:**

- 接受清单条目中带一个或多个末尾正斜杠的非空相对 `path`。
- 在构造 `SkillRef` 前移除末尾斜杠，使后续资源拼接继续接收现有规范形式。
- 保持所有既有路径安全约束和异常类型。

**Non-Goals:**

- 不允许中间连续斜杠、点路径段、反斜杠、scheme 或绝对路径。
- 不兼容 `addition_files`、transport 参数或公共 `normalize_relative_path()` 调用中的末尾斜杠。
- 不改变公共数据模型、transport 或 URI 拼接算法。

## Architecture

变更位于清单输入到通用路径规范化之间的边界：

`skill_list.json path` → 清单目录 path 预处理 → `normalize_relative_path()` → `SkillRef.path`

通用安全规范化与后续 `join_relative_paths()`、`append_uri_path()` 保持不变。该设计不引入新模块、依赖或扩展点，也不改变主要调用链，因此无需结构性更新 `docs/ARCHITECTURE.md`；仅在现有文档表述与新行为冲突时修订文字。

## Components

- `parser.py`：在解析清单 `path` 时剥离末尾正斜杠，然后调用现有安全规范化函数。该处理只应用于 `path` 字段。
- `paths.py`：优先保持通用函数行为不变；若实现需要辅助函数，应使其用途明确为目录型清单 path，而不是全局放宽规则。
- 测试：覆盖单个及多个末尾斜杠、规范化后的资源读取路径，以及中间双斜杠和纯斜杠输入仍失败。
- README/架构说明：明确 `path` 可带末尾斜杠但内部不保留。

与现有模块的集成点是 `parse_skill_list()` 构造 `SkillIndexEntry` 之前；它补充输入兼容，不替代通用路径校验。

## APIs

公共 Python API、函数签名和异常层级均不改变。行为变化仅体现在 `SRPParser` 读取清单时：

- `path: "example/"` 与 `path: "example"` 产生相同的 `SkillRef.path == "example"`。
- 不合法 path 继续抛出 `InvalidPathError`；清单 JSON 结构错误继续遵循现有 `ManifestError` 行为。

本变更不涉及 HTTP API、认证或请求响应字段。

## Data Model

不新增或修改字段。输入清单允许目录边界末尾斜杠，内存中的 `SkillIndexEntry.path` 与 `SkillRef.path` 仍保存无末尾斜杠的安全相对路径。无数据库或持久化迁移。

## Decisions

1. **只在清单 `path` 边界剥离末尾斜杠。** 这能表达目录 path 的兼容语义，同时让 `addition_files` 和资源读取参数保持严格。替代方案是修改 `normalize_relative_path()` 全局接受末尾斜杠，但会无意扩大公共函数及 transport 的输入契约。
2. **剥离后继续调用现有安全校验。** 预处理不替代验证，`a//b/` 在去除尾部斜杠后仍因中间空段失败。替代方案是过滤所有空段，但会把含糊或潜在恶意路径静默改写。
3. **规范化结果不保留末尾斜杠。** 这避免影响唯一性比较、声明文件匹配和后续路径拼接。保留原始文本会让同一目录出现两种内部表示。

上述方案只触及清单解析边界，是满足需求且不扩展其他路径契约的最小实现路径。

## Error Handling and Security

- 剥离后为空的值（如 `/` 或 `///`）必须失败，不得被视为仓库根目录。
- 开头斜杠、中间空段、`.`、`..`、反斜杠及 scheme 仍由现有安全规范化拒绝。
- 不在错误日志中新增清单敏感信息；沿用现有异常传播和日志策略。
- 无高风险动作、权限变化或审计要求；失败时解析终止，不执行底层资源读取。

## Risks / Trade-offs

- [预处理放置过于通用，意外放宽资源文件路径] → 将逻辑限定在 `parse_skill_list()` 的 `path` 字段，并用 `addition_files` 回归测试锁定边界。
- [多个末尾斜杠是否应接受存在歧义] → 统一视为重复目录分隔边界并规范化；中间重复分隔仍拒绝。
- [文档仍声称所有空路径段非法] → 将说明细化为清单目录 path 的末尾边界例外，通用资源路径规则不变。

## Migration Plan

无需数据迁移。发布后现有合法清单行为不变，带末尾斜杠的清单开始可用。回滚只需恢复原清单解析逻辑；已规范化 path 不会写回或持久化，因此无回滚数据处理。

## Open Questions

无。需求按“manifest 指 `skill_list.json` 清单条目”解释；若未来需要让其他路径字段接受目录尾斜杠，应作为独立契约变更评估。
