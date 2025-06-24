"""
Script to split 'item' field in existing JSON files into separate fields
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def split_item_field(item: str) -> Dict[str, str]:
    """
    Split item field into components
    
    Args:
        item: String like "서울특별시 - 계 - 추계인구"
        
    Returns:
        Dict with region, category, subcategory, data_name fields
    """
    parts = [part.strip() for part in item.split(' - ')]
    
    result = {}
    
    # First part is always region
    if len(parts) >= 1:
        result['region'] = parts[0]
    
    # Last part is always data_name
    if len(parts) >= 2:
        result['data_name'] = parts[-1]
    
    # Middle parts are categories
    if len(parts) >= 3:
        result['category'] = parts[1]
    
    if len(parts) >= 4:
        result['subcategory'] = parts[2]
    
    # If there are more parts, combine them into subcategory
    if len(parts) > 4:
        result['subcategory'] = ' - '.join(parts[2:-1])
    
    return result


def process_json_file(file_path: Path) -> bool:
    """
    Process a single JSON file to split item fields
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if data has the expected structure
        if 'data' not in data:
            logger.warning(f"No 'data' field in {file_path}")
            return False
        
        # Process each record
        modified = False
        for record in data['data']:
            if 'item' in record and isinstance(record['item'], str):
                # Split the item field
                split_fields = split_item_field(record['item'])
                
                # Add new fields to the record
                for field_name, field_value in split_fields.items():
                    record[field_name] = field_value
                
                modified = True
        
        # Save the modified data
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated: {file_path.name}")
            return True
        else:
            logger.info(f"No changes needed: {file_path.name}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to process all JSON files"""
    # Define the directory containing JSON files
    json_dir = Path(__file__).parent.parent.parent / "kosis_data" / "processed" / "json"
    
    if not json_dir.exists():
        logger.error(f"Directory not found: {json_dir}")
        return
    
    # Get all JSON files
    json_files = list(json_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files to process")
    
    # Process each file
    success_count = 0
    for file_path in tqdm(json_files, desc="Processing JSON files"):
        if process_json_file(file_path):
            success_count += 1
    
    logger.info(f"Successfully processed {success_count}/{len(json_files)} files")


if __name__ == "__main__":
    main()