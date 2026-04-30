"""
데이터 저장 기능 테스트.

MCP 패턴에 따라 원본 데이터를 파일로 저장하고
요약만 LLM에 전달하는 기능을 테스트합니다.
"""

import json
import pytest
from pathlib import Path
from typing import List, Dict, Any

from kosis_tools.report_tools import (
    save_raw_data,
    load_raw_data,
    list_saved_data,
    format_data_for_llm,
)
from kosis_tools.config import DataStorageConfig


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_data() -> List[Dict[str, Any]]:
    """테스트용 샘플 데이터."""
    return [
        {
            "TBL_ID": "DT_TEST001",
            "TBL_NM": "테스트 통계표",
            "ORG_ID": "101",
            "ORG_NM": "통계청",
            "PRD_DE": str(year),
            "C1_NM": region,
            "ITM_NM": "인구수",
            "DT": str(1000000 + i * 1000),
            "UNIT_NM": "명",
        }
        for i, (year, region) in enumerate(
            [
                (2021, "서울특별시"),
                (2021, "부산광역시"),
                (2022, "서울특별시"),
                (2022, "부산광역시"),
                (2023, "서울특별시"),
                (2023, "부산광역시"),
            ]
        )
    ]


@pytest.fixture
def large_data() -> List[Dict[str, Any]]:
    """대용량 테스트 데이터 (500건)."""
    regions = ["서울", "부산", "대구", "인천", "광주"]
    years = [str(y) for y in range(2010, 2024)]
    items = ["인구수", "세대수", "면적"]

    data = []
    for year in years:
        for region in regions:
            for item in items:
                data.append(
                    {
                        "TBL_ID": "DT_LARGE001",
                        "TBL_NM": "대용량 테스트 통계표",
                        "ORG_ID": "101",
                        "ORG_NM": "통계청",
                        "PRD_DE": year,
                        "C1_NM": region,
                        "ITM_NM": item,
                        "DT": str(hash((year, region, item)) % 10000000),
                        "UNIT_NM": "단위",
                    }
                )
    return data


@pytest.fixture
def temp_data_dir(tmp_path):
    """임시 데이터 디렉토리 설정."""
    original_dir = DataStorageConfig.DATA_DIR
    DataStorageConfig.DATA_DIR = str(tmp_path)
    yield tmp_path
    DataStorageConfig.DATA_DIR = original_dir


# =============================================================================
# save_raw_data 테스트
# =============================================================================


class TestSaveRawData:
    """save_raw_data 함수 테스트."""

    def test_save_creates_file(self, sample_data, temp_data_dir):
        """데이터 저장 시 파일이 생성되는지 확인."""
        result = save_raw_data(sample_data)

        assert "error" not in result
        assert "data_id" in result
        assert "file_path" in result
        assert Path(result["file_path"]).exists()

    def test_save_returns_metadata(self, sample_data, temp_data_dir):
        """저장 결과에 메타데이터가 포함되는지 확인."""
        result = save_raw_data(sample_data)

        assert result["record_count"] == len(sample_data)
        assert "file_size_kb" in result
        assert "created_at" in result

    def test_save_empty_data(self, temp_data_dir):
        """빈 데이터 저장 시 에러 반환."""
        result = save_raw_data([])

        assert "error" in result
        assert result["data_id"] is None

    def test_save_with_custom_id(self, sample_data, temp_data_dir):
        """커스텀 ID로 저장."""
        custom_id = "custom_test_id"
        result = save_raw_data(sample_data, data_id=custom_id)

        assert result["data_id"] == custom_id
        assert custom_id in result["file_path"]

    def test_saved_file_contains_data(self, sample_data, temp_data_dir):
        """저장된 파일에 데이터가 포함되어 있는지 확인."""
        result = save_raw_data(sample_data)

        with open(result["file_path"], "r", encoding="utf-8") as f:
            stored = json.load(f)

        assert "meta" in stored
        assert "data" in stored
        assert len(stored["data"]) == len(sample_data)


# =============================================================================
# load_raw_data 테스트
# =============================================================================


class TestLoadRawData:
    """load_raw_data 함수 테스트."""

    def test_load_full_data(self, sample_data, temp_data_dir):
        """전체 데이터 로드."""
        save_result = save_raw_data(sample_data)
        data_id = save_result["data_id"]

        load_result = load_raw_data(data_id)

        assert "error" not in load_result
        assert load_result["data_id"] == data_id
        assert len(load_result["data"]) == len(sample_data)

    def test_load_chunk(self, large_data, temp_data_dir):
        """청크 단위로 데이터 로드."""
        save_result = save_raw_data(large_data)
        data_id = save_result["data_id"]

        # 첫 번째 청크 로드
        chunk_result = load_raw_data(data_id, chunk_index=0, chunk_size=50)

        assert "chunk_info" in chunk_result
        assert chunk_result["chunk_info"]["chunk_index"] == 0
        assert chunk_result["chunk_info"]["chunk_size"] == 50
        assert chunk_result["chunk_info"]["has_more"] is True
        assert len(chunk_result["data"]) == 50

    def test_load_multiple_chunks(self, large_data, temp_data_dir):
        """여러 청크 순회."""
        save_result = save_raw_data(large_data)
        data_id = save_result["data_id"]

        all_data = []
        chunk_index = 0
        has_more = True

        while has_more:
            result = load_raw_data(data_id, chunk_index=chunk_index, chunk_size=100)
            all_data.extend(result["data"])
            has_more = result["chunk_info"]["has_more"]
            chunk_index += 1

        assert len(all_data) == len(large_data)

    def test_load_nonexistent_data(self, temp_data_dir):
        """존재하지 않는 데이터 로드 시 에러."""
        result = load_raw_data("nonexistent_id")

        assert "error" in result

    def test_load_invalid_chunk_index(self, sample_data, temp_data_dir):
        """잘못된 청크 인덱스."""
        save_result = save_raw_data(sample_data)
        data_id = save_result["data_id"]

        result = load_raw_data(data_id, chunk_index=1000)

        assert "error" in result


# =============================================================================
# list_saved_data 테스트
# =============================================================================


class TestListSavedData:
    """list_saved_data 함수 테스트."""

    def test_list_empty(self, temp_data_dir):
        """빈 디렉토리."""
        result = list_saved_data()
        assert result == []

    def test_list_after_save(self, sample_data, temp_data_dir):
        """저장 후 목록 조회."""
        save_raw_data(sample_data)

        result = list_saved_data()

        assert len(result) == 1
        assert "data_id" in result[0]
        assert "tbl_nm" in result[0]
        assert result[0]["record_count"] == len(sample_data)

    def test_list_multiple_files(self, sample_data, temp_data_dir):
        """여러 파일 저장 후 목록."""
        save_raw_data(sample_data, data_id="test_1")
        save_raw_data(sample_data, data_id="test_2")
        save_raw_data(sample_data, data_id="test_3")

        result = list_saved_data()

        assert len(result) == 3


# =============================================================================
# format_data_for_llm 통합 테스트
# =============================================================================


class TestFormatDataForLLMWithStorage:
    """format_data_for_llm의 파일 저장 기능 테스트."""

    def test_format_saves_raw_data(self, sample_data, temp_data_dir):
        """format_data_for_llm이 원본 데이터를 저장하는지 확인."""
        result = format_data_for_llm(sample_data, save_raw=True)

        assert "raw_data_file" in result
        assert "data_id" in result["raw_data_file"]
        assert "file_path" in result["raw_data_file"]
        assert Path(result["raw_data_file"]["file_path"]).exists()

    def test_format_without_save(self, sample_data, temp_data_dir):
        """save_raw=False일 때 파일 저장 안 함."""
        result = format_data_for_llm(sample_data, save_raw=False)

        assert "raw_data_file" not in result

    def test_format_includes_access_hint(self, sample_data, temp_data_dir):
        """접근 힌트가 포함되는지 확인."""
        result = format_data_for_llm(sample_data, save_raw=True)

        assert "access_hint" in result["raw_data_file"]
        assert "read_stored_data" in result["raw_data_file"]["access_hint"]

    def test_format_summary_plus_file(self, large_data, temp_data_dir):
        """대용량 데이터: 요약 + 파일 저장."""
        result = format_data_for_llm(large_data, max_rows=50, save_raw=True)

        # 요약은 50행 이하
        assert len(result["data_preview"]) <= 50

        # 원본은 파일에 저장
        assert result["raw_data_file"]["record_count"] == len(large_data)

        # 파일에서 전체 데이터 접근 가능
        data_id = result["raw_data_file"]["data_id"]
        loaded = load_raw_data(data_id)
        assert len(loaded["data"]) == len(large_data)

    def test_roundtrip_data_integrity(self, large_data, temp_data_dir):
        """저장 -> 로드 후 데이터 무결성 확인."""
        # 저장
        result = format_data_for_llm(large_data, save_raw=True)
        data_id = result["raw_data_file"]["data_id"]

        # 로드
        loaded = load_raw_data(data_id)

        # 무결성 검증
        assert len(loaded["data"]) == len(large_data)

        # 첫 레코드 비교
        original_first = large_data[0]
        loaded_first = loaded["data"][0]
        assert original_first["TBL_ID"] == loaded_first["TBL_ID"]
        assert original_first["PRD_DE"] == loaded_first["PRD_DE"]


# =============================================================================
# 성능 테스트
# =============================================================================


class TestPerformance:
    """성능 관련 테스트."""

    def test_large_data_save_performance(self, temp_data_dir):
        """대용량 데이터 저장 성능."""
        import time

        # 10,000건 데이터 생성
        data = [
            {"TBL_ID": "PERF", "PRD_DE": str(i), "DT": str(i * 100)}
            for i in range(10000)
        ]

        start = time.time()
        save_raw_data(data)
        elapsed = time.time() - start

        # 10,000건 저장이 5초 이내
        assert elapsed < 5.0

    def test_chunk_load_performance(self, temp_data_dir):
        """청크 로드 성능."""
        import time

        # 10,000건 데이터 생성 및 저장
        data = [
            {"TBL_ID": "PERF", "PRD_DE": str(i), "DT": str(i * 100)}
            for i in range(10000)
        ]
        result = save_raw_data(data)
        data_id = result["data_id"]

        # 청크 로드 시간 측정
        start = time.time()
        load_raw_data(data_id, chunk_index=0, chunk_size=100)
        elapsed = time.time() - start

        # 청크 로드가 1초 이내
        assert elapsed < 1.0
