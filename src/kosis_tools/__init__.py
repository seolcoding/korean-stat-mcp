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
from .big_data import StatisticsBigData, SdmxType, BigDataFormat
from .key_indicators import (
    KeyIndicators,
    IndicatorEndpoint,
    IndicatorExplanation,
    IndicatorListItem,
    IndicatorSearchResult,
    IndicatorDetailData,
)

# Optional backend — only loaded if the extra is installed
# pip install korean-stat-mcp[postgres]  → asyncpg
try:
    from .database import DatabasePool, DatabaseError, check_database_health  # noqa: F401

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

from .cache_builder import CacheBuilder
from .metadata_fetcher import AsyncMetadataFetcher
from .metadata_enricher import MetadataEnricher
from .metadata_models import StatisticsTable, TablesFile, DataSource
from .report_tools import (
    # Layer 1: DISCOVER
    search_tables,
    browse_categories,
    get_table_meta,
    get_available_values,
    # Layer 2: FETCH
    fetch_data,
    filter_data as filter_data_tool,
    aggregate_data,
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
    # Report Tools - Layer 1: DISCOVER
    "search_tables",
    "browse_categories",
    "get_table_meta",
    "get_available_values",
    # Report Tools - Layer 2: FETCH
    "fetch_data",
    "filter_data_tool",
    "aggregate_data",
    # Cache Builder
    "CacheBuilder",
    "AsyncMetadataFetcher",
    "MetadataEnricher",
    "StatisticsTable",
    "TablesFile",
    "DataSource",
    # Optional backend availability flags
    "POSTGRES_AVAILABLE",
]

if POSTGRES_AVAILABLE:
    __all__.extend(
        [
            "DatabasePool",
            "DatabaseError",
            "check_database_health",
        ]
    )
