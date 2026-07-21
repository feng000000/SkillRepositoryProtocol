# Skill Repository Protocol

Skill 存储库协议 (SRP) 定义了 怎样通过一个 skill URL 来访问skill;
目的是为了 将 skill 与文件系统解耦, 允许 `http://`, `https://`, `s3://` 这样的协议访问.

## 基本结构

SRP 的基本结构为 URI 的基本结构

```
scheme://[userinfo@]host[:port]/path/to/resource?query=value#fragment
```

例如
- `file:///root/skills/`
- `https://example.com/skills/`


## URI 需提供的资源
(URI部分用 `${URI}` 代替)
1. `${URI}/skill_list.jsonl`
    ```json
    {
        "version": "1", // skill_list 结构版本, 默认为1
        "skill_list": [
            {
                // skill 名称, 应与 SKILL.md 中的name相符
                "name": "skill name",

                // skill 的描述, 应与 SKILL.md 中的description 相符
                "desc": "This is a example skill",

                // 访问 SKILL.md 的路径
                "path": "/example-skill",

                // 可选的附加文件路径, 默认为 []
                // 文件访问方式为 `${URI}/example-skill/scripts/tool.py`
                "addition_files": [
                    "scripts/tool.py",
                    "reference/docs.md",
                    "assets/template.pdf"
                ],

                // skill 已有版本
                // 可选, 列表元素为语义化版本字符串, 默认为 ["v1.0.0"]
                "versions": ["v1.0.0"]
            }
        ]
    }
    ```

2. meta.yaml (`${URI}/example-skill/meta.yaml`)
    应返回 example-skill 对应的 SKILL.md 的 meta yaml 部分

    格式参考: [SKILL.md format](https://agentskills.io/specification?utm_source=chatgpt.com#skill-md-format)

3. SKILL.md (`${URI}/example-skill/SKILL.md`)
    应返回 example-skill 对应的 SKILL.md

    格式参考: [SKILL.md format](https://agentskills.io/specification?utm_source=chatgpt.com#skill-md-format)

4. addition files (`${URI}/example-skill/script/tool.py`)
    应返回 skill_list.json 中定义的 addition_files 的具体文件内容


## 错误

获取资源错误 委托给具体的 scheme 类型, SRP 保持简单, 只定义需要提供的资源

## scheme 支持
- `file://`
- `http://`, `https://`
- `s3://`
- `git://`
- [ ] 自定义 scheme 支持

## 解析器语言支持

- [ ] python
- [ ] golang
