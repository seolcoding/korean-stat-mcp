"""
KOSIS Tools - Korean Statistical Information Service API Tools

이 패키지는 KOSIS OpenAPI를 래핑한 도구 모음입니다.
각 모듈은 특정 API 엔드포인트를 담당하며, MCP 서버와 통합됩니다.

Modules:
    config: API 설정 (rate limit, timeout, retry 등)
    base: 공통 베이스 클래스
    search: 통계표 검색 (statisticsList.do)
    list_categories: 카테고리 목록 (statisticsList.do)
    data: 데이터 조회 (statisticsParameterData.do)
    table_meta: 테이블 메타데이터 (statisticsMetaData.do)
    stats_explanation: 통계설명 (statisticsExplanation.do)
    kstat_metadata: k-stat 메타데이터 (statHtmlContent.do)
    transform: 데이터 변환/집계 (pandas 기반)
    visualize: 데이터 시각화 (plotly 기반, 한글 지원)
    cache_builder: 메타데이터 캐시 빌드 (비동기, 점진적)
    metadata_fetcher: 통계표 목록 비동기 수집
    metadata_enricher: 통계설명/영문명 보강
"""

from .config import KosisConfig, load_config, Endpoints, PeriodType
from .base import KosisBaseClient, fix_malformed_json
from .search import StatisticsSearch
from .list_categories import CategoryList, OrgCode, ThemeCode
from .data import StatisticsData
from .table_meta import TableMetadata
from .stats_explanation import StatsExplanation, MetaItem
from .kstat_metadata import KstatMetadata
from .big_data import StatisticsBigData, SdmxType, BigDataFormat
from .key_indicators import (
    KeyIndicators,
    IndicatorEndpoint,
    IndicatorExplanation,
    IndicatorListItem,
    IndicatorSearchResult,
    IndicatorDetailData,
)
from .transform import (
    KosisTransformer,
    Fields,
    to_dataframe,
    pivot_data,
    filter_data,
    get_llm_context,
)
from .visualize import (
    KosisVisualizer,
    quick_line,
    quick_bar,
    quick_pie,
)
from .report_generator import (
    ReportGenerator,
    UserQuery,
    create_report,
    create_llm_prompt,
    generate_html_report,
)
from .cache_builder import CacheBuilder
from .metadata_fetcher import AsyncMetadataFetcher
from .metadata_enricher import MetadataEnricher
from .metadata_models import StatisticsTable, TablesFile, DataSource
from .report_tools import (
    # 데이터 클래스
    ReportComponent,
    AnalysisResult,
    # Layer 1: DISCOVER
    search_tables,
    browse_categories,
    get_table_meta,
    get_available_values,
    # Layer 2: FETCH
    fetch_data,
    filter_data as filter_data_tool,  # transform.filter_data와 구분
    aggregate_data,
    # Layer 3: PRESENT - Visualization
    viz_line_trend,
    viz_bar_comparison,
    viz_kpi_card,
    viz_pie_composition,
    viz_heatmap,
    # Layer 3: PRESENT - Analysis
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    # Layer 3: PRESENT - Text
    text_headline,
    text_summary,
    text_insight,
    text_data_note,
    # Layer 3: PRESENT - Layout
    layout_section,
    layout_card_grid,
    layout_two_column,
    layout_highlight_box,
    layout_table,
    # Layer 3: PRESENT - Assembly
    assemble_report,
    quick_report,
)

__all__ = [
    # Config
    "KosisConfig",
    "load_config",
    "Endpoints",
    "PeriodType",
    # Base
    "KosisBaseClient",
    "fix_malformed_json",
    # Search
    "StatisticsSearch",
    # Categories
    "CategoryList",
    "OrgCode",
    "ThemeCode",
    # Data
    "StatisticsData",
    # Metadata (Phase 4)
    "TableMetadata",
    "StatsExplanation",
    "MetaItem",
    "KstatMetadata",
    # Big Data (Phase B)
    "StatisticsBigData",
    "SdmxType",
    "BigDataFormat",
    # Key Indicators (Phase C)
    "KeyIndicators",
    "IndicatorEndpoint",
    "IndicatorExplanation",
    "IndicatorListItem",
    "IndicatorSearchResult",
    "IndicatorDetailData",
    # Transform (pandas)
    "KosisTransformer",
    "Fields",
    "to_dataframe",
    "pivot_data",
    "filter_data",
    "get_llm_context",
    # Visualize (plotly)
    "KosisVisualizer",
    "quick_line",
    "quick_bar",
    "quick_pie",
    # Report Generator
    "ReportGenerator",
    "UserQuery",
    "create_report",
    "create_llm_prompt",
    "generate_html_report",
    # Report Tools - Data Classes
    "ReportComponent",
    "AnalysisResult",
    # Report Tools - Layer 1: DISCOVER
    "search_tables",
    "browse_categories",
    "get_table_meta",
    "get_available_values",
    # Report Tools - Layer 2: FETCH
    "fetch_data",
    "filter_data_tool",
    "aggregate_data",
    # Report Tools - Layer 3: PRESENT - Visualization
    "viz_line_trend",
    "viz_bar_comparison",
    "viz_kpi_card",
    "viz_pie_composition",
    "viz_heatmap",
    # Report Tools - Layer 3: PRESENT - Analysis
    "analyze_trend",
    "analyze_comparison",
    "analyze_ranking",
    "analyze_stats",
    # Report Tools - Layer 3: PRESENT - Text
    "text_headline",
    "text_summary",
    "text_insight",
    "text_data_note",
    # Report Tools - Layer 3: PRESENT - Layout
    "layout_section",
    "layout_card_grid",
    "layout_two_column",
    "layout_highlight_box",
    "layout_table",
    # Report Tools - Layer 3: PRESENT - Assembly
    "assemble_report",
    "quick_report",
    # Cache Builder
    "CacheBuilder",
    "AsyncMetadataFetcher",
    "MetadataEnricher",
    "StatisticsTable",
    "TablesFile",
    "DataSource",
]
