"""Configuration helpers for the Oracle MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def _truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _int_from_env(
    environ: Mapping[str, str],
    key: str,
    *,
    default: int,
    minimum: int | None = None,
) -> int:
    raw = environ.get(key)
    if raw is None or raw.strip() == "":
        return default

    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc

    if minimum is not None and parsed < minimum:
        raise ValueError(f"{key} must be greater than or equal to {minimum}")
    return parsed


def _first_present(environ: Mapping[str, str], *keys: str) -> str | None:
    for key in keys:
        value = environ.get(key)
        if value is not None and value.strip() != "":
            return value
    return None


@dataclass(frozen=True)
class OracleSettings:
    """Runtime settings used to connect to Oracle."""

    username: str | None
    password: str | None
    dsn: str | None
    config_dir: str | None = None
    wallet_location: str | None = None
    wallet_password: str | None = None
    thick_mode: bool = False
    client_lib_dir: str | None = None
    pool_min: int = 1
    pool_max: int = 4
    pool_increment: int = 1
    default_fetch_limit: int = 100
    call_timeout_ms: int = 30_000
    allow_dml: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "OracleSettings":
        env = os.environ if environ is None else environ
        return cls(
            username=_first_present(env, "ORACLE_USER", "ORACLE_USERNAME"),
            password=_first_present(env, "ORACLE_PASSWORD"),
            dsn=_first_present(env, "ORACLE_DSN"),
            config_dir=_first_present(env, "ORACLE_CONFIG_DIR", "TNS_ADMIN"),
            wallet_location=_first_present(env, "ORACLE_WALLET_LOCATION"),
            wallet_password=_first_present(env, "ORACLE_WALLET_PASSWORD"),
            thick_mode=_truthy(env.get("ORACLE_THICK_MODE")),
            client_lib_dir=_first_present(env, "ORACLE_CLIENT_LIB_DIR"),
            pool_min=_int_from_env(env, "ORACLE_POOL_MIN", default=1, minimum=1),
            pool_max=_int_from_env(env, "ORACLE_POOL_MAX", default=4, minimum=1),
            pool_increment=_int_from_env(
                env, "ORACLE_POOL_INCREMENT", default=1, minimum=1
            ),
            default_fetch_limit=_int_from_env(
                env, "ORACLE_FETCH_LIMIT", default=100, minimum=1
            ),
            call_timeout_ms=_int_from_env(
                env, "ORACLE_CALL_TIMEOUT_MS", default=30_000, minimum=1
            ),
            allow_dml=_truthy(env.get("ORACLE_ALLOW_DML")),
        )

    def missing_required(self) -> list[str]:
        missing: list[str] = []
        if not self.username:
            missing.append("ORACLE_USER")
        if not self.password:
            missing.append("ORACLE_PASSWORD")
        if not self.dsn:
            missing.append("ORACLE_DSN")
        return missing

    def validate(self) -> None:
        missing = self.missing_required()
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required Oracle configuration: {joined}")

        if self.pool_max < self.pool_min:
            raise ValueError("ORACLE_POOL_MAX must be greater than or equal to ORACLE_POOL_MIN")

    def connect_kwargs(self) -> dict[str, object]:
        self.validate()
        kwargs: dict[str, object] = {
            "user": self.username,
            "password": self.password,
            "dsn": self.dsn,
        }
        if self.config_dir:
            kwargs["config_dir"] = self.config_dir
        if self.wallet_location:
            kwargs["wallet_location"] = self.wallet_location
        if self.wallet_password:
            kwargs["wallet_password"] = self.wallet_password
        return kwargs
