import logging
import bpy
import sys

# Create a custom logger for M8
LOG_NAME = "M8_Toolbox"
logger = logging.getLogger(LOG_NAME)

class M8TelemetryErrorHandler(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        
        try:
            from ..property.keymap_helpers import _get_addon_prefs
            prefs = _get_addon_prefs()
            if (
                not prefs
                or not getattr(prefs, "auto_error_report", False)
                or getattr(prefs, "error_report_consent_version", 0) < 1
            ):
                return
        except Exception:
            return
            
        tb_str = ""
        if record.exc_info:
            import traceback
            exc_type, exc_value, exc_traceback = record.exc_info
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            tb_str = "".join(tb_lines)
            
        msg = record.getMessage()
        content = f"Log Message: {msg}\n"
        if tb_str:
            content += f"Traceback:\n{tb_str}"
        else:
            import inspect
            stack = inspect.stack()
            content += "Call Stack:\n"
            for frame in stack[2:10]:
                content += f"  File {frame.filename}, line {frame.lineno}, in {frame.function}\n"
                
        try:
            from .network import send_error_report_background
            send_error_report_background(content)
        except Exception:
            pass

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

# Ensure telemetry handler is registered
has_telemetry = any(isinstance(h, M8TelemetryErrorHandler) for h in logger.handlers)
if not has_telemetry:
    try:
        telemetry_handler = M8TelemetryErrorHandler()
        telemetry_handler.setLevel(logging.ERROR)
        logger.addHandler(telemetry_handler)
    except Exception:
        pass

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
