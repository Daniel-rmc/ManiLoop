"""Explicit, single-request model discovery with credential-safe failures.

An advertised model ID says nothing about image, Responses, or structured-output
support. Callers must present this list as provider-advertised IDs only.
"""

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)


class ModelCatalogError(RuntimeError):
    """A model-list request failed; never contains a provider response body."""


def fetch_models(api_key: str, base_url: str) -> list[str]:
    """Read one page of provider-advertised IDs; never auto-paginate or retry.

    The caller validates the selected endpoint before entering here. Both the key
    and URL are explicit so SDK environment defaults cannot mix two profiles.
    """
    if not isinstance(api_key, str) or not api_key.strip():
        raise ModelCatalogError("未配置模型列表查询所需的密钥。")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ModelCatalogError("未配置模型列表查询所需的服务地址。")
    client = None
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=10, max_retries=0)
        page = client.models.list()
        # Iterating the SDK page itself may fetch additional pages. Only examine
        # its already-received data; browsing models must remain one request.
        data = getattr(page, "data", None)
        if not isinstance(data, list):
            raise ModelCatalogError(
                "服务返回了无法识别的模型列表；可手动填写模型名称。"
            )
        model_ids = set()
        for item in data:
            model_id = (
                item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            )
            if isinstance(model_id, str) and model_id.strip() and len(model_id) <= 120:
                model_ids.add(model_id)
        return sorted(model_ids)[:1000]
    except (APITimeoutError, TimeoutError):
        raise ModelCatalogError(
            "读取模型列表超时，请稍后重试或手动填写模型名称。"
        ) from None
    except AuthenticationError:
        raise ModelCatalogError("模型列表认证失败，请检查当前密钥。") from None
    except RateLimitError:
        raise ModelCatalogError(
            "模型列表请求触发限流或额度不足，请切换配置或稍后重试。"
        ) from None
    except APIConnectionError:
        raise ModelCatalogError(
            "无法连接模型列表服务，请检查服务地址和网络。"
        ) from None
    except APIStatusError:
        raise ModelCatalogError(
            "服务拒绝了模型列表请求或不支持此接口；可手动填写模型名称。"
        ) from None
    except ModelCatalogError:
        raise
    except Exception:
        raise ModelCatalogError(
            "读取模型列表失败，请检查配置或手动填写模型名称。"
        ) from None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                # Closing must not replace a sanitized request error with a
                # potentially credential-bearing transport exception.
                pass
