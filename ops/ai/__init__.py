"""AI module operators and menu classes."""

from .ops_model_select import CLASSES as MODEL_SELECT_CLASSES
from .ops_generate import CLASSES as GENERATE_CLASSES
from .ops_fix_error import CLASSES as FIX_ERROR_CLASSES
from .ops_run_script import CLASSES as RUN_SCRIPT_CLASSES

CLASSES = (
    MODEL_SELECT_CLASSES
    + GENERATE_CLASSES
    + FIX_ERROR_CLASSES
    + RUN_SCRIPT_CLASSES
)
