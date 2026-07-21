## ADDED Requirements

### Requirement: 结构化 URI
系统 MUST 将 SRP URI 解析为 scheme、userinfo、host、port、path、query 和 fragment，并保留未被 SRP 核心解释的 query 与 fragment。

#### Scenario: 完整 URI 结构化
- **GIVEN** SRP URI 同时包含 authority、port、path、query 与 fragment
- **WHEN** 系统解析该 URI
- **THEN** 系统返回各部分可独立访问的结构化 URI 且不赋予 fragment 业务含义

#### Scenario: URI 缺少 scheme
- **GIVEN** 输入 URI 未声明 scheme
- **WHEN** 系统尝试解析并路由
- **THEN** 系统抛出无效 URI 错误

### Requirement: 路由内置 scheme
系统 SHALL 内置 `file`、`http`、`https`、`s3` 和 `git` scheme 的资源读取器，并按结构化 URI 的 scheme 路由。

#### Scenario: 路由 HTTPS 仓库
- **GIVEN** 输入 URI 的 scheme 为 `https`
- **WHEN** 系统请求仓库资源
- **THEN** 系统使用 HTTP(S) 资源读取器读取该资源

#### Scenario: 不支持的 scheme
- **GIVEN** 输入 URI 的 scheme 未内置且未注册
- **WHEN** 系统请求仓库资源
- **THEN** 系统抛出不支持 scheme 错误且不尝试其他读取器

### Requirement: scheme 读取器遵守统一契约
每个 scheme 读取器 MUST 接收结构化仓库 URI 与安全相对资源路径，并返回资源字节或统一分类的资源错误，同时保留底层错误作为原因。

#### Scenario: 成功读取资源
- **GIVEN** 已选中的 scheme 读取器可以访问目标资源
- **WHEN** SRP 核心请求相对资源路径
- **THEN** 读取器返回原始资源字节供 SRP 核心解析

#### Scenario: 底层读取超时
- **GIVEN** scheme 底层服务在配置的超时时间内未响应
- **WHEN** 读取器访问资源
- **THEN** 系统抛出统一超时错误并保留底层异常上下文

### Requirement: 注册自定义 scheme
系统 SHALL 允许使用者在 parser 实例上注册自定义 scheme 读取器；覆盖内置 scheme MUST 通过显式覆盖选项完成。

#### Scenario: 使用自定义 scheme
- **GIVEN** 使用者为 `ipfs` 注册了符合统一契约的读取器
- **WHEN** 系统读取 `ipfs` URI 的仓库资源
- **THEN** 系统将请求路由到已注册的读取器

#### Scenario: 禁止无声覆盖
- **GIVEN** `https` 已存在内置读取器
- **WHEN** 使用者未声明显式覆盖而再次注册 `https`
- **THEN** 系统抛出 scheme 已注册错误并保留原读取器

### Requirement: 支持自定义路由决策
系统 SHALL 允许使用者提供接收结构化 URI 的 resolver，以便根据 host 等字段选择已有或自定义读取器。

#### Scenario: 根据 file host 改写路由
- **GIVEN** resolver 将带特定 host 的 `file` URI 映射到自定义读取器
- **WHEN** 系统处理该结构化 URI
- **THEN** 系统使用 resolver 返回的读取器且仍以原结构化 URI 作为读取上下文
