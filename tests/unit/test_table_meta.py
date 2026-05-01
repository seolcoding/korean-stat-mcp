"""
kosis_tools.table_meta 모듈 유닛 테스트.

테스트 범위:
    - TableMetadata.get_table_info: 테이블 기본 정보 조회
    - TableMetadata.get_obj_vars: 분류항목 조회
    - TableMetadata.get_itm_vars: 항목 조회
    - TableMetadata.get_prd_info: 수록기간 조회
    - TableMetadata.get_all_metadata: 전체 메타데이터 조회
    - TableMetadata.get_comments: 주석(CMMT) 조회 (Phase A)
    - TableMetadata.get_source: 출처(SOURCE) 조회 (Phase A)
    - TableMetadata.get_weight: 가중치(WGT) 조회 (Phase A)
    - TableMetadata.get_update_date: 자료갱신일(NCD) 조회 (Phase A)
    - TableMetadata.get_unit: 단위(UNIT) 조회 (Phase A)
    - TableMetadata.get_org_info: 기관정보(ORG) 조회 (Phase A)
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.table_meta import TableMetadata


@pytest.fixture
def meta_client(test_config: KosisConfig) -> TableMetadata:
    """테스트용 메타데이터 클라이언트."""
    return TableMetadata(test_config)


@pytest.fixture
def sample_tbl_response() -> str:
    """테이블 정보 응답 샘플 (KOSIS 비표준 JSON)."""
    return """[{TBL_NM:"총조사인구 총괄(읍면동/성/연령별)",TBL_NM_ENG:"Summary of Census Population"}]"""


@pytest.fixture
def sample_obj_var_response() -> str:
    """분류항목 응답 샘플."""
    return """[
        {OBJ_ID:"ITEM",OBJ_NM:"행정구역별",OBJ_NM_ENG:"By region",OBJ_LV:"1",OBJ_VAR_CNT:"250"},
        {OBJ_ID:"ITEM2",OBJ_NM:"성별",OBJ_NM_ENG:"By sex",OBJ_LV:"2",OBJ_VAR_CNT:"3"}
    ]"""


@pytest.fixture
def sample_itm_var_response() -> str:
    """항목 응답 샘플."""
    return """[
        {ITM_ID:"T001",ITM_NM:"총인구",ITM_NM_ENG:"Total",UNIT_NM:"명"},
        {ITM_ID:"T002",ITM_NM:"남자",ITM_NM_ENG:"Male",UNIT_NM:"명"}
    ]"""


@pytest.fixture
def sample_prd_response() -> str:
    """수록기간 응답 샘플."""
    return """[{PRD_SE:"Y",STRT_PRD_DE:"1992",END_PRD_DE:"2023"}]"""


class TestTableMetadataGetTableInfo:
    """TableMetadata.get_table_info 테스트."""

    def test_empty_org_id_returns_none(self, meta_client: TableMetadata):
        """빈 기관 ID는 None을 반환해야 함."""
        result = meta_client.get_table_info("", "DT_1IN0001")
        assert result is None

    def test_empty_tbl_id_returns_none(self, meta_client: TableMetadata):
        """빈 테이블 ID는 None을 반환해야 함."""
        result = meta_client.get_table_info("101", "")
        assert result is None

    @responses.activate
    def test_get_table_info_success(
        self, meta_client: TableMetadata, sample_tbl_response: str
    ):
        """테이블 정보 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_tbl_response,
            status=200,
        )

        result = meta_client.get_table_info("101", "DT_1IN0001")

        assert result is not None
        assert result["TBL_NM"] == "총조사인구 총괄(읍면동/성/연령별)"
        assert result["TBL_NM_ENG"] == "Summary of Census Population"
        # 파라미터 확인
        assert "method=getMeta" in responses.calls[0].request.url
        assert "type=TBL" in responses.calls[0].request.url
        assert "orgId=101" in responses.calls[0].request.url
        assert "tblId=DT_1IN0001" in responses.calls[0].request.url

    @responses.activate
    def test_get_table_info_not_found(self, meta_client: TableMetadata):
        """테이블을 찾지 못한 경우."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )

        result = meta_client.get_table_info("101", "NOT_EXIST")

        assert result is None


class TestTableMetadataGetObjVars:
    """TableMetadata.get_obj_vars 테스트."""

    def test_empty_ids_returns_empty_list(self, meta_client: TableMetadata):
        """빈 ID는 빈 리스트를 반환해야 함."""
        assert meta_client.get_obj_vars("", "DT_1IN0001") == []
        assert meta_client.get_obj_vars("101", "") == []

    @responses.activate
    def test_get_obj_vars_success(
        self, meta_client: TableMetadata, sample_obj_var_response: str
    ):
        """분류항목 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_obj_var_response,
            status=200,
        )

        result = meta_client.get_obj_vars("101", "DT_1IN0001")

        assert len(result) == 2
        assert result[0]["OBJ_ID"] == "ITEM"
        assert result[0]["OBJ_NM"] == "행정구역별"
        assert result[1]["OBJ_LV"] == "2"
        # 파라미터 확인
        assert "type=OBJ_VAR" in responses.calls[0].request.url


class TestTableMetadataGetItmVars:
    """TableMetadata.get_itm_vars 테스트."""

    def test_empty_ids_returns_empty_list(self, meta_client: TableMetadata):
        """빈 ID는 빈 리스트를 반환해야 함."""
        assert meta_client.get_itm_vars("", "DT_1IN0001") == []
        assert meta_client.get_itm_vars("101", "") == []

    @responses.activate
    def test_get_itm_vars_success(
        self, meta_client: TableMetadata, sample_itm_var_response: str
    ):
        """항목 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_itm_var_response,
            status=200,
        )

        result = meta_client.get_itm_vars("101", "DT_1IN0001")

        assert len(result) == 2
        assert result[0]["ITM_ID"] == "T001"
        assert result[0]["ITM_NM"] == "총인구"
        assert result[0]["UNIT_NM"] == "명"
        # 파라미터 확인
        assert "type=ITM_VAR" in responses.calls[0].request.url


class TestTableMetadataGetPrdInfo:
    """TableMetadata.get_prd_info 테스트."""

    def test_empty_ids_returns_empty_list(self, meta_client: TableMetadata):
        """빈 ID는 빈 리스트를 반환해야 함."""
        assert meta_client.get_prd_info("", "DT_1IN0001") == []
        assert meta_client.get_prd_info("101", "") == []

    @responses.activate
    def test_get_prd_info_success(
        self, meta_client: TableMetadata, sample_prd_response: str
    ):
        """수록기간 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_prd_response,
            status=200,
        )

        result = meta_client.get_prd_info("101", "DT_1IN0001")

        assert len(result) == 1
        assert result[0]["PRD_SE"] == "Y"
        assert result[0]["STRT_PRD_DE"] == "1992"
        assert result[0]["END_PRD_DE"] == "2023"
        # 파라미터 확인
        assert "type=PRD" in responses.calls[0].request.url


class TestTableMetadataGetAllMetadata:
    """TableMetadata.get_all_metadata 테스트."""

    @responses.activate
    def test_get_all_metadata_success(
        self,
        meta_client: TableMetadata,
        sample_tbl_response: str,
        sample_obj_var_response: str,
        sample_itm_var_response: str,
        sample_prd_response: str,
    ):
        """전체 메타데이터 조회 성공.

        get_all_metadata는 4개 sub-type을 ThreadPoolExecutor로 병렬 호출하므로
        request 순서가 비결정적이다. type 파라미터로 dispatch되는 mock으로 검증.
        """
        from responses import matchers

        for type_code, body in (
            ("TBL", sample_tbl_response),
            ("OBJ_VAR", sample_obj_var_response),
            ("ITM_VAR", sample_itm_var_response),
            ("PRD", sample_prd_response),
        ):
            responses.add(
                responses.GET,
                "https://kosis.kr/openapi/statisticsData.do",
                body=body,
                status=200,
                match=[
                    matchers.query_param_matcher(
                        {"type": type_code}, strict_match=False
                    )
                ],
            )

        result = meta_client.get_all_metadata("101", "DT_1IN0001")

        assert result["org_id"] == "101"
        assert result["tbl_id"] == "DT_1IN0001"
        assert result["table_info"]["TBL_NM"] == "총조사인구 총괄(읍면동/성/연령별)"
        assert len(result["obj_vars"]) == 2
        assert len(result["itm_vars"]) == 2
        assert len(result["prd_info"]) == 1


# ============================================================================
# Phase A: 확장 메타데이터 테스트 (CMMT, SOURCE, WGT, NCD, UNIT, ORG)
# ============================================================================


@pytest.fixture
def sample_cmmt_response() -> str:
    """주석(CMMT) 응답 샘플."""
    return """[
        {CMMT_NM:"일반주석",CMMT_DC:"해당 통계표는 2020년 기준입니다.",OBJ_ID:"",ITM_ID:""},
        {CMMT_NM:"분류주석",CMMT_DC:"행정구역은 2023년 기준입니다.",OBJ_ID:"ITEM",ITM_ID:""}
    ]"""


@pytest.fixture
def sample_source_response() -> str:
    """출처(SOURCE) 응답 샘플."""
    return """[{JOSA_NM:"인구총조사",DEPT_NM:"인구동향과",DEPT_PHONE:"042-481-2500",STAT_ID:"101001"}]"""


@pytest.fixture
def sample_weight_response() -> str:
    """가중치(WGT) 응답 샘플."""
    return """[
        {C1:"00",C1_NM:"전국",ITM_ID:"T001",ITM_NM:"총인구",WGT_CO:1.0},
        {C1:"11",C1_NM:"서울",ITM_ID:"T001",ITM_NM:"총인구",WGT_CO:1.2}
    ]"""


@pytest.fixture
def sample_ncd_response() -> str:
    """자료갱신일(NCD) 응답 샘플."""
    return """[
        {ORG_NM:"통계청",TBL_NM:"총조사인구",PRD_SE:"Y",PRD_DE:"2023",SEND_DE:"2024-01-15"},
        {ORG_NM:"통계청",TBL_NM:"총조사인구",PRD_SE:"Y",PRD_DE:"2022",SEND_DE:"2023-01-20"}
    ]"""


@pytest.fixture
def sample_unit_response() -> str:
    """단위(UNIT) 응답 샘플."""
    return """[{UNIT_NM:"명",UNIT_NM_ENG:"Persons"}]"""


@pytest.fixture
def sample_org_response() -> str:
    """기관(ORG) 응답 샘플."""
    return """[{orgNm:"통계청",orgNmEng:"Statistics Korea"}]"""


class TestTableMetadataGetComments:
    """TableMetadata.get_comments 테스트 (Phase A: CMMT)."""

    def test_empty_org_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 기관 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_comments("", "DT_1IN0001")
        assert result == []

    def test_empty_tbl_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 테이블 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_comments("101", "")
        assert result == []

    @responses.activate
    def test_get_comments_success(
        self, meta_client: TableMetadata, sample_cmmt_response: str
    ):
        """주석 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_cmmt_response,
            status=200,
        )

        result = meta_client.get_comments("101", "DT_1IN0001")

        assert len(result) == 2
        assert result[0]["CMMT_NM"] == "일반주석"
        assert result[0]["CMMT_DC"] == "해당 통계표는 2020년 기준입니다."
        assert result[1]["OBJ_ID"] == "ITEM"
        # 파라미터 확인
        assert "type=CMMT" in responses.calls[0].request.url

    @responses.activate
    def test_get_comments_empty_result(self, meta_client: TableMetadata):
        """주석이 없는 테이블은 빈 리스트 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            json=[],
            status=200,
        )

        result = meta_client.get_comments("101", "DT_1IN0001")
        assert result == []


class TestTableMetadataGetSource:
    """TableMetadata.get_source 테스트 (Phase A: SOURCE)."""

    def test_empty_org_id_returns_none(self, meta_client: TableMetadata):
        """빈 기관 ID는 None을 반환해야 함."""
        result = meta_client.get_source("", "DT_1IN0001")
        assert result is None

    def test_empty_tbl_id_returns_none(self, meta_client: TableMetadata):
        """빈 테이블 ID는 None을 반환해야 함."""
        result = meta_client.get_source("101", "")
        assert result is None

    @responses.activate
    def test_get_source_success(
        self, meta_client: TableMetadata, sample_source_response: str
    ):
        """출처 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_source_response,
            status=200,
        )

        result = meta_client.get_source("101", "DT_1IN0001")

        assert result is not None
        assert result["JOSA_NM"] == "인구총조사"
        assert result["DEPT_NM"] == "인구동향과"
        assert result["DEPT_PHONE"] == "042-481-2500"
        # 파라미터 확인
        assert "type=SOURCE" in responses.calls[0].request.url


class TestTableMetadataGetWeight:
    """TableMetadata.get_weight 테스트 (Phase A: WGT)."""

    def test_empty_org_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 기관 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_weight("", "DT_1IN0001")
        assert result == []

    def test_empty_tbl_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 테이블 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_weight("101", "")
        assert result == []

    @responses.activate
    def test_get_weight_success(
        self, meta_client: TableMetadata, sample_weight_response: str
    ):
        """가중치 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_weight_response,
            status=200,
        )

        result = meta_client.get_weight("101", "DT_1IN0001")

        assert len(result) == 2
        assert result[0]["C1"] == "00"
        assert result[0]["C1_NM"] == "전국"
        assert result[0]["WGT_CO"] == 1.0
        assert result[1]["WGT_CO"] == 1.2
        # 파라미터 확인
        assert "type=WGT" in responses.calls[0].request.url

    @responses.activate
    def test_get_weight_with_filters(
        self, meta_client: TableMetadata, sample_weight_response: str
    ):
        """분류코드 및 항목 필터로 가중치 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_weight_response,
            status=200,
        )

        result = meta_client.get_weight(
            "101", "DT_1IN0001", obj_codes={"C1": "00"}, itm_id="T001"
        )

        assert len(result) >= 1
        # 필터 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "C1=00" in request_url
        assert "ITEM=T001" in request_url


class TestTableMetadataGetUpdateDate:
    """TableMetadata.get_update_date 테스트 (Phase A: NCD)."""

    def test_empty_org_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 기관 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_update_date("", "DT_1IN0001")
        assert result == []

    def test_empty_tbl_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 테이블 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_update_date("101", "")
        assert result == []

    @responses.activate
    def test_get_update_date_success(
        self, meta_client: TableMetadata, sample_ncd_response: str
    ):
        """자료갱신일 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_ncd_response,
            status=200,
        )

        result = meta_client.get_update_date("101", "DT_1IN0001")

        assert len(result) == 2
        assert result[0]["PRD_DE"] == "2023"
        assert result[0]["SEND_DE"] == "2024-01-15"
        assert result[1]["PRD_DE"] == "2022"
        # 파라미터 확인
        assert "type=NCD" in responses.calls[0].request.url

    @responses.activate
    def test_get_update_date_with_prd_se(
        self, meta_client: TableMetadata, sample_ncd_response: str
    ):
        """수록주기 필터로 자료갱신일 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_ncd_response,
            status=200,
        )

        result = meta_client.get_update_date("101", "DT_1IN0001", prd_se="Y")

        assert len(result) >= 1
        # prdSe 파라미터 확인
        assert "prdSe=Y" in responses.calls[0].request.url


class TestTableMetadataGetUnit:
    """TableMetadata.get_unit 테스트 (Phase A: UNIT)."""

    def test_empty_org_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 기관 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_unit("", "DT_1IN0001")
        assert result == []

    def test_empty_tbl_id_returns_empty_list(self, meta_client: TableMetadata):
        """빈 테이블 ID는 빈 리스트를 반환해야 함."""
        result = meta_client.get_unit("101", "")
        assert result == []

    @responses.activate
    def test_get_unit_success(
        self, meta_client: TableMetadata, sample_unit_response: str
    ):
        """단위 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_unit_response,
            status=200,
        )

        result = meta_client.get_unit("101", "DT_1IN0001")

        assert len(result) == 1
        assert result[0]["UNIT_NM"] == "명"
        assert result[0]["UNIT_NM_ENG"] == "Persons"
        # 파라미터 확인
        assert "type=UNIT" in responses.calls[0].request.url


class TestTableMetadataGetOrgInfo:
    """TableMetadata.get_org_info 테스트 (Phase A: ORG)."""

    def test_empty_org_id_returns_none(self, meta_client: TableMetadata):
        """빈 기관 ID는 None을 반환해야 함."""
        result = meta_client.get_org_info("")
        assert result is None

    @responses.activate
    def test_get_org_info_success(
        self, meta_client: TableMetadata, sample_org_response: str
    ):
        """기관 정보 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsData.do",
            body=sample_org_response,
            status=200,
        )

        result = meta_client.get_org_info("101")

        assert result is not None
        assert result["orgNm"] == "통계청"
        assert result["orgNmEng"] == "Statistics Korea"
        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "type=ORG" in request_url
        assert "orgId=101" in request_url
        # tblId는 ORG 조회에서는 없어야 함
        assert "tblId" not in request_url


class TestTableMetadataGetAllMetadataExtended:
    """TableMetadata.get_all_metadata(include_extended=True) 테스트."""

    @responses.activate
    def test_get_all_metadata_with_extended(
        self,
        meta_client: TableMetadata,
        sample_tbl_response: str,
        sample_obj_var_response: str,
        sample_itm_var_response: str,
        sample_prd_response: str,
        sample_cmmt_response: str,
        sample_source_response: str,
        sample_unit_response: str,
        sample_ncd_response: str,
    ):
        """확장 메타데이터 포함 전체 조회 성공.

        병렬 fan-out 시 type 파라미터로 dispatch되는 mock으로 검증.
        """
        from responses import matchers

        for type_code, body in (
            ("TBL", sample_tbl_response),
            ("OBJ_VAR", sample_obj_var_response),
            ("ITM_VAR", sample_itm_var_response),
            ("PRD", sample_prd_response),
            ("CMMT", sample_cmmt_response),
            ("SOURCE", sample_source_response),
            ("UNIT", sample_unit_response),
            ("NCD", sample_ncd_response),
        ):
            responses.add(
                responses.GET,
                "https://kosis.kr/openapi/statisticsData.do",
                body=body,
                status=200,
                match=[
                    matchers.query_param_matcher(
                        {"type": type_code}, strict_match=False
                    )
                ],
            )

        result = meta_client.get_all_metadata(
            "101", "DT_1IN0001", include_extended=True
        )

        # 기본 메타데이터
        assert result["org_id"] == "101"
        assert result["tbl_id"] == "DT_1IN0001"
        assert result["table_info"]["TBL_NM"] == "총조사인구 총괄(읍면동/성/연령별)"
        assert len(result["obj_vars"]) == 2
        assert len(result["itm_vars"]) == 2
        assert len(result["prd_info"]) == 1

        # 확장 메타데이터
        assert "comments" in result
        assert len(result["comments"]) == 2
        assert "source" in result
        assert result["source"]["JOSA_NM"] == "인구총조사"
        assert "units" in result
        assert result["units"][0]["UNIT_NM"] == "명"
        assert "update_dates" in result
        assert len(result["update_dates"]) == 2

    @responses.activate
    def test_get_all_metadata_without_extended_excludes_extended_fields(
        self,
        meta_client: TableMetadata,
        sample_tbl_response: str,
        sample_obj_var_response: str,
        sample_itm_var_response: str,
        sample_prd_response: str,
    ):
        """include_extended=False일 때 확장 필드는 포함되지 않음."""
        from responses import matchers

        for type_code, body in (
            ("TBL", sample_tbl_response),
            ("OBJ_VAR", sample_obj_var_response),
            ("ITM_VAR", sample_itm_var_response),
            ("PRD", sample_prd_response),
        ):
            responses.add(
                responses.GET,
                "https://kosis.kr/openapi/statisticsData.do",
                body=body,
                status=200,
                match=[
                    matchers.query_param_matcher(
                        {"type": type_code}, strict_match=False
                    )
                ],
            )

        result = meta_client.get_all_metadata(
            "101", "DT_1IN0001", include_extended=False
        )

        # 기본 메타데이터만 있어야 함
        assert "table_info" in result
        assert "obj_vars" in result
        assert "itm_vars" in result
        assert "prd_info" in result

        # 확장 메타데이터는 없어야 함
        assert "comments" not in result
        assert "source" not in result
        assert "units" not in result
        assert "update_dates" not in result

    @responses.activate
    def test_get_all_metadata_runs_in_parallel(
        self,
        meta_client: TableMetadata,
        sample_tbl_response: str,
        sample_obj_var_response: str,
        sample_itm_var_response: str,
        sample_prd_response: str,
    ):
        """병렬 fan-out 검증.

        각 sub-call에 일정 sleep을 끼워, 직렬이면 4*delay, 병렬이면 ~delay만
        걸려야 함. 안전 마진을 두고 < 2.5*delay 면 통과로 본다.
        """
        import time

        from responses import matchers

        delay = 0.2

        def _slow(body):
            def _cb(request):
                time.sleep(delay)
                return (
                    200,
                    {"Content-Type": "application/json; charset=utf-8"},
                    body.encode("utf-8"),
                )

            return _cb

        for type_code, body in (
            ("TBL", sample_tbl_response),
            ("OBJ_VAR", sample_obj_var_response),
            ("ITM_VAR", sample_itm_var_response),
            ("PRD", sample_prd_response),
        ):
            responses.add_callback(
                responses.GET,
                "https://kosis.kr/openapi/statisticsData.do",
                callback=_slow(body),
                match=[
                    matchers.query_param_matcher(
                        {"type": type_code}, strict_match=False
                    )
                ],
            )

        t0 = time.monotonic()
        result = meta_client.get_all_metadata("101", "DT_1IN0001")
        elapsed = time.monotonic() - t0

        # 병렬이면 ~delay, 직렬이면 ~4*delay = 0.8s. 마진 두고 < 2.5*delay (0.5s).
        assert elapsed < 2.5 * delay, (
            f"get_all_metadata took {elapsed:.2f}s with {delay}s mock delay; "
            "expected parallel fan-out (< {:.2f}s)".format(2.5 * delay)
        )
        # 결과는 정상이어야 함
        assert result["table_info"]["TBL_NM"] == "총조사인구 총괄(읍면동/성/연령별)"
