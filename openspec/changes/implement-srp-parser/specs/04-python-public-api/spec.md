## ADDED Requirements

### Requirement: 提供类型化 Python 公共 API
Python 包 SHALL 暴露带完整类型注解的 SRPParser、结构化 URI、repository、skill 引用、skill 内容、scheme 读取器接口和公共异常类型。

#### Scenario: 使用统一 parser
- **GIVEN** 使用者构造 SRPParser 并传入一个或多个仓库 URI
- **WHEN** 使用者调用列表、查找或精确获取方法
- **THEN** 系统返回声明的类型化领域对象或公共异常

### Requirement: 暴露 scheme 专用读取器
Python 包 SHALL 允许使用者独立构造和调用各个内置 scheme 读取器，并 MUST 校验输入 URI 的 scheme 是否属于该读取器支持范围。

#### Scenario: 独立使用 file 读取器
- **GIVEN** 使用者构造 file scheme 读取器并传入 file URI
- **WHEN** 使用者请求合法相对资源
- **THEN** 读取器返回对应文件内容

#### Scenario: scheme 与读取器不匹配
- **GIVEN** 使用者向 file scheme 读取器传入 HTTPS URI
- **WHEN** 读取器校验输入
- **THEN** 系统抛出 scheme 不匹配错误

### Requirement: 公共错误可供调用者分类处理
Python 包 MUST 提供可区分参数、URI、scheme、路径、清单、重复、歧义、元数据、资源不存在、超时和底层读取失败的异常层级。

#### Scenario: 调用者捕获歧义错误
- **GIVEN** 精确获取匹配多个仓库
- **WHEN** 系统抛出歧义错误
- **THEN** 调用者可以通过公共异常类型捕获错误并读取候选 repository 信息

### Requirement: Python 项目质量约束
生产代码 MUST 支持 Python 3.10 及以上版本，MUST 使用类型注解、中文 Google Style Docstring 与项目命名日志，MUST NOT 使用 `print` 或 `assert` 执行诊断和运行时校验，并 SHALL 通过 `uv` 与 `pyproject.toml` 管理依赖。

#### Scenario: 最低 Python 版本兼容
- **GIVEN** 项目安装在 Python 3.10 环境
- **WHEN** 同步项目依赖并运行完整测试
- **THEN** 项目成功安装且所有测试通过

#### Scenario: 自动化质量验收
- **GIVEN** Python 包实现完成
- **WHEN** 执行项目规定的格式、静态类型、静态扫描和测试命令
- **THEN** 所有检查通过且生产代码中不存在被禁止的 print 或 assert 用法
