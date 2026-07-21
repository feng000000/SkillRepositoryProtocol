## ADDED Requirements

### Requirement: 基于声明路径定位 skill 资源
系统 SHALL 在 `${repository URI}/{path}/` 下定位 `manifest.json` 与 `SKILL.md`，且 MUST NOT 根据 name 或 version 隐式修改 path。

#### Scenario: 无版本目录的合法资源
- **GIVEN** skill 的 path 为 `example-skill` 且 version 缺省
- **WHEN** 使用者读取该 skill
- **THEN** 系统读取 `${repository URI}/example-skill/manifest.json` 和 `${repository URI}/example-skill/SKILL.md`

#### Scenario: path 自行包含版本目录
- **GIVEN** skill 的 path 为 `example-skill/v1.2.0` 且 version 为 `v1.2.0`
- **WHEN** 使用者读取该 skill
- **THEN** 系统读取 `${repository URI}/example-skill/v1.2.0/` 下的资源而不再次添加版本

### Requirement: 相对路径安全拼接
系统 MUST 将 path 与 addition_files 作为相对路径安全拼接到父资源 URI，并拒绝绝对路径、authority、scheme、`.`、`..` 或归一化后逃逸父路径的输入。

#### Scenario: 处理边界斜杠
- **GIVEN** repository URI、path 和资源名的边界包含或缺少斜杠
- **WHEN** 系统拼接资源 URI
- **THEN** 系统生成只有一个路径分隔语义且保留 repository base path 的 URI

#### Scenario: 拒绝路径逃逸
- **GIVEN** path 或 addition_file 包含 `..` 以访问父目录
- **WHEN** 系统解析该资源路径
- **THEN** 系统抛出非法路径错误且不执行底层资源读取

### Requirement: 读取附加文件
系统 SHALL 将每个 addition_file 路径叠加在 `${repository URI}/{path}/` 后读取，并限制调用者只能读取清单声明的附加文件。

#### Scenario: 读取已声明附加文件
- **GIVEN** skill path 为 `example-skill` 且 addition_files 包含 `scripts/tool.py`
- **WHEN** 使用者读取该附加文件
- **THEN** 系统读取 `${repository URI}/example-skill/scripts/tool.py`

#### Scenario: 拒绝未声明附加文件
- **GIVEN** 请求的相对文件路径不在 skill 的 addition_files 中
- **WHEN** 使用者尝试读取该文件
- **THEN** 系统抛出未声明资源错误且不执行底层资源读取

### Requirement: 合并 manifest 与 frontmatter
系统 SHALL 解析 `SKILL.md` frontmatter，并以 `manifest.json` 中存在的字段逐字段覆盖 frontmatter；身份字段与清单冲突时 MUST 显式失败。

#### Scenario: FileTransport 生成 JSON manifest
- **GIVEN** file 仓库的 skill 目录包含带 YAML frontmatter 的 `SKILL.md`，但不存在 `manifest.json`
- **WHEN** 系统通过 FileTransport 读取该 skill 的 `manifest.json`
- **THEN** 系统返回由 frontmatter 转换得到的 UTF-8 JSON 内容

#### Scenario: manifest 字段覆盖 frontmatter
- **GIVEN** manifest 与 frontmatter 都声明 description 且值不同，同时 frontmatter 还声明 license
- **WHEN** 系统构造有效 skill 元数据
- **THEN** description 使用 manifest 的值且 license 保留 frontmatter 的值

#### Scenario: 身份字段不一致
- **GIVEN** 有效元数据中的 name 与 skill_list 条目的 name 不一致
- **WHEN** 系统加载 skill
- **THEN** 系统抛出元数据不一致错误并标识冲突来源
