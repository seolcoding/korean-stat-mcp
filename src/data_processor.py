"""
Data processor for transforming KOSIS API responses into various formats
"""
import json
import pandas as pd
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and transform KOSIS data into various formats"""
    
    def __init__(self):
        """Initialize data processor"""
        self.processed_count = 0
        
    def transform_to_item_based(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Transform KOSIS raw data to item-based format
        
        Args:
            raw_data: Raw data from KOSIS API
            
        Returns:
            List of records in format: [{item, timestamp, value}]
        """
        processed_records = []
        
        if not raw_data:
            return processed_records
        
        for record in raw_data:
            # Build item name from C1_NM through C8_NM and ITM_NM
            item_parts = []
            
            # Collect classification names (C1 through C8)
            for i in range(1, 9):
                c_nm = record.get(f"C{i}_NM")
                if c_nm and c_nm.strip():
                    item_parts.append(c_nm.strip())
            
            # Add item name
            itm_nm = record.get("ITM_NM", "").strip()
            if itm_nm:
                item_parts.append(itm_nm)
            
            # Create full item name
            item_name = " - ".join(item_parts) if item_parts else "Unknown"
            
            # Get timestamp and value
            timestamp = record.get("PRD_DE", "")
            value = record.get("DT", "")
            
            # Convert value to numeric if possible
            try:
                value = float(value) if value and value != '-' else None
            except ValueError:
                value = None
            
            processed_records.append({
                "item": item_name,
                "timestamp": timestamp,
                "value": value,
                # Keep original classification codes for reference
                "item_codes": {f"C{i}": record.get(f"C{i}", "") for i in range(1, 9) if record.get(f"C{i}")},
                "itm_id": record.get("ITM_ID", "")
            })
        
        return processed_records
    
    def extract_year_columns(self, data: List[Dict]) -> List[str]:
        """
        Extract unique years from timestamp data
        
        Args:
            data: Item-based data with timestamp field
            
        Returns:
            Sorted list of year strings
        """
        years = set()
        
        for record in data:
            timestamp = str(record.get("timestamp", ""))
            if len(timestamp) >= 4:
                year = timestamp[:4]
                if year.isdigit() and 1900 <= int(year) <= 2100:
                    years.add(year)
        
        return sorted(list(years))
    
    def pivot_to_wide_format(self, item_records: List[Dict], include_all_years: bool = False) -> pd.DataFrame:
        """
        Pivot item-based records to wide format with year columns
        
        Args:
            item_records: List of item-based records
            include_all_years: Whether to include all years (even with no data)
            
        Returns:
            DataFrame in wide format with columns: [item, category, year1, year2, ...]
        """
        if not item_records:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(item_records)
        
        # Extract year from timestamp
        df['year'] = df['timestamp'].astype(str).str[:4]
        
        # Filter valid years
        df = df[df['year'].str.isdigit()]
        df = df[df['year'].astype(int).between(1900, 2100)]
        
        # Create pivot table
        pivot_df = df.pivot_table(
            index='item',
            columns='year',
            values='value',
            aggfunc='first'  # Use first value if duplicates exist
        )
        
        # Reset index to make 'item' a column
        pivot_df = pivot_df.reset_index()
        
        # Add category column (simplified for now - could be enhanced)
        pivot_df.insert(1, 'category', 'Statistics')
        
        # Sort columns: item, category, then years in chronological order
        year_cols = [col for col in pivot_df.columns if col not in ['item', 'category']]
        year_cols.sort()
        
        column_order = ['item', 'category'] + year_cols
        pivot_df = pivot_df[column_order]
        
        return pivot_df
    
    def augment_with_metadata(self, data: Dict, metadata: Dict) -> Dict:
        """
        Augment processed data with metadata information
        
        Args:
            data: Processed data
            metadata: Original metadata from KOSIS
            
        Returns:
            Enriched data with metadata
        """
        enriched_data = {
            "metadata": {
                "org_id": metadata.get("ORG_ID"),
                "org_name": metadata.get("ORG_NM"),
                "table_id": metadata.get("TBL_ID"),
                "table_name": metadata.get("TBL_NM"),
                "stat_id": metadata.get("STAT_ID"),
                "stat_name": metadata.get("STAT_NM"),
                "date_range": f"{metadata.get('STRT_PRD_DE')} ~ {metadata.get('END_PRD_DE')}",
                "description": metadata.get("CONTENTS", ""),
                "item_info": metadata.get("ITEM03", ""),
                "source_url": metadata.get("LINK_URL", ""),
                "last_updated": datetime.now().isoformat()
            },
            "data": data
        }
        
        return enriched_data
    
    def save_formats(
        self, 
        data: Any, 
        metadata: Dict,
        output_dir: Path,
        period_info: Optional[Dict] = None,
        formats: List[str] = ["json", "csv", "parquet"]
    ) -> Dict[str, Path]:
        """
        Save data in multiple formats
        
        Args:
            data: Processed data (can be list or DataFrame)
            metadata: Table metadata
            output_dir: Output directory path
            period_info: Information about the data period
            formats: List of output formats to save
            
        Returns:
            Dict mapping format to saved file path
        """
        table_id = metadata.get("TBL_ID", "unknown")
        table_name = metadata.get("TBL_NM", "").replace("/", "_").replace(" ", "_")
        saved_files = {}
        
        # Ensure output directories exist
        for fmt in formats:
            (output_dir / fmt).mkdir(parents=True, exist_ok=True)
        
        try:
            # Save JSON format (long format with full metadata)
            if "json" in formats:
                json_data = self.augment_with_metadata(data, metadata)
                if period_info:
                    json_data["metadata"]["period_type"] = period_info.get("period_type")
                    json_data["metadata"]["period_name"] = period_info.get("period_name")
                
                json_path = output_dir / "json" / f"{table_id}_{table_name}.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                saved_files["json"] = json_path
                logger.info(f"Saved JSON: {json_path}")
            
            # For CSV and Parquet, we need DataFrame format
            if "csv" in formats or "parquet" in formats:
                if isinstance(data, list):
                    # Convert to wide format DataFrame
                    df = self.pivot_to_wide_format(data)
                else:
                    df = data
                
                # Save CSV format
                if "csv" in formats and not df.empty:
                    csv_path = output_dir / "csv" / f"{table_id}_{table_name}.csv"
                    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                    saved_files["csv"] = csv_path
                    logger.info(f"Saved CSV: {csv_path}")
                
                # Save Parquet format
                if "parquet" in formats and not df.empty:
                    parquet_path = output_dir / "parquet" / f"{table_id}_{table_name}.parquet"
                    df.to_parquet(parquet_path, index=False, engine='pyarrow')
                    saved_files["parquet"] = parquet_path
                    logger.info(f"Saved Parquet: {parquet_path}")
        
        except Exception as e:
            logger.error(f"Error saving data for {table_id}: {e}")
            raise
        
        self.processed_count += 1
        return saved_files
    
    def validate_data(self, data: List[Dict]) -> Dict[str, Any]:
        """
        Validate processed data and return statistics
        
        Args:
            data: Processed data records
            
        Returns:
            Dictionary with validation results and statistics
        """
        if not data:
            return {
                "valid": False,
                "record_count": 0,
                "error": "No data records"
            }
        
        total_records = len(data)
        valid_values = sum(1 for record in data if record.get("value") is not None)
        unique_items = len(set(record.get("item", "") for record in data))
        unique_timestamps = len(set(record.get("timestamp", "") for record in data))
        
        years = self.extract_year_columns(data)
        year_range = f"{years[0]} - {years[-1]}" if years else "N/A"
        
        validation_result = {
            "valid": True,
            "record_count": total_records,
            "valid_values": valid_values,
            "null_values": total_records - valid_values,
            "unique_items": unique_items,
            "unique_timestamps": unique_timestamps,
            "year_range": year_range,
            "years_available": len(years)
        }
        
        # Check for data quality issues
        if valid_values == 0:
            validation_result["valid"] = False
            validation_result["error"] = "No valid numeric values found"
        elif valid_values < total_records * 0.1:  # Less than 10% valid values
            validation_result["warning"] = f"Low data quality: only {valid_values/total_records*100:.1f}% valid values"
        
        return validation_result