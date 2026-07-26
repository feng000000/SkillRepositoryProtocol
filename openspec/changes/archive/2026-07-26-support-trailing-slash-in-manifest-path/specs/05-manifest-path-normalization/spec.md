## ADDED Requirements

### Requirement: 清单目录 path 兼容末尾斜杠

系统 SHALL 接受 `skill_list.json` 条目中带一个或多个末尾正斜杠的非空安全相对 `path`，并 MUST 在构造 skill 引用前将其规范化为不带末尾斜杠的形式。

#### Scenario: 规范化单个末尾斜杠

- **GIVEN** 合法清单条目的 `path` 为 `example/`
- **WHEN** 系统解析该仓库清单
- **THEN** 系统返回 `path` 为 `example` 的 skill 引用

#### Scenario: 规范化多个末尾斜杠

- **GIVEN** 合法清单条目的 `path` 为 `stable/example///`
- **WHEN** 系统解析该仓库清单
- **THEN** 系统返回 `path` 为 `stable/example` 的 skill 引用

#### Scenario: 使用规范化 path 定位资源

- **GIVEN** 清单条目的 `path` 为 `example/` 且对应目录包含 skill 资源
- **WHEN** 系统加载该 skill
- **THEN** 系统从 `${repository URI}/example/manifest.json` 和 `${repository URI}/example/SKILL.md` 读取资源，且生成的路径不包含重复分隔语义

### Requirement: 末尾斜杠兼容不得放宽路径安全边界

系统 MUST 在处理清单 `path` 的末尾斜杠后继续执行相对路径安全校验，并 MUST 拒绝空目录、绝对路径、反斜杠、scheme、`.`、`..` 或中间空路径段；系统 MUST NOT 将该兼容行为应用于 `addition_files` 或资源读取参数。

#### Scenario: 拒绝只有斜杠的 path

- **GIVEN** 清单条目的 `path` 为 `///`
- **WHEN** 系统解析该仓库清单
- **THEN** 系统抛出非法路径错误且不执行 skill 资源读取

#### Scenario: 拒绝中间连续斜杠

- **GIVEN** 清单条目的 `path` 为 `stable//example/`
- **WHEN** 系统解析该仓库清单
- **THEN** 系统抛出非法路径错误且不将其静默规范化为 `stable/example`

#### Scenario: addition file 的严格校验保持不变

- **GIVEN** 清单条目的 `addition_files` 包含 `scripts/`
- **WHEN** 系统解析该仓库清单
- **THEN** 系统仍抛出非法路径错误
