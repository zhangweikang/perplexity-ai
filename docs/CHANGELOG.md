# 更新日志 (Changelog)

## [未发布] - 2025-12-02

### 修复 (Fixed)

#### Bug #1: 遗漏了导入 (Missing Import)

- 在 `perplexity/emailnator.py` 中添加了遗漏的 `time` 模块导入。

#### Bug #2: 响应解析返回 `None` (Response Parsing Returned `None`)

- 更新了解析逻辑，以适配 API 返回的新版三级 JSON 结构。
- 从 `FINAL` 步骤的负载 (Payload) 中提取 `answer` 字段。
- 捕获了 `chunks`，以便流式传输的使用者可以重新构建答案。
- 使用防御性的 `try/except` 块封装了解析流程，防止程序崩溃。
- 在访问嵌套数据前添加了字段验证。
- 确保空的块列表现在返回空字典而不是 `None`。

### 变更 (Changed)

- 更新了同步客户端的 `stream_response()` 方法，以使用新的解析器。
- 更新了同步分块迭代，使解析后的答案显示保持一致。
- 更新了异步客户端的 `stream_response()` 方法，与新解析器保持同步。
- 更新了异步分块迭代，使其行为与同步客户端一致。

### 已测试 (Tested)

- 手动测试了 Emailnator 账号创建功能。
- 测试了基础的免认证搜索。
- 测试了流式搜索（接收到 79 个分块）。
- 测试了追问搜索。
- 测试了文本文件上传。
- 测试了异步客户端并行发起三个查询。
