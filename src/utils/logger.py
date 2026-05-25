import logging
import sys

class ColoredFormatter(logging.Formatter):
    RED = '\033[91m'
    RESET = '\033[0m'

    def format(self, record):
        if record.levelno >= logging.ERROR:
            return f"{self.RED}{super().format(record)}{self.RESET}"
        return super().format(record)

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Returns a configured logger with a standard format.
    Ensures that handlers are not duplicated if the logger already exists.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent propagation to the root logger to avoid duplicate prints
    logger.propagate = False

    if not logger.handlers:
        formatter = ColoredFormatter(
            fmt="[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Output to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
