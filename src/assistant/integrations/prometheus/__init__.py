# This file makes the src directory a Python package
from .client import get_prometheus_client

__all__ = ["get_prometheus_client"]
