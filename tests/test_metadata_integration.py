"""
KOSIS API와 통계설명자료서비스 연동 테스트
TBL_ID -> STAT_ID -> confmNo -> k-stat.go.kr 메타데이터
"""

import os
import json
import re
import pytest
import requests
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("KOSIS_API_KEY")


def fix_json(text: str) -> Optional[Dict]:
    """KOSIS 비표준 JSON 파싱"""
    if not text or text.strip() == "":
        return None
    try:
        corrected = re.sub(r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text)
        return json.loads(corrected)
    except json.JSONDecodeError:
        return None


class TestMetadataIntegration:
    """KOSIS와 통계설명자료서비스 연동 테스트"""

    # 테스트용 테이블 정보 (메타데이터에서 가져온 STAT_ID 포함)
    TEST_TABLES = [
        {"org_id": "101", "tbl_id": "DT_1YL20631", "name": "고령인구비율", "stat_id": "1962009"},
        {"org_id": "101", "tbl_id": "DT_1IN1503", "name": "주민등록인구", "stat_id": "1962001"},
        {"org_id": "101", "tbl_id": "DT_1SSSA132R", "name": "야간 보행 안전도", "stat_id": "1977013"},
    ]

    def test_get_confm_no_by_stat_id(self):
        """STAT_ID를 사용해서 통계설명 조회 (승인번호 포함 여부 확인)"""
        endpoint = "https://kosis.kr/openapi/statisticsExplData.do"

        for table in self.TEST_TABLES:
            if "stat_id" not in table:
                continue

            params = {
                "method": "getList",
                "apiKey": API_KEY,
                "format": "json",
                "jsonVD": "Y",
                "statId": table["stat_id"],
                "metaItm": "ALL",
            }

            resp = requests.get(endpoint, params=params, timeout=30)
            data = fix_json(resp.text)

            print(f"\n=== STAT_ID로 통계설명 조회: {table['name']} (statId={table['stat_id']}) ===")

            if data and isinstance(data, list) and len(data) > 0:
                info = data[0]
                print(f"  필드 목록: {list(info.keys())}")

                # 주요 필드 출력
                key_fields = ["statsNm", "confmNo", "statsKind", "writingPurps"]
                for field in key_fields:
                    value = info.get(field, "N/A")
                    if value and len(str(value)) > 100:
                        value = str(value)[:100] + "..."
                    print(f"  {field}: {value}")

                # 승인번호 필드 찾기
                for key in info.keys():
                    if "confm" in key.lower():
                        print(f"  ** 승인번호 필드 발견 ** {key}: {info[key]}")
            else:
                print(f"  응답 실패: {resp.text[:200]}")

    def test_get_confm_no_from_statistics_explanation(self):
        """통계설명 API에서 승인번호(confmNo) 조회"""
        endpoint = "https://kosis.kr/openapi/statisticsExplData.do"

        for table in self.TEST_TABLES:
            params = {
                "method": "getList",
                "apiKey": API_KEY,
                "format": "json",
                "jsonVD": "Y",
                "orgId": table["org_id"],
                "tblId": table["tbl_id"],
                "metaItm": "ALL",
            }

            resp = requests.get(endpoint, params=params, timeout=30)
            data = fix_json(resp.text)

            print(f"\n=== 통계설명 조회: {table['name']} ({table['tbl_id']}) ===")

            if data and isinstance(data, list) and len(data) > 0:
                info = data[0]
                print(f"  전체 필드: {list(info.keys())}")

                # 승인번호 관련 필드 찾기
                confm_fields = [k for k in info.keys() if "confm" in k.lower() or "stat" in k.lower()]
                print(f"  승인/통계 관련 필드: {confm_fields}")

                for field in ["confmNo", "statsConfmNo", "CONFM_NO", "STAT_CONFM_NO"]:
                    if field in info:
                        print(f"  {field}: {info[field]}")

                # 모든 필드 출력
                print("\n  [전체 응답 내용]")
                for key, value in info.items():
                    value_str = str(value)[:100] if value else "N/A"
                    print(f"    {key}: {value_str}")
            else:
                print(f"  응답: {resp.text[:300]}")

    def test_get_stat_id_from_data_response(self):
        """데이터 API 응답에서 STAT_ID 확인"""
        endpoint = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "orgId": "101",
            "tblId": "DT_1YL20631",
            "objL1": "ALL",
            "itmId": "ALL",
            "prdSe": "Y",
            "startPrdDe": "2024",
            "endPrdDe": "2024",
        }

        resp = requests.get(endpoint, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 데이터 응답에서 STAT_ID 확인 ===")

        if data and len(data) > 0:
            sample = data[0]
            print(f"  필드 목록: {list(sample.keys())}")

            stat_fields = [k for k in sample.keys() if "stat" in k.lower()]
            print(f"  STAT 관련 필드: {stat_fields}")

            for field in stat_fields:
                print(f"    {field}: {sample.get(field)}")

    def test_alternative_stat_table_api(self):
        """통계표설명 API 테스트 (다른 엔드포인트)"""
        endpoint = "https://kosis.kr/openapi/statisTable/statisTableExplData.do"

        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "orgId": "101",
            "tblId": "DT_1YL20631",
        }

        resp = requests.get(endpoint, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 통계표설명 API 응답 ===")

        if data:
            if isinstance(data, dict):
                print(f"  필드 목록: {list(data.keys())}")
                for key in ["confmNo", "statsConfmNo", "statId", "STAT_ID"]:
                    if key in data:
                        print(f"  {key}: {data[key]}")
            elif isinstance(data, list) and len(data) > 0:
                print(f"  필드 목록: {list(data[0].keys())}")
                for key, value in data[0].items():
                    print(f"    {key}: {str(value)[:80]}")
        else:
            print(f"  응답: {resp.text[:500]}")

    def test_stat_list_api(self):
        """통계목록 API에서 승인번호 찾기"""
        endpoint = "https://kosis.kr/openapi/statisticsList.do"

        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "vwCd": "MT_ZTITLE",
            "parentListId": "",
        }

        resp = requests.get(endpoint, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 통계목록 API 응답 ===")

        if data and isinstance(data, list) and len(data) > 0:
            sample = data[0]
            print(f"  필드 목록: {list(sample.keys())}")

            # 승인번호 관련 필드 찾기
            for key in sample.keys():
                if "confm" in key.lower() or "stat" in key.lower():
                    print(f"    {key}: {sample[key]}")

    def test_search_api_for_confm_no(self):
        """통합검색 API에서 승인번호 확인"""
        endpoint = "https://kosis.kr/openapi/search/search.do"

        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "searchWord": "고령인구",
            "searchType": "T",
        }

        resp = requests.get(endpoint, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 통합검색 API 응답 ===")

        if data and isinstance(data, list) and len(data) > 0:
            sample = data[0]
            print(f"  필드 목록: {list(sample.keys())}")

            # 모든 필드와 값 출력
            for key, value in sample.items():
                print(f"    {key}: {str(value)[:80]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
