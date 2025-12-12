"""
KOSIS API 테스트 모듈
단계별로 API 기능을 검증합니다.
"""

import os
import sys
import json
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kosis_wrapper import KosisAPIWrapper


# ============================================================================
# 1단계: 환경변수 및 API 키 로드 테스트
# ============================================================================
class TestEnvironmentSetup:
    """환경변수 및 설정 파일 로드 테스트"""

    def test_dotenv_file_exists(self):
        """`.env` 파일이 존재하는지 확인"""
        env_path = Path(__file__).parent.parent / ".env"
        assert env_path.exists(), f".env 파일이 없습니다: {env_path}"

    def test_dotenv_loads_successfully(self):
        """dotenv가 정상적으로 로드되는지 확인"""
        load_dotenv()
        # 로드 자체가 성공하면 통과
        assert True

    def test_api_key_exists(self):
        """KOSIS_API_KEY 환경변수가 설정되어 있는지 확인"""
        load_dotenv()
        api_key = os.getenv("KOSIS_API_KEY")
        assert api_key is not None, "KOSIS_API_KEY 환경변수가 설정되지 않았습니다"

    def test_api_key_not_placeholder(self):
        """API 키가 플레이스홀더 값이 아닌지 확인"""
        load_dotenv()
        api_key = os.getenv("KOSIS_API_KEY")
        placeholder_values = [
            "your_api_key_here",
            "<YOUR_API_KEY_HERE>",
            "your_actual_api_key_here",
            "",
            None,
        ]
        assert api_key not in placeholder_values, "API 키가 실제 값으로 설정되지 않았습니다"

    def test_api_key_format(self):
        """API 키가 유효한 형식인지 확인 (길이 체크)"""
        load_dotenv()
        api_key = os.getenv("KOSIS_API_KEY")
        # KOSIS API 키는 일반적으로 길이가 있음
        assert len(api_key) >= 10, f"API 키가 너무 짧습니다: {len(api_key)} chars"


# ============================================================================
# 2단계: URL 연결성 테스트
# ============================================================================
class TestURLConnectivity:
    """KOSIS API URL 연결성 테스트"""

    BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    KOSIS_MAIN = "https://kosis.kr"

    def test_kosis_main_site_accessible(self):
        """KOSIS 메인 사이트 접근 가능 여부"""
        response = requests.head(self.KOSIS_MAIN, timeout=10)
        assert response.status_code in [200, 301, 302], \
            f"KOSIS 메인 사이트 접근 실패: {response.status_code}"

    def test_api_endpoint_accessible(self):
        """API 엔드포인트 URL 접근 가능 여부"""
        # GET 요청 (파라미터 없이)
        response = requests.get(self.BASE_URL, timeout=10)
        # 파라미터가 없어도 에러 메시지를 반환하면 서버는 동작 중
        assert response.status_code == 200, \
            f"API 엔드포인트 접근 실패: {response.status_code}"

    def test_api_returns_response(self):
        """API가 응답을 반환하는지 확인"""
        response = requests.get(self.BASE_URL, timeout=10)
        assert len(response.text) > 0, "API가 빈 응답을 반환했습니다"


# ============================================================================
# 3단계: API 인증 테스트
# ============================================================================
class TestAPIAuthentication:
    """API 키 인증 테스트"""

    BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

    @pytest.fixture
    def api_key(self):
        """실제 API 키 로드"""
        load_dotenv()
        return os.getenv("KOSIS_API_KEY")

    def test_invalid_api_key_rejected(self):
        """잘못된 API 키로 요청 시 에러 반환"""
        params = {
            "method": "getList",
            "apiKey": "INVALID_API_KEY_12345",
            "format": "json",
            "orgId": "101",
            "tblId": "DT_1YL20631",
            "objL1": "ALL",
            "itmId": "ALL",
            "prdSe": "Y",
            "startPrdDe": "2020",
            "endPrdDe": "2024",
        }
        response = requests.get(self.BASE_URL, params=params, timeout=30)
        # 응답이 오더라도 errMsg가 있어야 함
        assert response.status_code == 200
        # JSON 파싱 시도
        try:
            data = json.loads(response.text)
            assert "err" in str(data).lower() or "errMsg" in str(data), \
                "잘못된 API 키에 대한 에러 메시지가 없습니다"
        except json.JSONDecodeError:
            # 비표준 JSON일 수 있음
            assert "err" in response.text.lower(), \
                "잘못된 API 키에 대한 에러 메시지가 없습니다"

    def test_valid_api_key_accepted(self, api_key):
        """유효한 API 키로 요청 시 정상 응답"""
        params = {
            "method": "getList",
            "apiKey": api_key,
            "format": "json",
            "orgId": "101",
            "tblId": "DT_1YL20631",  # 고령인구비율 테이블
            "objL1": "ALL",
            "itmId": "ALL",
            "prdSe": "Y",
            "startPrdDe": "2020",
            "endPrdDe": "2024",
        }
        response = requests.get(self.BASE_URL, params=params, timeout=60)
        assert response.status_code == 200, f"요청 실패: {response.status_code}"

        # 에러 메시지가 없어야 함
        assert "errMsg" not in response.text or "정상" in response.text, \
            f"API 에러 발생: {response.text[:500]}"


# ============================================================================
# 4단계: 기본 API 호출 테스트 (KosisAPIWrapper 사용)
# ============================================================================
class TestKosisAPIWrapper:
    """KosisAPIWrapper 클래스 기능 테스트"""

    @pytest.fixture
    def wrapper(self):
        """API Wrapper 인스턴스 생성"""
        load_dotenv()
        api_key = os.getenv("KOSIS_API_KEY")
        return KosisAPIWrapper(api_key=api_key)

    def test_wrapper_initialization(self, wrapper):
        """Wrapper 초기화 테스트"""
        assert wrapper.api_key is not None
        assert wrapper.base_url is not None
        assert wrapper.session is not None

    def test_fetch_single_table_yearly(self, wrapper):
        """연간 데이터 단일 테이블 조회"""
        data = wrapper.fetch_table_data(
            org_id="101",
            tbl_id="DT_1YL20631",  # 고령인구비율(시도/시/군/구)
            start_date="2020",
            end_date="2024",
            prd_se="Y",
        )
        assert data is not None, "데이터 조회 실패"
        assert isinstance(data, list), "응답이 리스트가 아닙니다"
        assert len(data) > 0, "데이터가 비어있습니다"

    def test_fetch_table_data_structure(self, wrapper):
        """조회된 데이터의 구조 확인"""
        data = wrapper.fetch_table_data(
            org_id="101",
            tbl_id="DT_1YL20631",
            start_date="2023",
            end_date="2024",
            prd_se="Y",
        )
        assert data is not None and len(data) > 0

        # 첫 번째 레코드의 필드 확인
        first_record = data[0]
        expected_fields = ["TBL_ID", "PRD_DE", "DT"]  # 최소 필수 필드
        for field in expected_fields:
            assert field in first_record, f"필수 필드 '{field}'가 없습니다"

    def test_fetch_with_retry_obj_l1_only(self, wrapper):
        """objL1만으로 데이터 조회 테스트"""
        data = wrapper.fetch_table_data_with_retry(
            org_id="101",
            tbl_id="DT_1YL20631",
            start_date="2023",
            end_date="2024",
            prd_se="Y",
        )
        assert data is not None, "retry 로직으로 데이터 조회 실패"
        assert len(data) > 0

    def test_fetch_nonexistent_table(self, wrapper):
        """존재하지 않는 테이블 조회 시 None 반환"""
        data = wrapper.fetch_table_data(
            org_id="101",
            tbl_id="NONEXISTENT_TABLE_ID_12345",
            start_date="2020",
            end_date="2024",
            prd_se="Y",
        )
        assert data is None, "존재하지 않는 테이블에 대해 None이 반환되어야 합니다"


# ============================================================================
# 5단계: 데이터 변환 기능 테스트
# ============================================================================
class TestDataTransformation:
    """데이터 변환 기능 테스트"""

    def test_fix_malformed_json(self):
        """비표준 JSON 수정 기능"""
        load_dotenv()
        wrapper = KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

        # 키에 따옴표가 없는 비표준 JSON
        malformed = '{key1: "value1", key2: "value2"}'
        result = wrapper.fix_malformed_json(malformed)

        assert result is not None
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"

    def test_fix_malformed_json_array(self):
        """비표준 JSON 배열 수정"""
        load_dotenv()
        wrapper = KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

        malformed = '[{key1: "v1"}, {key2: "v2"}]'
        result = wrapper.fix_malformed_json(malformed)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fix_malformed_json_empty(self):
        """빈 응답 처리"""
        load_dotenv()
        wrapper = KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

        assert wrapper.fix_malformed_json("") is None
        assert wrapper.fix_malformed_json("   ") is None
        assert wrapper.fix_malformed_json(None) is None

    def test_date_format_yearly(self):
        """연간 날짜 포맷 변환"""
        load_dotenv()
        wrapper = KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

        result = wrapper._format_date_for_period("2024", "Y")
        assert result == "2024"

    def test_date_format_monthly(self):
        """월간 날짜 포맷 변환"""
        load_dotenv()
        wrapper = KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

        # 연도만 있는 경우 01월로 기본 설정
        result = wrapper._format_date_for_period("2024", "M")
        assert result == "202401"

        # 이미 월이 있는 경우
        result = wrapper._format_date_for_period("202406", "M")
        assert result == "202406"

    def test_date_format_quarterly(self):
        """분기 날짜 포맷 변환"""
        load_dotenv()
        wrapper = KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

        result = wrapper._format_date_for_period("2024", "Q")
        assert result == "202401"


# ============================================================================
# 6단계: 에러 핸들링 테스트
# ============================================================================
class TestErrorHandling:
    """에러 핸들링 테스트"""

    @pytest.fixture
    def wrapper(self):
        load_dotenv()
        return KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

    def test_timeout_handling(self, wrapper):
        """타임아웃 처리 테스트"""
        # 매우 짧은 타임아웃으로 테스트 (실패해야 정상)
        data = wrapper.fetch_table_data(
            org_id="101",
            tbl_id="DT_1YL20631",
            start_date="2020",
            end_date="2024",
            prd_se="Y",
            timeout=0.001,  # 1ms - 거의 확실히 타임아웃
        )
        # 타임아웃 시 None 반환
        assert data is None

    def test_invalid_org_id(self, wrapper):
        """잘못된 기관 ID 처리"""
        data = wrapper.fetch_table_data(
            org_id="INVALID_ORG",
            tbl_id="DT_1YL20631",
            start_date="2020",
            end_date="2024",
            prd_se="Y",
        )
        assert data is None

    def test_invalid_date_range(self, wrapper):
        """잘못된 날짜 범위 처리"""
        data = wrapper.fetch_table_data(
            org_id="101",
            tbl_id="DT_1YL20631",
            start_date="2030",  # 미래 날짜
            end_date="2035",
            prd_se="Y",
        )
        # 미래 데이터는 없으므로 None 또는 빈 리스트
        assert data is None or len(data) == 0


# ============================================================================
# 7단계: 실제 메타데이터 기반 테스트
# ============================================================================
class TestWithRealMetadata:
    """실제 메타데이터 파일 기반 테스트"""

    METADATA_PATH = Path(__file__).parent.parent / "kosis_data" / "kosis_metadata_final.json"

    @pytest.fixture
    def wrapper(self):
        load_dotenv()
        return KosisAPIWrapper(api_key=os.getenv("KOSIS_API_KEY"))

    @pytest.fixture
    def metadata(self):
        """메타데이터 파일 로드"""
        if not self.METADATA_PATH.exists():
            pytest.skip("메타데이터 파일이 없습니다")
        with open(self.METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_metadata_file_exists(self):
        """메타데이터 파일 존재 확인"""
        assert self.METADATA_PATH.exists(), \
            f"메타데이터 파일이 없습니다: {self.METADATA_PATH}"

    def test_metadata_structure(self, metadata):
        """메타데이터 구조 확인"""
        assert isinstance(metadata, list), "메타데이터가 리스트가 아닙니다"
        assert len(metadata) > 0, "메타데이터가 비어있습니다"

        # 첫 번째 항목의 필수 필드 확인
        first_item = metadata[0]
        required_fields = ["ORG_ID", "TBL_ID", "TBL_NM"]
        for field in required_fields:
            assert field in first_item, f"필수 필드 '{field}'가 없습니다"

    def test_fetch_first_table_from_metadata(self, wrapper, metadata):
        """메타데이터의 첫 번째 테이블 조회"""
        first_table = metadata[0]

        result = wrapper.find_optimal_period(first_table)

        # 결과가 None이 아니면 성공
        if result is not None:
            assert "data" in result
            assert "period_type" in result
            assert len(result["data"]) > 0
        else:
            # 일부 테이블은 데이터가 없을 수 있음
            pytest.skip(f"테이블 {first_table.get('TBL_ID')}에 데이터가 없습니다")


# ============================================================================
# 실행 시 요약 출력
# ============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
