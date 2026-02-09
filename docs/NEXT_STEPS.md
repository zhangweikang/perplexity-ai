# 下一步行动指南 (Next Steps Guide)

本指南概述了重构旧版模块所需的剩余步骤，使其与新的基础架构（配置、日志、异常和工具类）保持一致。

## 核心目标 (Objectives)

1. 在所有地方复用共享的基础架构（不再使用硬编码常量或 print 语句）。
2. 为每个公共函数添加完善的类型提示和 Google 风格的文档字符串。
3. 使用 `perplexity.exceptions` 中的类型化异常体系替换通用的 `Exception` 处理。
4. 为拥有网络资源的客户端提供确定性的清理机制（通过上下文管理器）。
5. 在重构完成后，扩展自动化测试以涵盖客户端行为。

## 第一阶段 – 同步客户端 (Phase 1 – Synchronous Client)

### 1.1 更新 `perplexity/client.py`

- 导入配置、日志、工具类和异常模块，而不是重复定义这些值。
- 使用 `config.py` 中的条目替换每一个字面量形式的端点、头信息或限制。
- 使用 `@retry_with_backoff` 和 `@rate_limit` 装饰对外调用。
- 使用 `validate_search_params`、`validate_query_limits` 和 `validate_file_data` 验证查询、来源和文件上传。
- 抛出类型化错误，如 `ValidationError`、`AuthenticationError`、`RateLimitError`、`ResponseParseError` 和 `NetworkError`。
- 为类和方法添加完整的类型提示（包括流式生成器）。
- 编写文档字符串，描述参数、返回值和可能抛出的异常。
- 通过 `logger.info()` / `logger.error()` 发送结构化日志，而不是使用 `print()`。

### 1.2 更新 `perplexity/emailnator.py`

- 从 `config.py` 加载 URL 模板、超时和重试值。
- 使用结构化日志替换控制台输出。
- 验证 cookie/token 输入，并抛出相应的异常 (`AuthenticationError`、`ValidationError` 或 `SessionExpiredError`)。
- 为公共辅助函数（如账号创建、cookie 刷新）添加文档字符串和类型提示。

### 1.3 更新 `perplexity/driver.py`

- 在 `config.py` 中集中管理浏览器路径、User-Agent 和等待时间。
- 为自动化失败创建一个专用的异常（例如 `DriverError`）。
- 通过实现上下文管理器支持，确保驱动程序能干净地关闭。
- 记录导航步骤、屏幕截图抓取以及失败情况。

### 1.4 更新 `perplexity/labs.py`

- 对 Labs/WebSocket 客户端应用相同的改进。
- 通过使用上下文管理器或显式的 `close()` 调用，确保 WebSocket 会话得到清理。
- 将底层错误转化为自定义的异常体系。

## 第二阶段 – 异步客户端 (Phase 2 – Async Client)

- 在 `perplexity_async/client.py`、`perplexity_async/emailnator.py` 和 `perplexity_async/labs.py` 中同步执行第一阶段的所有更改。
- 提供异步安全的重试和频率限制装饰器（接收异步可调用对象）。
- 使用 `async with aiohttp.ClientSession()` 并确保会话以可预测的方式关闭。
- 添加 `pytest-asyncio` 测试，覆盖成功路径、流式传输和错误转换。

## 第三阶段 – 集成测试 (Phase 3 – Integration Tests)

- 在 `tests/` 中扩展针对同步和异步客户端的模拟 (Mock) HTTP 会话测试。
- 覆盖：成功的搜索、验证错误、流式分块解析、频率限制处理和重试逻辑。
- 示例原型：

```python
@patch("perplexity.client.requests.Session")
def test_search_basic(mock_session):
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "text": '{"steps":[{"FINAL":{"answer":"{\\"answer\\":\\"测试\\"}"}}]}'
    }
    mock_session.return_value.post.return_value = mock_resp

    client = Client()
    result = client.search("test query")

    assert result["answer"] == "测试"
```

## 第四阶段 – 上下文管理器 (Phase 4 – Context Managers)

- 为同步客户端实现 `__enter__` / `__exit__`，为异步客户端实现 `__aenter__` / `__aexit__`。
- 确保即使发生错误，HTTP 会话、浏览器驱动和 WebSocket 连接也能正常关闭。

## 第五阶段 – 文档与示例 (Phase 5 – Documentation and Examples)

- 重构完成后更新 README 中的使用示例。
- 为每个公共符号添加文档字符串，并运行 `pydocstyle`。
- 如果引入了新的工作流（如上下文管理器的用法），则扩展 `examples/` 目录。

## 支持工具 (Supporting Tooling)

- `mypy perplexity/ perplexity_async/ --strict`
- `pytest tests/ --cov=perplexity --cov-report=term-missing`
- `black`, `isort`, `flake8`, `pylint`, `bandit`
- `pydocstyle` (用于文档字符串校验)
- 发布参考文档时使用 `sphinx-build -b html docs/ docs/_build/`

## 重构清单 (Refactor Checklist)

- [ ] 使用配置引用替换字面量
- [ ] 移除所有 `print()` 语句（改用日志记录器）
- [ ] 在所有发起请求的地方应用重试和频率限制装饰器
- [ ] 在进行网络调用前强制执行验证辅助函数
- [ ] 抛出自定义异常而非通用异常
- [ ] 提供完整的类型提示和文档字符串
- [ ] 为拥有资源的客户端实现上下文管理器
- [ ] 添加同步和异步的集成测试
- [ ] 在重构完成后更新 README、更新日志和示例

## 优先级排序 (Prioritization)

1. **高优先级** – 重构 `perplexity/client.py`，在异步模块间共享基础架构，更新文档。
2. **中优先级** – 集成测试、异步专用辅助函数、响应缓存。
3. **低优先级** – CLI 工具、Sphinx 站点、性能分析。

## 工作建议 (Working Tips)

1. 每次只重构一个模块，保持提交记录的专注。
2. 每次重大更改后，运行 Pytest 套件和 `verify_implementation.py`。
3. 一旦完成一个重构片段，立即更新更新日志。
4. 即使您是唯一的维护者，也请使用 Pull Request 进行审查，以保留完整的历史文档。

---

**上次更新**: 2025年1月
