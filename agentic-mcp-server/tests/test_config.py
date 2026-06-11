import pytest

from agentic_oracle_mcp.config import OracleSettings


def test_settings_from_env_accepts_username_alias_and_defaults() -> None:
    settings = OracleSettings.from_env(
        {
            "ORACLE_USERNAME": "app",
            "ORACLE_PASSWORD": "secret",
            "ORACLE_DSN": "localhost:1521/FREEPDB1",
        }
    )

    assert settings.username == "app"
    assert settings.password == "secret"
    assert settings.dsn == "localhost:1521/FREEPDB1"
    assert settings.default_fetch_limit == 100
    assert settings.pool_min == 1
    assert settings.pool_max == 4


def test_settings_validates_required_values() -> None:
    settings = OracleSettings.from_env({})

    with pytest.raises(ValueError, match="ORACLE_USER"):
        settings.validate()


def test_settings_rejects_invalid_integer() -> None:
    with pytest.raises(ValueError, match="ORACLE_FETCH_LIMIT"):
        OracleSettings.from_env({"ORACLE_FETCH_LIMIT": "many"})


def test_connect_kwargs_includes_optional_wallet_values() -> None:
    settings = OracleSettings.from_env(
        {
            "ORACLE_USER": "app",
            "ORACLE_PASSWORD": "secret",
            "ORACLE_DSN": "db",
            "ORACLE_CONFIG_DIR": "/opt/oracle/network/admin",
            "ORACLE_WALLET_LOCATION": "/opt/oracle/wallet",
            "ORACLE_WALLET_PASSWORD": "wallet-secret",
        }
    )

    assert settings.connect_kwargs() == {
        "user": "app",
        "password": "secret",
        "dsn": "db",
        "config_dir": "/opt/oracle/network/admin",
        "wallet_location": "/opt/oracle/wallet",
        "wallet_password": "wallet-secret",
    }
