"""Adapter package.

Import concrete adapters directly, for example:
    from adapters.oracle import OracleAdapter

Keeping this file lightweight avoids importing optional provider adapters that
may not be installed or present in an Oracle-only setup.
"""

__all__: list[str] = []
