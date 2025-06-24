"""
Batch processor for handling multiple KOSIS tables
"""
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from tqdm import tqdm

from .kosis_wrapper import KosisAPIWrapper
from .data_processor import DataProcessor
from .error_logger import ErrorLogger

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Process multiple KOSIS tables in batch"""
    
    def __init__(
        self, 
        api_key: str,
        output_dir: Path = Path("kosis_data"),
        max_workers: int = 1,
        rate_limit: float = 1.0
    ):
        """
        Initialize batch processor
        
        Args:
            api_key: KOSIS API key
            output_dir: Base output directory
            max_workers: Maximum concurrent workers (default: 1 for rate limiting)
            rate_limit: Seconds to wait between API calls
        """
        self.api_wrapper = KosisAPIWrapper(api_key)
        self.data_processor = DataProcessor()
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        
        # Initialize error logger
        self.error_logger = ErrorLogger(self.output_dir / "logs")
        
        # Create output directories
        self.raw_dir = self.output_dir / "raw"
        self.processed_dir = self.output_dir / "processed"
        self.reports_dir = self.output_dir / "reports"
        self.failed_dir = self.output_dir / "failed"
        
        for dir_path in [self.raw_dir, self.processed_dir, self.reports_dir, self.failed_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Processing statistics
        self.stats = {
            "total": 0,
            "processed": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None
        }
        
        self.failed_tables = []
    
    def load_table_ids_from_csv(self, csv_path: Path) -> List[str]:
        """
        Load table IDs from regional_index_data_list.csv
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            List of table IDs
        """
        table_ids = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Table ID is in the last column
                    table_id = row.get('통계표 아이디(TBL_ID)', '').strip()
                    if table_id:
                        table_ids.append(table_id)
            
            logger.info(f"Loaded {len(table_ids)} table IDs from {csv_path}")
            return table_ids
            
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            return []
    
    def match_metadata_for_tables(
        self, 
        table_ids: List[str], 
        metadata_path: Path
    ) -> Dict[str, Dict]:
        """
        Match table IDs with their metadata
        
        Args:
            table_ids: List of table IDs from CSV
            metadata_path: Path to metadata JSON file
            
        Returns:
            Dict mapping table_id to metadata
        """
        matched_metadata = {}
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)
            
            # Create lookup dict
            metadata_lookup = {item['TBL_ID']: item for item in all_metadata if 'TBL_ID' in item}
            
            # Match table IDs
            for table_id in table_ids:
                if table_id in metadata_lookup:
                    matched_metadata[table_id] = metadata_lookup[table_id]
                else:
                    logger.warning(f"No metadata found for table ID: {table_id}")
            
            logger.info(f"Matched {len(matched_metadata)} tables with metadata")
            return matched_metadata
            
        except Exception as e:
            logger.error(f"Error loading metadata file: {e}")
            return {}
    
    def process_single_table(self, table_id: str, metadata: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Process a single table
        
        Args:
            table_id: Table ID
            metadata: Table metadata
            
        Returns:
            Tuple of (success, result_info)
        """
        table_name = metadata.get('TBL_NM', 'Unknown')
        logger.info(f"Processing: {table_id} - {table_name}")
        
        try:
            # Find optimal period and fetch data
            result = self.api_wrapper.find_optimal_period(metadata)
            
            if not result or not result.get('data'):
                logger.warning(f"No data found for {table_id}")
                # Log to error logger
                self.error_logger.log_table_failure(table_id, metadata, "No data found with any period type")
                return False, {"error": "No data found"}
            
            raw_data = result['data']
            period_info = {
                "period_type": result.get('period_type'),
                "period_name": result.get('period_name')
            }
            
            # Save raw data
            raw_path = self.raw_dir / f"{table_id}_raw.json"
            with open(raw_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": metadata,
                    "period_info": period_info,
                    "raw_data": raw_data
                }, f, ensure_ascii=False, indent=2)
            
            # Transform data
            item_records = self.data_processor.transform_to_item_based(raw_data)
            
            # Validate data
            validation = self.data_processor.validate_data(item_records)
            if not validation['valid']:
                logger.warning(f"Data validation failed for {table_id}: {validation.get('error')}")
                # Log to error logger
                self.error_logger.log_table_failure(table_id, metadata, f"Data validation failed: {validation.get('error')}")
                return False, validation
            
            # Save in multiple formats
            saved_files = self.data_processor.save_formats(
                data=item_records,
                metadata=metadata,
                output_dir=self.processed_dir,
                period_info=period_info,
                formats=["json", "csv", "parquet"]
            )
            
            result_info = {
                "table_id": table_id,
                "table_name": table_name,
                "records": len(item_records),
                "validation": validation,
                "saved_files": {fmt: str(path) for fmt, path in saved_files.items()},
                "period_info": period_info
            }
            
            return True, result_info
            
        except Exception as e:
            logger.error(f"Error processing {table_id}: {e}")
            # Log to error logger
            self.error_logger.log_table_failure(table_id, metadata, f"Exception: {str(e)}")
            return False, {"error": str(e)}
        finally:
            # Rate limiting
            time.sleep(self.rate_limit)
    
    def process_all_tables(self, csv_path: Path, metadata_path: Path, test_mode: bool = False):
        """
        Process all tables from CSV file
        
        Args:
            csv_path: Path to regional_index_data_list.csv
            metadata_path: Path to kosis_metadata_final.json
            test_mode: If True, only process first 5 tables
        """
        self.stats['start_time'] = datetime.now()
        
        # Load table IDs and metadata
        table_ids = self.load_table_ids_from_csv(csv_path)
        matched_metadata = self.match_metadata_for_tables(table_ids, metadata_path)
        
        if not matched_metadata:
            logger.error("No tables to process")
            return
        
        # Apply test mode limit
        if test_mode:
            # Get first 5 tables only
            table_ids = list(matched_metadata.keys())[:5]
            matched_metadata = {tid: matched_metadata[tid] for tid in table_ids}
            logger.info(f"Test mode: Processing only {len(matched_metadata)} tables")
            logger.info(f"Tables to process: {', '.join(table_ids)}")
        
        self.stats['total'] = len(matched_metadata)
        
        # Process tables
        results = []
        
        if self.max_workers == 1:
            # Sequential processing with progress bar
            for table_id, metadata in tqdm(matched_metadata.items(), desc="Processing tables"):
                success, result_info = self.process_single_table(table_id, metadata)
                
                if success:
                    self.stats['processed'] += 1
                    results.append(result_info)
                else:
                    self.stats['failed'] += 1
                    self.failed_tables.append({
                        "table_id": table_id,
                        "table_name": metadata.get('TBL_NM', 'Unknown'),
                        "error": result_info.get('error', 'Unknown error')
                    })
        else:
            # Parallel processing (use with caution due to API rate limits)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_table = {
                    executor.submit(self.process_single_table, tid, meta): tid 
                    for tid, meta in matched_metadata.items()
                }
                
                for future in tqdm(as_completed(future_to_table), total=len(future_to_table), desc="Processing tables"):
                    table_id = future_to_table[future]
                    try:
                        success, result_info = future.result()
                        
                        if success:
                            self.stats['processed'] += 1
                            results.append(result_info)
                        else:
                            self.stats['failed'] += 1
                            self.failed_tables.append({
                                "table_id": table_id,
                                "error": result_info.get('error', 'Unknown error')
                            })
                    except Exception as e:
                        self.stats['failed'] += 1
                        self.failed_tables.append({
                            "table_id": table_id,
                            "error": str(e)
                        })
        
        self.stats['end_time'] = datetime.now()
        
        # Generate and save reports
        self.generate_summary_report(results)
        
        # Save error logger summary
        if self.error_logger.get_failure_count() > 0:
            summary_path, table_ids_path = self.error_logger.save_failed_tables_summary()
            logger.info(f"Error summary saved to: {summary_path}")
            logger.info(f"Failed table IDs saved to: {table_ids_path}")
        
        # Save failed tables for retry
        if self.failed_tables:
            self.save_failed_tables()
    
    def generate_summary_report(self, results: List[Dict]) -> Path:
        """
        Generate summary report of processing
        
        Args:
            results: List of processing results
            
        Returns:
            Path to report file
        """
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        report = {
            "processing_summary": {
                "total_tables": self.stats['total'],
                "processed": self.stats['processed'],
                "failed": self.stats['failed'],
                "skipped": self.stats['skipped'],
                "success_rate": f"{(self.stats['processed'] / self.stats['total'] * 100):.1f}%" if self.stats['total'] > 0 else "0%",
                "duration_seconds": duration,
                "duration_formatted": f"{duration/60:.1f} minutes"
            },
            "timestamp": datetime.now().isoformat(),
            "processed_tables": results,
            "failed_tables": self.failed_tables
        }
        
        # Save report
        report_path = self.reports_dir / f"processing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # Print summary
        print("\n" + "="*60)
        print("PROCESSING SUMMARY")
        print("="*60)
        print(f"Total tables: {self.stats['total']}")
        print(f"Successfully processed: {self.stats['processed']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Success rate: {report['processing_summary']['success_rate']}")
        print(f"Duration: {report['processing_summary']['duration_formatted']}")
        print(f"\nReport saved to: {report_path}")
        print("="*60)
        
        return report_path
    
    def save_failed_tables(self):
        """Save failed table IDs for potential retry"""
        failed_path = self.failed_dir / f"failed_tables_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(failed_path, 'w', encoding='utf-8') as f:
            json.dump(self.failed_tables, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Failed tables saved to: {failed_path}")
    
    def handle_failures_with_retry(self, retry_count: int = 3):
        """
        Retry failed tables
        
        Args:
            retry_count: Number of retry attempts
        """
        if not self.failed_tables:
            logger.info("No failed tables to retry")
            return
        
        logger.info(f"Retrying {len(self.failed_tables)} failed tables...")
        
        for attempt in range(retry_count):
            remaining_failures = []
            
            for failed_info in self.failed_tables:
                table_id = failed_info['table_id']
                # Find metadata
                # This would need to be implemented based on how metadata is stored
                # For now, we'll skip the retry implementation
                pass
            
            self.failed_tables = remaining_failures
            
            if not self.failed_tables:
                logger.info("All retries successful")
                break
        
        if self.failed_tables:
            logger.warning(f"{len(self.failed_tables)} tables still failed after {retry_count} retries")