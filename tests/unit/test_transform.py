"""
kosis_tools.transform 모듈 유닛 테스트.

테스트 범위:
    - KosisTransformer: DataFrame 변환, 필터링, 피벗
    - Fields: 필드 상수
    - 편의 함수: to_dataframe, pivot_data, filter_data, get_llm_context
"""

import pytest
import pandas as pd

from kosis_tools.transform import (
    KosisTransformer,
    Fields,
    to_dataframe,
    pivot_data,
    filter_data,
    get_llm_context,
)


@pytest.fixture
def sample_data() -> list[dict]:
    """테스트용 KOSIS 응답 데이터 샘플."""
    return [
        {"PRD_DE": "2020", "C1_NM": "전국", "DT": "50000000", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "서울", "DT": "10000000", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "부산", "DT": "3500000", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "전국", "DT": "49500000", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "서울", "DT": "9800000", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "부산", "DT": "3400000", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "전국", "DT": "49000000", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "서울", "DT": "9600000", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "부산", "DT": "3300000", "ITM_NM": "인구수"},
    ]


@pytest.fixture
def transformer(sample_data: list[dict]) -> KosisTransformer:
    """테스트용 KosisTransformer 인스턴스."""
    return KosisTransformer(sample_data)


class TestFields:
    """Fields 상수 테스트."""

    def test_field_constants(self):
        """필드 상수 확인."""
        assert Fields.PERIOD == "PRD_DE"
        assert Fields.VALUE == "DT"
        assert Fields.REGION == "C1_NM"
        assert Fields.ITM_NM == "ITM_NM"


class TestKosisTransformerBasic:
    """KosisTransformer 기본 기능 테스트."""

    def test_init(self, sample_data: list[dict]):
        """초기화 테스트."""
        tx = KosisTransformer(sample_data)
        assert tx.raw_data == sample_data
        assert tx._df is None  # 지연 생성 확인

    def test_df_property(self, transformer: KosisTransformer):
        """DataFrame 속성 테스트."""
        df = transformer.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 9

    def test_to_dataframe(self, transformer: KosisTransformer):
        """DataFrame 변환 테스트."""
        df = transformer.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 9
        # 숫자 변환 확인
        assert df["DT"].dtype in ["float64", "int64"]

    def test_dt_numeric_conversion(self, transformer: KosisTransformer):
        """DT 필드 숫자 변환 테스트."""
        df = transformer.to_dataframe()
        assert df["DT"].iloc[0] == 50000000.0

    def test_to_records(self, transformer: KosisTransformer):
        """레코드 리스트 반환 테스트."""
        records = transformer.to_records()
        assert isinstance(records, list)
        assert len(records) == 9


class TestKosisTransformerFilter:
    """KosisTransformer 필터링 테스트."""

    def test_filter_by_single(self, transformer: KosisTransformer):
        """단일 값 필터링."""
        filtered = transformer.filter_by("C1_NM", "서울")
        assert len(filtered.df) == 3

    def test_filter_by_multiple(self, transformer: KosisTransformer):
        """다중 값 필터링."""
        filtered = transformer.filter_by("C1_NM", ["서울", "부산"])
        assert len(filtered.df) == 6

    def test_filter_chaining(self, transformer: KosisTransformer):
        """필터 체이닝."""
        filtered = transformer.filter_by("PRD_DE", "2020").filter_by("C1_NM", "서울")
        assert len(filtered.df) == 1

    def test_filter_period(self, transformer: KosisTransformer):
        """기간 필터링."""
        filtered = transformer.filter_period(start="2021", end="2022")
        assert len(filtered.df) == 6
        periods = filtered.get_unique_values("PRD_DE")
        assert "2020" not in periods
        assert "2021" in periods
        assert "2022" in periods

    def test_filter_custom(self, transformer: KosisTransformer):
        """커스텀 조건 필터링."""
        filtered = transformer.filter_custom(lambda df: df["DT"] >= 10000000)
        # 전국(3: 50M, 49.5M, 49M) + 서울 2020만(10M) = 4건
        # (서울 2021: 9.8M, 서울 2022: 9.6M은 미만)
        assert len(filtered.df) == 4

    def test_select_columns(self, transformer: KosisTransformer):
        """컬럼 선택."""
        selected = transformer.select_columns(["PRD_DE", "DT"])
        assert list(selected.df.columns) == ["PRD_DE", "DT"]


class TestKosisTransformerPivot:
    """KosisTransformer 피벗 테스트."""

    def test_pivot(self, transformer: KosisTransformer):
        """피벗 테이블 생성."""
        pivot = transformer.pivot(index="C1_NM", columns="PRD_DE", values="DT")
        assert isinstance(pivot, pd.DataFrame)
        assert len(pivot) == 3  # 3개 지역
        assert "2020" in pivot.columns
        assert "2021" in pivot.columns
        assert "2022" in pivot.columns


class TestKosisTransformerGroupby:
    """KosisTransformer 그룹 집계 테스트."""

    def test_groupby_default(self, transformer: KosisTransformer):
        """기본 그룹 집계 (합계)."""
        grouped = transformer.groupby("C1_NM")
        assert len(grouped) == 3
        # 전국 3년 합계 확인
        nation = grouped[grouped["C1_NM"] == "전국"]["DT"].iloc[0]
        assert nation == 50000000 + 49500000 + 49000000

    def test_groupby_custom(self, transformer: KosisTransformer):
        """커스텀 집계 함수."""
        grouped = transformer.groupby("PRD_DE", {"DT": "mean"})
        assert len(grouped) == 3


class TestKosisTransformerRank:
    """KosisTransformer 순위 테스트."""

    def test_rank_by(self, transformer: KosisTransformer):
        """순위 매기기."""
        ranked = transformer.rank_by("DT", top_n=3)
        assert "rank" in ranked.columns
        assert len(ranked) == 3
        # 가장 큰 값이 1위
        assert ranked.iloc[0]["DT"] == 50000000

    def test_rank_by_group(self, transformer: KosisTransformer):
        """그룹 내 순위."""
        ranked = transformer.rank_by("DT", group_field="PRD_DE", top_n=2)
        # 각 연도별 상위 2개
        assert len(ranked) == 6


class TestKosisTransformerGrowth:
    """KosisTransformer 성장률 테스트."""

    def test_calculate_growth(self, transformer: KosisTransformer):
        """성장률 계산."""
        growth = transformer.filter_by("C1_NM", "전국").calculate_growth()
        assert "growth_rate" in growth.columns
        assert "growth_pct" in growth.columns


class TestKosisTransformerStats:
    """KosisTransformer 통계 테스트."""

    def test_get_summary_stats(self, transformer: KosisTransformer):
        """요약 통계."""
        stats = transformer.get_summary_stats()
        assert "mean" in stats.columns
        assert "std" in stats.columns
        assert "min" in stats.columns
        assert "max" in stats.columns

    def test_get_unique_values(self, transformer: KosisTransformer):
        """고유값 조회."""
        regions = transformer.get_unique_values("C1_NM")
        assert len(regions) == 3
        assert "전국" in regions

    def test_get_field_info(self, transformer: KosisTransformer):
        """필드 정보 조회."""
        info = transformer.get_field_info()
        assert "PRD_DE" in info
        assert info["PRD_DE"]["nunique"] == 3


class TestKosisTransformerLLMContext:
    """KosisTransformer LLM 컨텍스트 테스트."""

    def test_get_llm_context(self, transformer: KosisTransformer):
        """LLM 컨텍스트 생성."""
        context = transformer.get_llm_context()
        assert "# KOSIS 데이터 컨텍스트" in context
        assert "기본 정보" in context
        assert "필드 정보" in context


class TestConvenienceFunctions:
    """편의 함수 테스트."""

    def test_to_dataframe_func(self, sample_data: list[dict]):
        """to_dataframe 함수."""
        df = to_dataframe(sample_data)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 9

    def test_pivot_data_func(self, sample_data: list[dict]):
        """pivot_data 함수."""
        pivot = pivot_data(sample_data, index="C1_NM", columns="PRD_DE")
        assert isinstance(pivot, pd.DataFrame)
        assert len(pivot) == 3

    def test_filter_data_func(self, sample_data: list[dict]):
        """filter_data 함수."""
        filtered = filter_data(sample_data, PRD_DE="2020")
        assert len(filtered) == 3

    def test_filter_data_multiple(self, sample_data: list[dict]):
        """filter_data 다중 필터."""
        filtered = filter_data(sample_data, PRD_DE="2020", C1_NM=["서울", "부산"])
        assert len(filtered) == 2

    def test_get_llm_context_func(self, sample_data: list[dict]):
        """get_llm_context 함수."""
        context = get_llm_context(sample_data)
        assert isinstance(context, str)
        assert "# KOSIS 데이터 컨텍스트" in context
