## Why

部分 skill 仓库在清单中将目录型 `path` 写成 `example/`，当前解析器会把末尾斜杠视为空路径段并拒绝整个清单。目录路径带或不带末尾斜杠语义等价，解析器需要兼容这种常见表示，同时继续阻止路径逃逸和含糊的中间空路径段。

## What Changes

- 允许 `skill_list.json` 清单条目的 `path` 带一个或多个末尾正斜杠，并将其规范化为不带末尾斜杠的安全相对路径。
- 保持 `path` 的其他安全约束不变：仍拒绝绝对路径、反斜杠、scheme、`.`、`..` 和中间空路径段。
- 不放宽 `addition_files` 或调用者传入资源相对路径的校验，避免目录兼容规则改变文件路径契约。
- 增加带末尾斜杠的清单解析、资源定位和非法中间双斜杠回归场景。
- 关键假设与歧义取舍：用户所称 manifest 指仓库的 `skill_list.json` 清单条目；末尾斜杠只表达目录边界，不属于 skill 的逻辑 path。采用解析边界规范化是兼容现有数据的最小改动。

## Capabilities

### New Capabilities

- `05-manifest-path-normalization`: 定义清单 `path` 的末尾斜杠兼容、规范化结果及保持不变的路径安全边界。

### Modified Capabilities

无。当前仓库尚无已同步的主规格；相关既有行为仍位于先前 change 中。

## Impact

- 受影响模块：`src/skill_repository_protocol` 的清单解析与路径规范化边界、`testing` 中的路径及解析器测试、README/文档中的 path 说明。
- API 兼容性：向后兼容；原有合法输入结果不变，原先被拒绝的末尾斜杠清单 path 将被接受并规范化。
- 配置变更风险：无新增配置；仅扩大清单 `path` 的兼容输入集合。
- 数据迁移风险：无；不要求仓库维护者重写现有清单。
- 依赖与系统：不新增依赖，不改变 transport、公共类型或持久化数据格式。
- `docs/ARCHITECTURE.md`：不涉及模块边界、公共 API 或核心数据模型的大修改，预计无需更新；若实现检查发现其中对空路径段的描述需要区分末尾边界，则仅做行为说明修订。

## Non-goals

- 不接受开头斜杠、反斜杠、中间连续斜杠或点路径段。
- 不改变 `addition_files`、`read_additional_file()` 参数或 transport 相对资源路径的校验。
- 不根据 name 或 version 推导、补全或改写 path。
- 不改变 URL、file、S3 或 Git transport 的路径拼接规则。

## Change Metadata

- 创建日期：2026-07-26
- 当前状态：active
- 关联需求来源：用户提出“manifest 中的 path 兼容后缀斜杠”
