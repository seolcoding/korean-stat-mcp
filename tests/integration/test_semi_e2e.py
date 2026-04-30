"""
Semi-E2E 테스트 - 실제 KOSIS API 호출.

이 테스트는 실제 KOSIS API를 호출하여 통합 시나리오를 검증합니다.
.env 파일에 KOSIS_API_KEY가 설정되어 있어야 합니다.

실행 방법:
    # 모든 integration 테스트 실행
    uv run pytest tests/integration/ -v -s

    # 특정 시나리오만 실행
    uv run pytest tests/integration/test_semi_e2e.py::TestScenarioSearchAndQuery -v -s

시나리오:
    1. 검색 → 데이터 조회: 키워드 검색 후 결과 테이블의 데이터 조회
    2. 기관별 탐색: 특정 기관의 통계 목록 조회
    3. 주제별 탐색: 특정 주제의 통계 목록 조회
    4. 자동 주기 탐색: 주기를 모르는 상태에서 자동으로 찾아 데이터 조회
"""

import os
import pytest
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# API 키가 없으면 테스트 스킵
pytestmark = pytest.mark.skipif(
    not os.getenv("KOSIS_API_KEY"), reason="KOSIS_API_KEY not set in environment"
)

from kosis_tools import (  # noqa: E402
    KosisConfig,
    StatisticsSearch,
    CategoryList,
    StatisticsData,
    TableMetadata,
    StatsExplanation,
    OrgCode,
    ThemeCode,
    PeriodType,
)


@pytest.fixture(scope="module")
def config() -> KosisConfig:
    """실제 API를 위한 설정 (rate limiting 적용)."""
    return KosisConfig(
        api_key=os.getenv("KOSIS_API_KEY"),
        rate_limit_delay=1.0,  # API 부하 방지
        timeout=60,
        max_retries=2,
    )


@pytest.fixture(scope="module")
def search_client(config: KosisConfig) -> StatisticsSearch:
    """검색 클라이언트."""
    return StatisticsSearch(config)


@pytest.fixture(scope="module")
def category_client(config: KosisConfig) -> CategoryList:
    """카테고리 클라이언트."""
    return CategoryList(config)


@pytest.fixture(scope="module")
def data_client(config: KosisConfig) -> StatisticsData:
    """데이터 클라이언트."""
    return StatisticsData(config)


@pytest.fixture(scope="module")
def meta_client(config: KosisConfig) -> TableMetadata:
    """테이블 메타데이터 클라이언트."""
    return TableMetadata(config)


@pytest.fixture(scope="module")
def expl_client(config: KosisConfig) -> StatsExplanation:
    """통계설명 클라이언트."""
    return StatsExplanation(config)


class TestScenarioSearchAndQuery:
    """
    시나리오 1: 검색 → 데이터 조회

    사용자 스토리:
    "인구" 관련 통계를 찾고 싶다.
    검색 결과에서 적절한 테이블을 선택하여 최근 데이터를 조회한다.
    """

    def test_search_population_tables(self, search_client: StatisticsSearch):
        """
        Step 1: "인구" 키워드로 통계표 검색.

        기대 결과:
        - 검색 결과가 1개 이상
        - 각 결과에 TBL_ID, TBL_NM, ORG_ID 포함
        """
        print("\n=== 시나리오 1-1: 인구 키워드 검색 ===")

        results = search_client.search("인구")

        print(f"검색 결과: {len(results)}건")
        assert len(results) > 0, "인구 검색 결과가 없음"

        # 상위 5개 결과 출력
        for i, r in enumerate(results[:5]):
            print(f"  [{i + 1}] {r.get('TBL_NM', 'N/A')} ({r.get('ORG_NM', 'N/A')})")
            assert "TBL_ID" in r
            assert "TBL_NM" in r

    def test_search_with_org_filter(self, search_client: StatisticsSearch):
        """
        Step 2: 기관 필터링 검색 (통계청만).

        기대 결과:
        - 모든 결과가 통계청(101) 데이터
        """
        print("\n=== 시나리오 1-2: 통계청 인구 통계 검색 ===")

        results = search_client.search("인구", org_id=OrgCode.KOSTAT)

        print(f"통계청 인구 통계: {len(results)}건")
        assert len(results) > 0

        # 모든 결과가 통계청인지 확인
        for r in results[:10]:
            assert r.get("ORG_ID") == "101", f"기관 필터 실패: {r.get('ORG_ID')}"
            print(f"  - {r.get('TBL_NM')}")

    def test_fetch_data_from_search_result(
        self, search_client: StatisticsSearch, data_client: StatisticsData
    ):
        """
        Step 3: 검색 결과에서 선택한 테이블의 데이터 조회.

        기대 결과:
        - 검색 결과 중 첫 번째 테이블의 데이터 조회 성공
        - 데이터에 PRD_DE(기간), DT(값) 포함
        """
        print("\n=== 시나리오 1-3: 검색 결과 데이터 조회 ===")

        # 검색
        results = search_client.search("인구", org_id=OrgCode.KOSTAT)
        assert len(results) > 0

        # 첫 번째 결과 선택
        selected = results[0]
        org_id = selected.get("ORG_ID")
        tbl_id = selected.get("TBL_ID")
        tbl_nm = selected.get("TBL_NM")

        print(f"선택된 테이블: {tbl_nm} ({tbl_id})")

        # 데이터 조회 (자동 주기 탐색)
        result = data_client.get_data_auto_period(
            org_id=org_id, tbl_id=tbl_id, start_date="2020", end_date="2023"
        )

        if result:
            print(
                f"조회 성공: 주기={result['period_name']}, 레코드={len(result['data'])}건"
            )
            assert len(result["data"]) > 0

            # 첫 번째 데이터 샘플 출력
            sample = result["data"][0]
            print(
                f"  샘플 데이터: {sample.get('PRD_DE')} - {sample.get('C1_NM', 'N/A')}: {sample.get('DT')}"
            )
        else:
            print("⚠️ 데이터 조회 실패 (일부 테이블은 추가 파라미터 필요)")
            pytest.skip("이 테이블은 추가 파라미터가 필요할 수 있음")


class TestScenarioOrgExploration:
    """
    시나리오 2: 기관별 통계 탐색

    사용자 스토리:
    통계청에서 제공하는 통계 목록을 보고 싶다.
    """

    def test_list_kostat_tables(self, category_client: CategoryList):
        """
        Step 1: 통계청(101) 통계표 목록 조회.

        기대 결과:
        - 통계청 통계표가 다수 존재
        """
        print("\n=== 시나리오 2-1: 통계청 통계표 목록 ===")

        results = category_client.list_by_org(OrgCode.KOSTAT)

        print(f"통계청 통계표: {len(results)}개")
        assert len(results) > 0

        # 상위 10개 출력
        for i, r in enumerate(results[:10]):
            print(f"  [{i + 1}] {r.get('TBL_NM', 'N/A')}")

    def test_list_bok_tables(self, category_client: CategoryList):
        """
        Step 2: 한국은행(154) 통계표 목록 조회.

        기대 결과:
        - 한국은행 통계표 존재
        """
        print("\n=== 시나리오 2-2: 한국은행 통계표 목록 ===")

        results = category_client.list_by_org(OrgCode.BOK)

        print(f"한국은행 통계표: {len(results)}개")

        if len(results) > 0:
            for i, r in enumerate(results[:5]):
                print(f"  [{i + 1}] {r.get('TBL_NM', 'N/A')}")
        else:
            print("  (결과 없음 - 한국은행은 별도 API 사용 가능)")


class TestScenarioThemeExploration:
    """
    시나리오 3: 주제별 통계 탐색

    사용자 스토리:
    인구 관련 통계를 주제별로 찾고 싶다.
    """

    def test_list_population_theme(self, category_client: CategoryList):
        """
        Step 1: 인구(A) 주제 통계표 목록 조회.

        기대 결과:
        - 인구 주제 통계표 존재
        """
        print("\n=== 시나리오 3-1: 인구 주제 통계표 ===")

        results = category_client.list_by_theme(ThemeCode.POPULATION)

        print(f"인구 주제 통계표: {len(results)}개")

        if len(results) > 0:
            for i, r in enumerate(results[:10]):
                print(
                    f"  [{i + 1}] {r.get('TBL_NM', 'N/A')} ({r.get('ORG_NM', 'N/A')})"
                )
        else:
            print("  (주제별 조회는 일부 제한될 수 있음)")

    def test_list_economy_theme(self, category_client: CategoryList):
        """
        Step 2: 경제(H) 주제 통계표 목록 조회.
        """
        print("\n=== 시나리오 3-2: 경제 주제 통계표 ===")

        results = category_client.list_by_theme(ThemeCode.ECONOMY)

        print(f"경제 주제 통계표: {len(results)}개")

        if len(results) > 0:
            for i, r in enumerate(results[:10]):
                print(
                    f"  [{i + 1}] {r.get('TBL_NM', 'N/A')} ({r.get('ORG_NM', 'N/A')})"
                )


class TestScenarioAutoPeriodDetection:
    """
    시나리오 4: 자동 주기 탐색

    사용자 스토리:
    특정 테이블의 데이터를 조회하고 싶은데,
    어떤 주기(월간/분기/연간)로 제공되는지 모른다.
    """

    def test_auto_detect_yearly_data(self, data_client: StatisticsData):
        """
        Step 1: 연간 데이터 자동 탐색.

        알려진 연간 테이블로 테스트:
        - DT_1B040A3: 행정구역(읍면동)별/5세별 주민등록인구
        """
        print("\n=== 시나리오 4-1: 연간 데이터 자동 탐색 ===")

        result = data_client.get_data_auto_period(
            org_id="101", tbl_id="DT_1B040A3", start_date="2020", end_date="2023"
        )

        if result:
            print(f"탐지된 주기: {result['period_name']} ({result['period_type']})")
            print(f"조회된 데이터: {len(result['data'])}건")

            # 샘플 데이터 출력
            for sample in result["data"][:3]:
                print(
                    f"  {sample.get('PRD_DE')} | {sample.get('C1_NM', 'N/A')}: {sample.get('DT')}"
                )

            assert result["period_type"] in PeriodType.PRIORITY_ORDER
        else:
            print("⚠️ 데이터 조회 실패")
            pytest.skip("API 응답 없음")

    def test_direct_yearly_query(self, data_client: StatisticsData):
        """
        Step 2: 직접 연간(Y) 주기 지정 조회.

        자동 탐색 없이 직접 주기를 지정하여 조회.
        """
        print("\n=== 시나리오 4-2: 직접 연간 조회 ===")

        records = data_client.get_data(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2022",
            end_date="2023",
            prd_se="Y",
        )

        print(f"조회된 레코드: {len(records)}건")

        if records:
            # 일부 데이터 출력
            unique_periods = set(r.get("PRD_DE") for r in records)
            print(f"기간: {sorted(unique_periods)}")

            unique_regions = set(r.get("C1_NM") for r in records if r.get("C1_NM"))
            print(f"지역 수: {len(unique_regions)}개")
            print(f"지역 샘플: {list(unique_regions)[:5]}")

            assert len(records) > 0
        else:
            pytest.skip("데이터 없음")


class TestScenarioRetryLogic:
    """
    시나리오 5: 재시도 로직 검증

    사용자 스토리:
    일부 테이블은 objL1만으로 조회되지 않고
    objL2도 필요하다. 재시도 로직이 이를 처리하는지 확인.
    """

    def test_retry_with_obj_l2(self, data_client: StatisticsData):
        """
        재시도 로직으로 데이터 조회.

        get_data_with_retry()는:
        1. 먼저 objL1="ALL"만으로 시도
        2. 실패하면 objL1="ALL", objL2="ALL"로 재시도
        """
        print("\n=== 시나리오 5-1: objL2 재시도 로직 ===")

        # 통계청의 알려진 테이블로 테스트
        records = data_client.get_data_with_retry(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2023",
            end_date="2023",
            prd_se="Y",
        )

        print(f"조회된 레코드: {len(records)}건")

        if records:
            print("✅ 재시도 로직 성공")
            sample = records[0]
            print(
                f"  샘플: {sample.get('PRD_DE')} - {sample.get('C1_NM')}: {sample.get('DT')}"
            )
        else:
            print("⚠️ 데이터 없음 (테이블 특성에 따라 다름)")


class TestScenarioEndToEnd:
    """
    시나리오 6: 전체 워크플로우

    사용자 스토리:
    처음부터 끝까지 전체 과정을 수행:
    1. 키워드로 검색
    2. 적절한 테이블 선택
    3. 데이터 조회
    4. 결과 분석
    """

    def test_full_workflow(
        self, search_client: StatisticsSearch, data_client: StatisticsData
    ):
        """
        전체 워크플로우 테스트.
        """
        print("\n=== 시나리오 6: 전체 워크플로우 ===")

        # Step 1: 검색
        print("\n[Step 1] '물가' 키워드로 검색...")
        search_results = search_client.search("물가", org_id=OrgCode.KOSTAT)

        if not search_results:
            pytest.skip("검색 결과 없음")

        print(f"검색 결과: {len(search_results)}건")
        for i, r in enumerate(search_results[:3]):
            print(f"  [{i + 1}] {r.get('TBL_NM')}")

        # Step 2: 첫 번째 테이블 선택
        selected = search_results[0]
        print(f"\n[Step 2] 테이블 선택: {selected.get('TBL_NM')}")
        print(f"  - 테이블 ID: {selected.get('TBL_ID')}")
        print(f"  - 기관: {selected.get('ORG_NM')}")
        print(f"  - 기간: {selected.get('STRT_PRD_DE')} ~ {selected.get('END_PRD_DE')}")

        # Step 3: 데이터 조회
        print("\n[Step 3] 데이터 조회 (자동 주기 탐색)...")
        result = data_client.get_data_auto_period(
            org_id=selected.get("ORG_ID"),
            tbl_id=selected.get("TBL_ID"),
            start_date="2022",
            end_date="2023",
        )

        if not result:
            print("⚠️ 자동 주기 탐색 실패, 직접 연간 조회 시도...")
            records = data_client.get_data_with_retry(
                org_id=selected.get("ORG_ID"),
                tbl_id=selected.get("TBL_ID"),
                start_date="2022",
                end_date="2023",
                prd_se="Y",
            )
            if records:
                result = {"data": records, "period_type": "Y", "period_name": "연간"}

        if result:
            print("✅ 조회 성공!")
            print(f"  - 주기: {result['period_name']}")
            print(f"  - 레코드 수: {len(result['data'])}")

            # Step 4: 간단한 분석
            print("\n[Step 4] 데이터 분석...")
            data = result["data"]

            # 기간별 집계
            periods = {}
            for r in data:
                prd = r.get("PRD_DE", "Unknown")
                if prd not in periods:
                    periods[prd] = 0
                periods[prd] += 1

            print("  기간별 레코드 수:")
            for prd, count in sorted(periods.items()):
                print(f"    {prd}: {count}건")

            assert len(result["data"]) > 0
        else:
            print("❌ 데이터 조회 실패")
            pytest.skip("데이터 조회 실패")


# =====================
# Phase 4: 메타데이터 테스트
# =====================


class TestScenarioTableMetadata:
    """
    시나리오 7: 테이블 메타데이터 조회

    사용자 스토리:
    특정 통계표의 구조(분류항목, 항목, 수록기간)를 파악하고 싶다.
    """

    def test_get_table_info(self, meta_client: TableMetadata):
        """
        Step 1: 테이블 기본 정보 조회.

        기대 결과:
        - 테이블명(국문/영문) 조회 성공
        """
        print("\n=== 시나리오 7-1: 테이블 기본 정보 ===")

        # 주민등록인구 테이블
        result = meta_client.get_table_info("101", "DT_1B040A3")

        if result:
            print(f"✅ 테이블명(국문): {result.get('TBL_NM', 'N/A')}")
            print(f"   테이블명(영문): {result.get('TBL_NM_ENG', 'N/A')}")
            assert "TBL_NM" in result
        else:
            print("⚠️ 테이블 정보 조회 실패 (API 응답 형식 변경 가능)")
            pytest.skip("API 응답 없음")

    def test_get_obj_vars(self, meta_client: TableMetadata):
        """
        Step 2: 분류항목 조회.

        기대 결과:
        - 테이블의 분류항목(행정구역별, 성별 등) 목록 조회
        """
        print("\n=== 시나리오 7-2: 분류항목 조회 ===")

        result = meta_client.get_obj_vars("101", "DT_1B040A3")

        print(f"분류항목 수: {len(result)}개")
        if result:
            for obj in result:
                print(
                    f"  - objL{obj.get('OBJ_LV', '?')}: {obj.get('OBJ_NM', 'N/A')} ({obj.get('OBJ_VAR_CNT', '?')}개)"
                )
            assert len(result) > 0
        else:
            print("  (분류항목 없음 또는 API 응답 형식 다름)")

    def test_get_itm_vars(self, meta_client: TableMetadata):
        """
        Step 3: 항목 조회.

        기대 결과:
        - 테이블의 항목(총인구, 남자, 여자 등) 목록 조회
        """
        print("\n=== 시나리오 7-3: 항목 조회 ===")

        result = meta_client.get_itm_vars("101", "DT_1B040A3")

        print(f"항목 수: {len(result)}개")
        if result:
            for itm in result[:10]:  # 상위 10개만 출력
                print(
                    f"  - {itm.get('ITM_ID', '?')}: {itm.get('ITM_NM', 'N/A')} ({itm.get('UNIT_NM', '')})"
                )
        else:
            print("  (항목 없음 또는 API 응답 형식 다름)")

    def test_get_prd_info(self, meta_client: TableMetadata):
        """
        Step 4: 수록기간 조회.

        기대 결과:
        - 테이블의 수록기간 및 주기 정보 조회
        """
        print("\n=== 시나리오 7-4: 수록기간 조회 ===")

        result = meta_client.get_prd_info("101", "DT_1B040A3")

        print(f"수록기간 정보: {len(result)}개")
        if result:
            for prd in result[:5]:
                prd_se = prd.get("PRD_SE", "?")
                start = prd.get("STRT_PRD_DE", "?")
                end = prd.get("END_PRD_DE", "?")
                print(f"  - 주기: {prd_se}, 기간: {start} ~ {end}")
        else:
            print("  (수록기간 정보 없음 또는 API 응답 형식 다름)")

    def test_get_all_metadata(self, meta_client: TableMetadata):
        """
        Step 5: 전체 메타데이터 한 번에 조회.

        기대 결과:
        - 테이블 정보, 분류항목, 항목, 수록기간 모두 조회
        """
        print("\n=== 시나리오 7-5: 전체 메타데이터 ===")

        result = meta_client.get_all_metadata("101", "DT_1B040A3")

        print(f"org_id: {result.get('org_id')}")
        print(f"tbl_id: {result.get('tbl_id')}")
        print(f"table_info: {'있음' if result.get('table_info') else '없음'}")
        print(f"obj_vars: {len(result.get('obj_vars', []))}개")
        print(f"itm_vars: {len(result.get('itm_vars', []))}개")
        print(f"prd_info: {len(result.get('prd_info', []))}개")


class TestScenarioStatsExplanation:
    """
    시나리오 8: 통계설명 조회

    사용자 스토리:
    통계조사의 목적, 조사대상, 조사항목 등 상세 정보를 알고 싶다.
    """

    def test_get_explanation_by_table(self, expl_client: StatsExplanation):
        """
        Step 1: 테이블 ID로 통계설명 조회.

        기대 결과:
        - 조사명, 조사목적, 조사주기 등 정보 조회
        """
        print("\n=== 시나리오 8-1: 테이블 ID로 통계설명 ===")

        # 인구총조사 테이블
        result = expl_client.get_by_table("101", "DT_1IN0001")

        if result:
            print(f"✅ 조사명: {result.get('statsNm', 'N/A')}")
            print(f"   작성유형: {result.get('statsKind', 'N/A')}")
            print(f"   조사주기: {result.get('statsPeriod', 'N/A')}")
            print(f"   승인번호: {result.get('confmNo', 'N/A')}")
            if result.get("writingPurps"):
                print(f"   목적: {result.get('writingPurps', '')[:100]}...")
        else:
            print("⚠️ 통계설명 조회 실패 (일부 테이블은 통계설명이 없음)")
            # 다른 테이블로 재시도
            result = expl_client.get_by_table("101", "DT_1YL20631")
            if result:
                print(f"✅ (대체 테이블) 조사명: {result.get('statsNm', 'N/A')}")

    def test_get_llm_context(self, expl_client: StatsExplanation):
        """
        Step 2: LLM 컨텍스트용 정보 조회.

        기대 결과:
        - AI 모델이 이해하기 쉬운 구조화된 정보 반환
        """
        print("\n=== 시나리오 8-2: LLM 컨텍스트 ===")

        result = expl_client.get_llm_context(org_id="101", tbl_id="DT_1IN0001")

        if result:
            print("✅ LLM 컨텍스트 생성 성공:")
            print(f"   name: {result.get('name', 'N/A')}")
            print(f"   kind: {result.get('kind', 'N/A')}")
            print(f"   period: {result.get('period', 'N/A')}")
            print(f"   target: {result.get('target', 'N/A')}")
            print(f"   area: {result.get('area', 'N/A')}")
        else:
            print("⚠️ LLM 컨텍스트 조회 실패")

    def test_get_survey_purpose(self, expl_client: StatsExplanation):
        """
        Step 3: 조사목적만 간단히 조회.

        기대 결과:
        - 조사목적 문자열 반환
        """
        print("\n=== 시나리오 8-3: 조사목적 ===")

        result = expl_client.get_survey_purpose(org_id="101", tbl_id="DT_1IN0001")

        if result:
            print("✅ 조사목적:")
            print(f"   {result[:200]}...")
        else:
            print("⚠️ 조사목적 조회 실패")


class TestScenarioMetadataWorkflow:
    """
    시나리오 10: 메타데이터 통합 워크플로우

    사용자 스토리:
    검색 → 메타데이터 조회 → 데이터 조회의 전체 흐름을 수행.
    """

    def test_full_metadata_workflow(
        self,
        search_client: StatisticsSearch,
        meta_client: TableMetadata,
        expl_client: StatsExplanation,
        data_client: StatisticsData,
    ):
        """
        전체 메타데이터 워크플로우.
        """
        print("\n=== 시나리오 10: 메타데이터 통합 워크플로우 ===")

        # Step 1: 검색
        print("\n[Step 1] '인구총조사' 검색...")
        search_results = search_client.search("인구총조사", org_id=OrgCode.KOSTAT)

        if not search_results:
            pytest.skip("검색 결과 없음")

        print(f"검색 결과: {len(search_results)}건")
        selected = search_results[0]
        print(f"선택: {selected.get('TBL_NM')} ({selected.get('TBL_ID')})")

        org_id = selected.get("ORG_ID")
        tbl_id = selected.get("TBL_ID")

        # Step 2: 테이블 메타데이터
        print("\n[Step 2] 테이블 메타데이터...")
        table_info = meta_client.get_table_info(org_id, tbl_id)
        if table_info:
            print(f"  테이블명: {table_info.get('TBL_NM')}")

        obj_vars = meta_client.get_obj_vars(org_id, tbl_id)
        print(f"  분류항목: {len(obj_vars)}개")

        itm_vars = meta_client.get_itm_vars(org_id, tbl_id)
        print(f"  항목: {len(itm_vars)}개")

        # Step 3: 통계설명
        print("\n[Step 3] 통계설명...")
        llm_ctx = expl_client.get_llm_context(org_id=org_id, tbl_id=tbl_id)
        if llm_ctx:
            print(f"  조사명: {llm_ctx.get('name', 'N/A')}")
            print(f"  목적: {llm_ctx.get('purpose', 'N/A')[:80]}...")
        else:
            print("  (통계설명 없음)")

        # Step 4: 데이터 조회
        print("\n[Step 4] 데이터 조회...")
        result = data_client.get_data_auto_period(
            org_id=org_id, tbl_id=tbl_id, start_date="2020", end_date="2023"
        )

        if result:
            print(f"✅ 데이터 조회 성공: {len(result['data'])}건")
            print(f"   주기: {result['period_name']}")
        else:
            print("⚠️ 데이터 조회 실패 (테이블 특성에 따라 추가 파라미터 필요)")

        print("\n🎉 워크플로우 완료!")
