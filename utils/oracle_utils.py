import sys
import logging
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

def setup_logging(debug=False)  -> logging.Logger:
    """
    Setup the logging configuration for the application. 
    """          
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    # Remove all existing handlers to prevent accumulation
    for handler in logger.handlers:
        logger.removeHandler(handler)
    
    handlers = []
           
    # Create a new handler
    try:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG if debug else logging.INFO)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        handlers.append(handler)
    except Exception as e:
        logger.error(f"Failed to create stdout log handler: {e}", file=sys.stderr)

    # Add the handlers to the logger
    for handler in handlers:
        logger.addHandler(handler)
    
    return logger

def create_db_connection(connection_string: str) -> object:
    """
    Create a new database connection object using the provided connection string.

    Args:
        connection_string (str): The connection string to use to connect to the database.
    
    Returns:
        object: The database connection object.
    """
    try:
        engine = create_engine(connection_string)
        connection = engine.connect()
        logger.debug("Connected to oracle database successfully")
        return connection
    except Exception as e:
        logger.error(f"Failed to create oracle database connection: {e}")
        sys.exit(1)