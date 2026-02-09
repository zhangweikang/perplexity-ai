# Perplexity AI - 示例代码 (Examples)

此目录包含了展示 Perplexity AI 库各项功能的实用示例程序。

## 可用示例 (Available Examples)

### 1. 基础用法 (`basic_usage.py`)

快速上手的最简单方法。

- 创建客户端 (Client)
- 发起基础查询
- 使用不同的搜索源 (web, scholar, social)

```bash
python examples/basic_usage.py
```

### 2. 流式输出 (`streaming.py`)

实时接收生成的响应内容。

- 分块 (Chunks) 接收流式响应
- 进度跟踪
- 实时展示结果

```bash
python examples/streaming.py
```

### 3. 异步用法 (`async_usage.py`)

利用非阻塞操作获得更佳性能。

- 单个异步查询
- 多个并发查询
- 异步流式输出

```bash
python examples/async_usage.py
```

### 4. 文件上传 (`file_upload.py`)

上传文档进行分析和问答。

- 文本文件上传
- PDF 文件上传
- 多文件同时上传
- **注意**: 需要带有 cookies 的账号

```bash
python examples/file_upload.py
```

### 5. 账号创建 (`account_creation.py`)

自动创建账号以获得无限额度。

- 通过 Emailnator 自动创建账号
- 开启增强模式 (pro, reasoning)
- **注意**: 需要 Emailnator 的 cookies

```bash
python examples/account_creation.py
```

### 6. 批量处理 (`batch_processing.py`)

高效处理大量查询。

- 顺序执行与并发执行对比
- 性能评估
- 异步批量操作

```bash
python examples/batch_processing.py
```

## 使用要求 (Requirements)

大多数示例开箱即用。部分高级功能需要：

- **文件上传与账号创建**: 需要 Perplexity 账号的 cookies。
- **批量处理**: 需要 Python 3.8+ 且支持 asyncio。

## 获取 Cookies 指引 (Getting Cookies)

### Perplexity Cookies (用于文件上传)

1. 打开 [Perplexity.ai](https://perplexity.ai/) 并登录。
2. 按 F12 打开开发者工具。
3. 切换到 "网络" (Network) 选项卡。
4. 刷新页面。
5. 右键点击第一个请求 -> 复制 (Copy) -> 以 cURL (bash) 格式复制。
6. 在 [CurlConverter.com](https://curlconverter.com/python/) 粘贴。
7. 复制生成的 cookies 字典。

### Emailnator Cookies (用于创建账号)

1. 打开 [Emailnator.com](https://emailnator.com/)。
2. 完成真人验证。
3. 按 F12 打开开发者工具。
4. 切换到 "网络" (Network) 选项卡。
5. 刷新页面。
6. 右键点击第一个请求 -> 复制 -> 以 cURL (bash) 格式复制。
7. 在 [CurlConverter.com](https://curlconverter.com/python/) 粘贴。
8. 复制生成的 cookies 字典。

注意：Emailnator 的 cookies 过期较快，使用时需要保持更新。

## 小贴士 (Tips)

- 从 `basic_usage.py` 开始学习基础概念。
- 在生产环境下建议使用 `async_usage.py`。
- `batch_processing.py` 展示了并发处理可带来 3-5 倍的性能提升。
- 在编写生产代码时务必注意错误处理。

## 下一步 (Next Steps)

运行完示例后，您可以：

1. 阅读 [详细文档](../docs/)
2. 查看 [API 参考手册](../README.md)
3. 探索 [高级功能](../docs/IMPROVEMENTS.md)
