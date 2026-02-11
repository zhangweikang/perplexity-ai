@echo off
chcp 65001 >nul
title Perplexity AI Proxy Server

echo ============================================
echo   Perplexity AI Proxy Server
echo   http://localhost:8046
echo   Admin: http://localhost:8046/admin
echo ============================================
echo.

python -m perplexity_server.server

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 启动失败，请检查 Python 环境和依赖是否已安装。
    echo 尝试运行: pip install -e .
    pause
)
