#!/usr/bin/env python3
"""
Test script to process a single KOSIS table
"""
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import colorlog
from src.kosis_wrapper import KosisAPIWrapper
from src.data_processor import DataProcessor

# Setup colored logging
log_colors = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}

console_formatter = colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)-8s%(reset)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors=log_colors
)

console_handler = colorlog.StreamHandler()
console_handler.setFormatter(console_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler]
)

def test_single_table():
    """Test processing of a single table"""
    
    # Load environment variables
    load_dotenv()
    
    # Configuration
    API_KEY = os.getenv('KOSIS_API_KEY')
    TABLE_ID = "DT_1YL20631"  # 고령인구비율(시도/시/군/구)
    
    # Check if API key is set
    if not API_KEY:
        print("ERROR: Please set KOSIS_API_KEY in your .env file")
        print("You can get an API key from: https://kosis.kr/openapi/")
        return
    
    # Load metadata for the table
    metadata_path = Path("kosis_data/kosis_metadata_final.json")
    
    print(f"Loading metadata from: {metadata_path}")
    with open(metadata_path, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)
    
    # Find metadata for our test table
    metadata = None
    for item in all_metadata:
        if item.get('TBL_ID') == TABLE_ID:
            metadata = item
            break
    
    if not metadata:
        print(f"No metadata found for table ID: {TABLE_ID}")
        return
    
    print(f"\nTable: {metadata['TBL_NM']}")
    print(f"Organization: {metadata['ORG_NM']}")
    print(f"Date range: {metadata['STRT_PRD_DE']} ~ {metadata['END_PRD_DE']}")
    
    # Initialize API wrapper
    api_wrapper = KosisAPIWrapper(API_KEY)
    
    # Find optimal period and fetch data
    print("\nFetching data from KOSIS API...")
    result = api_wrapper.find_optimal_period(metadata)
    
    if not result:
        print("No data found")
        return
    
    print(f"Found {len(result['data'])} records with period type: {result['period_name']}")
    
    # Transform data
    data_processor = DataProcessor()
    item_records = data_processor.transform_to_item_based(result['data'])
    
    print(f"\nTransformed to {len(item_records)} item-based records")
    
    # Show sample records
    print("\nSample records:")
    for i, record in enumerate(item_records[:5]):
        print(f"{i+1}. {record['item']}: {record['timestamp']} = {record['value']}")
    
    # Validate data
    validation = data_processor.validate_data(item_records)
    print("\nValidation results:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Total records: {validation['record_count']}")
    print(f"  Valid values: {validation['valid_values']}")
    print(f"  Unique items: {validation['unique_items']}")
    print(f"  Year range: {validation['year_range']}")
    
    # Save test output
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    saved_files = data_processor.save_formats(
        data=item_records,
        metadata=metadata,
        output_dir=output_dir,
        period_info=result,
        formats=["json", "csv"]
    )
    
    print("\nSaved test output files:")
    for fmt, path in saved_files.items():
        print(f"  {fmt}: {path}")


if __name__ == "__main__":
    test_single_table()