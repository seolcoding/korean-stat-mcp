"""
kosis_tools.big_data 모듈 유닛 테스트.

테스트 범위:
    - StatisticsBigData.fetch_sdmx: SDMX 형식 데이터 조회
    - StatisticsBigData.fetch_csv: CSV 형식 데이터 조회
    - StatisticsBigData.fetch_dsd: DSD 메타데이터 조회
    - StatisticsBigData.parse_sdmx_xml: SDMX XML 파싱
    - StatisticsBigData._parse_csv: CSV 파싱
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.big_data import StatisticsBigData, SdmxType, BigDataFormat


@pytest.fixture
def big_data_client(test_config: KosisConfig) -> StatisticsBigData:
    """테스트용 대용량 데이터 클라이언트."""
    return StatisticsBigData(test_config)


@pytest.fixture
def sample_user_stats_id() -> str:
    """샘플 사용자 등록 통계표 ID."""
    return "openapisample/101/DT_1IN1502/2/1/20191106094026_1"


@pytest.fixture
def sample_sdmx_json_response() -> dict:
    """SDMX JSON 응답 샘플."""
    return {
        "header": {
            "id": "101_DT_1IN1502",
            "name": "총조사인구",
            "prepared": "2024-01-15T10:00:00",
            "sender": {
                "id": "KOSTAT",
                "name": "통계청"
            }
        },
        "dataSets": [
            {
                "series": {
                    "0:0:0": {
                        "observations": {
                            "0": [51829023],
                            "1": [51709098],
                            "2": [51558034]
                        }
                    }
                }
            }
        ]
    }


@pytest.fixture
def sample_csv_response() -> str:
    """CSV 응답 샘플."""
    return """PRD_DE,C1,C1_NM,ITM_ID,ITM_NM,DT,UNIT_NM
2023,00,전국,T001,총인구,51829023,명
2022,00,전국,T001,총인구,51709098,명
2021,00,전국,T001,총인구,51558034,명
2023,11,서울특별시,T001,총인구,9411211,명
2022,11,서울특별시,T001,총인구,9509458,명"""


@pytest.fixture
def sample_sdmx_xml_response() -> str:
    """SDMX XML 응답 샘플."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<message:GenericData xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message">
    <message:Header>
        <message:ID>101_DT_1IN1502</message:ID>
        <message:Name>총조사인구</message:Name>
        <message:Prepared>2024-01-15T10:00:00</message:Prepared>
        <message:Sender id="KOSTAT">
            <message:Name>통계청</message:Name>
        </message:Sender>
    </message:Header>
    <message:DataSet>
        <Series>
            <SeriesKey>
                <Value id="C1" value="00"/>
                <Value id="ITEM" value="T001"/>
            </SeriesKey>
            <Obs>
                <ObsDimension value="2023"/>
                <ObsValue value="51829023"/>
            </Obs>
            <Obs>
                <ObsDimension value="2022"/>
                <ObsValue value="51709098"/>
            </Obs>
        </Series>
    </message:DataSet>
</message:GenericData>"""


class TestStatisticsBigDataValidation:
    """StatisticsBigData 파라미터 검증 테스트."""

    def test_fetch_sdmx_empty_user_stats_id_raises_error(self, big_data_client: StatisticsBigData):
        """빈 user_stats_id는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="user_stats_id는 필수"):
            big_data_client.fetch_sdmx("", prd_se="Y")

    def test_fetch_sdmx_empty_prd_se_raises_error(
        self, big_data_client: StatisticsBigData, sample_user_stats_id: str
    ):
        """빈 prd_se는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="prd_se"):
            big_data_client.fetch_sdmx(sample_user_stats_id, prd_se="")

    def test_fetch_sdmx_invalid_type_raises_error(
        self, big_data_client: StatisticsBigData, sample_user_stats_id: str
    ):
        """잘못된 sdmx_type은 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="잘못된 sdmx_type"):
            big_data_client.fetch_sdmx(sample_user_stats_id, sdmx_type="InvalidType", prd_se="Y")

    def test_fetch_sdmx_partial_period_raises_error(
        self, big_data_client: StatisticsBigData, sample_user_stats_id: str
    ):
        """시작/종료 기간 중 하나만 있으면 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="startPrdDe와 endPrdDe 모두"):
            big_data_client.fetch_sdmx(
                sample_user_stats_id,
                prd_se="Y",
                start_prd_de="2020"
                # end_prd_de 누락
            )

    def test_fetch_csv_empty_user_stats_id_raises_error(self, big_data_client: StatisticsBigData):
        """CSV 조회 시 빈 user_stats_id는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="user_stats_id는 필수"):
            big_data_client.fetch_csv("", prd_se="Y")


class TestStatisticsBigDataFetchSdmx:
    """StatisticsBigData.fetch_sdmx 테스트."""

    @responses.activate
    def test_fetch_sdmx_generic_success(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
        sample_sdmx_json_response: dict,
    ):
        """SDMX Generic 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            json=sample_sdmx_json_response,
            status=200,
        )

        result = big_data_client.fetch_sdmx(
            user_stats_id=sample_user_stats_id,
            sdmx_type=SdmxType.GENERIC,
            prd_se="Y",
            new_est_prd_cnt=5,
        )

        assert result is not None
        assert "header" in result
        assert result["header"]["name"] == "총조사인구"

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "type=Generic" in request_url
        assert "prdSe=Y" in request_url
        assert "newEstPrdCnt=5" in request_url

    @responses.activate
    def test_fetch_sdmx_with_period_range(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
        sample_sdmx_json_response: dict,
    ):
        """시작/종료 기간으로 SDMX 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            json=sample_sdmx_json_response,
            status=200,
        )

        result = big_data_client.fetch_sdmx(
            user_stats_id=sample_user_stats_id,
            sdmx_type="StructureSpecific",
            prd_se="Y",
            start_prd_de="2020",
            end_prd_de="2023",
        )

        assert result is not None

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "type=StructureSpecific" in request_url
        assert "startPrdDe=2020" in request_url
        assert "endPrdDe=2023" in request_url

    @responses.activate
    def test_fetch_sdmx_dsd_no_period_params(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
        sample_sdmx_json_response: dict,
    ):
        """DSD 조회 시 기간 파라미터 불필요."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            json=sample_sdmx_json_response,
            status=200,
        )

        result = big_data_client.fetch_sdmx(
            user_stats_id=sample_user_stats_id,
            sdmx_type=SdmxType.DSD,
            prd_se="Y",  # 무시됨
        )

        assert result is not None

        # DSD는 prdSe 파라미터가 포함되지 않아야 함
        request_url = responses.calls[0].request.url
        assert "type=DSD" in request_url


class TestStatisticsBigDataFetchCsv:
    """StatisticsBigData.fetch_csv 테스트."""

    @responses.activate
    def test_fetch_csv_success(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
        sample_csv_response: str,
    ):
        """CSV 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            body=sample_csv_response,
            status=200,
        )

        result = big_data_client.fetch_csv(
            user_stats_id=sample_user_stats_id,
            prd_se="Y",
            new_est_prd_cnt=5,
        )

        assert isinstance(result, list)
        assert len(result) == 5
        assert result[0]["PRD_DE"] == "2023"
        assert result[0]["C1_NM"] == "전국"
        assert result[0]["DT"] == "51829023"

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "format=csv" in request_url

    @responses.activate
    def test_fetch_csv_empty_response(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
    ):
        """빈 CSV 응답 처리."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            body="",
            status=200,
        )

        result = big_data_client.fetch_csv(
            user_stats_id=sample_user_stats_id,
            prd_se="Y",
        )

        assert result == []


class TestStatisticsBigDataParsing:
    """StatisticsBigData 파싱 테스트."""

    def test_parse_csv_success(self, big_data_client: StatisticsBigData, sample_csv_response: str):
        """CSV 파싱 성공."""
        result = big_data_client._parse_csv(sample_csv_response)

        assert len(result) == 5
        assert result[0]["PRD_DE"] == "2023"
        assert result[0]["ITM_NM"] == "총인구"

    def test_parse_csv_empty_string(self, big_data_client: StatisticsBigData):
        """빈 문자열 CSV 파싱."""
        result = big_data_client._parse_csv("")
        assert result == []

    def test_parse_csv_whitespace_only(self, big_data_client: StatisticsBigData):
        """공백만 있는 CSV 파싱."""
        result = big_data_client._parse_csv("   \n\t  ")
        assert result == []

    def test_parse_sdmx_xml_success(
        self, big_data_client: StatisticsBigData, sample_sdmx_xml_response: str
    ):
        """SDMX XML 파싱 성공."""
        result = big_data_client.parse_sdmx_xml(sample_sdmx_xml_response)

        assert "header" in result
        assert "series" in result
        assert len(result["series"]) == 1

    def test_parse_sdmx_xml_empty_string(self, big_data_client: StatisticsBigData):
        """빈 XML 파싱."""
        result = big_data_client.parse_sdmx_xml("")
        assert result == {}

    def test_parse_sdmx_xml_invalid_xml(self, big_data_client: StatisticsBigData):
        """잘못된 XML 파싱."""
        result = big_data_client.parse_sdmx_xml("<invalid>xml</no_close>")
        assert result == {}


class TestStatisticsBigDataHelpers:
    """StatisticsBigData 헬퍼 메서드 테스트."""

    @responses.activate
    def test_fetch_dsd_calls_fetch_sdmx_with_dsd_type(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
        sample_sdmx_json_response: dict,
    ):
        """fetch_dsd는 DSD 타입으로 fetch_sdmx를 호출해야 함."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            json=sample_sdmx_json_response,
            status=200,
        )

        result = big_data_client.fetch_dsd(sample_user_stats_id)

        assert result is not None
        request_url = responses.calls[0].request.url
        assert "type=DSD" in request_url

    @responses.activate
    def test_get_registered_stats_info_success(
        self,
        big_data_client: StatisticsBigData,
        sample_user_stats_id: str,
        sample_sdmx_json_response: dict,
    ):
        """등록 통계표 정보 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            json=sample_sdmx_json_response,
            status=200,
        )

        result = big_data_client.get_registered_stats_info(sample_user_stats_id)

        assert result["user_stats_id"] == sample_user_stats_id
        assert result["valid"] is True
        assert result["name"] == "총조사인구"

    @responses.activate
    def test_get_registered_stats_info_invalid_id(
        self,
        big_data_client: StatisticsBigData,
    ):
        """잘못된 ID로 등록 통계표 정보 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsBigData.do",
            json={},
            status=200,
        )

        result = big_data_client.get_registered_stats_info("invalid_id")

        assert result["user_stats_id"] == "invalid_id"
        # 빈 응답이면 valid는 False


class TestSdmxTypeEnum:
    """SdmxType enum 테스트."""

    def test_sdmx_type_values(self):
        """SdmxType enum 값 확인."""
        assert SdmxType.DSD.value == "DSD"
        assert SdmxType.GENERIC.value == "Generic"
        assert SdmxType.STRUCTURE_SPECIFIC.value == "StructureSpecific"

    def test_sdmx_type_from_string(self):
        """문자열에서 SdmxType 생성."""
        assert SdmxType("DSD") == SdmxType.DSD
        assert SdmxType("Generic") == SdmxType.GENERIC
        assert SdmxType("StructureSpecific") == SdmxType.STRUCTURE_SPECIFIC

    def test_sdmx_type_invalid_string(self):
        """잘못된 문자열은 ValueError."""
        with pytest.raises(ValueError):
            SdmxType("Invalid")


class TestBigDataFormatEnum:
    """BigDataFormat enum 테스트."""

    def test_big_data_format_values(self):
        """BigDataFormat enum 값 확인."""
        assert BigDataFormat.JSON.value == "json"
        assert BigDataFormat.SDMX.value == "sdmx"
        assert BigDataFormat.CSV.value == "csv"
        assert BigDataFormat.XLS.value == "xls"
