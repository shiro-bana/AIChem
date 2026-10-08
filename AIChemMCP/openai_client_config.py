#!/usr/bin/env python3
"""
OpenAI 客户端配置工具
用于创建带有连接池和超时配置的 OpenAI 客户端，避免端口耗尽问题
"""

import os
import time
from typing import Optional
from openai import OpenAI
import httpx


# 配置参数
DEFAULT_TIMEOUT = httpx.Timeout(
    connect=10.0,      # 连接超时：10秒
    read=120.0,        # 读取超时：120秒（给API足够时间响应）
    write=10.0,        # 写入超时：10秒
    pool=5.0           # 连接池获取超时：5秒
)

# 连接池限制 - 防止端口耗尽的关键配置（配合 HTTP/2 使用更保守的设置）
DEFAULT_LIMITS = httpx.Limits(
    max_connections=10,        # 最大连接数：进一步减少到10个
    max_keepalive_connections=5,  # 最大保持活动连接数：复用5个连接
    keepalive_expiry=60.0      # 保持活动连接过期时间：60秒
)


def create_openai_client(
    api_key: Optional[str] = None,
    timeout: Optional[httpx.Timeout] = DEFAULT_TIMEOUT,
    limits: Optional[httpx.Limits] = DEFAULT_LIMITS
) -> OpenAI:
    """
    创建带有连接池配置的 OpenAI 客户端

    Args:
        api_key: OpenAI API key，如果不提供则从环境变量读取
        timeout: httpx.Timeout 配置
        limits: httpx.Limits 连接池配置

    Returns:
        OpenAI: 配置好的客户端实例
    """
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 环境变量未设置！")

    # 创建带有连接池配置的 httpx 客户端
    http_client = httpx.Client(
        timeout=timeout,
        limits=limits,
        http2=True,  # 启用 HTTP/2 以提高性能和减少连接数
        verify=True  # 验证 SSL 证书
    )

    # 创建 OpenAI 客户端，传入自定义的 http_client
    client = OpenAI(
        api_key=api_key,
        http_client=http_client
    )

    return client


def sleep_between_requests(seconds: float = 1.0):
    """
    在 API 请求之间添加延迟，避免触发速率限制

    Args:
        seconds: 延迟秒数（默认1秒）
    """
    time.sleep(seconds)


# 预定义的配置
CONSERVATIVE_CONFIG = {
    'limits': httpx.Limits(
        max_connections=20,
        max_keepalive_connections=5,
        keepalive_expiry=30.0
    ),
    'timeout': httpx.Timeout(
        connect=10.0,
        read=180.0,
        write=10.0,
        pool=5.0
    )
}

BALANCED_CONFIG = {
    'limits': DEFAULT_LIMITS,
    'timeout': DEFAULT_TIMEOUT
}

AGGRESSIVE_CONFIG = {
    'limits': httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30.0
    ),
    'timeout': httpx.Timeout(
        connect=5.0,
        read=60.0,
        write=5.0,
        pool=2.0
    )
}


def create_client_with_config(config_name: str = 'balanced') -> OpenAI:
    """
    使用预定义配置创建客户端

    Args:
        config_name: 配置名称 ('conservative', 'balanced', 'aggressive')

    Returns:
        OpenAI: 配置好的客户端实例
    """
    configs = {
        'conservative': CONSERVATIVE_CONFIG,
        'balanced': BALANCED_CONFIG,
        'aggressive': AGGRESSIVE_CONFIG
    }

    if config_name not in configs:
        raise ValueError(f"未知配置: {config_name}。可用配置: {list(configs.keys())}")

    config = configs[config_name]
    return create_openai_client(
        timeout=config['timeout'],
        limits=config['limits']
    )
