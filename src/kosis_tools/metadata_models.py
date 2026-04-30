"""KOSIS 메타데이터 Pydantic 모델 정의.

MCP 검색 최적화를 위한 통계표/카테고리/지표 데이터 구조.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DataSource(str, Enum):
    """데이터 출처 구분."""

    SUBJECT = "subject"  # 주제별통계
    ORGANIZATION = "organization"  # 기관별통계
    INTERNATIONAL = "international"  # 국제통계
    NORTH_KOREA = "north_korea"  # 북한통계
    REGIONAL = "regional"  # 지역통계_기관별
    LOCAL_INDICATOR = "local_indicator"  # e-지방지표


class PeriodType(str, Enum):
    """수록 주기."""

    YEAR = "Y"  # 연
    QUARTER = "Q"  # 분기
    MONTH = "M"  # 월
    HALF = "H"  # 반기


class StatisticsTable(BaseModel):
    """통계표 메타데이터.

    MCP 검색의 핵심 엔티티. API 응답 전체 필드를 저장.
    """

    # API 원본 필드 (statisticsList.do 응답)
    tbl_id: str = Field(..., description="통계표 고유 ID (예: DT_1YL20631)")
    tbl_nm: Optional[str] = Field(None, description="통계표명 (API 원본)")
    org_id: Optional[str] = Field(None, description="기관 ID (예: 101)")
    org_nm: Optional[str] = Field(None, description="기관명")
    stat_id: Optional[str] = Field(None, description="통계 ID")
    vw_cd: Optional[str] = Field(None, description="뷰 코드 (MT_ZTITLE 등)")
    list_id: Optional[str] = Field(None, description="목록 ID")

    # 수록 기간 (API 원본)
    strt_prd_de: Optional[str] = Field(None, description="수록 시작 (예: 2000)")
    end_prd_de: Optional[str] = Field(None, description="수록 종료 (예: 2024)")
    prd_se: Optional[str] = Field(None, description="수록 주기 코드 (Y/M/Q/S)")

    # 기타 API 필드
    rec_tbl_se: Optional[str] = Field(None, description="추천 통계표 여부")
    send_de: Optional[str] = Field(None, description="송신 일자")

    # 가공 필드 (검색/분류용)
    data_source: DataSource = Field(..., description="데이터 출처 구분")
    level: int = Field(..., ge=1, le=10, description="계층 레벨")
    path: str = Field(..., description="전체 경로 (예: 인구 > 인구동향조사 > ...)")
    path_ids: list[str] = Field(default_factory=list, description="경로 ID 목록")
    keywords: list[str] = Field(default_factory=list, description="검색 키워드")

    # 보강 필드 - 기본 (statisticsExplData API)
    tbl_nm_eng: Optional[str] = Field(None, description="통계표 영문명")
    stats_nm: Optional[str] = Field(None, description="조사명")
    writing_purps: Optional[str] = Field(None, description="조사목적")
    stats_period: Optional[str] = Field(None, description="조사주기")
    examin_obj_range: Optional[str] = Field(None, description="조사 대상범위")
    josa_itm: Optional[str] = Field(None, description="조사항목")
    main_term_expl: Optional[str] = Field(None, description="주요 용어해설")
    confm_no: Optional[str] = Field(None, description="승인번호")

    # 보강 필드 - 확장 (statisticsExplData API 추가 필드)
    stats_kind: Optional[str] = Field(
        None, description="작성유형 (조사통계, 가공통계 등)"
    )
    stats_end: Optional[str] = Field(
        None, description="통계종류 (지정통계, 일반통계 등)"
    )
    stats_continue: Optional[str] = Field(None, description="계속여부")
    basis_law: Optional[str] = Field(None, description="법적근거")
    examin_pd: Optional[str] = Field(None, description="조사기간")
    writing_system: Optional[str] = Field(None, description="조사체계")
    writing_tel: Optional[str] = Field(None, description="연락처")
    stats_field: Optional[str] = Field(None, description="통계(활용)분야·실태")
    examin_obj_area: Optional[str] = Field(None, description="조사 대상지역")
    josa_unit: Optional[str] = Field(None, description="조사단위 및 조사대상규모")
    apply_group: Optional[str] = Field(None, description="적용분류")
    pub_period: Optional[str] = Field(None, description="공표주기")
    pub_extent: Optional[str] = Field(None, description="공표범위")
    pub_date: Optional[str] = Field(None, description="공표시기")
    publict_mth: Optional[str] = Field(None, description="공표방법 및 URL")
    examin_trget_pd: Optional[str] = Field(
        None, description="조사대상기간 및 조사기준시점"
    )
    data_user_note: Optional[str] = Field(None, description="자료이용시 유의사항")
    data_collect_mth: Optional[str] = Field(None, description="자료 수집방법")
    examin_history: Optional[str] = Field(None, description="조사연혁")
    confm_dt: Optional[str] = Field(None, description="승인일자")

    # 보강 필드 - 검색 API (statisticsSearch.do)
    mt_atitle: Optional[str] = Field(
        None, description="분류 경로 (예: 국내통계 > 인구 > ...)"
    )
    contents: Optional[str] = Field(None, description="데이터 내용 미리보기")
    item03: Optional[str] = Field(None, description="통계 설명/출처 정보")
    tbl_view_url: Optional[str] = Field(None, description="KOSIS 웹 뷰 URL")
    stat_db_cnt: Optional[str] = Field(None, description="데이터 건수")

    # 보강 필드 - 메타자료 API (statisticsData.do getMeta)
    org_nm_eng: Optional[str] = Field(None, description="기관 영문명")
    source_josa_nm: Optional[str] = Field(None, description="조사기관명")
    source_dept_nm: Optional[str] = Field(None, description="담당부서명")
    source_dept_phone: Optional[str] = Field(None, description="담당부서 연락처")

    model_config = {"use_enum_values": True}


class TablesMetadata(BaseModel):
    """tables.json 메타데이터."""

    version: str = Field(..., description="생성 일자 (YYYY-MM-DD)")
    total_count: int = Field(..., description="총 통계표 수")
    sources: dict[str, int] = Field(
        default_factory=dict, description="출처별 통계표 수"
    )


class TablesFile(BaseModel):
    """tables.json 전체 구조."""

    tables: list[StatisticsTable] = Field(..., description="통계표 목록")
    metadata: TablesMetadata = Field(..., description="메타데이터")


class Category(BaseModel):
    """카테고리 노드.

    계층형 브라우징을 위한 트리 구조.
    """

    id: str = Field(..., description="카테고리 ID")
    name: str = Field(..., description="카테고리명")
    level: int = Field(..., description="계층 레벨")
    parent_id: Optional[str] = Field(None, description="부모 카테고리 ID")

    # 하위 정보
    children_count: int = Field(0, description="하위 카테고리 수")
    tables_count: int = Field(0, description="포함된 통계표 수")

    # 경로
    path: str = Field(..., description="전체 경로")
    path_ids: list[str] = Field(default_factory=list, description="경로 ID 목록")


class CategoryTree(BaseModel):
    """카테고리 트리."""

    subject: list[Category] = Field(default_factory=list, description="주제별통계")
    organization: list[Category] = Field(default_factory=list, description="기관별통계")
    international: list[Category] = Field(default_factory=list, description="국제통계")
    north_korea: list[Category] = Field(default_factory=list, description="북한통계")
    local_indicator: list[Category] = Field(
        default_factory=list, description="e-지방지표"
    )


class Indicator(BaseModel):
    """OpenAPI 지표.

    100대 지표 등 주요 지표 정보.
    """

    indicator_id: str = Field(..., description="지표 ID")
    name: str = Field(..., description="지표명")

    # 분류
    sector: str = Field(..., description="부문 (예: 100대 지표)")
    sub_sector: str = Field(..., description="세부부문")

    # 지역/기간
    region_type: str = Field(..., description="지역구분 (전국, 시도 등)")
    period_start: Optional[str] = Field(None, description="수록 시작")
    period_end: Optional[str] = Field(None, description="수록 종료")
    period_type: Optional[PeriodType] = Field(None, description="수록 주기")

    # 메타
    has_explanation: bool = Field(False, description="설명자료 유무")

    model_config = {"use_enum_values": True}


class IndicatorList(BaseModel):
    """지표 목록 ID."""

    list_id: str = Field(..., description="목록 ID")
    major_category: str = Field(..., description="대분류")
    minor_category: Optional[str] = Field(None, description="중분류")


class IndicatorsFile(BaseModel):
    """indicators.json 전체 구조."""

    indicators: list[Indicator] = Field(..., description="지표 목록")
    list_ids: list[IndicatorList] = Field(..., description="목록 ID 매핑")


class Survey(BaseModel):
    """통계조사.

    기관별 조사명 매핑.
    """

    organization: str = Field(..., description="기관명")
    survey_name: str = Field(..., description="조사명")

    # 정규화된 검색 키
    org_normalized: str = Field(..., description="정규화된 기관명")
    survey_normalized: str = Field(..., description="정규화된 조사명")


class SurveysFile(BaseModel):
    """surveys.json 전체 구조."""

    surveys: list[Survey] = Field(..., description="조사 목록")
    by_organization: dict[str, list[str]] = Field(
        default_factory=dict, description="기관별 조사명 목록"
    )
