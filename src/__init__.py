"""
KOSIS Data Processor Package
"""
from .kosis_wrapper import KosisAPIWrapper
from .data_processor import DataProcessor
from .batch_processor import BatchProcessor

__version__ = "1.0.0"
__all__ = ["KosisAPIWrapper", "DataProcessor", "BatchProcessor"]