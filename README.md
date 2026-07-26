# Skill Repository Protocol

Skill 存储库协议（SRP）定义怎样通过一个 skill URL 访问 skill。
目的是将 skill 与文件系统解耦，允许通过 `file://`、`http://`、
`https://`、`s3://`、`git://` 等 scheme 访问。

- [golang 实现](https://github.com/feng000000/srp-parser-golang)

## 基本结构

SRP 使用 URI 的基本结构：

```text
scheme://[userinfo@]host[:port]/path/to/resource?query=value#fragment
```

例如：

- `file:///root/skills/`
- `https://example.com/skills/`

需实现 endpoint:
- `${URI}/skill_list.json`
- `${URI}/{path}/manifest.json`
- `${URI}/{path}/SKILL.md`
- `${URI}/{path}/{addition_file}` (取决于skill_list 中的定义)

## URI 需提供的资源

以下使用 `${URI}` 表示仓库根 URI。

1. `${URI}/skill_list.json`

   ```jsonc
   {
     "version": "1",
     "skill_list": [
       {
         "name": "example-skill",
         "description": "This is an example skill",
         "path": "example-skill/v1.0.0",
         "addition_files": [
           "scripts/tool.py",
           "references/docs.md",
           "assets/template.pdf"
         ],
         "version": "v1.0.0"
       }
     ]
   }
   ```

   - `name` 应与 `SKILL.md` 中的 name 相符。
   - `description` 应与 skill 元数据中的 description 相符。
   - `path` 是拼接到 `${URI}/` 后的相对目录路径。允许一个或多个末尾
     正斜杠；解析器会将其移除，因此 `example/` 与 `example` 等价。
     中间连续斜杠、绝对路径、反斜杠及 `.`、`..` 路径段仍然非法。
   - `addition_files` 可选，默认值为 `[]`；其路径拼接在
     `${URI}/{path}/` 后。它表示具体资源文件，不接受末尾斜杠。
   - `version` 可选，默认值为 `v1.0.0`；版本由 skill 自己管理，
     解析器不会根据 version 修改 path。

2. `manifest.json`（`${URI}/{path}/manifest.json`）

   返回 skill 的 manifest。字段与 `SKILL.md` frontmatter 重复时，
   `manifest.json` 优先。
   ```jsonc
    {
        "name": "example-skill",
        "description": "This is an example skill",
        "path": "example-skill/v1.0.0",
        "addition_files": [
            "scripts/tool.py",
            "references/docs.md",
            "assets/template.pdf"
        ],
        "version": "v1.0.0"
    }
   ```

3. `SKILL.md`（`${URI}/{path}/SKILL.md`）

   返回对应的 `SKILL.md`。

4. Addition files（`${URI}/{path}/{addition_file}`）

   返回 `skill_list.json` 中声明的附加文件。

`SKILL.md` 格式参考
[Agent Skills specification](https://agentskills.io/specification#skill-md-format)。

## Quick Start

项目要求 Python 3.10 或更高版本，使用 uv 管理依赖：

```bash
uv sync
```

读取本地 SRP 仓库：

```python
from skill_repository_protocol import SRPParser

parser = SRPParser(["file:///root/skills"])

skills = parser.list_skills()
skill = parser.get_skill("example-skill", version="v1.0.0")
```

## Usage

### 多仓库

可以为仓库指定 alias，以便同名 skill 消歧：

```python
from skill_repository_protocol import SRPParser

parser = SRPParser(
    {
        "official": "https://example.com/skills",
        "internal": "s3://company-skills/production",
    }
)

matches = parser.find_skills("example-skill", version="v1.0.0")
skill = parser.get_skill(
    "example-skill",
    version="v1.0.0",
    repository="official",
)
```

同一仓库内同名同版本 skill 会报错；不同仓库可以存在同名同版本
skill。未指定 repository 且匹配多个仓库时，`get_skill()` 会抛出
`AmbiguousSkillError`。

### 读取附加文件

```python
content = parser.read_additional_file(
    "example-skill",
    "scripts/tool.py",
    version="v1.0.0",
    repository="official",
)
```

### 自定义 scheme

自定义 Transport 实现以下接口即可注册：

```python
class CustomTransport:
    schemes = frozenset({"custom"})

    def read(self, repository, relative_path):
        return b"resource"


parser = SRPParser(
    ["custom://repository/skills"],
    transports={"custom": CustomTransport()},
)
```

## 错误处理

获取资源产生的底层错误由具体 scheme 的 Transport 处理。SRP 保持简单，
只定义仓库需要提供的资源与统一公共异常。

## Scheme 支持

- [x] `file://`
- [x] `http://`、`https://`
- [x] `s3://`
- [x] `git://`
- [x] 自定义 scheme

## 解析器SDK 支持

- [x] Python: 本仓库
- [x] Go: [srp-parser-golang](https://github.com/feng000000/srp-parser-golang)

## 代码结构

模块职责、公共接口、调用链与扩展方式见
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。
