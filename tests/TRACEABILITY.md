# Spec 场景测试追踪

| Spec | 行为范围 | 主要测试文件 |
|---|---|---|
| 01-repository-index | 清单默认值、重复、跨仓库合并、查找与消歧 | `test_index_parser.py` |
| 02-skill-resource-resolution | path/version 解耦、路径安全、manifest 合并、附加文件 | `test_models_paths.py`、`test_index_parser.py` |
| 03-scheme-routing | URI 结构化、注册与 resolver、file/HTTP/S3/Git | `test_models_paths.py`、`test_transports.py` |
| 04-python-public-api | 包导出、异常、日志、类型与静态质量 | `test_transports.py`、Ruff、mypy |

完整验收命令：

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

