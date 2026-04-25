import logging
import bpy
import sys

# Create a custom logger for M8
LOG_NAME = "M8_Toolbox"
logger = logging.getLogger(LOG_NAME)

# Prevent adding multiple handlers if reloaded
if not logger.handlers:
    logger.setLevel(logging.DEBUG)  # Default level, can be configured via preferences later

    # Create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(ch)

def get_logger():
    """Return the central M8 logger instance."""
    return logger

def log_error(msg, exc_info=True):
    """Convenience method to log an error."""
    logger.error(msg, exc_info=exc_info)

def log_warning(msg):
    """Convenience method to log a warning."""
    logger.warning(msg)

def log_info(msg):
    """Convenience method to log info."""
    logger.info(msg)

def log_debug(msg):
    """Convenience method to log debug info."""
    logger.debug(msg)

def report_and_log(operator, level, msg):
    """Log the message and also report it to the Blender UI."""
    if level in {'INFO', 'WARNING', 'ERROR'}:
        operator.report({level}, msg)
    
    if level == 'INFO':
        logger.info(msg)
    elif level == 'WARNING':
        logger.warning(msg)
    elif level == 'ERROR':
        logger.error(msg)
    else:
        logger.debug(msg)
