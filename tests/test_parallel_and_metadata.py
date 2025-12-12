"""
KOSIS API 병렬 조회 및 메타데이터 테스트
1. 여러 테이블 동시 조회 가능 여부
2. 통계설명/통계표설명 API
3. 컬럼 의미 파악
"""

import os
import json
import re
import time
import pytest
import requests
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# ============================================================================
# 테스트용 테이블 목록 (다양한 기관/유형)
# ============================================================================
TEST_TABLES = [
    {"org_id": "101", "tbl_id": "DT_1YL20631", "name": "고령인구비율"},
    {"org_id": "101", "tbl_id": "DT_1YL20701", "name": "인구천명당 자동차등록대수"},
    {"org_id": "101", "tbl_id": "DT_1YL20621", "name": "도로포장률"},
    {"org_id": "101", "tbl_id": "DT_1YL20951", "name": "재정자립도"},
    {"org_id": "101", "tbl_id": "DT_1IN1503", "name": "주민등록인구"},
]


# ============================================================================
# 1. 병렬 조회 테스트
# ============================================================================
class TestParallelRequests:
    """병렬 API 요청 테스트"""

    def fetch_table(self, table_info: Dict) -> Tuple[str, bool, float, int]:
        """단일 테이블 조회 및 결과 반환"""
        start = time.time()

        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "orgId": table_info["org_id"],
            "tblId": table_info["tbl_id"],
            "objL1": "ALL",
            "itmId": "ALL",
            "prdSe": "Y",
            "startPrdDe": "2023",
            "endPrdDe": "2024",
        }

        try:
            resp = requests.get(
                "https://kosis.kr/openapi/Param/statisticsParameterData.do",
                params=params,
                timeout=30,
            )
            elapsed = time.time() - start
            data = fix_json(resp.text)

            if data and isinstance(data, list) and "errMsg" not in str(data):
                return (table_info["tbl_id"], True, elapsed, len(data))
            else:
                return (table_info["tbl_id"], False, elapsed, 0)
        except Exception as e:
            elapsed = time.time() - start
            return (table_info["tbl_id"], False, elapsed, 0)

    def test_sequential_requests(self):
        """순차 요청 테스트 (기준선)"""
        print("\n=== 순차 요청 테스트 ===")
        start_total = time.time()
        results = []

        for table in TEST_TABLES:
            result = self.fetch_table(table)
            results.append(result)
            print(f"  {result[0]}: {'✅' if result[1] else '❌'} {result[2]:.2f}s ({result[3]}건)")

        total_time = time.time() - start_total
        success_count = sum(1 for r in results if r[1])

        print(f"\n총 소요시간: {total_time:.2f}s")
        print(f"성공: {success_count}/{len(TEST_TABLES)}")

        return total_time, success_count

    def test_parallel_requests_2_workers(self):
        """2개 동시 요청 테스트"""
        print("\n=== 병렬 요청 테스트 (2 workers) ===")
        start_total = time.time()
        results = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(self.fetch_table, t): t for t in TEST_TABLES}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(f"  {result[0]}: {'✅' if result[1] else '❌'} {result[2]:.2f}s ({result[3]}건)")

        total_time = time.time() - start_total
        success_count = sum(1 for r in results if r[1])

        print(f"\n총 소요시간: {total_time:.2f}s")
        print(f"성공: {success_count}/{len(TEST_TABLES)}")

        return total_time, success_count

    def test_parallel_requests_5_workers(self):
        """5개 동시 요청 테스트"""
        print("\n=== 병렬 요청 테스트 (5 workers) ===")
        start_total = time.time()
        results = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.fetch_table, t): t for t in TEST_TABLES}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(f"  {result[0]}: {'✅' if result[1] else '❌'} {result[2]:.2f}s ({result[3]}건)")

        total_time = time.time() - start_total
        success_count = sum(1 for r in results if r[1])

        print(f"\n총 소요시간: {total_time:.2f}s")
        print(f"성공: {success_count}/{len(TEST_TABLES)}")

        return total_time, success_count

    def test_compare_sequential_vs_parallel(self):
        """순차 vs 병렬 성능 비교"""
        seq_time, seq_success = self.test_sequential_requests()
        time.sleep(1)  # API 쿨다운
        par_time, par_success = self.test_parallel_requests_5_workers()

        print("\n" + "="*50)
        print("=== 성능 비교 결과 ===")
        print(f"순차 처리: {seq_time:.2f}s (성공: {seq_success})")
        print(f"병렬 처리: {par_time:.2f}s (성공: {par_success})")
        print(f"속도 향상: {seq_time/par_time:.1f}x")
        print("="*50)

        # 병렬이 더 빠르거나 비슷해야 함
        assert par_time <= seq_time * 1.5, "병렬 처리가 너무 느림"
        assert par_success == seq_success, "병렬 처리 성공률 불일치"


# ============================================================================
# 2. 통계설명 API 테스트 (조사 메타데이터)
# ============================================================================
class TestStatisticsExplanation:
    """통계설명 API - 조사(통계) 수준의 메타데이터"""

    ENDPOINT = "https://kosis.kr/openapi/statisticsExplData.do"

    def test_get_statistics_explanation(self):
        """통계설명 조회 (statId 사용)"""
        # 인구총조사 (statId: 1962009)
        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "statId": "1962009",
            "metaItm": "ALL",
        }

        resp = requests.get(self.ENDPOINT, params=params, timeout=30)
        data = fix_json(resp.text)

        assert data is not None, "통계설명 조회 실패"
        print("\n=== 통계설명 (인구총조사) ===")

        if isinstance(data, list) and len(data) > 0:
            info = data[0]
            fields = [
                ("statsNm", "조사명"),
                ("statsKind", "작성유형"),
                ("statsPeriod", "조사주기"),
                ("writingPurps", "조사목적"),
                ("examinObjrange", "조사대상범위"),
                ("mainTermExpl", "주요용어해설"),
                ("confmNo", "승인번호"),
            ]
            for field, label in fields:
                value = info.get(field, "N/A")
                if value and len(str(value)) > 100:
                    value = str(value)[:100] + "..."
                print(f"  {label}: {value}")

    def test_get_explanation_by_org_tbl(self):
        """통계설명 조회 (orgId + tblId 사용)"""
        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "orgId": "101",
            "tblId": "DT_1YL20631",
            "metaItm": "ALL",
        }

        resp = requests.get(self.ENDPOINT, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 통계설명 (orgId+tblId) ===")
        if data and isinstance(data, list) and len(data) > 0:
            print(f"  조사명: {data[0].get('statsNm', 'N/A')}")
            print(f"  성공!")
        else:
            print(f"  응답: {resp.text[:200]}")


# ============================================================================
# 3. 통계표설명 API 테스트 (테이블 수준 메타데이터)
# ============================================================================
class TestTableExplanation:
    """통계표설명 API - 개별 테이블의 상세 정보"""

    ENDPOINT = "https://kosis.kr/openapi/statisTable/statisTableExplData.do"

    def test_get_table_explanation(self):
        """통계표설명 조회"""
        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "orgId": "101",
            "tblId": "DT_1YL20631",
        }

        resp = requests.get(self.ENDPOINT, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 통계표설명 (DT_1YL20631) ===")

        if data:
            if isinstance(data, dict):
                for key, value in list(data.items())[:10]:
                    print(f"  {key}: {str(value)[:80]}")
            elif isinstance(data, list) and len(data) > 0:
                for key, value in list(data[0].items())[:10]:
                    print(f"  {key}: {str(value)[:80]}")
        else:
            print(f"  응답: {resp.text[:300]}")


# ============================================================================
# 4. 데이터 컬럼 의미 분석
# ============================================================================
class TestColumnMeaning:
    """데이터 응답 컬럼의 의미 분석"""

    # 컬럼 정의 (KOSIS API 공식 문서 기반)
    COLUMN_DEFINITIONS = {
        # 기본 정보
        "TBL_ID": "통계표 ID",
        "TBL_NM": "통계표명",
        "ORG_ID": "기관 ID (예: 101=통계청)",
        "STAT_ID": "통계조사 ID",

        # 분류 항목 (Classification)
        "C1": "분류1 코드",
        "C1_NM": "분류1 명칭 (예: 시도명)",
        "C1_NM_ENG": "분류1 영문명",
        "C1_OBJ_NM": "분류1 객체명",
        "C2": "분류2 코드",
        "C2_NM": "분류2 명칭 (예: 시군구명)",
        "C3": "분류3 코드",
        "C3_NM": "분류3 명칭",
        # C4~C8도 동일한 패턴

        # 항목 (Item)
        "ITM_ID": "항목 ID",
        "ITM_NM": "항목명 (예: 고령인구비율, 총인구 등)",

        # 시점 (Period)
        "PRD_DE": "수록시점 (YYYY, YYYYMM, YYYYQQ 등)",
        "PRD_SE": "수록주기 (Y=연간, M=월간, Q=분기)",

        # 값 (Data)
        "DT": "데이터 값 (실제 통계 수치)",
        "UNIT_NM": "단위명 (%, 명, 원 등)",

        # 기타
        "LST_CHN_DE": "최종변경일자",
    }

    def test_fetch_and_analyze_columns(self):
        """실제 데이터 조회 후 컬럼 분석"""
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

        resp = requests.get(
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            params=params,
            timeout=30,
        )
        data = fix_json(resp.text)

        assert data and len(data) > 0, "데이터 조회 실패"

        print("\n" + "="*70)
        print("=== 데이터 컬럼 의미 분석 ===")
        print("="*70)

        sample = data[0]

        print("\n[컬럼별 설명 및 샘플값]")
        for col, value in sample.items():
            definition = self.COLUMN_DEFINITIONS.get(col, "정의 필요")
            print(f"  {col:15} | {definition:30} | 예: {value}")

        print("\n[분류 체계 이해]")
        print("  C1 ~ C8: 분류 항목 (지역, 성별, 연령대 등)")
        print("  ITM: 측정 항목 (고령인구비율, 인구수 등)")
        print("  PRD_DE: 시점 (연도, 월 등)")
        print("  DT: 실제 측정값")

        # 여러 레코드에서 구조 확인
        print("\n[데이터 구조 예시 (첫 5개)]")
        for i, record in enumerate(data[:5]):
            c1 = record.get("C1_NM", "")
            itm = record.get("ITM_NM", "")
            prd = record.get("PRD_DE", "")
            dt = record.get("DT", "")
            unit = record.get("UNIT_NM", "")
            print(f"  {i+1}. {c1} | {itm} | {prd} | {dt} {unit}")

    def test_column_definitions_dict(self):
        """컬럼 정의 딕셔너리 출력"""
        print("\n=== KOSIS API 응답 컬럼 정의 ===")
        for col, definition in self.COLUMN_DEFINITIONS.items():
            print(f"  {col}: {definition}")


# ============================================================================
# 5. 통합 검색 API 테스트
# ============================================================================
class TestSearchAPI:
    """KOSIS 통합검색 API"""

    ENDPOINT = "https://kosis.kr/openapi/search/search.do"

    def test_search_tables(self):
        """통계표 검색"""
        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "jsonVD": "Y",
            "searchWord": "고령인구",
            "searchType": "T",  # T=통계표, I=지표
        }

        resp = requests.get(self.ENDPOINT, params=params, timeout=30)
        data = fix_json(resp.text)

        print("\n=== 통계표 검색: '고령인구' ===")
        if data and isinstance(data, list):
            print(f"검색 결과: {len(data)}건")
            for item in data[:5]:
                tbl_nm = item.get("TBL_NM", "N/A")
                org_nm = item.get("ORG_NM", "N/A")
                print(f"  - [{org_nm}] {tbl_nm}")
        else:
            print(f"응답: {resp.text[:200]}")


# ============================================================================
# 메인 실행
# ============================================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("KOSIS API 병렬 조회 및 메타데이터 테스트")
    print("="*70)

    # pytest 실행
    pytest.main([__file__, "-v", "-s", "--tb=short"])
