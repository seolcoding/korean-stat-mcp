"""
KOSIS API Wrapper for fetching statistical data from Korean Statistical Information Service
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class KosisAPIWrapper:
    """Wrapper class for KOSIS OpenAPI"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://kosis.kr/openapi/Param/statisticsParameterData.do",
    ):
        """
        Initialize KOSIS API wrapper

        Args:
            api_key: KOSIS API key
            base_url: Base URL for KOSIS API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()

    def fix_malformed_json(self, response_text: str) -> Optional[Dict]:
        """
        Fix KOSIS's non-standard JSON response

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        if not response_text or response_text.strip() == "":
            return None

        try:
            # Fix unquoted keys in JSON
            corrected_text = re.sub(
                r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', response_text
            )
            return json.loads(corrected_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Response preview: {response_text[:500]}...")
            return None

    def fetch_table_data(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str = "Y",
        obj_l1: str = "ALL",
        obj_l2: Optional[str] = None,
        itm_id: str = "ALL",
        timeout: int = 60,
    ) -> Optional[List[Dict]]:
        """
        Fetch data for a specific table from KOSIS API

        Args:
            org_id: Organization ID
            tbl_id: Table ID
            start_date: Start date (format depends on prd_se)
            end_date: End date (format depends on prd_se)
            prd_se: Period type (M=Month/Bi-monthly, Q=Quarter, S=Semi-annual, Y=Year, F=Multi-year, IR=Irregular)
            obj_l1: Object level 1 (default: ALL)
            obj_l2: Object level 2 (optional, used if obj_l1 alone fails)
            itm_id: Item ID (default: ALL)
            timeout: Request timeout in seconds

        Returns:
            List of data records or None if request fails
        """
        # Build base parameters
        params = {
            "method": "getList",
            "apiKey": self.api_key,
            "format": "json",
            "orgId": org_id,
            "tblId": tbl_id,
            "objL1": obj_l1,
            "itmId": itm_id,
            "prdSe": prd_se,
            "startPrdDe": start_date,
            "endPrdDe": end_date,
        }
        
        # Add objL2 only if provided
        if obj_l2:
            params["objL2"] = obj_l2

        try:
            # Log the full URL for debugging
            request_url = self.session.prepare_request(
                requests.Request('GET', self.base_url, params=params)
            ).url
            logger.debug(f"🌐 API Request URL: {request_url}")
            
            response = self.session.get(self.base_url, params=params, timeout=timeout)
            response.raise_for_status()

            # Log response status
            logger.debug(f"📥 Response status code: {response.status_code}")
            
            data = self.fix_malformed_json(response.text)

            if data and "errMsg" not in data:
                logger.debug(f"✅ Successfully retrieved {len(data) if isinstance(data, list) else 'unknown'} records")
                return data
            elif data and "errMsg" in data:
                logger.warning(f"⚠️  API error for {tbl_id}: {data.get('errMsg')}")
                logger.debug(f"📋 Error response: {data}")
                return None
            else:
                logger.debug("❌ No data returned or failed to parse response")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"🔥 API request failed for {tbl_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Unexpected error for {tbl_id}: {e}")
            return None

    def fetch_table_data_with_retry(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str = "Y",
        itm_id: str = "ALL",
        timeout: int = 60
    ) -> Optional[List[Dict]]:
        """
        Fetch table data with retry logic:
        1. First try with only objL1="ALL"
        2. If failed, retry with objL1="ALL" and objL2="ALL"
        
        Args:
            Same as fetch_table_data but without obj_l1 and obj_l2
            
        Returns:
            List of data records or None if both attempts fail
        """
        # First attempt: objL1 only
        logger.debug(f"🔄 First attempt with objL1 only for {tbl_id}")
        data = self.fetch_table_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            obj_l1="ALL",
            obj_l2=None,
            itm_id=itm_id,
            timeout=timeout
        )
        
        if data:
            return data
        
        # Second attempt: objL1 + objL2
        logger.debug(f"🔄 Second attempt with objL1 + objL2 for {tbl_id}")
        data = self.fetch_table_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            obj_l1="ALL",
            obj_l2="ALL",
            itm_id=itm_id,
            timeout=timeout
        )
        
        return data

    def find_optimal_period(self, metadata: Dict) -> Optional[Dict]:
        """
        Find the optimal data period by trying different period types

        Args:
            metadata: Table metadata containing ORG_ID, TBL_ID, STRT_PRD_DE, END_PRD_DE

        Returns:
            Dict with 'data' and 'period_type' or None if no data found
        """
        org_id = metadata.get("ORG_ID")
        tbl_id = metadata.get("TBL_ID")
        start_date = metadata.get("STRT_PRD_DE")
        end_date = metadata.get("END_PRD_DE")

        if not all([org_id, tbl_id, start_date, end_date]):
            logger.error(f"Missing required metadata fields for {tbl_id}")
            return None

        # Try periods in order of granularity: Monthly > Quarterly > Semi-annual > Yearly > Multi-year > Irregular
        # Note: Bi-monthly uses same code 'M' as monthly, so API will return appropriate data
        period_priority = [
            ("M", "월간"),      # Monthly (also handles bi-monthly with same code)
            ("Q", "분기"),      # Quarterly  
            ("S", "반기"),      # Semi-annual
            ("Y", "연간"),      # Yearly
            ("F", "다년"),      # Multi-year (2, 3, 4, 5, 10 years)
            ("IR", "부정기"),   # Irregular
        ]

        for prd_se, prd_name in period_priority:
            logger.info(f"🔍 Trying period '{prd_name}' ({prd_se}) for {tbl_id}")

            # Adjust date format based on period type
            formatted_start = self._format_date_for_period(start_date, prd_se)
            formatted_end = self._format_date_for_period(end_date, prd_se)

            data = self.fetch_table_data_with_retry(
                org_id=org_id,
                tbl_id=tbl_id,
                start_date=formatted_start,
                end_date=formatted_end,
                prd_se=prd_se,
            )

            if data:
                logger.info(
                    f"✨ Found {len(data)} records with period '{prd_name}' for {tbl_id}"
                )
                return {"data": data, "period_type": prd_se, "period_name": prd_name}

            # Rate limiting
            time.sleep(1)

        # Log detailed error when all attempts fail
        logger.error(f"❌ Failed to fetch data for table {tbl_id} after trying all period types")
        logger.error(f"  Table Name: {metadata.get('TBL_NM', 'Unknown')}")
        logger.error(f"  Organization: {metadata.get('ORG_NM', 'Unknown')} (ID: {org_id})")
        logger.error(f"  Date Range: {start_date} ~ {end_date}")
        logger.error(f"  Description: {metadata.get('CONTENTS', 'No description')[:200]}...")
        logger.error(f"  Tried periods: {', '.join([f'{p[1]}({p[0]})' for p in period_priority])}")
        logger.error("-" * 80)
        
        return None

    def _format_date_for_period(self, date_str: str, period_type: str) -> str:
        """
        Format date string based on period type

        Args:
            date_str: Date string (usually YYYY format)
            period_type: Period type (M, Q, S, Y, F, IR)

        Returns:
            Formatted date string
        """
        # Remove any non-numeric characters
        date_clean = re.sub(r"[^0-9]", "", date_str)

        if period_type == "M":
            # Monthly/Bi-monthly format: YYYYMM (MM: 01~12 for monthly, odd months for bi-monthly)
            if len(date_clean) >= 6:
                return date_clean[:6]
            else:
                # If only year is provided, default to January
                return date_clean[:4] + "01"
        elif period_type == "Q":
            # Quarter format: YYYYQQ (QQ: 01~04)
            if len(date_clean) >= 6:
                return date_clean[:6]
            else:
                # If only year is provided, default to Q1
                return date_clean[:4] + "01"
        elif period_type == "S":
            # Semi-annual format: YYYYHH (HH: 01, 02)
            if len(date_clean) >= 6:
                return date_clean[:6]
            else:
                # If only year is provided, default to H1
                return date_clean[:4] + "01"
        elif period_type == "Y":
            # Year format: YYYY
            return date_clean[:4]
        elif period_type == "F":
            # Multi-year format: YYYY (use year as-is)
            return date_clean[:4]
        elif period_type == "IR":
            # Irregular format: Use as-is or year
            if len(date_clean) >= 8:
                return date_clean[:8]
            else:
                return date_clean[:4]
        else:
            return date_clean

