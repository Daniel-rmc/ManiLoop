"""Read local API credentials without copying them or exposing them to the browser.

CC Switch's current Codex database row is an atomic source when Codex Desktop
preserves its own OAuth login. Native config.toml/auth.json pairs and small JSON
API configurations are supported as well. Every load rereads the selected source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import closing
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import tomllib
from urllib.parse import urlsplit, urlunsplit

MAX_CONFIG_BYTES = 1024 * 1024
DEFAULT_BASE_URL = "https://api.openai.com/v1"


class ConfigError(ValueError):
    """A sanitized configuration error that is safe to display to the user."""


@dataclass(frozen=True)
class CredentialConfig:
    api_key: str = field(repr=False)
    base_url: str
    model: str | None
    provider: str
    path: str
    fingerprint: str = field(repr=False)
    models: tuple[str, ...] = ()

    def public(self) -> dict:
        """An explicit allowlist; never serialize the dataclass itself."""

        def safe(value):
            return (
                value.replace(self.api_key, "[已隐藏]")
                if self.api_key and isinstance(value, str)
                else value
            )

        return {
            "path": safe(self.path),
            "provider": safe(self.provider),
            "base_url": safe(self.base_url),
            "model": safe(self.model),
            "key_configured": bool(self.api_key),
            "models": [safe(model) for model in self.models],
        }


def _path(value: str | Path) -> Path:
    try:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError
        return Path(value).expanduser().absolute()
    except (OSError, TypeError, ValueError, RuntimeError):
        raise ConfigError("本地配置路径无效，请选择配置文件。") from None


def _parse_json(raw: bytes | str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ConfigError("本地 JSON 配置格式无效，请检查文件格式。") from None


def _parse_toml(raw: bytes | str) -> dict:
    try:
        return tomllib.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ConfigError("本地 TOML 配置格式无效，请检查文件格式。") from None


def _file_state(path: Path, optional: bool = False) -> tuple | None:
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ConfigError("请选择普通配置文件。")
        if info.st_size > MAX_CONFIG_BYTES:
            raise ConfigError("本地配置内容超过 1 MB，无法读取。")
        return (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )
    except FileNotFoundError:
        if optional:
            return None
        raise ConfigError("未找到本地配置文件，请检查所选路径。") from None
    except (OSError, ValueError):
        raise ConfigError("无法读取本地配置文件，请检查文件权限。") from None


def _read_stable(paths: list[tuple[Path, bool]]) -> list[bytes | None]:
    """Reject a changing native pair instead of combining two observed versions.

    The quiet interval catches ordinary consecutive CC Switch writes. Files have
    no shared transaction marker, so the database source is preferred when present.
    """
    for _ in range(3):
        before = [_file_state(path, optional) for path, optional in paths]
        try:
            contents = []
            for (path, _), state in zip(paths, before):
                if state is None:
                    contents.append(None)
                    continue
                with path.open("rb") as handle:
                    raw = handle.read(MAX_CONFIG_BYTES + 1)
                if len(raw) > MAX_CONFIG_BYTES:
                    raise ConfigError("本地配置内容超过 1 MB，无法读取。")
                contents.append(raw)
            after = [_file_state(path, optional) for path, optional in paths]
            if before == after:
                time.sleep(0.03)
                if after == [_file_state(path, optional) for path, optional in paths]:
                    return contents
        except (OSError, ValueError) as exc:
            if isinstance(exc, ConfigError):
                raise
            # An atomic replacement may briefly remove a file: reread both files.
    raise ConfigError("配置正在切换或无法稳定读取，请稍后重试。")


def discover_configs() -> list[dict]:
    """Return path candidates only, without reading any credentials."""
    candidates: list[tuple[Path, str]] = []
    if os.environ.get("ARX_CONFIG_PATH", "").strip():
        candidates.append((_path(os.environ["ARX_CONFIG_PATH"]), "指定的本地配置"))
    cc_dir = Path.home() / ".cc-switch"
    cc_database = cc_dir / "cc-switch.db"
    if cc_database.is_file():
        candidates.append((cc_database, "CC Switch 当前 Codex 供应商"))
    settings_path = cc_dir / "settings.json"
    if settings_path.is_file():
        try:
            settings = _parse_json(_read_stable([(settings_path, False)])[0])
            override = settings.get("codexConfigDir")
            if isinstance(override, str) and override.strip():
                candidates.append(
                    (_path(override) / "config.toml", "CC Switch 自定义 Codex 配置")
                )
        except ConfigError:
            # An unrelated settings problem must not hide the normal Codex paths.
            pass
    if os.environ.get("CODEX_HOME", "").strip():
        candidates.append(
            (
                _path(os.environ["CODEX_HOME"]) / "config.toml",
                "Codex 配置（CODEX_HOME）",
            )
        )
    candidates.append((Path.home() / ".codex" / "config.toml", "Codex 默认配置"))
    result, seen = [], set()
    for path, label in candidates:
        value = str(path)
        if value not in seen:
            result.append({"path": value, "label": label})
            seen.add(value)
    return result


def normalize_base_url(value: str | None) -> str:
    """Require an API base URL; preserve non-root provider paths verbatim."""
    if value is None:
        return DEFAULT_BASE_URL
    message = (
        "API 地址无效：请使用无账号、查询参数和片段的 HTTPS 地址；HTTP 仅允许本机地址。"
    )
    try:
        if (
            not isinstance(value, str)
            or not value.strip()
            or any(c.isspace() for c in value)
        ):
            raise ValueError
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host:
            raise ValueError
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        # A dangling query/fragment is not part of an API endpoint either.
        if "?" in value or "#" in value or "\\" in value or parsed.port == 0:
            raise ValueError
        if parsed.scheme == "http":
            is_loopback = host.lower() == "localhost"
            try:
                is_loopback = is_loopback or ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
            if not is_loopback:
                raise ValueError
        path = parsed.path.rstrip("/") or "/v1"
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    except (ValueError, TypeError):
        raise ConfigError(message) from None


def _optional_string(value, label: str, max_length: int = 256) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > max_length
        or any(ord(c) < 32 for c in value)
    ):
        raise ConfigError(f"本地配置的{label}字段无效。")
    return value.strip()


def _models(model: str | None, configured) -> tuple[str, ...]:
    if configured is None:
        configured = []
    if not isinstance(configured, list) or len(configured) > 500:
        raise ConfigError("本地配置的模型列表无效。")
    values = [model] if model else []
    for value in configured:
        candidate = _optional_string(value, "模型", 120)
        if candidate is None:
            raise ConfigError("本地配置的模型列表无效。")
        if candidate not in values:
            values.append(candidate)
    return tuple(values)


def _api_key_override(value: str | None) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ConfigError("手动填写的 API 密钥格式无效。")
    if value is None:
        return None
    return value.strip() or None


def _make(
    key,
    base_url,
    model,
    provider,
    path: Path | str,
    models=None,
    oauth=False,
    allow_missing_key=False,
) -> CredentialConfig:
    if key is None or (isinstance(key, str) and not key.strip()):
        if allow_missing_key:
            key = ""
        elif oauth:
            raise ConfigError(
                "当前配置只有 ChatGPT 登录凭据，不能作为 API 密钥。请在 CC Switch 的 Codex 页切换到使用 API Key 的供应商。"
            )
        else:
            raise ConfigError(
                "本地配置中没有可用的 API 密钥，请单独填写 API Key 或在 CC Switch 中配置。"
            )
    if not isinstance(key, str):
        raise ConfigError("本地配置中的 API 密钥格式无效。")
    key = key.strip()
    if len(key) > 32768 or any(c.isspace() or ord(c) < 32 for c in key):
        raise ConfigError("本地配置中的 API 密钥格式无效。")
    model = _optional_string(model, "模型", 120)
    provider = _optional_string(provider, "供应商") or "openai"
    endpoint = normalize_base_url(base_url)
    choices = _models(model, models)
    digest = hashlib.sha256(
        json.dumps(
            [key, endpoint, model, provider, choices], ensure_ascii=False
        ).encode()
    ).hexdigest()
    return CredentialConfig(key, endpoint, model, provider, str(path), digest, choices)


def _check_transport(config: dict, allowed_transports=("responses",)):
    if config.get("wire_api", "responses") not in allowed_transports:
        raise ConfigError(
            "当前供应商没有使用 Responses API；本 Demo 需要支持图像和结构化输出的 Responses API 配置。"
        )


def _from_codex(
    config: dict, auth: dict, path: Path | str, *, api_key=None, allow_missing_key=False, allowed_transports=("responses",)
) -> CredentialConfig:
    if not isinstance(config, dict) or not isinstance(auth, dict):
        raise ConfigError("Codex 配置结构无效。")
    provider = _optional_string(config.get("model_provider"), "供应商") or "openai"
    providers = config.get("model_providers", {})
    if not isinstance(providers, dict):
        raise ConfigError("Codex 供应商配置结构无效。")
    selected = providers.get(provider, {})
    if not isinstance(selected, dict) or (
        provider != "openai" and provider not in providers
    ):
        raise ConfigError(
            "未找到当前 Codex 供应商的配置，请重新选择 CC Switch 供应商。"
        )
    _check_transport(selected, allowed_transports)
    base_url = selected.get("base_url", config.get("base_url"))
    if provider != "openai" and not base_url:
        raise ConfigError("当前 Codex 供应商缺少 API 地址，请检查配置。")
    key = api_key or selected.get("experimental_bearer_token")
    if not key:
        env_key = _optional_string(selected.get("env_key"), "密钥环境变量")
        if env_key:
            key = os.environ.get(env_key)
        else:
            key = auth.get("OPENAI_API_KEY")
    return _make(
        key,
        base_url,
        config.get("model"),
        provider,
        path,
        selected.get("models", config.get("models")),
        oauth=bool(auth.get("tokens")),
        allow_missing_key=allow_missing_key,
    )


def _from_json(
    config: dict, path: Path, *, api_key=None, allow_missing_key=False, allowed_transports=("responses",)
) -> CredentialConfig:
    _check_transport(config, allowed_transports)
    env = config.get("env", {})
    if not isinstance(env, dict):
        raise ConfigError("本地配置的环境变量映射无效。")
    key = api_key or config.get(
        "api_key", config.get("OPENAI_API_KEY", env.get("OPENAI_API_KEY"))
    )
    endpoint = config.get(
        "base_url", config.get("OPENAI_BASE_URL", env.get("OPENAI_BASE_URL"))
    )
    model = config.get("model", config.get("OPENAI_MODEL", env.get("OPENAI_MODEL")))
    return _make(
        key,
        endpoint,
        model,
        config.get("provider", "openai"),
        path,
        config.get("models"),
        oauth=bool(config.get("tokens")),
        allow_missing_key=allow_missing_key,
    )


def _from_cc_database(
    path: Path, *, api_key=None, allow_missing_key=False, allowed_transports=("responses",)
) -> CredentialConfig:
    """Read only the active Codex row, in a single SQLite snapshot."""
    if not path.is_file():
        raise ConfigError("未找到 CC Switch 数据库，请检查所选路径。")
    try:
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        ) as connection:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(providers)")
            }
            if not {"settings_config", "app_type", "is_current"} <= columns:
                raise ConfigError(
                    "当前 CC Switch 数据库格式不兼容，请改选 Codex config.toml。"
                )
            rows = connection.execute(
                "SELECT CASE WHEN length(CAST(settings_config AS BLOB)) <= ? "
                f"THEN settings_config ELSE NULL END, {'name' if 'name' in columns else 'NULL'} FROM providers "
                "WHERE app_type = ? AND is_current = 1 LIMIT 2",
                (MAX_CONFIG_BYTES, "codex"),
            ).fetchall()
        if len(rows) != 1:
            raise ConfigError(
                "CC Switch 中没有唯一的当前 Codex 供应商，请先在 Codex 页选择供应商。"
            )
        if rows[0][0] is None:
            raise ConfigError("CC Switch 当前供应商配置为空或超过 1 MB。")
        settings = _parse_json(rows[0][0])
        auth = settings.get("auth", {})
        config = settings.get("config", {})
        if isinstance(auth, str):
            auth = _parse_json(auth)
        if isinstance(config, str):
            config = _parse_toml(config)
        result = _from_codex(
            config, auth, path, api_key=api_key, allow_missing_key=allow_missing_key, allowed_transports=allowed_transports
        )
        display_name = rows[0][1] if len(rows[0]) > 1 else None
        return _make(
            result.api_key,
            result.base_url,
            result.model,
            display_name or result.provider,
            path,
            list(result.models),
            allow_missing_key=allow_missing_key,
        )
    except (sqlite3.Error, OSError, ValueError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(
            "无法读取 CC Switch 当前供应商，请稍后重试或选择 Codex config.toml。"
        ) from None


def load_local_config(
    path: str | None = None,
    *,
    api_key: str | None = None,
    allow_missing_key: bool = False,
    allowed_transports: tuple[str, ...] = ("responses",),
) -> CredentialConfig:
    """Reload the active local configuration; callers retain it only in memory."""
    api_key = _api_key_override(api_key)
    if path is not None and not isinstance(path, str):
        raise ConfigError("本地配置路径无效，请选择配置文件。")
    selected = _path(path if path and path.strip() else discover_configs()[0]["path"])
    if selected.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        return _from_cc_database(
            selected, api_key=api_key, allow_missing_key=allow_missing_key, allowed_transports=allowed_transports
        )
    if selected.suffix.lower() == ".toml" or selected.name == "auth.json":
        config_path = (
            selected
            if selected.suffix.lower() == ".toml"
            else selected.with_name("config.toml")
        )
        auth_path = (
            selected
            if selected.name == "auth.json"
            else selected.with_name("auth.json")
        )
        if api_key:
            # A separate key needs only the selected endpoint/model configuration.
            config_raw = _read_stable([(config_path, selected.name == "auth.json")])[0]
            auth_raw = None
        else:
            config_raw, auth_raw = _read_stable(
                [(config_path, selected.name == "auth.json"), (auth_path, True)]
            )
        return _from_codex(
            _parse_toml(config_raw) if config_raw is not None else {},
            _parse_json(auth_raw) if auth_raw is not None else {},
            selected,
            api_key=api_key,
            allow_missing_key=allow_missing_key, allowed_transports=allowed_transports,
        )
    if selected.suffix.lower() == ".json":
        return _from_json(
            _parse_json(_read_stable([(selected, False)])[0]),
            selected,
            api_key=api_key,
            allow_missing_key=allow_missing_key, allowed_transports=allowed_transports,
        )
    raise ConfigError(
        "请选择 config.toml、auth.json、API JSON 配置或 CC Switch 数据库文件。"
    )


def load_toml_config(
    content: str,
    *,
    api_key: str | None = None,
    name: str = "config.toml",
    allow_missing_key: bool = False,
    allowed_transports: tuple[str, ...] = ("responses",),
) -> CredentialConfig:
    """Read uploaded or pasted TOML entirely in memory, without sibling auth files."""
    if not isinstance(content, str):
        raise ConfigError("上传的 TOML 配置内容无效，请选择文本配置文件。")
    try:
        if len(content.encode("utf-8")) > MAX_CONFIG_BYTES:
            raise ConfigError("本地配置内容超过 1 MB，无法读取。")
    except UnicodeError:
        raise ConfigError("本地 TOML 配置格式无效，请检查文件格式。") from None
    label = _optional_string(name, "文件名", 256) or "config.toml"
    return _from_codex(
        _parse_toml(content),
        {},
        label,
        api_key=_api_key_override(api_key),
        allow_missing_key=allow_missing_key, allowed_transports=allowed_transports,
    )
