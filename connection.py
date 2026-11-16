import os

import snowflake.connector


def get_connection() -> snowflake.connector.SnowflakeConnection:
    """Open a fresh connection from a profile in connections.toml."""
    connection_name = os.getenv("SNOWFLAKE_CONNECTION_NAME", "fm94707.ap-southeast-2")
    return snowflake.connector.connect(connection_name=connection_name)
