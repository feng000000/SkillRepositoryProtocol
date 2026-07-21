## ADDED Requirements

### Requirement: 读取仓库清单
系统 SHALL 从每个仓库根 URI 的 `skill_list.json` 读取清单，并将清单条目解析为带 repository 身份的 skill 引用。

#### Scenario: 成功读取单仓库清单
- **GIVEN** 仓库根 URI 下存在合法的 `skill_list.json`
- **WHEN** 使用者读取该仓库的 skill 列表
- **THEN** 系统返回包含 repository、name、规范化 version 和 path 的 skill 引用列表

#### Scenario: 清单资源不存在
- **GIVEN** 仓库根 URI 下不存在 `skill_list.json`
- **WHEN** 使用者读取该仓库的 skill 列表
- **THEN** 系统抛出包含仓库上下文的资源不存在错误

### Requirement: 应用清单默认值
系统 MUST 将缺省的 skill `version` 规范化为 `v1.0.0`，并将缺省的 `addition_files` 规范化为空列表；系统 MUST NOT 根据 version 推导或改写 path。

#### Scenario: 缺省可选字段
- **GIVEN** skill 条目提供 name、description 和 path，但未提供 version 与 addition_files
- **WHEN** 系统解析该条目
- **THEN** 系统得到 version 为 `v1.0.0`、addition_files 为空且 path 保持原语义的 skill 引用

### Requirement: 校验仓库内唯一性
系统 MUST 要求同一仓库内规范化后的 `(name, version)` 唯一。

#### Scenario: 同仓库重复条目
- **GIVEN** 同一仓库包含两个 name 相同且规范化 version 相同的条目
- **WHEN** 系统解析仓库清单
- **THEN** 系统抛出重复 skill 错误并标识冲突的 name、version 与 repository

### Requirement: 合并多个仓库
系统 SHALL 保留不同仓库中具有相同 name 和 version 的 skill，并在每个结果中保留 repository 身份。

#### Scenario: 跨仓库存在同名同版本 skill
- **GIVEN** 两个仓库均声明 `formatter@v1.0.0`
- **WHEN** 系统合并两个仓库的 skill 列表
- **THEN** 系统返回两个具有不同 repository 身份的 skill 引用且不报告重复错误

### Requirement: 区分查找与精确获取
系统 SHALL 允许查找操作返回全部匹配项；精确获取在未指定 repository 且匹配多个仓库时 MUST 抛出歧义错误。

#### Scenario: 唯一匹配的简化获取
- **GIVEN** 已加载仓库中只有一个 skill 匹配给定 name 和 version
- **WHEN** 使用者未指定 repository 执行精确获取
- **THEN** 系统返回唯一匹配的 skill

#### Scenario: 多仓库匹配导致歧义
- **GIVEN** 多个仓库中存在相同 name 和 version 的 skill
- **WHEN** 使用者未指定 repository 执行精确获取
- **THEN** 系统抛出歧义错误并返回可用于消歧的 repository 标识

#### Scenario: 指定仓库消歧
- **GIVEN** 多个仓库中存在相同 name 和 version 的 skill
- **WHEN** 使用者指定其中一个 repository 执行精确获取
- **THEN** 系统仅返回该 repository 中的匹配项
