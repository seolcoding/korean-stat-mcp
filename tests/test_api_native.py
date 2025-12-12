"""
KOSIS API Native 테스트
로컬 캐시 없이 순수 API만으로 통계 목록 및 데이터 조회
"""

import os
import json
import re
import time
import pytest
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv


# ============================================================================
# KOSIS Native API Client
# ============================================================================
class KosisNativeClient:
    """순수 API만 사용하는 KOSIS 클라이언트"""

    # 서비스뷰 코드
    VIEW_CODES = {
        "MT_ZTITLE": "국내통계 주제별",
        "MT_OTITLE": "국내통계 기관별",
        "MT_GTITLE01": "e-지방지표(주제별)",
        "MT_GTITLE02": "e-지방지표(지역별)",
        "MT_CHOSUN_TITLE": "광복이전통계(1908~1943)",
        "MT_HANKUK_TITLE": "대한민국통계연감",
        "MT_STOP_TITLE": "작성중지통계",
        "MT_RTITLE": "국제통계",
        "MT_BUKHAN": "북한통계",
        "MT_TM1_TITLE": "대상별통계",
        "MT_TM2_TITLE": "이슈별통계",
        "MT_ETITLE": "영문 KOSIS",
    }

    # API 엔드포인트
    ENDPOINTS = {
        "list": "https://kosis.kr/openapi/statisticsList.do",
        "data": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
        "search": "https://kosis.kr/openapi/search/search.do",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def _fix_json(self, text: str) -> Optional[Dict]:
        """KOSIS 비표준 JSON 파싱"""
        if not text or text.strip() == "":
            return None
        try:
            corrected = re.sub(r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text)
            return json.loads(corrected)
        except json.JSONDecodeError:
            return None

    def get_categories(self, vw_cd: str = "MT_ZTITLE", parent_id: str = "") -> List[Dict]:
        """카테고리/목록 조회"""
        params = {
            "method": "getList",
            "apiKey": self.api_key,
            "vwCd": vw_cd,
            "parentListId": parent_id,
            "format": "json",
            "jsonVD": "Y",
        }
        resp = self.session.get(self.ENDPOINTS["list"], params=params, timeout=30)
        data = self._fix_json(resp.text)
        return data if isinstance(data, list) else []

    def get_all_tables(
        self, vw_cd: str = "MT_ZTITLE", parent_id: str = "", max_depth: int = 10, delay: float = 0.5
    ) -> List[Dict]:
        """
        재귀적으로 모든 통계표 목록 조회

        Returns:
            통계표 정보 리스트 [{ORG_ID, TBL_ID, TBL_NM, ...}, ...]
        """
        tables = []
        self._traverse(vw_cd, parent_id, tables, 0, max_depth, delay)
        return tables

    def _traverse(
        self, vw_cd: str, parent_id: str, tables: List, depth: int, max_depth: int, delay: float
    ):
        """카테고리 트리 순회"""
        if depth >= max_depth:
            return

        items = self.get_categories(vw_cd, parent_id)
        time.sleep(delay)

        for item in items:
            if "TBL_ID" in item:
                # 통계표 발견
                tables.append(item)
            elif "LIST_ID" in item:
                # 하위 카테고리 탐색
                self._traverse(vw_cd, item["LIST_ID"], tables, depth + 1, max_depth, delay)

    def search_tables(self, query: str, vw_cd: str = "MT_ZTITLE") -> List[Dict]:
        """통계표 검색 (KOSIS 통합검색 API)"""
        params = {
            "method": "getList",
            "apiKey": self.api_key,
            "vwCd": vw_cd,
            "searchWord": query,
            "format": "json",
            "jsonVD": "Y",
        }
        resp = self.session.get(self.ENDPOINTS["search"], params=params, timeout=30)
        data = self._fix_json(resp.text)
        return data if isinstance(data, list) else []

    def get_table_data(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str = "Y",
    ) -> Optional[List[Dict]]:
        """통계 데이터 조회"""
        params = {
            "method": "getList",
            "apiKey": self.api_key,
            "format": "json",
            "jsonVD": "Y",
            "orgId": org_id,
            "tblId": tbl_id,
            "objL1": "ALL",
            "itmId": "ALL",
            "prdSe": prd_se,
            "startPrdDe": start_date,
            "endPrdDe": end_date,
        }
        resp = self.session.get(self.ENDPOINTS["data"], params=params, timeout=60)
        data = self._fix_json(resp.text)

        if data and isinstance(data, list) and "errMsg" not in str(data):
            return data
        return None


# ============================================================================
# 테스트 클래스
# ============================================================================
class TestKosisNativeAPI:
    """KOSIS Native API 테스트"""

    @pytest.fixture
    def client(self):
        load_dotenv()
        api_key = os.getenv("KOSIS_API_KEY")
        return KosisNativeClient(api_key)

    # --- 1. 서비스뷰 목록 조회 테스트 ---
    def test_get_top_categories_by_subject(self, client):
        """주제별 최상위 카테고리 조회"""
        categories = client.get_categories("MT_ZTITLE", "")
        assert len(categories) > 0, "주제별 카테고리가 비어있습니다"

        # 필드 확인
        first = categories[0]
        assert "LIST_ID" in first or "TBL_ID" in first

        print(f"\n주제별 최상위 카테고리: {len(categories)}개")
        for cat in categories[:5]:
            print(f"  - {cat.get('LIST_NM', cat.get('TBL_NM'))}")

    def test_get_top_categories_by_org(self, client):
        """기관별 최상위 카테고리 조회"""
        categories = client.get_categories("MT_OTITLE", "")
        assert len(categories) > 0, "기관별 카테고리가 비어있습니다"

        print(f"\n기관별 최상위 카테고리: {len(categories)}개")
        for cat in categories[:5]:
            print(f"  - {cat.get('LIST_NM', cat.get('TBL_NM'))}")

    def test_get_regional_categories(self, client):
        """e-지방지표 카테고리 조회"""
        categories = client.get_categories("MT_GTITLE01", "")
        assert len(categories) > 0, "지방지표 카테고리가 비어있습니다"

        print(f"\ne-지방지표(주제별): {len(categories)}개")
        for cat in categories:
            print(f"  - {cat.get('LIST_NM', cat.get('TBL_NM'))}")

    # --- 2. 하위 카테고리 탐색 테스트 ---
    def test_drill_down_category(self, client):
        """하위 카테고리 탐색"""
        # 최상위 조회
        top = client.get_categories("MT_ZTITLE", "")
        assert len(top) > 0

        # 첫 번째 카테고리의 하위 조회
        first_id = top[0].get("LIST_ID")
        if first_id:
            sub = client.get_categories("MT_ZTITLE", first_id)
            print(f"\n'{top[0].get('LIST_NM')}' 하위 항목: {len(sub)}개")
            for item in sub[:5]:
                name = item.get("LIST_NM", item.get("TBL_NM"))
                is_table = "TBL_ID" in item
                print(f"  - {'[표]' if is_table else '[폴더]'} {name}")

    # --- 3. 통계표 조회 테스트 ---
    def test_find_tables_in_category(self, client):
        """특정 카테고리에서 통계표 찾기"""
        # 인구 > 인구총조사 경로 탐색 예시
        tables = client.get_all_tables("MT_ZTITLE", "", max_depth=3, delay=0.3)

        print(f"\n발견된 통계표: {len(tables)}개 (depth=3)")
        for tbl in tables[:10]:
            print(f"  - [{tbl.get('ORG_ID')}] {tbl.get('TBL_NM')} ({tbl.get('TBL_ID')})")

    # --- 4. 통계 데이터 조회 테스트 ---
    def test_get_table_data(self, client):
        """통계 데이터 조회"""
        # 고령인구비율 테이블 (알려진 테이블)
        data = client.get_table_data(
            org_id="101",
            tbl_id="DT_1YL20631",
            start_date="2020",
            end_date="2024",
            prd_se="Y",
        )
        assert data is not None, "데이터 조회 실패"
        assert len(data) > 0, "데이터가 비어있습니다"

        print(f"\n고령인구비율 데이터: {len(data)}건")
        print(f"  필드: {list(data[0].keys())}")

    # --- 5. 전체 서비스뷰 통계 ---
    def test_all_view_codes(self, client):
        """모든 서비스뷰 코드 접근성 테스트"""
        results = {}
        for code, name in KosisNativeClient.VIEW_CODES.items():
            cats = client.get_categories(code, "")
            results[code] = len(cats)
            time.sleep(0.3)

        print("\n=== 서비스뷰별 카테고리 수 ===")
        for code, count in results.items():
            name = KosisNativeClient.VIEW_CODES[code]
            status = "✅" if count > 0 else "❌"
            print(f"  {status} {name} ({code}): {count}개")

        # 주요 서비스뷰는 접근 가능해야 함
        assert results["MT_ZTITLE"] > 0
        assert results["MT_OTITLE"] > 0


# ============================================================================
# 유틸리티: 전체 테이블 목록 수집 (별도 실행용)
# ============================================================================
def collect_all_tables(output_path: str = "kosis_tables_native.json"):
    """모든 통계표 목록 수집 (시간 소요)"""
    load_dotenv()
    client = KosisNativeClient(os.getenv("KOSIS_API_KEY"))

    all_tables = []

    # 주요 서비스뷰에서 테이블 수집
    for vw_cd in ["MT_ZTITLE", "MT_GTITLE01"]:
        print(f"Collecting from {vw_cd}...")
        tables = client.get_all_tables(vw_cd, "", max_depth=10, delay=0.5)
        all_tables.extend(tables)
        print(f"  Found {len(tables)} tables")

    # 중복 제거
    unique = {t["TBL_ID"]: t for t in all_tables if "TBL_ID" in t}
    result = list(unique.values())

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nTotal unique tables: {len(result)}")
    print(f"Saved to: {output_path}")

    return result


if __name__ == "__main__":
    # 직접 실행 시 전체 테이블 수집
    # collect_all_tables()

    # 또는 pytest 실행
    pytest.main([__file__, "-v", "-s"])
