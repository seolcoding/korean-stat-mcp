#!/usr/bin/env python3
"""
Main script for processing KOSIS statistical data
"""
import argparse
import logging
import sys
from pathlib import Path
import yaml
from datetime import datetime
import os
from dotenv import load_dotenv
import colorlog

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.batch_processor import BatchProcessor


def setup_logging(config: dict):
    """Setup logging configuration with colored output"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    
    # Color scheme for different log levels
    log_colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    
    # Formatter for console output with colors
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)-8s%(reset)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors=log_colors,
        secondary_log_colors={
            'message': {
                'ERROR': 'red',
                'CRITICAL': 'red'
            }
        }
    )
    
    # Formatter for file output (no colors)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with colors
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    
    # File handler without colors (all logs)
    file_handler = logging.FileHandler(log_config.get('file', 'kosis_processor.log'), encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    
    # Error file handler (errors only)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s\n%(message)s\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler = logging.FileHandler('error.log', encoding='utf-8')
    error_handler.setFormatter(error_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Reduce noise from some libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)


def validate_config(config: dict) -> bool:
    """Validate configuration"""
    # First try to get API key from environment
    api_key = os.getenv('KOSIS_API_KEY')
    
    # If not in environment, try config file
    if not api_key:
        api_key = config.get('api', {}).get('api_key', '')
    
    if not api_key or api_key == "<YOUR_API_KEY_HERE>":
        print("ERROR: Please set your KOSIS API key")
        print("You can either:")
        print("1. Set KOSIS_API_KEY in your .env file")
        print("2. Set api_key in config.yaml")
        print("Get an API key from: https://kosis.kr/openapi/")
        return False
    
    # Update config with API key from environment if needed
    config['api']['api_key'] = api_key
    
    # Check input files exist
    csv_path = Path(config['input']['csv_path'])
    metadata_path = Path(config['input']['metadata_path'])
    
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return False
    
    if not metadata_path.exists():
        print(f"ERROR: Metadata file not found: {metadata_path}")
        return False
    
    return True


def main():
    """Main execution function"""
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Process KOSIS statistical data')
    parser.add_argument(
        '--config', 
        type=str, 
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--test', 
        action='store_true',
        help='Test mode - process only first 5 tables'
    )
    parser.add_argument(
        '--table-id',
        type=str,
        help='Process only a specific table ID'
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Retry previously failed tables'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}")
        sys.exit(1)
    
    config = load_config(config_path)
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    if not validate_config(config):
        sys.exit(1)
    
    # Print startup information
    print("\n" + "="*60)
    print("KOSIS Data Processor")
    print("="*60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Configuration: {config_path}")
    print(f"Output directory: {config['output']['base_dir']}")
    print("="*60 + "\n")
    
    try:
        # Initialize batch processor
        processor = BatchProcessor(
            api_key=config['api']['api_key'],
            output_dir=Path(config['output']['base_dir']),
            max_workers=config['processing']['max_workers'],
            rate_limit=config['api']['rate_limit']
        )
        
        if args.table_id:
            # Process single table
            logger.info(f"Processing single table: {args.table_id}")
            
            # Load metadata
            metadata_path = Path(config['input']['metadata_path'])
            import json
            with open(metadata_path, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)
            
            # Find metadata for specific table
            metadata = None
            for item in all_metadata:
                if item.get('TBL_ID') == args.table_id:
                    metadata = item
                    break
            
            if metadata:
                success, result = processor.process_single_table(args.table_id, metadata)
                if success:
                    print(f"\nSuccessfully processed {args.table_id}")
                    print(f"Records: {result.get('records', 0)}")
                else:
                    print(f"\nFailed to process {args.table_id}: {result.get('error')}")
            else:
                print(f"No metadata found for table ID: {args.table_id}")
        
        elif args.retry_failed:
            # Retry failed tables
            logger.info("Retrying previously failed tables")
            processor.handle_failures_with_retry()
        
        else:
            # Process all tables
            csv_path = Path(config['input']['csv_path'])
            metadata_path = Path(config['input']['metadata_path'])
            
            processor.process_all_tables(csv_path, metadata_path, test_mode=args.test)
        
        print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show error log location if there were errors
        error_log_path = Path("error.log")
        if error_log_path.exists() and error_log_path.stat().st_size > 0:
            print(f"\n⚠️  Errors were logged to: {error_log_path}")
            print("Check the logs directory for detailed error summaries.")
        
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()