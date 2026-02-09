# Perplexity AI (Perplexity AI 助手)

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Perplexity AI 是一个 Python 模块，利用 [Emailnator](https://emailnator.com/) 生成新账号，从而实现无限量的 Pro 查询。它同时支持同步和异步 API，并为喜欢 GUI（图形界面）操作的用户提供了 Web 界面。

## 功能特性 (Features)

- **账号生成**: 利用 Emailnator 自动生成 Gmail 账号
- **无限 Pro 查询**: 通过创建新账号绕过查询限制
- **Web 界面**: 通过浏览器自动化账号创建 and 使用
- **同步与异步 API**: 全面支持同步和异步编程模型
- **类型安全**: 完整的类型提示，提供更好的 IDE 支持
- **健壮的错误处理**: 自定义异常，实现更好的错误管理
- **全面日志**: 结构化日志，方便调试
- **文件上传**: 支持文档分析和问答 (Q&A)
- **流式响应**: 实时流式传输响应内容
- **重试逻辑**: 具有指数退避机制的自动重试
- **频率限制**: 内置频率限制，防止滥用

## 安装指引 (Installation)

### 基础安装

```bash
pip install -e .
```

### 包含驱动支持 (Web 界面)

```bash
pip install -e ".[driver]"
patchright install chromium
```

### 开发模式安装

```bash
pip install -e ".[dev]"
```

这包括测试工具 (pytest, pytest-cov, pytest-asyncio)、代码规范检查 (flake8, black, isort, mypy) 以及所有可选依赖。

## 快速上手 (Quick Start)

### 基础用法

```python
import perplexity

# 创建客户端
client = perplexity.Client()

# 发起查询
response = client.search("什么是人工智能？")
print(response['answer'])
```

### 使用自有账号 (以获得增强功能)

```python
import perplexity

# 您的 Perplexity cookies
cookies = {
    'next-auth.csrf-token': '您的-token',
    'next-auth.session-token': '您的-会话-token',
}

client = perplexity.Client(cookies)

# 使用增强模式 (Pro 模式)
response = client.search(
    "在这里输入复杂查询",
    mode='pro',
    model='gpt-5.2',
    sources=['scholar']
)
```

### 流式响应

```python
for chunk in client.search("解释一下量子计算", stream=True):
    if 'answer' in chunk:
        print(chunk['answer'], end='', flush=True)
```

### 异步用法

```python
import asyncio
import perplexity_async

async def main():
    client = await perplexity_async.Client()
    response = await client.search("什么是机器学习？")
    print(response['answer'])

asyncio.run(main())
```

## 文档资源 (Documentation)

- **[使用示例](examples/)** - 常见场景的实用代码示例
- **[更新日志](docs/CHANGELOG.md)** - 修复的问题和更改历史
- **[改进建议](docs/IMPROVEMENTS.md)** - 建议的功能改进和路线图
- **[API 参考](#api-reference)** - 完整的 API 文档

## 使用说明 (Usage)

### Web 界面

Web 界面通过浏览器自动执行账号创建和使用。[Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python#best-practices) 使用 ["Chrome 用户数据目录"](https://www.google.com/search?q=chrome+user+data+directory) 来实现完全隐身（不被检测）。在 Windows 上，路径通常如下所示：

```python
import os
from perplexity.driver import Driver

cli = Driver()
cli.run(rf'C:\\Users\\{os.getlogin()}\\AppData\\Local\\Google\\Chrome\\User Data')
```

若要使用您正在运行的 Chrome 实例，请启用远程调试（注意：在 Cloudflare 验证中可能会陷入死循环）：

1. 在 Chrome 快捷方式的目标末尾添加 `--remote-debugging-port=9222`。
2. 将端口传递给 `Driver.run()` 方法：

```python
cli.run(rf'C:\\Users\\{os.getlogin()}\\AppData\\Local\\Google\\Chrome\\User Data', port=9222)
```

### API 使用

#### 同步 API

以下是简单用法的示例代码，不使用自有账号也不生成新账号。

```python3
import perplexity

perplexity_cli = perplexity.Client()

# model = 该模式对应的模型，仅能在自有账号中使用，具体对应如下：
# {
#     'auto': [None],
#     'pro': [None, 'sonar', 'gpt-5.2', 'claude-4.5-sonnet', 'grok-4-1'],
#     'reasoning': [None, 'gpt-5.2-thinking', 'claude-4.5-sonnet-thinking', 'gemini-3.0-pro', 'kimi-k2-thinking', 'grok-4.1-reasoning'],
#     'deep research': [None]
# }
# sources = 搜索来源，可选 ['web', 'scholar', 'social']
# files = 字典格式，键为文件名，值为文件数据
# stream = 启用时返回生成器，禁用时仅返回最终响应
# language = 您想使用的语言的 ISO 639 代码 (例如 'zh-CN')
# follow_up = 上一次查询的信息，用于追问。您可以直接传入上一次查询的响应，详见下方第二个示例。
# incognito = 启用无痕模式，适用于使用自有账号的用户
resp = perplexity_cli.search('在这里输入查询', mode='auto', model=None, sources=['web'], files={}, stream=False, language='zh-CN', follow_up=None, incognito=False)
print(resp)

# 第二个示例：展示如何进行追问和流式输出
for i in perplexity_cli.search('追问内容', stream=True, follow_up=resp):
    print(i)
```

这是如何使用您自己的账号。您需要获取 cookies 才能使用。请参考 [如何获取 Cookies](#如何获取-cookies)。

```python3
import perplexity

perplexity_cookies = {
    # 在这里填入您的 cookies
}

perplexity_cli = perplexity.Client(perplexity_cookies)

resp = perplexity_cli.search('您的查询', mode='reasoning', model='gpt-5.2-thinking', sources=['web'], files={'myfile.txt': open('file.txt').read()}, stream=False, language='zh-CN', follow_up=None, incognito=False)
print(resp)
```

最后是账号生成功能。您需要获取 [Emailnator](https://emailnator.com/) 的 cookies 才能使用此功能。请参考 [如何获取 Cookies](#如何获取-cookies)。

```python3
import perplexity

emailnator_cookies = {
    # 在这里填入您的 cookies
}

perplexity_cli = perplexity.Client()
perplexity_cli.create_account(emailnator_cookies) # 创建一个新的 Gmail 账号，重置您的 5 次 Pro 查询额度。

resp = perplexity_cli.search('您的查询', mode='reasoning', model=None, sources=['web'], files={'myfile.txt': open('file.txt').read()}, stream=False, language='zh-CN', follow_up=None, incognito=False)
print(resp)
```

#### 异步 API

以下是简单用法的异步示例代码。

```python3
import asyncio
import perplexity_async

async def test():
    perplexity_cli = await perplexity_async.Client()

    # mode = ['auto', 'pro', 'reasoning', 'deep research']
    # model = 对应模式的模型，仅能在自有账号中使用：
    # {
    #     'auto': [None],
    #     'pro': [None, 'sonar', 'gpt-5.2', 'claude-4.5-sonnet', 'grok-4-1'],
    #     'reasoning': [None, 'gpt-5.2-thinking', 'claude-4.5-sonnet-thinking', 'gemini-3.0-pro', 'kimi-k2-thinking', 'grok-4.1-reasoning'],
    #     'deep research': [None]
    # }
    # ... 其余参数同同步 API ...
    resp = await perplexity_cli.search('在这里输入查询', mode='auto', model=None, sources=['web'], files={}, stream=False, language='zh-CN', follow_up=None, incognito=False)
    print(resp)

    # 追问和流式响应示例
    async for i in await perplexity_cli.search('追问内容', stream=True, follow_up=resp):
        print(i)

asyncio.run(test())
```

使用自有账号的异步示例：

```python3
import asyncio
import perplexity_async

perplexity_cookies = {
    # 在这里填入您的 cookies
}

async def test():
    perplexity_cli = await perplexity_async.Client(perplexity_cookies)

    resp = await perplexity_cli.search('您的查询', mode='reasoning', model='gpt-5.2-thinking', sources=['web'], files={'myfile.txt': open('file.txt').read()}, stream=False, language='zh-CN', follow_up=None, incognito=False)
    print(resp)

asyncio.run(test())
```

自动生成账号的异步示例：

```python3
import asyncio
import perplexity_async

emailnator_cookies = {
    # 在这里填入您的 cookies
}

async def test():
    perplexity_cli = await perplexity_async.Client()
    await perplexity_cli.create_account(emailnator_cookies) # 创建新账号，重置 Pro 额度。

    resp = await perplexity_cli.search('您的查询', mode='reasoning', model=None, sources=['web'], files={'myfile.txt': open('file.txt').read()}, stream=False, language='zh-CN', follow_up=None, incognito=False)
    print(resp)

asyncio.run(test())
```

## API 桥接服务器 (API Bridge Server) [NEW]

本项目包含一个内置的 API 桥接服务器，允许您使用 OpenAI、Claude 或 Gemini 的标准协议来调用 Perplexity AI。

### 启动服务器

您可以通过以下命令启动服务器（默认端口为 8046）：

```bash
python -m perplexity_server.server
```

### 支持的协议

1. **OpenAI 兼容端点**: `POST http://localhost:8046/v1/chat/completions`
2. **Claude 兼容端点**: `POST http://localhost:8046/v1/messages`
3. **Gemini 兼容端点**: `POST http://localhost:8046/v1beta/models/{model}:generateContent`

### 配置说明

服务器默认使用免登录模式。如果您想使用自己的 Pro 账号以获得更高权限，建议在 `perplexity_server/server.py` 中配置您的 Cookies。

### 示例请求 (OpenAI 协议)

```bash
curl http://localhost:8046/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好，请介绍一下你自己"}]
  }'
```

## 如何获取 Cookies

### Perplexity (用于使用自有账号)

- 打开 [Perplexity.ai](https://perplexity.ai/) 网站并登录您的账号。
- 按 F12 或 `Ctrl + Shift + I` 打开检查器 (Inspector)。
- 切换到 "网络" (Network) 选项卡。
- 刷新页面，右键点击第一个请求，选择 "复制" (Copy) -> "以 cURL (bash) 格式复制" (Copy as cURL (bash))。
- 前往 [CurlConverter](https://curlconverter.com/python/) 网站并将代码粘贴。网页会显示 cookies 字典，复制并将其用于您的代码中。

<img src="images/perplexity.png">

### Emailnator (用于自动生成账号)

- 打开 [Emailnator](https://emailnator.com/) 网站并完成真人验证。
- 按 F12 或 `Ctrl + Shift + I` 打开检查器。
- 切换到 "网络" (Network) 选项卡。
- 刷新页面，右键点击第一个请求，选择 "复制" -> "以 cURL (bash) 格式复制"。
- 前往 [CurlConverter](https://curlconverter.com/python/) 并粘贴代码。复制生成的 cookies 字典。
- [Emailnator](https://emailnator.com/) 的 cookies 是临时的，您需要定期更新它们。

<img src="images/emailnator.png">

## API 参考 (API Reference)

### Client 类

```python
class Client:
    def __init__(self, cookies: Optional[Dict[str, str]] = None):
        """
        初始化 Perplexity 客户端。

        参数:
            cookies: 可选，用于开启增强功能的 Perplexity 账号 cookies
        """

    def search(
        self,
        query: str,
        mode: str = 'auto',
        model: Optional[str] = None,
        sources: List[str] = ['web'],
        files: Dict[str, Union[str, bytes]] = {},
        stream: bool = False,
        language: str = 'zh-CN',
        follow_up: Optional[Dict] = None,
        incognito: bool = False
    ) -> Union[Dict, Generator]:
        """
        使用 Perplexity AI 进行搜索。

        参数:
            query: 搜索查询内容
            mode: 搜索模式 ('auto', 'pro', 'reasoning', 'deep research')
            model: 使用的模型 (取决于模式)
            sources: 信息来源 (['web', 'scholar', 'social'])
            files: 要上传的文件 {文件名: 内容}
            stream: 是否启用流式输出
            language: ISO 639 语言代码
            follow_up: 用于上下文的追问信息
            incognito: 是否启用无痕模式

        返回:
            包含 'answer' 键的响应字典，若 stream=True 则返回生成器
        """

    def create_account(self, emailnator_cookies: Dict[str, str]):
        """
        使用 Emailnator 创建新账号。

        参数:
            emailnator_cookies: 用于创建账号的 Emailnator cookies
        """
```

### 可用模型 (Available Models)

```python
{
    'auto': [None],
    'pro': [None, 'sonar', 'gpt-5.2', 'claude-4.5-sonnet', 'grok-4-1'],
    'reasoning': [None, 'gpt-5.2-thinking', 'claude-4.5-sonnet-thinking', 'gemini-3.0-pro', 'kimi-k2-thinking', 'grok-4.1-reasoning'],
    'deep research': [None]
}
```

### 自定义异常 (Custom Exceptions)

```python
from perplexity.exceptions import (
    PerplexityError,          # 基础异常
    AuthenticationError,      # 身份验证失败
    RateLimitError,          # 超出频率限制
    NetworkError,            # 网络问题
    ValidationError,         # 参数无效
    ResponseParseError,      # 响应解析失败
    AccountCreationError,    # 账号创建失败
    FileUploadError,         # 文件上传失败
)
```

## 测试 (Testing)

### 运行所有测试

```bash
pytest tests/ -v
```

### 带覆盖率报告

```bash
pytest tests/ --cov=perplexity --cov=perplexity_async --cov-report=html
```

### 运行特定测试

```bash
pytest tests/test_utils.py -v
pytest tests/test_config.py -v
```

## 开发指引 (Development)

### 搭建开发环境

```bash
# 克隆仓库
git clone https://github.com/yourusername/perplexity-ai.git
cd perplexity-ai

# 以开发模式安装
pip install -e ".[dev]"

# 运行测试
pytest

# 格式化代码
black perplexity perplexity_async

# 类型检查
mypy perplexity perplexity_async

# 代码规范检查 (Lint)
flake8 perplexity perplexity_async
```

### 贡献代码

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的修改
4. 运行测试和规范检查
5. 提交变更 (`git commit -m 'Add amazing feature'`)
6. 推送至分支 (`git push origin feature/amazing-feature`)
7. 开启一个 Pull Request

## 故障排除 (Troubleshooting)

### 常见问题

**问题**: 响应返回 `None`

- **解决方法**: API 结构可能已发生变化。请查看 [更新日志](docs/CHANGELOG.md) 了解更新情况。

**问题**: 账号创建失败

- **解决方法**: Emailnator cookies 过期较快。请从 [Emailnator.com](https://emailnator.com/) 获取最新 cookies。

**问题**: 文件上传失败

- **解决方法**: 请确保您的 Perplexity 账号有效且具有可用的文件上传配额。

**问题**: 频率限制 (Rate limiting)

- **解决方法**: 使用内置的频率限制功能或在请求之间等待。考虑使用异步 API 以获得更好的并发性能。

### 获取帮助

- 查看 [examples/](examples/) 目录下的示例代码
- 阅读 [文档](docs/)
- 在 GitHub 上提交 Issue

## 更新日志 (Changelog)

详见 [CHANGELOG.md](docs/CHANGELOG.md) 以了解详细的变更和修复。

## 路线图 (Roadmap)

详见 [IMPROVEMENTS.md](docs/IMPROVEMENTS.md) 以了解计划中的改进和功能。

## 开源协议 (License)

本项目采用 MIT 协议开源。详见 [LICENSE](LICENSE) 文件。

## 特别鸣谢 (Acknowledgments)

- [Perplexity.ai](https://perplexity.ai/) 提供的优秀 AI 搜索引擎
- [Emailnator](https://emailnator.com/) 提供的临时邮箱服务
- 所有帮助改进本项目的贡献者

## 免责声明 (Disclaimer)

这是一个非官方的 API 封装包。请负责任地使用，并遵守 Perplexity.ai 的服务条款。本项目仅供教学目的使用。
