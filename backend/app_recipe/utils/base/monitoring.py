import time
from typing import Callable, Any
from functools import wraps
from prometheus_client import Counter, Histogram, start_http_server
from backend.app.utils.logger import get_logger

logger = get_logger('monitoring')

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)

ERROR_COUNT = Counter(
    'http_errors_total',
    'Total number of HTTP errors',
    ['method', 'endpoint', 'error_type']
)

def monitor_performance(func: Callable) -> Callable:
    """
    Decorator to monitor function performance.
    
    Args:
        func: The function to monitor
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log performance metrics
            logger.info(f"Function {func.__name__} took {duration:.2f} seconds")
            
            # Update Prometheus metrics
            REQUEST_LATENCY.labels(
                method=kwargs.get('method', 'unknown'),
                endpoint=func.__name__
            ).observe(duration)
            
            return result
        except Exception as e:
            # Log error metrics
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            
            # Update error counter
            ERROR_COUNT.labels(
                method=kwargs.get('method', 'unknown'),
                endpoint=func.__name__,
                error_type=type(e).__name__
            ).inc()
            
            raise
    return wrapper

def start_monitoring(port: int = 8000) -> None:
    """
    Start the Prometheus metrics server.
    
    Args:
        port: Port to expose metrics on
    """
    try:
        start_http_server(port)
        logger.info(f"Started metrics server on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {str(e)}", exc_info=True)

class PerformanceMonitor:
    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()
        self.logger = get_logger(f'performance.{name}')
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.logger.info(f"Operation {self.name} took {duration:.2f} seconds")
        
        if exc_type is not None:
            self.logger.error(f"Operation {self.name} failed: {str(exc_val)}", exc_info=True)
    
    def log_metric(self, metric_name: str, value: float) -> None:
        """Log a custom metric."""
        self.logger.info(f"Metric {metric_name}: {value}")
        
        # Update Prometheus metric if it exists
        metric = globals().get(metric_name.upper())
        if metric:
            metric.labels(operation=self.name).observe(value) 