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
"""

from .config import KosisConfig, load_config, Endpoints, PeriodType
from .base import KosisBaseClient, fix_malformed_json
from .search import StatisticsSearch
from .list_categories import CategoryList, OrgCode, ThemeCode
from .data import StatisticsData

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
]
