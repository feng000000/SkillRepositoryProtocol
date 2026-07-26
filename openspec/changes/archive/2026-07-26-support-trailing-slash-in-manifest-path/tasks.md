## 1. Backend：清单 path 规范化

- [x] 1.1 在 `src/skill_repository_protocol/parser.py` 的清单 `path` 解析边界实现末尾正斜杠剥离，并继续调用现有安全路径校验；对应 `05-manifest-path-normalization` 的两个 Requirement。验证：运行 `uv run pytest tests/test_index_parser.py -q`。
- [x] 1.2 复核 `addition_files`、公共 `normalize_relative_path()` 与各 transport 的行为未被放宽，生产代码不使用 `print` 或 `assert`；对应安全边界 Requirement。验证：运行 `rg -n '\\b(print|assert)\\b' src/skill_repository_protocol` 并运行 `uv run pytest tests/test_models_paths.py tests/test_transports.py -q`。

## 2. Testing：规格场景与回归

- [x] 2.1 在 `tests/test_index_parser.py` 添加单个及多个末尾斜杠规范化测试，并验证规范化后的 `SkillRef.path` 与资源加载路径；对应成功场景“规范化单个末尾斜杠”“规范化多个末尾斜杠”“使用规范化 path 定位资源”。验证：运行 `uv run pytest tests/test_index_parser.py -q`。
- [x] 2.2 在 `tests/test_index_parser.py` 或 `tests/test_models_paths.py` 添加纯斜杠、中间连续斜杠和末尾斜杠 `addition_files` 的失败测试；对应安全边界 Requirement 的三个失败场景。验证：运行 `uv run pytest tests/test_index_parser.py tests/test_models_paths.py -q`。

## 3. Documentation：清单契约

- [x] 3.1 更新 `README.md`，说明清单 `path` 可带末尾正斜杠且内部会规范化，同时列明中间连续斜杠仍非法；对应 `05-manifest-path-normalization` 全部 Requirements。验证：人工核对 README 示例与规格一致。
- [x] 3.2 复核 `docs/ARCHITECTURE.md` 的路径安全说明；仅当现有“空路径段”表述与清单末尾边界例外冲突时更新相关文字，不改变模块或数据流。验证：运行 `rg -n 'path|路径段|斜杠' README.md docs/ARCHITECTURE.md` 并人工核对。

## 4. Quality：完整验收

- [x] 4.1 运行项目完整自动化检查，确认原有合法路径、恶意路径、所有 transport 与清单解析无回归；对应 `05-manifest-path-normalization` 全部 Requirements。验证：运行 `uv run pytest` 以及 `uv run ruff check .`。
- [x] 4.2 校验 OpenSpec change 并对照每个 Given/When/Then 场景确认测试可追溯。验证：运行 `openspec validate support-trailing-slash-in-manifest-path`。

## 5. Frontend / Database

- [x] 5.1 确认本 change 不涉及 frontend 与 database，不创建前端任务或数据库 migration；对应 proposal 的 Non-goals 与 Data Model。验证：检查最终 diff 仅包含 backend、testing、docs 与 change 状态更新。
