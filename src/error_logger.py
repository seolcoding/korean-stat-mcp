"""
Dedicated error logger for tracking failed table processing
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ErrorLogger:
    """Specialized logger for tracking failed table processing"""
    
    def __init__(self, log_dir: Path = Path("logs")):
        """
        Initialize error logger
        
        Args:
            log_dir: Directory to store error logs
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup error logger
        self.logger = logging.getLogger('kosis.error')
        self.logger.setLevel(logging.ERROR)
        
        # Create error log file with timestamp
        error_log_path = self.log_dir / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # File handler for detailed errors
        file_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s\n%(message)s\n' + '='*80 + '\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.handlers = []
        self.logger.addHandler(file_handler)
        
        # Track failed tables
        self.failed_tables = []
        self.error_log_path = error_log_path
        
    def log_table_failure(self, table_id: str, metadata: Dict, error_details: Optional[str] = None):
        """
        Log detailed information about a failed table
        
        Args:
            table_id: Table ID that failed
            metadata: Table metadata
            error_details: Additional error information
        """
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "table_id": table_id,
            "table_name": metadata.get("TBL_NM", "Unknown"),
            "organization": metadata.get("ORG_NM", "Unknown"),
            "org_id": metadata.get("ORG_ID", "Unknown"),
            "date_range": f"{metadata.get('STRT_PRD_DE', 'Unknown')} ~ {metadata.get('END_PRD_DE', 'Unknown')}",
            "stat_name": metadata.get("STAT_NM", "Unknown"),
            "description": metadata.get("CONTENTS", "No description")[:500],
            "error_details": error_details or "Failed to fetch data with all period types"
        }
        
        # Add to failed tables list
        self.failed_tables.append(error_info)
        
        # Log detailed error
        self.logger.error(
            f"FAILED TABLE: {table_id}\n"
            f"Table Name: {error_info['table_name']}\n"
            f"Organization: {error_info['organization']} (ID: {error_info['org_id']})\n"
            f"Statistics: {error_info['stat_name']}\n"
            f"Date Range: {error_info['date_range']}\n"
            f"Description: {error_info['description']}\n"
            f"Error: {error_info['error_details']}"
        )
        
    def save_failed_tables_summary(self):
        """Save a JSON summary of all failed tables"""
        if not self.failed_tables:
            return
        
        summary_path = self.log_dir / f"failed_tables_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            "total_failures": len(self.failed_tables),
            "timestamp": datetime.now().isoformat(),
            "error_log_path": str(self.error_log_path),
            "failed_tables": self.failed_tables
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # Also create a simple text file with just table IDs for easy reference
        table_ids_path = self.log_dir / f"failed_table_ids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(table_ids_path, 'w', encoding='utf-8') as f:
            f.write("Failed Table IDs:\n")
            f.write("=" * 50 + "\n")
            for table in self.failed_tables:
                f.write(f"{table['table_id']} - {table['table_name']}\n")
        
        return summary_path, table_ids_path
    
    def get_failure_count(self) -> int:
        """Get the number of failed tables"""
        return len(self.failed_tables)
    
    def get_failed_table_ids(self) -> List[str]:
        """Get list of failed table IDs"""
        return [table['table_id'] for table in self.failed_tables]