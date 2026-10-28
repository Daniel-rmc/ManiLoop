"""Independent, local Sign in with ChatGPT authorization for ManiLoop.

Uses the documented OSS OAuth flow, not Codex's credential files or backend API.
Credentials never leave this module except through access_token(), for the fixed
official Responses endpoint. All public views and exceptions are allowlisted.
Official protocol checked 2026-10-28:
https://developers.openai.com/siwc/token-sharing-open-source/sign-in
https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import stat
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
AUTHORIZE_URL = ISSUER + "/api/accounts/authorize"
TOKEN_URL = ISSUER + "/api/accounts/oauth/token"
DISCOVERY_URL = ISSUER + "/.well-known/openid-configuration"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
REQUIRED_PLAN_SCOPES = {"resource.invoke", "chatgpt.tokens.use.direct"}
_TERMINAL_REFRESH_ERRORS = {
    "invalid_grant", "invalid_refresh_token", "token_expired",
    "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused",
}
_TOKEN_FIELDS = ("access_token", "refresh_token", "id_token", "expires_at", "earliest_refresh_at")
_MAX_BYTES = 1024 * 1024


class ChatGPTAuthError(ValueError):
    """Safe-to-display error; never includes provider text or credential data."""

    def __init__(self, message, *, category="authentication", code=None):
        super().__init__(message)
        self.category = category
        self.code = code if code in _TERMINAL_REFRESH_ERRORS | {"invalid_client"} else None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _official_auth_url(value):
    try:
        parts = urlsplit(value)
        valid = (parts.scheme == "https" and parts.netloc == "auth.openai.com"
                 and not parts.query and not parts.fragment and parts.path.startswith("/"))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ChatGPTAuthError("OpenAI 认证服务地址无效。", category="configuration")
    return value


def _http_json(method, url, *, data=None):
    """Bounded requests; normal OS proxy support, no credential-bearing redirects."""
    _official_auth_url(url)
    body = urlencode(data).encode() if data is not None else None
    headers = {"Accept": "application/json", "User-Agent": "ManiLoop/ChatGPTPlan"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with build_opener(_NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(_MAX_BYTES + 1)
            if len(raw) > _MAX_BYTES:
                raise ChatGPTAuthError("OpenAI 认证响应过大。")
            value = json.loads(raw) if raw else {}
            if not isinstance(value, dict):
                raise ChatGPTAuthError("OpenAI 认证响应格式无效。")
            return value
    except HTTPError as exc:
        code = None
        try:
            payload = json.loads(exc.read(_MAX_BYTES))
            if isinstance(payload, dict):
                code = payload.get("error")
                if isinstance(code, dict):
                    code = code.get("code")
            if not isinstance(code, str):
                code = None
        except (ValueError, OSError):
            pass
        raise ChatGPTAuthError("OpenAI 认证请求未完成，请重试或重新授权。", code=code) from None
    except (URLError, OSError, ValueError):
        raise ChatGPTAuthError("无法连接 OpenAI 认证服务，请检查网络后重试。", category="connection") from None


def _string(value, *, maximum=32768):
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(ord(c) < 32 for c in value)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


class ChatGPTAuthStore:
    def __init__(self, directory=None, *, http=None, clock=None, validate_id_token=None):
        selected = directory or os.environ.get("MANILOOP_CHATGPT_AUTH_DIR")
        self.directory = Path(selected).expanduser().absolute() if selected else Path.home() / ".config/maniloop/chatgpt"
        self._http = http or _http_json
        self._clock = clock or time.time
        self._validator = validate_id_token
        self._mutex = threading.RLock()
        self._pending = None
        self._server = None
        self._error = ""
        self._generation = 0
        self._discovery_cache = None
        self._retry_client = None

    @contextmanager
    def _locked(self):
        """Serialize read/modify/refresh across processes as well as threads."""
        with self._mutex:
            try:
                if self.directory.is_symlink():
                    raise OSError("symlink")
                self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                if os.name != "nt":
                    self.directory.chmod(0o700)
                lock_path = self.directory / "session.lock"
                fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                handle = os.fdopen(fd, "r+b")
            except OSError:
                raise ChatGPTAuthError("无法访问 ManiLoop 的本地认证存储。", category="configuration") from None
            try:
                if os.name == "nt":
                    import msvcrt
                    if os.fstat(handle.fileno()).st_size == 0:
                        handle.write(b"\0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                yield
            except OSError:
                raise ChatGPTAuthError("无法更新 ManiLoop 的本地认证存储。", category="configuration") from None
            finally:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()

    def _read(self):
        path = self.directory / "sessions.json"
        try:
            if not path.exists() and not path.is_symlink():
                return {"version": 1, "host_id": "urn:uuid:" + str(uuid.uuid4()), "accounts": {}, "active": None}
            if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
                raise ValueError
            if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise ValueError
            value = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(value, dict) or value.get("version") != 1
                    or not _string(value.get("host_id"), maximum=256)
                    or not isinstance(value.get("accounts"), dict)
                    or len(value["accounts"]) > 100):
                raise ValueError
            for key, record in value["accounts"].items():
                if (not _string(key, maximum=64) or not isinstance(record, dict)
                        or not _string(record.get("client_id"), maximum=256)
                        or not _string(record.get("subject"), maximum=256)
                        or not isinstance(record.get("scopes", []), list)):
                    raise ValueError
            if value.get("active") is not None and value["active"] not in value["accounts"]:
                raise ValueError
            return value
        except (OSError, ValueError, TypeError):
            raise ChatGPTAuthError("ManiLoop 认证存储格式或权限无效；未覆盖原记录。", category="configuration") from None

    def _write(self, state):
        fd, name = tempfile.mkstemp(prefix=".sessions-", dir=self.directory)
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.directory / "sessions.json")
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _public_account(key, record):
        email = record.get("email")
        label = email if _string(email, maximum=254) else "ChatGPT 账号"
        return {"id": key, "label": f"{label} · {key[:6]}",
                "plan_enabled": REQUIRED_PLAN_SCOPES.issubset(record.get("scopes", [])),
                "logged_in": bool(record.get("access_token")),
                "reauth_required": not bool(record.get("access_token"))}

    def status(self):
        with self._locked():
            state = self._read()
            pending = self._pending
            expired = pending is not None and pending["expires_at"] <= self._clock()
            if expired:
                self._pending = None
                self._generation += 1
                self._error = "授权已超时，请重新开始。"
            accounts = [self._public_account(key, record) for key, record in state["accounts"].items()]
            active = next((account for account in accounts if account["id"] == state.get("active")), None)
            result = {"accounts": accounts, "active_account_id": state.get("active"),
                      "pending": self._pending is not None, "error": self._error,
                      "registration_retry_available": bool(self._retry_client),
                      "logged_in": bool(active and active["logged_in"]),
                      "plan_enabled": bool(active and active["logged_in"] and active["plan_enabled"])}
        if expired:
            self._stop_listener(pending["server"])
        return result

    def _discovery(self):
        if self._discovery_cache is None:
            data = self._http("GET", DISCOVERY_URL)
            if data.get("issuer") != ISSUER:
                raise ChatGPTAuthError("OpenAI 身份提供者验证失败。")
            for field in ("jwks_uri", "revocation_endpoint"):
                _official_auth_url(data.get(field))
            self._discovery_cache = data
        return self._discovery_cache

    def _validate_identity(self, token, client_id, nonce):
        if not _string(token):
            raise ChatGPTAuthError("OpenAI 未返回有效的身份凭据。")
        if self._validator:
            claims = self._validator(token, client_id, nonce)
        else:
            try:
                import jwt
            except ImportError:
                raise ChatGPTAuthError("请先安装 ManiLoop 的 chatgpt 可选依赖以验证登录。", category="configuration") from None
            try:
                header = jwt.get_unverified_header(token)
                if header.get("alg") not in {"RS256", "ES256"}:
                    raise ValueError
                keys = self._http("GET", self._discovery()["jwks_uri"]).get("keys")
                if not isinstance(keys, list) or len(keys) > 100:
                    raise ValueError
                matches = [key for key in keys if isinstance(key, dict) and key.get("kid") == header.get("kid")
                           and key.get("use", "sig") == "sig" and key.get("alg", header["alg"]) == header["alg"]]
                if len(matches) != 1:
                    raise ValueError
                key = jwt.PyJWK.from_dict(matches[0], algorithm=header["alg"])
                claims = jwt.decode(token, key.key, algorithms=[header["alg"]], issuer=ISSUER,
                                    audience=client_id, options={"require": ["iss", "aud", "exp", "sub", "nonce"]})
            except (ValueError, KeyError, TypeError, jwt.PyJWTError):
                raise ChatGPTAuthError("OpenAI 身份凭据验证失败，未保存登录。") from None
        audience = claims.get("aud") if isinstance(claims, dict) else None
        if (not isinstance(claims, dict) or claims.get("iss") != ISSUER
                or not (audience == client_id or isinstance(audience, list) and client_id in audience)
                or not _number(claims.get("exp")) or claims["exp"] <= self._clock()
                or not _string(claims.get("sub"), maximum=256)
                or not isinstance(claims.get("nonce"), str)
                or not secrets.compare_digest(claims["nonce"], nonce)
                or isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != client_id):
            raise ChatGPTAuthError("OpenAI 身份凭据验证失败，未保存登录。")
        return claims

    def start_login(self, account_id=None, *, retry_registration=False):
        self.cancel_login()
        if self._validator is None:
            try:
                import jwt  # noqa: F401: fail before asking the user to authorize
            except ImportError:
                raise ChatGPTAuthError("请先安装 ManiLoop 的 chatgpt 可选依赖。", category="configuration") from None
        with self._locked():
            state = self._read()
            record = state["accounts"].get(account_id) if account_id else None
            if account_id is not None and record is None:
                raise ChatGPTAuthError("请选择已保存的 ChatGPT 账号。", category="configuration")
            self._write(state)  # persist a stable host ID before the first browser visit
            owner = self

            class CallbackHandler(BaseHTTPRequestHandler):
                def log_message(self, *_args):
                    pass  # authorization URLs contain codes; never log them

                def do_GET(self):
                    expected_host = f"127.0.0.1:{self.server.server_port}"
                    if self.headers.get("Host") != expected_host:
                        self.send_error(400)
                        return
                    if urlsplit(self.path).path != "/auth/callback":
                        self.send_error(404)
                        return
                    try:
                        owner.handle_callback(self.path)
                        status, message = 200, "ChatGPT 授权完成。请返回 ManiLoop 工作台。"
                    except ChatGPTAuthError:
                        status, message = 400, "ChatGPT 授权未完成。请返回 ManiLoop 工作台查看状态。"
                    body = ("<!doctype html><html lang='zh'><meta charset='utf-8'><title>ManiLoop</title>"
                            "<p>" + message + "</p></html>").encode()
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                    self.end_headers()
                    self.wfile.write(body)

            try:
                server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
            except OSError:
                raise ChatGPTAuthError("无法启动本机授权回调，请重试。", category="connection") from None
            server.daemon_threads = True
            self._server = server
            verifier = secrets.token_urlsafe(48)
            nonce = secrets.token_urlsafe(32)
            oauth_state = secrets.token_urlsafe(32)
            redirect_uri = f"http://127.0.0.1:{server.server_port}/auth/callback"
            if retry_registration and (record is not None or not self._retry_client):
                server.server_close()
                self._server = None
                raise ChatGPTAuthError("没有可重试的注册，请重新开始登录。")
            client_id = record["client_id"] if record else (
                self._retry_client if retry_registration else "dynamic_agent_client")
            self._pending = {"state": oauth_state, "nonce": nonce, "verifier": verifier,
                             "redirect_uri": redirect_uri, "client_id": client_id,
                             "account_id": account_id, "expires_at": self._clock() + 600,
                             "generation": self._generation, "server": server}
            self._error = ""
            params = {"client_id": client_id, "ext_agent_host_id": state["host_id"],
                      "response_type": "code", "redirect_uri": redirect_uri, "scope": SCOPES,
                      "resource": RESOURCE, "state": oauth_state, "nonce": nonce,
                      "code_challenge_method": "S256",
                      "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")}
            if client_id == "dynamic_agent_client":
                params["agent_name_hint"] = "ManiLoop"
            if record and not REQUIRED_PLAN_SCOPES.issubset(record.get("scopes", [])):
                params["prompt"] = "consent"
            threading.Thread(target=server.serve_forever, daemon=True, name="maniloop-oauth-callback").start()
            return {"authorization_url": AUTHORIZE_URL + "?" + urlencode(params), "expires_in": 600}

    def _token_values(self, response, *, old=None):
        if (not isinstance(response, dict) or not _string(response.get("access_token"))
                or not isinstance(response.get("token_type"), str)
                or response["token_type"].lower() != "bearer"
                or not _number(response.get("expires_in")) or not 0 < response["expires_in"] <= 86400):
            raise ChatGPTAuthError("OpenAI 返回的授权凭据不完整。")
        refresh = response.get("refresh_token")
        if refresh is not None and not _string(refresh):
            raise ChatGPTAuthError("OpenAI 返回的续期凭据无效。")
        if old is not None and not refresh:
            raise ChatGPTAuthError("OpenAI 未返回轮换后的续期凭据。")
        scope = response.get("scope")
        if scope is None and old is not None:
            scopes = list(old["scopes"])
        elif isinstance(scope, str) and len(scope) <= 4096:
            scopes = sorted(set(scope.split()))
        else:
            raise ChatGPTAuthError("OpenAI 未返回有效的授权范围。")
        values = {"access_token": response["access_token"], "refresh_token": refresh,
                  "scopes": scopes, "expires_at": self._clock() + response["expires_in"]}
        earliest = response.get("earliest_refresh_at")
        if earliest is not None:
            if not _number(earliest):
                raise ChatGPTAuthError("OpenAI 返回的续期时间无效。")
            values["earliest_refresh_at"] = earliest
        return values

    def handle_callback(self, callback):
        """Used by the private listener and offline tests; callback never enters logs."""
        pending = None
        try:
            if not isinstance(callback, str) or len(callback) > 32768:
                raise ChatGPTAuthError("授权回调无效。")
            parsed = urlsplit(callback)
            params = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20)
            if parsed.path != "/auth/callback" or any(len(values) != 1 for values in params.values()):
                raise ChatGPTAuthError("授权回调无效。")
            with self._mutex:
                candidate = self._pending
                supplied_state = params.get("state", [""])[0]
                if (candidate is None or candidate["expires_at"] <= self._clock()
                        or candidate.get("consumed")
                        or not secrets.compare_digest(candidate["state"], supplied_state)):
                    raise ChatGPTAuthError("授权回调已过期或不匹配，请重新开始。")
                pending = candidate
                pending["consumed"] = True  # no replay; still pending while exchange/validation run
            if params.get("error"):
                raise ChatGPTAuthError("未完成 ChatGPT 授权，可在工作台重新登录。")
            code = params.get("code", [""])[0]
            client = params.get("client_id", [pending["client_id"]])[0]
            if (not _string(code, maximum=8192) or not _string(client, maximum=256)
                    or client == "dynamic_agent_client"
                    or pending["client_id"] != "dynamic_agent_client" and client != pending["client_id"]):
                raise ChatGPTAuthError("ChatGPT 注册信息不完整或不匹配。")
            if pending["client_id"] == "dynamic_agent_client":
                self._retry_client = client
            response = self._http("POST", TOKEN_URL, data={"grant_type": "authorization_code",
                "client_id": client, "code": code, "code_verifier": pending["verifier"],
                "redirect_uri": pending["redirect_uri"], "resource": RESOURCE})
            values = self._token_values(response)
            claims = self._validate_identity(response.get("id_token"), client, pending["nonce"])
            key = hashlib.sha256((ISSUER + "\0" + client + "\0" + claims["sub"]).encode()).hexdigest()[:24]
            with self._locked():
                if pending["generation"] != self._generation:
                    raise ChatGPTAuthError("授权已取消，未保存登录。")
                state = self._read()
                existing = state["accounts"].get(pending["account_id"])
                if pending["account_id"] is not None and (existing is None or existing["subject"] != claims["sub"]
                        or existing["client_id"] != client):
                    raise ChatGPTAuthError("授权账号与所选账号不一致，未覆盖原登录。")
                email = claims.get("email")
                state["accounts"][key] = {"client_id": client, "subject": claims["sub"],
                    "email": email if _string(email, maximum=254) else "", "id_token": response["id_token"], **values}
                state["active"] = key
                self._write(state)
                self._retry_client = None
                self._error = "" if REQUIRED_PLAN_SCOPES.issubset(values["scopes"]) else "已登录，但尚未授权使用 ChatGPT 套餐。"
        except ChatGPTAuthError as exc:
            if pending is not None:
                with self._mutex:
                    if pending["generation"] == self._generation:
                        self._error = str(exc)
            raise
        except (ValueError, TypeError, KeyError, OSError):
            if pending is not None:
                with self._mutex:
                    if pending["generation"] == self._generation:
                        self._error = "ChatGPT 授权未完成，请重新登录。"
            raise ChatGPTAuthError("ChatGPT 授权未完成，请重新登录。") from None
        finally:
            if pending is not None:
                with self._mutex:
                    if self._pending is pending:
                        self._pending = None
                self._stop_listener(pending["server"])

    def _stop_listener(self, expected=None):
        with self._mutex:
            server = expected or self._server
            if self._server is server:
                self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()

    def cancel_login(self):
        with self._mutex:
            self._pending = None
            self._generation += 1
        self._stop_listener()

    def select_account(self, account_id):
        self.cancel_login()
        with self._locked():
            state = self._read()
            if not isinstance(account_id, str) or account_id not in state["accounts"]:
                raise ChatGPTAuthError("请选择已保存的 ChatGPT 账号。", category="configuration")
            state["active"] = account_id
            self._write(state)
            self._error = ""
        return self.status()

    def access_token(self, account_id=None):
        """Return a token to the official transport; never serialize this result."""
        with self._locked():
            state = self._read()
            key = account_id or state.get("active")
            record = state["accounts"].get(key)
            if not record or not record.get("access_token"):
                raise ChatGPTAuthError("请先为 ManiLoop 登录 ChatGPT。")
            if not REQUIRED_PLAN_SCOPES.issubset(record.get("scopes", [])):
                raise ChatGPTAuthError("此账号尚未授权 ManiLoop 使用 ChatGPT 套餐。")
            expiry = record.get("expires_at", 0)
            if not _number(expiry):
                raise ChatGPTAuthError("本地授权时间无效，请重新登录。")
            now = self._clock()
            if expiry > now + 60:
                return record["access_token"]
            earliest = record.get("earliest_refresh_at", 0)
            if _number(earliest) and earliest > now:
                if expiry > now:
                    return record["access_token"]
                raise ChatGPTAuthError("授权尚不能续期，请稍后重试。")
            if not record.get("refresh_token"):
                raise ChatGPTAuthError("授权已过期，请重新登录 ChatGPT。")
            try:
                response = self._http("POST", TOKEN_URL, data={"grant_type": "refresh_token",
                    "client_id": record["client_id"], "refresh_token": record["refresh_token"], "resource": RESOURCE})
                values = self._token_values(response, old=record)
            except ChatGPTAuthError as exc:
                if exc.code in _TERMINAL_REFRESH_ERRORS:
                    for field in _TOKEN_FIELDS:
                        record.pop(field, None)
                    self._write(state)
                    self._error = "ChatGPT 授权已失效，请重新登录。"
                    raise ChatGPTAuthError(self._error) from None
                raise
            # Retain the ID token whose nonce/identity was validated at sign-in.
            record.update(values)
            self._write(state)
            if not REQUIRED_PLAN_SCOPES.issubset(record["scopes"]):
                raise ChatGPTAuthError("ChatGPT 套餐授权已变更，请重新授权。")
            return record["access_token"]

    def logout(self, account_id=None):
        self.cancel_login()
        confirmed = True
        with self._locked():
            state = self._read()
            key = account_id or state.get("active")
            record = state["accounts"].get(key)
            if record:
                refresh = record.get("refresh_token")
                if refresh:
                    try:
                        self._http("POST", self._discovery()["revocation_endpoint"], data={
                            "token": refresh, "token_type_hint": "refresh_token", "client_id": record["client_id"]})
                    except ChatGPTAuthError:
                        confirmed = False
                for field in _TOKEN_FIELDS:
                    record.pop(field, None)
                self._write(state)
            self._error = "" if confirmed else "已清除本地登录，远端撤销未确认；可在 ChatGPT 设置中断开 ManiLoop。"
        return {**self.status(), "revocation_confirmed": confirmed}

    def close(self):
        self.cancel_login()
