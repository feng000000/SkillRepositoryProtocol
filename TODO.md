# 实现解析器

解析器需要提供一个 包/模块/类, 使用者传入 SRP uri, 即可通过 解析器 处理对应 scheme 获取资源

解析器支持传入 uri 列表, 获取 skill_list 时拼接 结果返回列表

需要有一个通用的 SRPParser 方便用户直接 传入uri列表-获取资源, 内部可以分发给不同 scheme 的解析器

需要暴露各个 scheme 的解析器, 方便用户指定; 内部需要判断 传入 uri list 的 scheme 是否正确


需要方便用户重写 解析器来实现自定义逻辑,
例如 file://host/path/to/resource 这样的 uri, 用户可能会希望根据 host 做对应的分流, 调用不同的 http 解析器或 s3 解析器; 这种情况下 需要实现的钩子函数需要传入结构化后的 uri, 并暴露各个 scheme 的解析器方便各个用户调用

也支持用户注册自定义 scheme 的解析器
