import logging
import sys

# Log Silencer: Drops high-frequency GUI polling from the log file
class FilterHeartbeatLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return msg.find("/api/telemetry") == -1 and msg.find("/api/graph") == -1

def setup_core_logger():
    """Initializes the root logger. Safe to call multiple times."""
    root_logger = logging.getLogger()
    
    # Prevent handler duplication if imported by multiple active modules
    if root_logger.hasHandlers():
        return root_logger

    root_logger.setLevel(logging.INFO)
    
    # Standardized format: Timestamp [LEVEL] ModuleName: Message
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # File Handler
    file_handler = logging.FileHandler("data/link-core.log")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Stream Handler (Console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # Attach the silencer to FastAPI's uvicorn access logger
    logging.getLogger("uvicorn.access").addFilter(FilterHeartbeatLogs())

    return root_logger