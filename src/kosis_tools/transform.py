"""
KOSIS 데이터 변환/집계 모듈.

이 모듈은 KOSIS API 응답 데이터를 다양한 형태로 변환하고 집계합니다.
Pandas DataFrame을 기반으로 피벗, 필터링, 집계 등의 기능을 제공합니다.

주요 기능:
    - DataFrame 변환: API 응답을 DataFrame으로 변환
    - 피벗 테이블: 행/열 기준으로 데이터 재구성
    - 필터링: 조건에 맞는 데이터 추출
    - 집계: 그룹별 합계, 평균, 최대/최소 등
    - 컨텍스트 생성: LLM용 데이터 요약 텍스트 생성

Example:
    >>> from kosis_tools import StatisticsData
    >>> from kosis_tools.transform import KosisTransformer
    >>>
    >>> data_client = StatisticsData()
    >>> records = data_client.get_data("101", "DT_1B040A3", "2020", "2023")
    >>>
    >>> tx = KosisTransformer(records)
    >>> df = tx.to_dataframe()
    >>> pivot = tx.pivot(index="C1_NM", columns="PRD_DE", values="DT")
    >>> summary = tx.get_llm_context()

Note:
    - 모든 변환 메서드는 원본 데이터를 수정하지 않습니다.
    - DataFrame 작업은 pandas 라이브러리를 사용합니다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


# 자주 사용하는 KOSIS 필드명 상수
class Fields:
    """
    KOSIS API 응답의 주요 필드명 상수.

    API 응답에서 자주 사용하는 필드를 상수로 정의합니다.
    오타를 방지하고 자동완성을 활용할 수 있습니다.

    Example:
        >>> from kosis_tools.transform import Fields
        >>> tx.filter_by(Fields.REGION, "서울특별시")
    """

    # 기본 정보
    ORG_ID = "ORG_ID"          # 기관 ID
    ORG_NM = "ORG_NM"          # 기관명
    TBL_ID = "TBL_ID"          # 테이블 ID
    TBL_NM = "TBL_NM"          # 테이블명

    # 기간
    PERIOD = "PRD_DE"          # 기간 (연도/월 등)
    PERIOD_TYPE = "PRD_SE"     # 주기 구분

    # 분류항목
    C1 = "C1"                  # 분류1 코드
    C1_NM = "C1_NM"            # 분류1 이름
    REGION = "C1_NM"           # 지역 (보통 C1에 해당)
    C2 = "C2"                  # 분류2 코드
    C2_NM = "C2_NM"            # 분류2 이름
    C3 = "C3"                  # 분류3 코드
    C3_NM = "C3_NM"            # 분류3 이름

    # 항목
    ITM_ID = "ITM_ID"          # 항목 ID
    ITM_NM = "ITM_NM"          # 항목명

    # 데이터
    VALUE = "DT"               # 데이터 값
    UNIT = "UNIT_NM"           # 단위


class FieldLabels:
    """
    KOSIS 필드의 한국어 라벨 매핑.

    API 응답의 기술적 필드명을 사용자 친화적인 한국어로 변환합니다.
    컨텍스트(데이터 유형)에 따라 다른 라벨을 사용할 수 있습니다.

    Example:
        >>> from kosis_tools.transform import FieldLabels
        >>> FieldLabels.get_label("PRD_DE")  # "기간"
        >>> FieldLabels.get_label("DT", context="population")  # "인구수"
    """

    # 기본 한국어 라벨
    DEFAULT_LABELS: Dict[str, str] = {
        # 기간 관련
        "PRD_DE": "기간",
        "PRD_SE": "주기",

        # 분류 관련
        "C1": "분류1 코드",
        "C1_NM": "분류",
        "C2": "분류2 코드",
        "C2_NM": "분류2",
        "C3": "분류3 코드",
        "C3_NM": "분류3",

        # 항목 관련
        "ITM_ID": "항목코드",
        "ITM_NM": "항목",

        # 데이터 관련
        "DT": "값",
        "UNIT_NM": "단위",

        # 기관/통계표 관련
        "ORG_ID": "기관코드",
        "ORG_NM": "기관명",
        "TBL_ID": "통계표코드",
        "TBL_NM": "통계표명",
    }

    # 컨텍스트별 라벨 오버라이드
    CONTEXT_LABELS: Dict[str, Dict[str, str]] = {
        "population": {
            "C1_NM": "지역",
            "DT": "인구수",
            "UNIT_NM": "단위",
        },
        "price": {
            "C1_NM": "품목",
            "DT": "지수",
        },
        "employment": {
            "C1_NM": "지역",
            "DT": "고용률",
        },
        "trade": {
            "C1_NM": "품목",
            "DT": "금액",
        },
        "regional": {
            "C1_NM": "지역",
        },
    }

    @classmethod
    def get_label(cls, field: str, context: Optional[str] = None) -> str:
        """
        필드의 한국어 라벨을 반환합니다.

        Args:
            field: KOSIS API 필드명 (예: "PRD_DE", "C1_NM", "DT")
            context: 데이터 컨텍스트 (예: "population", "price")

        Returns:
            한국어 라벨. 매핑이 없으면 원본 필드명 반환.
        """
        # 컨텍스트별 라벨 확인
        if context and context in cls.CONTEXT_LABELS:
            if field in cls.CONTEXT_LABELS[context]:
                return cls.CONTEXT_LABELS[context][field]

        # 기본 라벨 반환
        return cls.DEFAULT_LABELS.get(field, field)

    @classmethod
    def get_all_labels(cls, fields: List[str], context: Optional[str] = None) -> Dict[str, str]:
        """
        여러 필드의 한국어 라벨을 딕셔너리로 반환합니다.

        Args:
            fields: 필드명 리스트
            context: 데이터 컨텍스트

        Returns:
            {필드명: 한국어라벨} 딕셔너리
        """
        return {field: cls.get_label(field, context) for field in fields}

    @classmethod
    def rename_columns(cls, df: pd.DataFrame, context: Optional[str] = None) -> pd.DataFrame:
        """
        DataFrame의 컬럼명을 한국어로 변환합니다.

        Args:
            df: 원본 DataFrame
            context: 데이터 컨텍스트

        Returns:
            컬럼명이 한국어로 변환된 새 DataFrame
        """
        rename_map = cls.get_all_labels(list(df.columns), context)
        return df.rename(columns=rename_map)

    @classmethod
    def detect_context(cls, data: Union[List[Dict], pd.DataFrame], query: Optional[str] = None) -> Optional[str]:
        """
        데이터 또는 쿼리에서 컨텍스트를 자동 감지합니다.

        Args:
            data: KOSIS 데이터 (레코드 리스트 또는 DataFrame)
            query: 사용자 쿼리 문자열

        Returns:
            감지된 컨텍스트 (예: "population", "price") 또는 None
        """
        # 쿼리 기반 감지
        if query:
            query_lower = query.lower()
            if any(kw in query_lower for kw in ["인구", "주민", "거주자", "세대"]):
                return "population"
            if any(kw in query_lower for kw in ["물가", "가격", "지수", "cpi"]):
                return "price"
            if any(kw in query_lower for kw in ["고용", "실업", "취업", "일자리"]):
                return "employment"
            if any(kw in query_lower for kw in ["수출", "수입", "무역", "교역"]):
                return "trade"

        # 데이터 기반 감지 (ITM_NM 또는 TBL_NM 확인)
        if isinstance(data, pd.DataFrame):
            if "ITM_NM" in data.columns and len(data) > 0:
                itm_nm = str(data["ITM_NM"].iloc[0]).lower()
                if any(kw in itm_nm for kw in ["인구", "주민"]):
                    return "population"
        elif isinstance(data, list) and len(data) > 0:
            itm_nm = str(data[0].get("ITM_NM", "")).lower()
            if any(kw in itm_nm for kw in ["인구", "주민"]):
                return "population"

        return None


class KosisTransformer:
    """
    KOSIS 데이터 변환 클래스.

    KOSIS API 응답 데이터를 다양한 형태로 변환하고 분석합니다.
    내부적으로 pandas DataFrame을 사용하여 효율적인 데이터 처리를 수행합니다.

    Attributes:
        raw_data: 원본 API 응답 데이터 (레코드 리스트)
        df: pandas DataFrame (지연 생성)

    Args:
        data: KOSIS API 응답 데이터 (레코드 리스트)

    Example:
        >>> tx = KosisTransformer(records)
        >>> df = tx.to_dataframe()
        >>> print(df.head())
    """

    def __init__(self, data: List[Dict[str, Any]]):
        """
        변환기를 초기화합니다.

        Args:
            data: KOSIS API 응답 데이터. 각 레코드는 딕셔너리 형태.
        """
        self.raw_data = data
        self._df: Optional[pd.DataFrame] = None

    @property
    def df(self) -> pd.DataFrame:
        """
        데이터를 pandas DataFrame으로 반환합니다.

        DataFrame은 첫 접근 시 생성되며 이후 캐시됩니다.
        DT(값) 필드는 자동으로 숫자로 변환됩니다.

        Returns:
            pandas DataFrame
        """
        if self._df is None:
            self._df = self._create_dataframe()
        return self._df

    def _create_dataframe(self) -> pd.DataFrame:
        """내부: DataFrame 생성 및 타입 변환"""
        df = pd.DataFrame(self.raw_data)

        # DT 필드 숫자 변환
        if Fields.VALUE in df.columns:
            df[Fields.VALUE] = pd.to_numeric(
                df[Fields.VALUE].replace(["-", "", None], pd.NA),
                errors="coerce"
            )

        return df

    def to_dataframe(self) -> pd.DataFrame:
        """
        데이터를 pandas DataFrame으로 변환합니다.

        Returns:
            변환된 DataFrame (복사본)

        Example:
            >>> tx = KosisTransformer(records)
            >>> df = tx.to_dataframe()
            >>> print(df.columns.tolist())
            ['TBL_ID', 'ORG_ID', 'PRD_DE', 'C1', 'C1_NM', 'DT', ...]
        """
        return self.df.copy()

    def filter_by(
        self,
        field: str,
        values: Union[str, List[str]],
    ) -> "KosisTransformer":
        """
        특정 필드 값으로 데이터를 필터링합니다.

        원본은 수정되지 않으며 새 KosisTransformer 인스턴스를 반환합니다.
        체이닝 방식으로 여러 필터를 연속 적용할 수 있습니다.

        Args:
            field: 필터링할 필드명
            values: 허용할 값 (단일 값 또는 값 리스트)

        Returns:
            필터링된 새 KosisTransformer 인스턴스

        Example:
            >>> tx = KosisTransformer(records)
            >>> # 단일 값 필터
            >>> seoul = tx.filter_by(Fields.REGION, "서울특별시")
            >>> # 다중 값 필터
            >>> metros = tx.filter_by(Fields.REGION, ["서울특별시", "부산광역시"])
            >>> # 체이닝
            >>> result = tx.filter_by("PRD_DE", "2023").filter_by("C1_NM", "전국")
        """
        if isinstance(values, str):
            values = [values]

        filtered = self.df[self.df[field].isin(values)]
        return KosisTransformer(filtered.to_dict("records"))

    def filter_period(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> "KosisTransformer":
        """
        기간으로 데이터를 필터링합니다.

        Args:
            start: 시작 기간 (포함). None이면 제한 없음.
            end: 종료 기간 (포함). None이면 제한 없음.

        Returns:
            필터링된 새 KosisTransformer 인스턴스

        Example:
            >>> tx = KosisTransformer(records)
            >>> recent = tx.filter_period(start="2020", end="2023")
        """
        df = self.df.copy()

        if Fields.PERIOD not in df.columns:
            return self

        if start is not None:
            df = df[df[Fields.PERIOD] >= start]
        if end is not None:
            df = df[df[Fields.PERIOD] <= end]

        return KosisTransformer(df.to_dict("records"))

    def filter_custom(
        self,
        condition: Callable[[pd.DataFrame], pd.Series],
    ) -> "KosisTransformer":
        """
        커스텀 조건으로 데이터를 필터링합니다.

        Args:
            condition: DataFrame을 받아 불리언 Series를 반환하는 함수

        Returns:
            필터링된 새 KosisTransformer 인스턴스

        Example:
            >>> tx = KosisTransformer(records)
            >>> # 값이 1000 이상인 데이터만
            >>> large = tx.filter_custom(lambda df: df["DT"] >= 1000)
            >>> # 특정 문자열 포함
            >>> contains = tx.filter_custom(lambda df: df["C1_NM"].str.contains("시"))
        """
        filtered = self.df[condition(self.df)]
        return KosisTransformer(filtered.to_dict("records"))

    def select_columns(self, columns: List[str]) -> "KosisTransformer":
        """
        특정 컬럼만 선택합니다.

        Args:
            columns: 선택할 컬럼명 리스트

        Returns:
            선택된 컬럼만 포함하는 새 KosisTransformer 인스턴스

        Example:
            >>> tx = KosisTransformer(records)
            >>> simple = tx.select_columns(["PRD_DE", "C1_NM", "DT"])
        """
        available = [c for c in columns if c in self.df.columns]
        selected = self.df[available]
        return KosisTransformer(selected.to_dict("records"))

    def pivot(
        self,
        index: Union[str, List[str]],
        columns: str,
        values: str = "DT",
        aggfunc: str = "sum",
        fill_value: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        피벗 테이블을 생성합니다.

        행(index)과 열(columns)을 기준으로 데이터를 재구성합니다.
        중복 값이 있으면 지정한 집계 함수로 처리합니다.

        Args:
            index: 행 인덱스 필드(들)
            columns: 열 필드
            values: 값 필드 (기본: "DT")
            aggfunc: 집계 함수 ("sum", "mean", "count", "first", "last")
            fill_value: 결측치 대체 값 (None이면 NaN 유지)

        Returns:
            피벗된 DataFrame

        Example:
            >>> tx = KosisTransformer(records)
            >>> # 지역(행) x 연도(열) 피벗
            >>> pivot = tx.pivot(
            ...     index="C1_NM",
            ...     columns="PRD_DE",
            ...     values="DT"
            ... )
            >>> print(pivot)
                          2020      2021      2022      2023
            C1_NM
            전국      51829023  51738071  51439038  51325329
            서울특별시  9411453   9509458   9428372   9386934
            ...
        """
        pivot_df = pd.pivot_table(
            self.df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
            fill_value=fill_value,
        )

        return pivot_df

    def groupby(
        self,
        by: Union[str, List[str]],
        aggfunc: Dict[str, Union[str, Callable]] = None,
    ) -> pd.DataFrame:
        """
        그룹별 집계를 수행합니다.

        Args:
            by: 그룹핑 기준 필드(들)
            aggfunc: 집계 함수 딕셔너리. 키는 컬럼명, 값은 집계 함수.
                    None이면 {"DT": "sum"} 사용.

        Returns:
            집계된 DataFrame

        Example:
            >>> tx = KosisTransformer(records)
            >>> # 지역별 합계
            >>> by_region = tx.groupby("C1_NM")
            >>> # 연도별 다중 집계
            >>> by_year = tx.groupby("PRD_DE", {
            ...     "DT": ["sum", "mean", "count"]
            ... })
        """
        if aggfunc is None:
            aggfunc = {Fields.VALUE: "sum"}

        grouped = self.df.groupby(by, as_index=False).agg(aggfunc)

        # 다중 레벨 컬럼 평탄화
        if isinstance(grouped.columns, pd.MultiIndex):
            grouped.columns = [
                "_".join(col).strip("_") for col in grouped.columns.values
            ]

        return grouped

    def rank_by(
        self,
        value_field: str = "DT",
        group_field: Optional[str] = None,
        ascending: bool = False,
        top_n: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        값 기준으로 순위를 매깁니다.

        Args:
            value_field: 순위 기준 필드
            group_field: 그룹 내 순위 필드 (None이면 전체 순위)
            ascending: True면 오름차순 (작은 값이 1위)
            top_n: 상위 N개만 반환 (None이면 전체)

        Returns:
            순위 컬럼이 추가된 DataFrame

        Example:
            >>> tx = KosisTransformer(records)
            >>> # 전체 순위
            >>> ranked = tx.rank_by("DT", top_n=10)
            >>> # 연도별 순위
            >>> yearly_rank = tx.rank_by("DT", group_field="PRD_DE", top_n=5)
        """
        df = self.df.copy()

        if group_field:
            df["rank"] = df.groupby(group_field)[value_field].rank(
                ascending=ascending, method="min"
            )
        else:
            df["rank"] = df[value_field].rank(ascending=ascending, method="min")

        df = df.sort_values("rank")

        if top_n is not None:
            if group_field:
                df = df[df["rank"] <= top_n]
            else:
                df = df.head(top_n)

        return df

    def calculate_growth(
        self,
        value_field: str = "DT",
        period_field: str = "PRD_DE",
        group_field: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        기간별 성장률을 계산합니다.

        Args:
            value_field: 값 필드
            period_field: 기간 필드
            group_field: 그룹 필드 (None이면 전체 데이터 대상)

        Returns:
            성장률 컬럼(growth_rate, growth_pct)이 추가된 DataFrame

        Example:
            >>> tx = KosisTransformer(records)
            >>> with_growth = tx.calculate_growth()
            >>> # 지역별 성장률
            >>> regional_growth = tx.calculate_growth(group_field="C1_NM")
        """
        df = self.df.copy().sort_values(period_field)

        if group_field:
            df["prev_value"] = df.groupby(group_field)[value_field].shift(1)
        else:
            df["prev_value"] = df[value_field].shift(1)

        df["growth_rate"] = (df[value_field] - df["prev_value"]) / df["prev_value"]
        df["growth_pct"] = df["growth_rate"] * 100

        df = df.drop(columns=["prev_value"])

        return df

    def get_summary_stats(
        self,
        value_field: str = "DT",
        group_field: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        요약 통계를 계산합니다.

        Args:
            value_field: 통계 계산 대상 필드
            group_field: 그룹 필드 (None이면 전체 통계)

        Returns:
            요약 통계 DataFrame (count, mean, std, min, 25%, 50%, 75%, max)

        Example:
            >>> tx = KosisTransformer(records)
            >>> stats = tx.get_summary_stats()
            >>> # 지역별 통계
            >>> regional_stats = tx.get_summary_stats(group_field="C1_NM")
        """
        if group_field:
            stats = self.df.groupby(group_field)[value_field].describe()
        else:
            stats = self.df[value_field].describe().to_frame().T

        return stats

    def to_records(self) -> List[Dict[str, Any]]:
        """
        데이터를 레코드 리스트로 반환합니다.

        Returns:
            딕셔너리 리스트 형태의 데이터
        """
        return self.df.to_dict("records")

    def get_unique_values(self, field: str) -> List[Any]:
        """
        특정 필드의 고유값 목록을 반환합니다.

        Args:
            field: 필드명

        Returns:
            고유값 리스트 (정렬됨)

        Example:
            >>> tx = KosisTransformer(records)
            >>> periods = tx.get_unique_values("PRD_DE")
            >>> regions = tx.get_unique_values("C1_NM")
        """
        if field not in self.df.columns:
            return []
        return sorted(self.df[field].dropna().unique().tolist())

    def get_field_info(self) -> Dict[str, Dict[str, Any]]:
        """
        모든 필드의 정보를 반환합니다.

        Returns:
            각 필드에 대한 정보 딕셔너리:
            {
                "필드명": {
                    "dtype": 데이터 타입,
                    "nunique": 고유값 개수,
                    "null_count": 결측치 개수,
                    "sample_values": 샘플 값 (최대 5개)
                }
            }
        """
        info = {}
        for col in self.df.columns:
            info[col] = {
                "dtype": str(self.df[col].dtype),
                "nunique": self.df[col].nunique(),
                "null_count": self.df[col].isnull().sum(),
                "sample_values": self.df[col].dropna().head(5).tolist(),
            }
        return info

    def get_llm_context(
        self,
        include_sample: bool = True,
        sample_size: int = 5,
        include_stats: bool = True,
    ) -> str:
        """
        LLM에 제공할 데이터 컨텍스트 텍스트를 생성합니다.

        데이터의 구조, 필드 정보, 요약 통계 등을 포함한 텍스트를 생성하여
        LLM이 데이터를 이해하고 분석할 수 있도록 합니다.

        Args:
            include_sample: 샘플 데이터 포함 여부
            sample_size: 샘플 데이터 개수
            include_stats: 요약 통계 포함 여부

        Returns:
            LLM 컨텍스트 텍스트

        Example:
            >>> tx = KosisTransformer(records)
            >>> context = tx.get_llm_context()
            >>> print(context)
            # KOSIS 데이터 컨텍스트

            ## 기본 정보
            - 레코드 수: 1,234
            - 컬럼 수: 12
            ...
        """
        lines = ["# KOSIS 데이터 컨텍스트", ""]

        # 기본 정보
        lines.append("## 기본 정보")
        lines.append(f"- 레코드 수: {len(self.df):,}")
        lines.append(f"- 컬럼 수: {len(self.df.columns)}")

        # 테이블 정보
        if Fields.TBL_NM in self.df.columns:
            tbl_nm = self.df[Fields.TBL_NM].iloc[0] if len(self.df) > 0 else "N/A"
            lines.append(f"- 테이블명: {tbl_nm}")

        if Fields.ORG_NM in self.df.columns:
            org_nm = self.df[Fields.ORG_NM].iloc[0] if len(self.df) > 0 else "N/A"
            lines.append(f"- 기관명: {org_nm}")

        lines.append("")

        # 필드 정보
        lines.append("## 필드 정보")
        field_info = self.get_field_info()
        for field, info in field_info.items():
            lines.append(f"- **{field}**: {info['dtype']}, {info['nunique']}개 고유값")

        lines.append("")

        # 차원 정보
        lines.append("## 데이터 차원")
        dimensions = []

        if Fields.PERIOD in self.df.columns:
            periods = self.get_unique_values(Fields.PERIOD)
            dimensions.append(f"- 기간: {len(periods)}개 ({periods[0]} ~ {periods[-1] if periods else 'N/A'})")

        for c_field, c_name in [
            (Fields.C1_NM, "분류1"),
            (Fields.C2_NM, "분류2"),
            (Fields.C3_NM, "분류3"),
        ]:
            if c_field in self.df.columns:
                values = self.get_unique_values(c_field)
                if values:
                    sample = ", ".join(values[:5])
                    if len(values) > 5:
                        sample += f" 외 {len(values)-5}개"
                    dimensions.append(f"- {c_name}: {len(values)}개 ({sample})")

        if Fields.ITM_NM in self.df.columns:
            items = self.get_unique_values(Fields.ITM_NM)
            if items:
                sample = ", ".join(items[:5])
                if len(items) > 5:
                    sample += f" 외 {len(items)-5}개"
                dimensions.append(f"- 항목: {len(items)}개 ({sample})")

        lines.extend(dimensions)
        lines.append("")

        # 요약 통계
        if include_stats and Fields.VALUE in self.df.columns:
            lines.append("## 값(DT) 요약 통계")
            stats = self.df[Fields.VALUE].describe()
            lines.append(f"- 개수: {int(stats['count']):,}")
            lines.append(f"- 평균: {stats['mean']:,.2f}")
            lines.append(f"- 표준편차: {stats['std']:,.2f}")
            lines.append(f"- 최소: {stats['min']:,.2f}")
            lines.append(f"- 최대: {stats['max']:,.2f}")
            lines.append("")

        # 샘플 데이터
        if include_sample:
            lines.append("## 샘플 데이터")
            lines.append("```")
            sample_df = self.df.head(sample_size)
            # 주요 컬럼만 선택
            display_cols = [c for c in [
                Fields.PERIOD, Fields.C1_NM, Fields.C2_NM,
                Fields.ITM_NM, Fields.VALUE, Fields.UNIT
            ] if c in sample_df.columns]
            if display_cols:
                lines.append(sample_df[display_cols].to_string(index=False))
            else:
                lines.append(sample_df.to_string(index=False))
            lines.append("```")

        return "\n".join(lines)


def to_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    API 응답 데이터를 DataFrame으로 변환하는 편의 함수.

    Args:
        data: KOSIS API 응답 데이터 (레코드 리스트)

    Returns:
        pandas DataFrame

    Example:
        >>> from kosis_tools.transform import to_dataframe
        >>> df = to_dataframe(records)
    """
    return KosisTransformer(data).to_dataframe()


def pivot_data(
    data: List[Dict[str, Any]],
    index: str,
    columns: str,
    values: str = "DT",
) -> pd.DataFrame:
    """
    피벗 테이블을 생성하는 편의 함수.

    Args:
        data: KOSIS API 응답 데이터
        index: 행 인덱스 필드
        columns: 열 필드
        values: 값 필드

    Returns:
        피벗된 DataFrame

    Example:
        >>> from kosis_tools.transform import pivot_data
        >>> pivot = pivot_data(records, index="C1_NM", columns="PRD_DE")
    """
    return KosisTransformer(data).pivot(index=index, columns=columns, values=values)


def filter_data(
    data: List[Dict[str, Any]],
    **filters: Union[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    데이터를 필터링하는 편의 함수.

    Args:
        data: KOSIS API 응답 데이터
        **filters: 필터 조건 (필드명=값 또는 필드명=[값1, 값2])

    Returns:
        필터링된 레코드 리스트

    Example:
        >>> from kosis_tools.transform import filter_data
        >>> filtered = filter_data(
        ...     records,
        ...     PRD_DE="2023",
        ...     C1_NM=["서울특별시", "부산광역시"]
        ... )
    """
    tx = KosisTransformer(data)
    for field, values in filters.items():
        tx = tx.filter_by(field, values)
    return tx.to_records()


def get_llm_context(data: List[Dict[str, Any]]) -> str:
    """
    LLM 컨텍스트를 생성하는 편의 함수.

    Args:
        data: KOSIS API 응답 데이터

    Returns:
        LLM 컨텍스트 텍스트

    Example:
        >>> from kosis_tools.transform import get_llm_context
        >>> context = get_llm_context(records)
        >>> # LLM 프롬프트에 포함
        >>> prompt = f"다음 데이터를 분석해주세요:\\n\\n{context}"
    """
    return KosisTransformer(data).get_llm_context()
