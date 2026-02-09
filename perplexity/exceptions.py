"""
Custom exceptions for Perplexity AI library. / Perplexity AI 库的自定义异常。

This module defines all custom exceptions used throughout the library / 该模块定义了库中使用的所有自定义异常，
for better error handling and debugging. / 以便更好地进行错误处理和调试。
"""


class PerplexityError(Exception):
    """Base exception for all Perplexity AI errors. / 所有 Perplexity AI 错误的基类异常。"""

    pass


class AuthenticationError(PerplexityError):
    """Raised when authentication fails. / 当身份验证失败时引发。"""

    pass


class RateLimitError(PerplexityError):
    """Raised when rate limit is exceeded. / 当超过速率限制时引发。"""

    pass


class NetworkError(PerplexityError):
    """Raised when network request fails. / 当网络请求失败时引发。"""

    pass


class InvalidModeError(PerplexityError):
    """Raised when an invalid search mode is provided. / 当提供了无效的搜索模式时引发。"""

    pass


class InvalidModelError(PerplexityError):
    """Raised when an invalid model is provided for a mode. / 当为某种模式提供了无效的模型时引发。"""

    pass


class InvalidSourceError(PerplexityError):
    """Raised when an invalid source is provided. / 当提供了无效的来源时引发。"""

    pass


class QueryLimitExceededError(PerplexityError):
    """Raised when query limit is exceeded. / 当超过查询限制时引发。"""

    pass


class FileUploadError(PerplexityError):
    """Raised when file upload fails. / 当文件上传失败时引发。"""

    pass


class EmailnatorError(PerplexityError):
    """Raised when Emailnator service fails. / 当 Emailnator 服务失败时引发。"""

    pass


class AccountCreationError(PerplexityError):
    """Raised when account creation fails. / 当账号创建失败时引发。"""

    pass


class ParsingError(PerplexityError):
    """Raised when response parsing fails. / 当响应解析失败时引发。"""

    pass


class ValidationError(PerplexityError):
    """Raised when input validation fails. / 当输入验证失败时引发。"""

    pass
