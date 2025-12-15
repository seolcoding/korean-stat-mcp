"""
KOSIS 리포트 빌더 도구 모음.

이 모듈은 LLM이 유저 쿼리에 맞는 리포트를 동적으로 생성할 수 있도록
세 가지 레이어의 도구를 제공합니다.

Layer 1: DISCOVER - 데이터 탐색
    어떤 데이터가 있는지 찾고, 구조를 파악합니다.
    - search_tables: 통계표 검색
    - browse_categories: 카테고리 탐색
    - get_table_meta: 테이블 메타데이터
    - get_available_values: 사용 가능한 값 조회

Layer 2: FETCH - 데이터 조회
    실제 데이터를 가져오고 가공합니다.
    - fetch_data: 통계 데이터 조회
    - filter_data: 필터링
    - aggregate_data: 집계

Layer 3: PRESENT - 결과물 생성
    시각화, 분석, 텍스트, 리포트를 생성합니다.
    - viz_*: 시각화 도구
    - analyze_*: 분석 도구
    - text_*: 텍스트 생성 도구
    - assemble_report: 리포트 조립

Example:
    LLM 워크플로우:
    >>> # 1. 데이터 탐색
    >>> tables = search_tables("인구")
    >>> meta = get_table_meta("101", "DT_1B040A3")
    >>>
    >>> # 2. 데이터 조회
    >>> data = fetch_data("101", "DT_1B040A3", "2019", "2023")
    >>> filtered = filter_data(data, regions=["서울", "부산"])
    >>>
    >>> # 3. 결과물 생성
    >>> chart = viz_line_trend(filtered, title="서울-부산 인구 추이")
    >>> insight = analyze_trend(filtered, group_by="C1_NM")
    >>> headline = text_headline(insight, style="news")
    >>> report = assemble_report([headline, chart, insight])
"""

from __future__ import annotations

import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path

import pandas as pd
import altair as alt

from .config import DataStorageConfig

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 저장/조회 유틸리티 (MCP 패턴: 원본은 파일에, 요약만 LLM에)
# =============================================================================

def _generate_data_id(data: List[Dict[str, Any]]) -> str:
    """데이터 고유 ID 생성 (해시 기반)."""
    # 데이터의 첫 레코드와 마지막 레코드, 총 길이로 해시 생성
    first = data[0] if data else {}
    last = data[-1] if data else {}
    content = f"{len(data)}:{first.get('TBL_ID', '')}:{first.get('PRD_DE', '')}:{last.get('PRD_DE', '')}"
    hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{hash_suffix}"


def save_raw_data(
    data: List[Dict[str, Any]],
    data_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    원본 데이터를 파일로 저장합니다.

    MCP 패턴에 따라 대용량 데이터는 파일로 저장하고
    참조 정보만 반환합니다.

    Args:
        data: 저장할 원본 데이터
        data_id: 데이터 ID (없으면 자동 생성)

    Returns:
        {
            "data_id": "20231213_abc12345",
            "file_path": "/tmp/kosis_data/20231213_abc12345.json",
            "record_count": 1000,
            "file_size_kb": 256,
            "created_at": "2023-12-13T10:30:00"
        }
    """
    if not data:
        return {"error": "저장할 데이터가 없습니다", "data_id": None}

    # ID 생성
    if not data_id:
        data_id = _generate_data_id(data)

    # 파일 경로
    data_dir = DataStorageConfig.get_data_dir()
    file_path = Path(data_dir) / f"{data_id}.json"

    # 메타데이터 포함하여 저장
    storage_obj = {
        "meta": {
            "data_id": data_id,
            "record_count": len(data),
            "created_at": datetime.now().isoformat(),
            "tbl_id": data[0].get("TBL_ID", "") if data else "",
            "tbl_nm": data[0].get("TBL_NM", "") if data else "",
        },
        "data": data,
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(storage_obj, f, ensure_ascii=False, indent=2)

    file_size_kb = file_path.stat().st_size / 1024

    return {
        "data_id": data_id,
        "file_path": str(file_path),
        "record_count": len(data),
        "file_size_kb": round(file_size_kb, 1),
        "created_at": storage_obj["meta"]["created_at"],
    }


def load_raw_data(
    data_id: str,
    chunk_index: Optional[int] = None,
    chunk_size: int = 50,
) -> Dict[str, Any]:
    """
    저장된 원본 데이터를 불러옵니다.

    Args:
        data_id: 데이터 ID
        chunk_index: 청크 인덱스 (None이면 전체 데이터)
        chunk_size: 청크 크기 (기본 50건)

    Returns:
        {
            "data_id": "20231213_abc12345",
            "meta": {...},
            "data": [...],  # 요청한 데이터 (전체 또는 청크)
            "chunk_info": {  # chunk_index 지정 시
                "chunk_index": 0,
                "chunk_size": 50,
                "total_chunks": 20,
                "has_more": True
            }
        }
    """
    data_dir = DataStorageConfig.get_data_dir()
    file_path = Path(data_dir) / f"{data_id}.json"

    if not file_path.exists():
        return {"error": f"데이터를 찾을 수 없습니다: {data_id}", "data_id": data_id}

    with open(file_path, "r", encoding="utf-8") as f:
        storage_obj = json.load(f)

    meta = storage_obj.get("meta", {})
    data = storage_obj.get("data", [])

    # 청크 요청
    if chunk_index is not None:
        total_records = len(data)
        total_chunks = (total_records + chunk_size - 1) // chunk_size
        start = chunk_index * chunk_size
        end = min(start + chunk_size, total_records)

        if chunk_index >= total_chunks:
            return {
                "error": f"청크 인덱스 초과: {chunk_index} >= {total_chunks}",
                "data_id": data_id,
            }

        return {
            "data_id": data_id,
            "meta": meta,
            "data": data[start:end],
            "chunk_info": {
                "chunk_index": chunk_index,
                "chunk_size": len(data[start:end]),
                "total_chunks": total_chunks,
                "total_records": total_records,
                "has_more": end < total_records,
            },
        }

    # 전체 데이터
    return {
        "data_id": data_id,
        "meta": meta,
        "data": data,
    }


def list_saved_data() -> List[Dict[str, Any]]:
    """
    저장된 데이터 파일 목록을 반환합니다.

    Returns:
        [
            {
                "data_id": "20231213_abc12345",
                "file_path": "/tmp/kosis_data/20231213_abc12345.json",
                "file_size_kb": 256,
                "created_at": "2023-12-13T10:30:00",
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수"
            },
            ...
        ]
    """
    data_dir = Path(DataStorageConfig.get_data_dir())
    result = []

    for file_path in sorted(data_dir.glob("*.json"), reverse=True):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                storage_obj = json.load(f)
            meta = storage_obj.get("meta", {})
            result.append({
                "data_id": meta.get("data_id", file_path.stem),
                "file_path": str(file_path),
                "file_size_kb": round(file_path.stat().st_size / 1024, 1),
                "created_at": meta.get("created_at", ""),
                "record_count": meta.get("record_count", 0),
                "tbl_id": meta.get("tbl_id", ""),
                "tbl_nm": meta.get("tbl_nm", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return result


# =============================================================================
# 공통 데이터 클래스
# =============================================================================

@dataclass
class ReportComponent:
    """
    리포트 구성 요소.

    모든 PRESENT 도구는 이 객체를 반환합니다.
    LLM이 결과를 이해하고 조합할 수 있도록 메타데이터를 포함합니다.

    Attributes:
        type: 구성 요소 유형 ("chart", "analysis", "text", "table", "card")
        html: 렌더링된 HTML 조각
        data: 원본 데이터 (LLM 참조용)
        summary: 한 줄 요약 (LLM이 빠르게 이해)
        metadata: 추가 정보 (파라미터, 통계 등)
        priority: 배치 우선순위 (낮을수록 먼저)
        tags: 검색/필터용 태그
    """
    type: str
    html: str
    data: Any = None
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 50
    tags: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """
    분석 결과.

    analyze_* 도구의 중간 결과로, 텍스트 생성에 활용됩니다.

    Attributes:
        type: 분석 유형 ("trend", "comparison", "ranking", "stats")
        findings: 주요 발견사항 리스트
        data: 분석 데이터 (DataFrame 또는 dict)
        metrics: 계산된 지표들
        interpretation: 해석 텍스트
    """
    type: str
    findings: List[str]
    data: Any = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    interpretation: str = ""


# =============================================================================
# Layer 1: DISCOVER - 데이터 탐색 도구
# =============================================================================

def search_tables(
    keyword: str,
    org_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    키워드로 KOSIS 통계표를 검색합니다.

    유저가 원하는 데이터를 찾을 때 첫 번째로 사용하는 도구입니다.
    검색 결과에서 org_id와 tbl_id를 얻어 다음 단계에 사용합니다.

    Args:
        keyword: 검색 키워드 (예: "인구", "고용", "물가")
        org_id: 기관 ID로 필터링 (선택)
                "101"=통계청, "154"=고용노동부 등
        limit: 최대 결과 수 (기본 10)

    Returns:
        검색된 통계표 목록:
        [
            {
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수",
                "org_id": "101",
                "org_nm": "통계청",
                "start_prd": "1992",
                "end_prd": "2023",
                "prd_se": "Y"  # Y=연간, M=월간, Q=분기
            },
            ...
        ]

    Example:
        >>> tables = search_tables("인구", org_id="101")
        >>> print(tables[0]["tbl_nm"])
        "행정구역별 인구수"
    """
    from .search import StatisticsSearch

    client = StatisticsSearch()
    results = client.search(keyword)

    if org_id:
        results = [r for r in results if r.get("ORG_ID") == org_id]

    # 필드명 정규화
    normalized = []
    for r in results[:limit]:
        normalized.append({
            "tbl_id": r.get("TBL_ID", ""),
            "tbl_nm": r.get("TBL_NM", ""),
            "org_id": r.get("ORG_ID", ""),
            "org_nm": r.get("ORG_NM", ""),
            "start_prd": r.get("PRD_DE", "").split("~")[0].strip() if "~" in r.get("PRD_DE", "") else r.get("PRD_DE", ""),
            "end_prd": r.get("PRD_DE", "").split("~")[-1].strip() if "~" in r.get("PRD_DE", "") else r.get("PRD_DE", ""),
            "prd_se": r.get("PRD_SE", "Y"),
        })

    return normalized


def browse_categories(
    by: str = "org",
    code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    카테고리별로 통계 목록을 탐색합니다.

    특정 기관이나 주제 분야의 통계를 찾을 때 사용합니다.

    Args:
        by: 탐색 기준
            - "org": 기관별 (통계청, 고용노동부 등)
            - "theme": 주제별 (인구, 경제, 사회 등)
        code: 기관 코드 또는 주제 코드 (선택)
              None이면 전체 목록 반환

    Returns:
        통계 목록 또는 하위 카테고리 목록

    Example:
        >>> # 통계청(101) 통계 목록
        >>> stats = browse_categories(by="org", code="101")
        >>>
        >>> # 전체 기관 목록
        >>> orgs = browse_categories(by="org")
    """
    from .list_categories import OrgCode, ThemeCode

    # code가 없으면 정적 목록 반환 (API 호출 불필요)
    if by == "org" and not code:
        return [
            {"code": OrgCode.KOSTAT, "name": "통계청"},
            {"code": OrgCode.MOF, "name": "기획재정부"},
            {"code": OrgCode.MOEL, "name": "고용노동부"},
            {"code": OrgCode.BOK, "name": "한국은행"},
            {"code": OrgCode.MOLIT, "name": "국토교통부"},
            {"code": OrgCode.MOE, "name": "교육부"},
            {"code": OrgCode.MOHW, "name": "보건복지부"},
            {"code": OrgCode.ME, "name": "환경부"},
        ]
    elif by == "theme" and not code:
        return [
            {"code": ThemeCode.POPULATION, "name": "인구"},
            {"code": ThemeCode.LABOR, "name": "고용/노동/임금"},
            {"code": ThemeCode.AGRICULTURE, "name": "농림수산업"},
            {"code": ThemeCode.MINING, "name": "광업/제조업/에너지"},
            {"code": ThemeCode.CONSTRUCTION, "name": "건설"},
            {"code": ThemeCode.TRANSPORT, "name": "교통/정보통신"},
            {"code": ThemeCode.TRADE, "name": "도소매/서비스업"},
            {"code": ThemeCode.ECONOMY, "name": "경기/기업경영"},
            {"code": ThemeCode.FINANCE, "name": "물가/가계/소비"},
            {"code": ThemeCode.HEALTH, "name": "보건/사회/복지"},
            {"code": ThemeCode.EDUCATION, "name": "교육/문화/과학"},
            {"code": ThemeCode.SAFETY, "name": "환경/재해/안전"},
            {"code": ThemeCode.ADMIN, "name": "행정/사법"},
            {"code": ThemeCode.NATIONAL_ACCOUNT, "name": "국민계정/재정/금융"},
            {"code": ThemeCode.INTERNATIONAL, "name": "국제/북한"},
        ]

    # code가 있으면 API 호출 필요
    from .list_categories import CategoryList
    client = CategoryList()

    if by == "org":
        return client.list_by_org(code)
    elif by == "theme":
        return client.list_by_theme(code)
    else:
        return []


def get_table_meta(
    org_id: str,
    tbl_id: str,
) -> Dict[str, Any]:
    """
    통계표의 메타데이터를 조회합니다.

    테이블의 구조(컬럼, 분류항목, 기간 등)를 파악할 때 사용합니다.
    데이터 조회 전에 어떤 필터가 가능한지 확인하는 데 유용합니다.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 테이블 ID (예: "DT_1B040A3")

    Returns:
        메타데이터 딕셔너리:
        {
            "tbl_nm": "행정구역별 인구수",
            "org_nm": "통계청",
            "prd_se": "Y",
            "start_prd": "1992",
            "end_prd": "2023",
            "dimensions": [
                {"id": "C1", "name": "행정구역별", "values": ["전국", "서울", ...]},
                ...
            ],
            "items": [
                {"id": "T1", "name": "인구수"},
                ...
            ]
        }

    Example:
        >>> meta = get_table_meta("101", "DT_1B040A3")
        >>> print(meta["dimensions"][0]["name"])
        "행정구역별"
    """
    from .table_meta import TableMetadata

    client = TableMetadata()
    raw_meta = client.get_all_metadata(org_id, tbl_id)

    if not raw_meta:
        return {}

    # table_info에서 기본 정보 추출
    table_info = raw_meta.get("table_info") or {}
    tbl_nm = table_info.get("TBL_NM", "")
    org_nm = table_info.get("ORG_NM", "")

    # 분류 항목 추출 (obj_vars)
    dimensions = []
    obj_vars = raw_meta.get("obj_vars") or []
    if obj_vars:
        # 그룹핑: OBJ_ID별로
        from collections import defaultdict
        grouped = defaultdict(list)
        for v in obj_vars:
            obj_id = v.get("OBJ_ID", "C1")
            grouped[obj_id].append(v)

        for obj_id, items in grouped.items():
            if items:
                dim_info = {
                    "id": obj_id,
                    "name": items[0].get("OBJ_NM", ""),
                    "values": [v.get("ITM_NM", "") for v in items],
                }
                dimensions.append(dim_info)

    # 항목 추출 (itm_vars)
    items = []
    itm_vars = raw_meta.get("itm_vars") or []
    for itm in itm_vars:
        items.append({
            "id": itm.get("ITM_ID", ""),
            "name": itm.get("ITM_NM", ""),
        })

    # 기간 정보 추출 (prd_info)
    prd_info = raw_meta.get("prd_info") or []
    prd_se = "Y"
    start_prd = ""
    end_prd = ""
    if prd_info:
        # 첫 번째 기간 정보 사용
        first_prd = prd_info[0]
        prd_se_map = {"년": "Y", "월": "M", "분기": "Q", "반기": "S"}
        prd_se = prd_se_map.get(first_prd.get("PRD_SE", "년"), "Y")
        start_prd = first_prd.get("STRT_PRD_DE", "")
        end_prd = first_prd.get("END_PRD_DE", "")

    return {
        "tbl_id": tbl_id,
        "tbl_nm": tbl_nm,
        "org_id": org_id,
        "org_nm": org_nm,
        "prd_se": prd_se,
        "start_prd": start_prd,
        "end_prd": end_prd,
        "dimensions": dimensions,
        "items": items,
        "raw": raw_meta,
    }


def get_available_values(
    data: List[Dict[str, Any]],
    field: str,
) -> List[str]:
    """
    데이터에서 특정 필드의 사용 가능한 값을 조회합니다.

    필터링 옵션을 사용자에게 보여주거나,
    LLM이 어떤 값으로 필터링할지 결정할 때 사용합니다.

    Args:
        data: KOSIS 데이터 (fetch_data 결과)
        field: 필드명 (예: "C1_NM", "PRD_DE", "ITM_NM")

    Returns:
        고유값 리스트 (정렬됨)

    Example:
        >>> data = fetch_data("101", "DT_1B040A3", "2020", "2023")
        >>> regions = get_available_values(data, "C1_NM")
        >>> print(regions[:3])
        ["강원도", "경기도", "경상남도"]
    """
    if not data:
        return []

    values = set()
    for row in data:
        if field in row and row[field]:
            values.add(str(row[field]))

    return sorted(list(values))


# =============================================================================
# Layer 2: FETCH - 데이터 조회 도구
# =============================================================================

def format_data_for_llm(
    data: List[Dict[str, Any]],
    max_rows: int = 50,
    include_sample: bool = True,
    save_raw: bool = True,
) -> Dict[str, Any]:
    """
    API 응답을 LLM 친화적 포맷으로 변환합니다.

    중복 메타데이터를 제거하고, 컨텍스트 효율적인 형태로 압축합니다.
    원본 데이터는 파일로 저장하고 참조 정보를 반환합니다 (MCP 패턴).

    Args:
        data: 원본 KOSIS API 응답 데이터
        max_rows: 샘플 데이터 최대 행 수
        include_sample: 샘플 데이터 포함 여부
        save_raw: 원본 데이터 파일 저장 여부 (기본 True)

    Returns:
        {
            "summary": {...},
            "metadata": {...},
            "data_preview": [...],
            "pivot_summary": {...},
            "raw_data_file": {  # save_raw=True일 때
                "data_id": "20231213_abc12345",
                "file_path": "/tmp/kosis_data/20231213_abc12345.json",
                "record_count": 1000,
                "access_hint": "load_raw_data('20231213_abc12345')로 전체 데이터 접근"
            }
        }
    """
    if not data:
        return {"error": "데이터가 없습니다", "total_records": 0}

    # 1. 공통 메타데이터 추출 (첫 레코드에서)
    first = data[0]
    metadata = {
        "tbl_id": first.get("TBL_ID", ""),
        "tbl_nm": first.get("TBL_NM", ""),
        "org_id": first.get("ORG_ID", ""),
        "org_nm": first.get("ORG_NM", ""),
        "unit": first.get("UNIT_NM", ""),
    }

    # 2. 유니크 값 추출
    unique_values = {}
    key_fields = ["PRD_DE", "C1_NM", "C2_NM", "C3_NM", "ITM_NM"]

    for field in key_fields:
        values = set()
        for row in data:
            val = row.get(field)
            if val:
                values.add(val)
        if values:
            unique_values[field] = sorted(list(values))

    # 3. 요약 정보 생성
    periods = unique_values.get("PRD_DE", [])
    period_range = f"{periods[0]}~{periods[-1]}" if len(periods) > 1 else (periods[0] if periods else "N/A")

    # 분류 항목 이름 추출
    dimensions = []
    for field in ["C1_NM", "C2_NM", "C3_NM"]:
        if field in unique_values:
            # 필드에 해당하는 OBJ_NM을 찾아봄
            obj_nm_field = field.replace("_NM", "_OBJ_NM") if "_NM" in field else None
            if obj_nm_field and first.get(obj_nm_field):
                dimensions.append(first.get(obj_nm_field))
            else:
                # 필드명 기반으로 추정
                dim_names = {"C1_NM": "분류1", "C2_NM": "분류2", "C3_NM": "분류3"}
                dimensions.append(dim_names.get(field, field))

    items = unique_values.get("ITM_NM", [])

    summary = {
        "total_records": len(data),
        "period_range": period_range,
        "period_count": len(periods),
        "dimensions": dimensions,
        "dimension_counts": {
            field: len(vals) for field, vals in unique_values.items()
            if field.startswith("C") and field.endswith("_NM")
        },
        "items": items,
        "item_count": len(items),
    }

    # 4. 피벗 요약 (기간별, 분류별 합계)
    pivot_summary = {}

    # 기간별 합계
    if periods:
        by_period = {}
        for period in periods[-5:]:  # 최근 5개 기간만
            period_sum = 0
            for row in data:
                if row.get("PRD_DE") == period:
                    try:
                        period_sum += float(row.get("DT", 0))
                    except (ValueError, TypeError):
                        pass
            by_period[period] = period_sum
        pivot_summary["by_period"] = by_period

    # 주요 분류별 합계 (상위 10개)
    c1_values = unique_values.get("C1_NM", [])
    if c1_values:
        by_c1 = {}
        for c1 in c1_values[:10]:  # 상위 10개만
            c1_sum = 0
            for row in data:
                if row.get("C1_NM") == c1:
                    try:
                        c1_sum += float(row.get("DT", 0))
                    except (ValueError, TypeError):
                        pass
            by_c1[c1] = c1_sum
        # 값 기준 정렬 (내림차순)
        pivot_summary["by_c1"] = dict(sorted(by_c1.items(), key=lambda x: x[1], reverse=True))

    # 5. 샘플 데이터 (압축된 형태)
    data_preview = []
    if include_sample:
        # 가장 최근 기간의 데이터만 샘플로
        latest_period = periods[-1] if periods else None
        sample_data = [r for r in data if r.get("PRD_DE") == latest_period][:max_rows]

        # 필요한 필드만 추출
        essential_fields = ["PRD_DE", "C1_NM", "C2_NM", "ITM_NM", "DT"]
        for row in sample_data:
            preview_row = {}
            for field in essential_fields:
                val = row.get(field)
                if val:
                    # 필드명 한글화
                    field_names = {
                        "PRD_DE": "기간",
                        "C1_NM": "분류1",
                        "C2_NM": "분류2",
                        "ITM_NM": "항목",
                        "DT": "값",
                    }
                    preview_row[field_names.get(field, field)] = val
            if preview_row:
                data_preview.append(preview_row)

    # 6. 원본 데이터 파일 저장 (MCP 패턴)
    raw_data_file = None
    if save_raw and len(data) > 0:
        save_result = save_raw_data(data)
        if "error" not in save_result:
            raw_data_file = {
                "data_id": save_result["data_id"],
                "file_path": save_result["file_path"],
                "record_count": save_result["record_count"],
                "file_size_kb": save_result["file_size_kb"],
                "access_hint": f"load_raw_data('{save_result['data_id']}')로 전체 데이터 접근, "
                              f"load_raw_data('{save_result['data_id']}', chunk_index=0)로 청크별 접근",
            }

    # 7. 전체 데이터 가용성 안내
    data_availability = {
        "full_data_available": True,
        "sample_period": periods[-1] if periods else None,
        "sample_count": len(data_preview),
        "note": f"전체 {len(data)}건 중 최근 기간({periods[-1] if periods else 'N/A'}) {len(data_preview)}건 샘플 제공" if len(data) > max_rows else "전체 데이터 제공",
    }

    # 8. 동적 컬럼 스키마 생성 (Code Execution용)
    # 실제 데이터에 존재하는 컬럼과 설명
    column_schema = {}
    column_descriptions = {
        "PRD_DE": "기간 (예: '2023', '202301')",
        "C1_NM": "분류1 - 주로 지역명 (예: '서울특별시')",
        "C2_NM": "분류2 - 세부 분류",
        "C3_NM": "분류3 - 추가 분류",
        "DT": "데이터 값 (문자열, 숫자 변환 필요: prepare_data 사용)",
        "ITM_NM": "항목명 (예: '인구수', '세대수')",
        "UNIT_NM": "단위 (예: '명', '%')",
        "TBL_ID": "테이블 ID",
        "TBL_NM": "테이블명",
        "ORG_ID": "기관 ID",
        "ORG_NM": "기관명",
    }

    # 첫 번째 레코드에서 실제 존재하는 컬럼 추출
    for col in first.keys():
        if first.get(col):  # 값이 있는 컬럼만
            column_schema[col] = {
                "description": column_descriptions.get(col, f"필드: {col}"),
                "sample_value": str(first.get(col))[:50],  # 샘플값 (50자 제한)
            }

    # 9. Code Execution 컨텍스트
    actual_columns = list(first.keys())
    code_context = {
        "columns": actual_columns,
        "column_schema": column_schema,
        "value_column": "DT",  # 숫자 값 컬럼
        "group_columns": [c for c in ["C1_NM", "C2_NM", "C3_NM", "ITM_NM"] if c in unique_values],
        "period_column": "PRD_DE" if "PRD_DE" in actual_columns else None,
        "usage_hint": """
# Code Execution 예시:
df = prepare_data(data, numeric_fields=["DT"])  # DT를 숫자로 변환
df.groupby("C1_NM")["DT"].sum()  # 분류별 합계
alt.Chart(df).mark_line().encode(x='PRD_DE:N', y='DT:Q', color='C1_NM:N')  # 차트
""",
    }

    result = {
        "summary": summary,
        "metadata": metadata,
        "data_preview": data_preview,
        "pivot_summary": pivot_summary,
        "data_availability": data_availability,
        "available_values": {
            k: v[:20] if len(v) > 20 else v  # 각 필드별 20개까지만
            for k, v in unique_values.items()
        },
        "code_context": code_context,  # Code Execution용 컨텍스트 추가
    }

    # 원본 파일 정보 추가
    if raw_data_file:
        result["raw_data_file"] = raw_data_file

    return result


def fetch_data(
    org_id: str,
    tbl_id: str,
    start_date: str,
    end_date: str,
    prd_se: str = "Y",
    **filters,
) -> List[Dict[str, Any]]:
    """
    KOSIS에서 통계 데이터를 조회합니다.

    search_tables나 get_table_meta로 확인한 테이블의 실제 데이터를 가져옵니다.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 테이블 ID (예: "DT_1B040A3")
        start_date: 시작 기간 (예: "2019", "202301")
        end_date: 종료 기간 (예: "2023", "202312")
        prd_se: 기간 유형
                "Y"=연간, "M"=월간, "Q"=분기, "S"=반기
        **filters: 추가 필터 (obj_l1, obj_l2, itm_id 등)

    Returns:
        데이터 레코드 리스트:
        [
            {
                "PRD_DE": "2023",
                "C1_NM": "서울특별시",
                "DT": "9411211",
                "ITM_NM": "인구수",
                ...
            },
            ...
        ]

    Example:
        >>> data = fetch_data("101", "DT_1B040A3", "2020", "2023", prd_se="Y")
        >>> print(f"총 {len(data)}건 조회")
    """
    from .data import StatisticsData

    client = StatisticsData()
    records = client.get_data(
        org_id=org_id,
        tbl_id=tbl_id,
        start_date=start_date,
        end_date=end_date,
        prd_se=prd_se,
        **filters,
    )

    return records or []


def filter_data(
    data: List[Dict[str, Any]],
    regions: Optional[List[str]] = None,
    periods: Optional[List[str]] = None,
    items: Optional[List[str]] = None,
    custom_filter: Optional[Callable[[Dict], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    데이터를 필터링합니다.

    지역, 기간, 항목 등으로 데이터를 좁힐 때 사용합니다.

    Args:
        data: 원본 데이터 (fetch_data 결과)
        regions: 포함할 지역 목록 (C1_NM 필드)
                 예: ["서울특별시", "부산광역시"]
        periods: 포함할 기간 목록 (PRD_DE 필드)
                 예: ["2022", "2023"]
        items: 포함할 항목 목록 (ITM_NM 필드)
               예: ["인구수", "세대수"]
        custom_filter: 커스텀 필터 함수
                       예: lambda row: float(row["DT"]) > 1000000

    Returns:
        필터링된 데이터 리스트

    Example:
        >>> filtered = filter_data(
        ...     data,
        ...     regions=["서울특별시", "부산광역시"],
        ...     periods=["2022", "2023"]
        ... )
    """
    result = data

    if regions:
        result = [r for r in result if r.get("C1_NM") in regions]

    if periods:
        result = [r for r in result if r.get("PRD_DE") in periods]

    if items:
        result = [r for r in result if r.get("ITM_NM") in items]

    if custom_filter:
        result = [r for r in result if custom_filter(r)]

    return result


def aggregate_data(
    data: List[Dict[str, Any]],
    group_by: Union[str, List[str]],
    value_field: str = "DT",
    agg_func: str = "sum",
) -> List[Dict[str, Any]]:
    """
    데이터를 그룹별로 집계합니다.

    Args:
        data: 원본 데이터
        group_by: 그룹핑 필드 (단일 또는 리스트)
                  예: "C1_NM" 또는 ["C1_NM", "PRD_DE"]
        value_field: 집계할 값 필드 (기본: "DT")
        agg_func: 집계 함수 ("sum", "mean", "min", "max", "count")

    Returns:
        집계된 데이터 리스트

    Example:
        >>> # 지역별 합계
        >>> by_region = aggregate_data(data, group_by="C1_NM", agg_func="sum")
        >>>
        >>> # 지역-연도별 평균
        >>> by_region_year = aggregate_data(
        ...     data, group_by=["C1_NM", "PRD_DE"], agg_func="mean"
        ... )
    """
    from .transform import KosisTransformer

    tx = KosisTransformer(data)

    if isinstance(group_by, str):
        group_by = [group_by]

    agg_dict = {value_field: agg_func}
    grouped_df = tx.groupby(group_by, agg_dict)

    return grouped_df.to_dict("records")


# =============================================================================
# Layer 3: PRESENT - 시각화 도구
# =============================================================================

def viz_line_trend(
    data: List[Dict[str, Any]],
    x: str = "PRD_DE",
    y: str = "DT",
    color: Optional[str] = "C1_NM",
    title: Optional[str] = None,
    highlight: Optional[Dict[str, Any]] = None,
    show_trend_line: bool = False,
    labels: Optional[Dict[str, str]] = None,
) -> ReportComponent:
    """
    시계열 추세 라인 차트를 생성합니다.

    기간별 변화를 보여줄 때 사용합니다.
    여러 그룹을 색상으로 구분하여 비교할 수 있습니다.

    Args:
        data: 차트 데이터
        x: X축 필드 (기본: "PRD_DE" 기간)
        y: Y축 필드 (기본: "DT" 값)
        color: 색상 구분 필드 (기본: "C1_NM" 지역)
               None이면 단일 라인
        title: 차트 제목
        highlight: 강조할 포인트
                   {"period": "2023", "color": "red"}
        show_trend_line: 추세선 표시 여부
        labels: 필드명→표시라벨 매핑 (MCP에서 LLM이 지정)
               예: {"PRD_DE": "연도", "DT": "인구수", "C1_NM": "지역"}

    Returns:
        ReportComponent (type="chart")

    Example:
        >>> chart = viz_line_trend(
        ...     data,
        ...     title="인구 추이",
        ...     color="C1_NM",
        ...     labels={"PRD_DE": "연도", "DT": "인구수", "C1_NM": "지역"}
        ... )
        >>> print(chart.summary)
        "4개 지역의 2020-2023 추이를 보여주는 라인 차트"
    """
    from .visualize import prepare_data

    labels = labels or {}
    df = prepare_data(data, numeric_fields=[y])

    # Altair 차트 생성
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X(f'{x}:N', title=labels.get(x, x)),
        y=alt.Y(f'{y}:Q', title=labels.get(y, y)),
    )

    if color and color in df.columns:
        chart = chart.encode(color=alt.Color(f'{color}:N', title=labels.get(color, color)))

    if title:
        chart = chart.properties(title=title)

    chart = chart.properties(width=600, height=400)

    # 요약 생성
    periods = get_available_values(data, x)
    groups = get_available_values(data, color) if color else []
    period_range = f"{periods[0]}-{periods[-1]}" if periods else ""
    group_count = len(groups) if groups else 1

    summary = f"{group_count}개 항목의 {period_range} 추이를 보여주는 라인 차트"

    # Vega-Embed HTML 생성
    spec = chart.to_json()
    html = f'''<div class="chart-container">
        <div id="chart-{id(chart)}"></div>
        <script>vegaEmbed('#chart-{id(chart)}', {spec}, {{"renderer": "svg"}}).catch(console.error);</script>
    </div>'''

    return ReportComponent(
        type="chart",
        html=html,
        data={"x": x, "y": y, "color": color, "periods": periods, "groups": groups},
        summary=summary,
        metadata={"chart_type": "line", "title": title},
        priority=30,
        tags=["visualization", "line", "trend"],
    )


def viz_bar_comparison(
    data: List[Dict[str, Any]],
    x: str = "C1_NM",
    y: str = "DT",
    color: Optional[str] = None,
    title: Optional[str] = None,
    sort: bool = True,
    top_n: Optional[int] = None,
    horizontal: bool = False,
    labels: Optional[Dict[str, str]] = None,
) -> ReportComponent:
    """
    비교 막대 차트를 생성합니다.

    카테고리간 크기 비교에 적합합니다.

    Args:
        data: 차트 데이터
        x: X축 필드 (기본: "C1_NM" 분류)
        y: Y축 필드 (기본: "DT" 값)
        color: 색상 구분 필드 (그룹 막대 시)
        title: 차트 제목
        sort: 값 기준 정렬 여부
        top_n: 상위 N개만 표시
        horizontal: 가로 막대 여부
        labels: 필드명→표시라벨 매핑 (MCP에서 LLM이 지정)
               예: {"C1_NM": "지역", "DT": "인구수", "PRD_DE": "연도"}

    Returns:
        ReportComponent (type="chart")

    Example:
        >>> chart = viz_bar_comparison(
        ...     data,
        ...     x="C1_NM",
        ...     title="지역별 인구",
        ...     sort=True,
        ...     top_n=10,
        ...     labels={"C1_NM": "지역", "DT": "인구수"}
        ... )
    """
    from .visualize import prepare_data

    labels = labels or {}
    df = prepare_data(data, numeric_fields=[y])

    # 정렬 및 Top N 처리
    if sort or top_n:
        df = df.sort_values(y, ascending=False)
        if top_n:
            df = df.head(top_n)

    # Altair 차트 생성
    if horizontal:
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(f'{y}:Q', title=labels.get(y, y)),
            y=alt.Y(f'{x}:N', title=labels.get(x, x), sort='-x'),
        )
    else:
        sort_order = '-y' if sort else None
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(f'{x}:N', title=labels.get(x, x), sort=sort_order),
            y=alt.Y(f'{y}:Q', title=labels.get(y, y)),
        )

    if color and color in df.columns:
        chart = chart.encode(color=alt.Color(f'{color}:N', title=labels.get(color, color)))

    if title:
        chart = chart.properties(title=title)

    chart = chart.properties(width=600, height=400)

    categories = df[x].unique().tolist() if x in df.columns else []
    summary = f"{len(categories)}개 항목의 비교 막대 차트"
    if top_n:
        summary = f"상위 {top_n}개 항목의 비교 막대 차트"

    # Vega-Embed HTML 생성
    spec = chart.to_json()
    html = f'''<div class="chart-container">
        <div id="chart-{id(chart)}"></div>
        <script>vegaEmbed('#chart-{id(chart)}', {spec}, {{"renderer": "svg"}}).catch(console.error);</script>
    </div>'''

    return ReportComponent(
        type="chart",
        html=html,
        data={"x": x, "y": y, "categories": categories, "top_n": top_n},
        summary=summary,
        metadata={"chart_type": "bar", "title": title, "sorted": sort},
        priority=30,
        tags=["visualization", "bar", "comparison"],
    )


def viz_kpi_card(
    value: Union[int, float, str],
    label: str,
    change: Optional[float] = None,
    change_label: Optional[str] = None,
    icon: Optional[str] = None,
    format_str: str = "{:,.0f}",
) -> ReportComponent:
    """
    핵심 수치(KPI) 카드를 생성합니다.

    한 가지 핵심 지표를 눈에 띄게 표시할 때 사용합니다.

    Args:
        value: 표시할 값
        label: 값의 라벨 (예: "총 인구수")
        change: 변동률 (예: -1.2)
        change_label: 변동 기간 (예: "전년 대비")
        icon: 아이콘 이모지 (예: "📊")
        format_str: 값 포맷 (기본: 천단위 콤마)

    Returns:
        ReportComponent (type="card")

    Example:
        >>> card = viz_kpi_card(
        ...     value=51000000,
        ...     label="총 인구",
        ...     change=-1.2,
        ...     change_label="전년 대비"
        ... )
    """
    # 값 포맷팅
    if isinstance(value, (int, float)):
        formatted_value = format_str.format(value)
    else:
        formatted_value = str(value)

    # 변동률 HTML
    change_html = ""
    if change is not None:
        change_color = "#10b981" if change >= 0 else "#ef4444"
        change_sign = "+" if change >= 0 else ""
        change_html = f'''
            <div style="color: {change_color}; font-size: 0.9rem; margin-top: 5px;">
                {change_sign}{change:.1f}% {change_label or ""}
            </div>
        '''

    icon_html = f'<span style="font-size: 1.5rem;">{icon}</span>' if icon else ""

    html = f'''
    <div class="kpi-card" style="
        background: white;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        min-width: 150px;
    ">
        {icon_html}
        <div style="font-size: 2rem; font-weight: 700; color: #667eea;">
            {formatted_value}
        </div>
        <div style="color: #666; font-size: 0.9rem; margin-top: 5px;">
            {label}
        </div>
        {change_html}
    </div>
    '''

    summary = f"{label}: {formatted_value}"
    if change is not None:
        summary += f" ({change:+.1f}%)"

    return ReportComponent(
        type="card",
        html=html,
        data={"value": value, "label": label, "change": change},
        summary=summary,
        metadata={"formatted_value": formatted_value},
        priority=10,
        tags=["visualization", "kpi", "card"],
    )


def viz_pie_composition(
    data: List[Dict[str, Any]],
    values: str = "DT",
    names: str = "C1_NM",
    title: Optional[str] = None,
    hole: float = 0.4,
    top_n: int = 5,
) -> ReportComponent:
    """
    구성비 파이/도넛 차트를 생성합니다.

    전체 대비 각 항목의 비중을 보여줄 때 사용합니다.

    Args:
        data: 차트 데이터
        values: 값 필드 (기본: "DT")
        names: 라벨 필드 (기본: "C1_NM")
        title: 차트 제목
        hole: 도넛 구멍 크기 (0=파이, 0.4=도넛)
        top_n: 상위 N개만 표시 (나머지는 "기타")

    Returns:
        ReportComponent (type="chart")
    """
    from .visualize import prepare_data

    df = prepare_data(data, numeric_fields=[values])
    df = df.sort_values(values, ascending=False)

    # Top N 처리 (나머지는 "기타"로 합침)
    if len(df) > top_n:
        top_df = df.head(top_n)
        others_sum = df.iloc[top_n:][values].sum()
        others_row = {names: "기타", values: others_sum}
        df = pd.concat([top_df, pd.DataFrame([others_row])], ignore_index=True)

    # Altair 파이/도넛 차트 (arc mark)
    inner_radius = int(hole * 100) if hole > 0 else 0
    chart = alt.Chart(df).mark_arc(innerRadius=inner_radius).encode(
        theta=alt.Theta(f'{values}:Q'),
        color=alt.Color(f'{names}:N'),
        tooltip=[f'{names}:N', f'{values}:Q']
    ).properties(width=400, height=400)

    if title:
        chart = chart.properties(title=title)

    # Vega-Embed HTML 생성
    spec = chart.to_json()
    html = f'''<div class="chart-container">
        <div id="chart-{id(chart)}"></div>
        <script>vegaEmbed('#chart-{id(chart)}', {spec}, {{"renderer": "svg"}}).catch(console.error);</script>
    </div>'''

    return ReportComponent(
        type="chart",
        html=html,
        data={"values": values, "names": names, "top_n": top_n},
        summary=f"상위 {top_n}개 항목의 구성비 차트",
        metadata={"chart_type": "pie", "title": title},
        priority=30,
        tags=["visualization", "pie", "composition"],
    )


def viz_heatmap(
    data: List[Dict[str, Any]],
    x: str = "PRD_DE",
    y: str = "C1_NM",
    z: str = "DT",
    title: Optional[str] = None,
    color_scale: str = "Blues",
) -> ReportComponent:
    """
    히트맵을 생성합니다.

    2차원 데이터의 패턴을 색상 강도로 보여줍니다.
    시간-지역, 항목-항목 등의 조합에 유용합니다.

    Args:
        data: 차트 데이터
        x: X축 필드 (기본: "PRD_DE")
        y: Y축 필드 (기본: "C1_NM")
        z: 값 필드 (기본: "DT")
        title: 차트 제목
        color_scale: 색상 스케일 ("blues", "reds", "viridis" 등)

    Returns:
        ReportComponent (type="chart")
    """
    from .visualize import prepare_data

    df = prepare_data(data, numeric_fields=[z])

    # Altair color scheme mapping
    scheme_map = {
        "Blues": "blues",
        "Reds": "reds",
        "Viridis": "viridis",
        "Greens": "greens",
    }
    scheme = scheme_map.get(color_scale, color_scale.lower())

    # Altair 히트맵
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X(f'{x}:N', title=x),
        y=alt.Y(f'{y}:N', title=y),
        color=alt.Color(f'{z}:Q', scale=alt.Scale(scheme=scheme)),
        tooltip=[f'{x}:N', f'{y}:N', f'{z}:Q']
    ).properties(width=600, height=400)

    if title:
        chart = chart.properties(title=title)

    x_vals = df[x].unique().tolist() if x in df.columns else []
    y_vals = df[y].unique().tolist() if y in df.columns else []

    # Vega-Embed HTML 생성
    spec = chart.to_json()
    html = f'''<div class="chart-container">
        <div id="chart-{id(chart)}"></div>
        <script>vegaEmbed('#chart-{id(chart)}', {spec}, {{"renderer": "svg"}}).catch(console.error);</script>
    </div>'''

    return ReportComponent(
        type="chart",
        html=html,
        data={"x": x, "y": y, "z": z, "x_count": len(x_vals), "y_count": len(y_vals)},
        summary=f"{len(y_vals)}x{len(x_vals)} 히트맵",
        metadata={"chart_type": "heatmap", "title": title},
        priority=30,
        tags=["visualization", "heatmap", "matrix"],
    )


# =============================================================================
# Layer 3: PRESENT - 분석 도구
# =============================================================================

def analyze_trend(
    data: List[Dict[str, Any]],
    value_field: str = "DT",
    period_field: str = "PRD_DE",
    group_by: Optional[str] = None,
) -> AnalysisResult:
    """
    추세 분석을 수행합니다.

    기간별 증감률, 방향, CAGR 등을 계산합니다.

    Args:
        data: 분석할 데이터
        value_field: 값 필드 (기본: "DT")
        period_field: 기간 필드 (기본: "PRD_DE")
        group_by: 그룹별 분석 필드 (선택)

    Returns:
        AnalysisResult:
        - findings: 주요 발견사항 리스트
        - metrics: {
            "direction": "증가" | "감소" | "보합",
            "total_change_pct": 전체 변화율,
            "avg_change_pct": 평균 변화율,
            "cagr": 연평균 성장률 (기간이 2년 이상일 때)
          }

    Example:
        >>> result = analyze_trend(data, group_by="C1_NM")
        >>> print(result.findings[0])
        "서울: 4년간 -5.2% 감소 (연평균 -1.3%)"
    """
    from .transform import KosisTransformer

    findings = []
    metrics = {}

    if group_by:
        # 그룹별 분석
        groups = get_available_values(data, group_by)
        group_metrics = {}

        for group in groups:
            # 직접 필터링 (group_by 필드 값으로)
            group_data = [r for r in data if r.get(group_by) == group]

            if len(group_data) < 2:
                continue

            tx = KosisTransformer(group_data)
            growth_df = tx.calculate_growth(value_field, period_field)

            if len(growth_df) > 0:
                total_change = growth_df["growth_pct"].sum()
                avg_change = growth_df["growth_pct"].mean()

                # CAGR 계산
                first_val = growth_df[value_field].iloc[0]
                last_val = growth_df[value_field].iloc[-1]
                n_years = len(growth_df) - 1

                if first_val > 0 and n_years > 0:
                    cagr = ((last_val / first_val) ** (1 / n_years) - 1) * 100
                else:
                    cagr = 0

                direction = "증가" if total_change > 1 else "감소" if total_change < -1 else "보합"

                group_metrics[group] = {
                    "direction": direction,
                    "total_change_pct": total_change,
                    "avg_change_pct": avg_change,
                    "cagr": cagr,
                }

                findings.append(
                    f"{group}: {n_years+1}년간 {total_change:+.1f}% {direction} (연평균 {cagr:+.1f}%)"
                )

        metrics = {"groups": group_metrics}
    else:
        # 전체 분석
        tx = KosisTransformer(data)
        growth_df = tx.calculate_growth(value_field, period_field)

        if len(growth_df) > 1:
            total_change = growth_df["growth_pct"].sum()
            avg_change = growth_df["growth_pct"].mean()

            first_val = growth_df[value_field].iloc[0]
            last_val = growth_df[value_field].iloc[-1]
            n_years = len(growth_df) - 1

            if first_val > 0 and n_years > 0:
                cagr = ((last_val / first_val) ** (1 / n_years) - 1) * 100
            else:
                cagr = 0

            direction = "증가" if total_change > 1 else "감소" if total_change < -1 else "보합"

            metrics = {
                "direction": direction,
                "total_change_pct": total_change,
                "avg_change_pct": avg_change,
                "cagr": cagr,
                "first_value": first_val,
                "last_value": last_val,
                "n_periods": n_years + 1,
            }

            findings.append(
                f"{n_years+1}년간 {total_change:+.1f}% {direction} (연평균 {cagr:+.1f}%)"
            )

    interpretation = " ".join(findings) if findings else "분석할 데이터가 부족합니다."

    return AnalysisResult(
        type="trend",
        findings=findings,
        data=data,
        metrics=metrics,
        interpretation=interpretation,
    )


def analyze_comparison(
    data: List[Dict[str, Any]],
    compare_field: str = "C1_NM",
    targets: Optional[List[str]] = None,
    value_field: str = "DT",
    period: Optional[str] = None,
) -> AnalysisResult:
    """
    비교 분석을 수행합니다.

    두 개 이상의 항목을 비교하여 차이와 비율을 계산합니다.

    Args:
        data: 분석할 데이터
        compare_field: 비교 기준 필드 (기본: "C1_NM")
        targets: 비교 대상 목록 (None이면 전체)
        value_field: 값 필드 (기본: "DT")
        period: 특정 기간으로 필터 (선택)

    Returns:
        AnalysisResult:
        - findings: 비교 결과 문장들
        - metrics: {
            "rankings": [{name, value, rank}, ...],
            "max": {name, value},
            "min": {name, value},
            "gap": 최대-최소 차이
          }

    Example:
        >>> result = analyze_comparison(
        ...     data,
        ...     targets=["서울특별시", "부산광역시"]
        ... )
        >>> print(result.findings[0])
        "서울특별시가 부산광역시보다 2.8배 많음"
    """
    from .transform import KosisTransformer

    # 기간 필터
    if period:
        data = filter_data(data, periods=[period])

    # 대상 필터
    if targets:
        data = [r for r in data if r.get(compare_field) in targets]

    # 집계
    aggregated = aggregate_data(data, group_by=compare_field, value_field=value_field, agg_func="sum")

    if not aggregated:
        return AnalysisResult(
            type="comparison",
            findings=["비교할 데이터가 없습니다."],
            data=data,
            metrics={},
            interpretation="비교할 데이터가 없습니다.",
        )

    # 정렬 및 순위
    df = pd.DataFrame(aggregated)
    df[value_field] = pd.to_numeric(df[value_field], errors="coerce")
    df = df.sort_values(value_field, ascending=False)
    df["rank"] = range(1, len(df) + 1)

    rankings = df.to_dict("records")

    max_item = rankings[0]
    min_item = rankings[-1]

    findings = []

    # 1위 vs 2위 비교
    if len(rankings) >= 2:
        first = rankings[0]
        second = rankings[1]
        ratio = first[value_field] / second[value_field] if second[value_field] > 0 else 0
        findings.append(
            f"{first[compare_field]}({first[value_field]:,.0f})이 "
            f"{second[compare_field]}({second[value_field]:,.0f})보다 {ratio:.1f}배"
        )

    # 최대 vs 최소
    if len(rankings) >= 2:
        gap = max_item[value_field] - min_item[value_field]
        gap_ratio = max_item[value_field] / min_item[value_field] if min_item[value_field] > 0 else 0
        findings.append(
            f"최대({max_item[compare_field]})와 최소({min_item[compare_field]}) 격차: {gap:,.0f} ({gap_ratio:.1f}배)"
        )

    metrics = {
        "rankings": rankings,
        "max": {"name": max_item[compare_field], "value": max_item[value_field]},
        "min": {"name": min_item[compare_field], "value": min_item[value_field]},
        "gap": max_item[value_field] - min_item[value_field],
        "count": len(rankings),
    }

    return AnalysisResult(
        type="comparison",
        findings=findings,
        data=rankings,
        metrics=metrics,
        interpretation=" | ".join(findings),
    )


def analyze_ranking(
    data: List[Dict[str, Any]],
    value_field: str = "DT",
    rank_field: str = "C1_NM",
    top_n: int = 10,
    period: Optional[str] = None,
) -> AnalysisResult:
    """
    순위 분석을 수행합니다.

    상위/하위 N개 항목을 추출하고 순위를 매깁니다.

    Args:
        data: 분석할 데이터
        value_field: 값 필드 (기본: "DT")
        rank_field: 순위 기준 필드 (기본: "C1_NM")
        top_n: 상위 N개 (기본: 10)
        period: 특정 기간으로 필터 (선택)

    Returns:
        AnalysisResult:
        - findings: 순위 결과 문장들
        - data: 순위 테이블 데이터
        - metrics: {
            "top_n": N,
            "total_count": 전체 항목 수,
            "top_1": 1위 정보
          }

    Example:
        >>> result = analyze_ranking(data, top_n=5)
        >>> print(result.findings[0])
        "1위: 경기도 (13,639,666)"
    """
    from .transform import KosisTransformer

    # 기간 필터
    if period:
        data = filter_data(data, periods=[period])
    else:
        # 가장 최근 기간 사용
        periods = sorted(get_available_values(data, "PRD_DE"))
        if periods:
            period = periods[-1]
            data = filter_data(data, periods=[period])

    tx = KosisTransformer(data)
    ranked_df = tx.rank_by(value_field, top_n=top_n)

    rankings = ranked_df.to_dict("records")

    findings = []
    for i, row in enumerate(rankings[:5], 1):  # 상위 5개만 문장으로
        name = row.get(rank_field, "N/A")
        value = row.get(value_field, 0)
        findings.append(f"{i}위: {name} ({value:,.0f})")

    metrics = {
        "top_n": top_n,
        "total_count": len(ranked_df),
        "top_1": rankings[0] if rankings else None,
        "period": period,
    }

    return AnalysisResult(
        type="ranking",
        findings=findings,
        data=rankings,
        metrics=metrics,
        interpretation=f"상위 {top_n}개 순위 ({period} 기준)" if period else f"상위 {top_n}개 순위",
    )


def analyze_stats(
    data: List[Dict[str, Any]],
    value_field: str = "DT",
    group_by: Optional[str] = None,
) -> AnalysisResult:
    """
    기술 통계를 계산합니다.

    평균, 표준편차, 최소, 최대, 중앙값 등을 계산합니다.

    Args:
        data: 분석할 데이터
        value_field: 값 필드 (기본: "DT")
        group_by: 그룹별 통계 필드 (선택)

    Returns:
        AnalysisResult:
        - findings: 통계 요약 문장들
        - metrics: {
            "count", "mean", "std", "min", "max", "median"
          }
    """
    from .transform import KosisTransformer

    tx = KosisTransformer(data)
    stats_df = tx.get_summary_stats()

    if stats_df.empty:
        return AnalysisResult(
            type="stats",
            findings=["통계를 계산할 데이터가 없습니다."],
            data=None,
            metrics={},
            interpretation="통계를 계산할 데이터가 없습니다.",
        )

    stats = stats_df.iloc[0].to_dict()

    findings = [
        f"평균: {stats.get('mean', 0):,.0f}",
        f"중앙값: {stats.get('50%', 0):,.0f}",
        f"범위: {stats.get('min', 0):,.0f} ~ {stats.get('max', 0):,.0f}",
        f"표준편차: {stats.get('std', 0):,.0f}",
    ]

    metrics = {
        "count": int(stats.get("count", 0)),
        "mean": stats.get("mean", 0),
        "std": stats.get("std", 0),
        "min": stats.get("min", 0),
        "max": stats.get("max", 0),
        "median": stats.get("50%", 0),
        "q1": stats.get("25%", 0),
        "q3": stats.get("75%", 0),
    }

    return AnalysisResult(
        type="stats",
        findings=findings,
        data=stats_df.to_dict(),
        metrics=metrics,
        interpretation=f"총 {metrics['count']}건, 평균 {metrics['mean']:,.0f}",
    )


# =============================================================================
# Layer 3: PRESENT - 텍스트 생성 도구
# =============================================================================

def text_headline(
    analysis: Union[AnalysisResult, Dict[str, Any]],
    style: str = "news",
    focus: str = "main",
) -> ReportComponent:
    """
    헤드라인(한 줄 제목)을 생성합니다.

    분석 결과를 한 줄로 요약합니다.

    Args:
        analysis: 분석 결과 (AnalysisResult) 또는 데이터 dict
        style: 스타일
               - "news": 뉴스 헤드라인 (예: "서울 인구 3년 연속 감소")
               - "formal": 공식 (예: "서울시 인구 감소 추세 지속")
               - "casual": 캐주얼 (예: "서울 인구, 계속 줄어드네")
        focus: 강조점
               - "main": 주요 발견사항
               - "change": 변화/추세
               - "comparison": 비교 결과

    Returns:
        ReportComponent (type="text")

    Example:
        >>> trend = analyze_trend(data)
        >>> headline = text_headline(trend, style="news")
        >>> print(headline.summary)
        "서울 인구 4년간 5.2% 감소, 감소세 지속"
    """
    if isinstance(analysis, AnalysisResult):
        findings = analysis.findings
        metrics = analysis.metrics
        analysis_type = analysis.type
    else:
        findings = analysis.get("findings", [])
        metrics = analysis.get("metrics", {})
        analysis_type = analysis.get("type", "unknown")

    # 스타일별 템플릿
    headline = ""

    if analysis_type == "trend":
        direction = metrics.get("direction", "변화")
        change = metrics.get("total_change_pct", 0)
        cagr = metrics.get("cagr", 0)

        if style == "news":
            headline = f"{abs(change):.1f}% {direction}, 연평균 {abs(cagr):.1f}% 변화"
        elif style == "formal":
            headline = f"분석 기간 중 {direction} 추세 ({change:+.1f}%)"
        else:
            headline = f"{'올라감' if change > 0 else '내려감'} {abs(change):.1f}%"

    elif analysis_type == "comparison":
        max_info = metrics.get("max", {})
        gap = metrics.get("gap", 0)

        if style == "news":
            headline = f"{max_info.get('name', '1위')} 선두, 격차 {gap:,.0f}"
        else:
            headline = f"비교 결과: {max_info.get('name', '')}이 최대"

    elif analysis_type == "ranking":
        top_1 = metrics.get("top_1", {})
        if style == "news":
            headline = f"1위 {top_1.get('C1_NM', 'N/A')}"
        else:
            headline = f"순위 분석 결과"

    else:
        headline = findings[0] if findings else "분석 결과"

    html = f'''
    <h2 style="
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a2e;
        margin: 20px 0;
        line-height: 1.4;
    ">{headline}</h2>
    '''

    return ReportComponent(
        type="text",
        html=html,
        data={"headline": headline, "style": style},
        summary=headline,
        metadata={"text_type": "headline", "style": style},
        priority=5,
        tags=["text", "headline"],
    )


def text_summary(
    data: List[Dict[str, Any]],
    analysis: Optional[AnalysisResult] = None,
    max_sentences: int = 3,
) -> ReportComponent:
    """
    요약문(2-3문장)을 생성합니다.

    데이터의 핵심 내용을 간략히 설명합니다.

    Args:
        data: 원본 데이터
        analysis: 분석 결과 (있으면 활용)
        max_sentences: 최대 문장 수

    Returns:
        ReportComponent (type="text")
    """
    sentences = []

    # 기본 정보
    periods = get_available_values(data, "PRD_DE")
    regions = get_available_values(data, "C1_NM")

    if periods:
        sentences.append(f"본 데이터는 {periods[0]}부터 {periods[-1]}까지의 기간을 포함합니다.")

    if regions:
        sentences.append(f"총 {len(regions)}개 지역의 데이터가 포함되어 있습니다.")

    # 분석 결과 활용
    if analysis and analysis.findings:
        sentences.append(analysis.findings[0])

    summary_text = " ".join(sentences[:max_sentences])

    html = f'''
    <p style="
        font-size: 1rem;
        color: #4a4a4a;
        line-height: 1.8;
        margin: 15px 0;
    ">{summary_text}</p>
    '''

    return ReportComponent(
        type="text",
        html=html,
        data={"sentences": sentences},
        summary=summary_text,
        metadata={"text_type": "summary", "sentence_count": len(sentences)},
        priority=15,
        tags=["text", "summary"],
    )


def text_insight(
    analysis: AnalysisResult,
    depth: str = "standard",
    perspective: Optional[str] = None,
) -> ReportComponent:
    """
    인사이트(시사점)를 생성합니다.

    분석 결과의 의미와 시사점을 설명합니다.

    Args:
        analysis: 분석 결과
        depth: 깊이
               - "quick": 한 줄
               - "standard": 단락 (2-3문장)
               - "deep": 여러 단락
        perspective: 관점 (선택)
                     - "policy": 정책적
                     - "economic": 경제적
                     - "social": 사회적

    Returns:
        ReportComponent (type="text")
    """
    findings = analysis.findings
    metrics = analysis.metrics
    analysis_type = analysis.type

    insights = []

    # 분석 유형별 인사이트 생성
    if analysis_type == "trend":
        direction = metrics.get("direction", "")
        cagr = metrics.get("cagr", 0)

        if direction == "감소":
            insights.append(f"지속적인 감소 추세가 관찰됩니다 (연평균 {cagr:.1f}%).")
            if depth in ["standard", "deep"]:
                insights.append("이러한 추세가 지속될 경우 향후 정책적 대응이 필요할 수 있습니다.")
        elif direction == "증가":
            insights.append(f"꾸준한 증가 추세를 보이고 있습니다 (연평균 {cagr:.1f}%).")

    elif analysis_type == "comparison":
        gap = metrics.get("gap", 0)
        max_info = metrics.get("max", {})
        min_info = metrics.get("min", {})

        insights.append(
            f"{max_info.get('name', '')}과 {min_info.get('name', '')} 간 "
            f"상당한 격차({gap:,.0f})가 존재합니다."
        )

    elif analysis_type == "ranking":
        top_1 = metrics.get("top_1", {})
        insights.append(f"{top_1.get('C1_NM', '')}이 가장 높은 수치를 기록하고 있습니다.")

    # 관점별 추가 인사이트
    if perspective == "policy" and depth == "deep":
        insights.append("정책 입안 시 이러한 추세를 고려한 대응 방안 마련이 필요합니다.")
    elif perspective == "economic" and depth == "deep":
        insights.append("경제적 관점에서 자원 배분의 효율성 검토가 요구됩니다.")

    # 기존 findings 추가
    if depth == "deep":
        insights.extend(findings)

    insight_text = " ".join(insights)

    html = f'''
    <div style="
        background: linear-gradient(135deg, #f6f9fc 0%, #eef2f7 100%);
        border-left: 4px solid #667eea;
        padding: 20px;
        margin: 20px 0;
        border-radius: 0 8px 8px 0;
    ">
        <h4 style="color: #667eea; margin-bottom: 10px;">💡 인사이트</h4>
        <p style="color: #4a4a4a; line-height: 1.8; margin: 0;">
            {insight_text}
        </p>
    </div>
    '''

    return ReportComponent(
        type="text",
        html=html,
        data={"insights": insights, "depth": depth},
        summary=insights[0] if insights else "",
        metadata={"text_type": "insight", "depth": depth, "perspective": perspective},
        priority=60,
        tags=["text", "insight"],
    )


def text_data_note(
    data: List[Dict[str, Any]],
    source: str = "KOSIS (국가통계포털)",
    include_period: bool = True,
    caveats: Optional[List[str]] = None,
) -> ReportComponent:
    """
    데이터 주석(출처, 주의사항)을 생성합니다.

    Args:
        data: 원본 데이터
        source: 데이터 출처
        include_period: 기간 정보 포함 여부
        caveats: 주의사항 리스트

    Returns:
        ReportComponent (type="text")
    """
    notes = [f"출처: {source}"]

    if include_period:
        periods = get_available_values(data, "PRD_DE")
        if periods:
            notes.append(f"기간: {periods[0]} ~ {periods[-1]}")

    if caveats:
        notes.extend([f"※ {c}" for c in caveats])

    notes_text = " | ".join(notes)

    html = f'''
    <div style="
        font-size: 0.85rem;
        color: #888;
        margin-top: 30px;
        padding-top: 15px;
        border-top: 1px solid #eee;
    ">
        {notes_text}
    </div>
    '''

    return ReportComponent(
        type="text",
        html=html,
        data={"notes": notes},
        summary=notes_text,
        metadata={"text_type": "note", "source": source},
        priority=90,
        tags=["text", "note", "source"],
    )


# =============================================================================
# Layer 3: PRESENT - 레이아웃 도구
# =============================================================================

def layout_section(
    title: str,
    components: List[ReportComponent],
    icon: Optional[str] = None,
    collapsible: bool = False,
) -> ReportComponent:
    """
    섹션 컨테이너를 생성합니다.

    여러 구성요소를 논리적으로 그룹핑합니다.

    Args:
        title: 섹션 제목
        components: 포함할 구성요소 리스트
        icon: 아이콘 이모지
        collapsible: 접기/펼치기 가능 여부

    Returns:
        ReportComponent (type="section")
    """
    icon_html = f"{icon} " if icon else ""

    # 구성요소 정렬 (priority 기준)
    sorted_components = sorted(components, key=lambda c: c.priority)
    inner_html = "\n".join(c.html for c in sorted_components)

    html = f'''
    <div class="report-section" style="margin: 30px 0;">
        <h3 style="
            font-size: 1.3rem;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        ">{icon_html}{title}</h3>
        <div class="section-content">
            {inner_html}
        </div>
    </div>
    '''

    return ReportComponent(
        type="section",
        html=html,
        data={"title": title, "component_count": len(components)},
        summary=f"{title} 섹션 ({len(components)}개 요소)",
        metadata={"layout_type": "section"},
        priority=20,
        tags=["layout", "section"],
    )


def layout_card_grid(
    cards: List[ReportComponent],
    columns: int = 3,
) -> ReportComponent:
    """
    카드 그리드 레이아웃을 생성합니다.

    KPI 카드 여러 개를 나란히 배치합니다.

    Args:
        cards: KPI 카드 리스트
        columns: 열 수 (기본 3)

    Returns:
        ReportComponent (type="layout")
    """
    cards_html = "\n".join(c.html for c in cards)

    html = f'''
    <div style="
        display: grid;
        grid-template-columns: repeat({columns}, 1fr);
        gap: 20px;
        margin: 20px 0;
    ">
        {cards_html}
    </div>
    '''

    return ReportComponent(
        type="layout",
        html=html,
        data={"card_count": len(cards), "columns": columns},
        summary=f"{len(cards)}개 KPI 카드 그리드",
        metadata={"layout_type": "card_grid"},
        priority=15,
        tags=["layout", "grid", "cards"],
    )


def layout_two_column(
    left: ReportComponent,
    right: ReportComponent,
    ratio: str = "1:1",
) -> ReportComponent:
    """
    2단 레이아웃을 생성합니다.

    차트와 텍스트를 나란히 배치할 때 유용합니다.

    Args:
        left: 왼쪽 구성요소
        right: 오른쪽 구성요소
        ratio: 비율 ("1:1", "2:1", "1:2")

    Returns:
        ReportComponent (type="layout")
    """
    ratios = {"1:1": ("1fr", "1fr"), "2:1": ("2fr", "1fr"), "1:2": ("1fr", "2fr")}
    left_fr, right_fr = ratios.get(ratio, ("1fr", "1fr"))

    html = f'''
    <div style="
        display: grid;
        grid-template-columns: {left_fr} {right_fr};
        gap: 30px;
        margin: 20px 0;
        align-items: start;
    ">
        <div>{left.html}</div>
        <div>{right.html}</div>
    </div>
    '''

    return ReportComponent(
        type="layout",
        html=html,
        data={"ratio": ratio},
        summary=f"2단 레이아웃 ({ratio})",
        metadata={"layout_type": "two_column"},
        priority=25,
        tags=["layout", "two-column"],
    )


def layout_highlight_box(
    content: str,
    style: str = "info",
    title: Optional[str] = None,
) -> ReportComponent:
    """
    강조 박스를 생성합니다.

    중요한 내용을 눈에 띄게 표시합니다.

    Args:
        content: 박스 내용
        style: 스타일
               - "info": 파란색 (정보)
               - "warning": 노란색 (주의)
               - "success": 녹색 (긍정)
               - "danger": 빨간색 (경고)
        title: 박스 제목 (선택)

    Returns:
        ReportComponent (type="layout")
    """
    colors = {
        "info": {"bg": "#e7f3ff", "border": "#2196F3", "text": "#1565C0"},
        "warning": {"bg": "#fff8e1", "border": "#FFC107", "text": "#F57F17"},
        "success": {"bg": "#e8f5e9", "border": "#4CAF50", "text": "#2E7D32"},
        "danger": {"bg": "#ffebee", "border": "#F44336", "text": "#C62828"},
    }
    c = colors.get(style, colors["info"])

    title_html = f'<strong style="display: block; margin-bottom: 8px;">{title}</strong>' if title else ""

    html = f'''
    <div style="
        background: {c['bg']};
        border-left: 4px solid {c['border']};
        padding: 15px 20px;
        margin: 20px 0;
        border-radius: 0 8px 8px 0;
        color: {c['text']};
    ">
        {title_html}
        {content}
    </div>
    '''

    return ReportComponent(
        type="layout",
        html=html,
        data={"content": content, "style": style},
        summary=content[:50] + "..." if len(content) > 50 else content,
        metadata={"layout_type": "highlight_box", "style": style},
        priority=40,
        tags=["layout", "highlight"],
    )


def layout_table(
    data: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    column_labels: Optional[Dict[str, str]] = None,
    max_rows: int = 20,
    highlight_max: bool = False,
) -> ReportComponent:
    """
    데이터 테이블을 생성합니다.

    Args:
        data: 테이블 데이터
        columns: 표시할 열 목록 (None이면 전체)
        column_labels: 열 라벨 매핑 (예: {"C1_NM": "지역"})
        max_rows: 최대 행 수
        highlight_max: 최대값 강조 여부

    Returns:
        ReportComponent (type="table")
    """
    if not data:
        return ReportComponent(
            type="table",
            html="<p>데이터가 없습니다.</p>",
            data=None,
            summary="빈 테이블",
            priority=50,
            tags=["table"],
        )

    df = pd.DataFrame(data[:max_rows])

    if columns:
        df = df[[c for c in columns if c in df.columns]]

    if column_labels:
        df = df.rename(columns=column_labels)

    # 숫자 포맷팅
    for col in df.select_dtypes(include=["float64", "int64"]).columns:
        df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")

    table_html = df.to_html(index=False, classes="report-table", escape=False)

    html = f'''
    <div style="overflow-x: auto; margin: 20px 0;">
        <style>
            .report-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
            }}
            .report-table th {{
                background: #f8f9fa;
                padding: 12px;
                text-align: left;
                border-bottom: 2px solid #dee2e6;
                font-weight: 600;
            }}
            .report-table td {{
                padding: 10px 12px;
                border-bottom: 1px solid #eee;
            }}
            .report-table tr:hover {{
                background: #f8f9fa;
            }}
        </style>
        {table_html}
    </div>
    '''

    return ReportComponent(
        type="table",
        html=html,
        data=data[:max_rows],
        summary=f"{len(data[:max_rows])}행 테이블",
        metadata={"columns": list(df.columns), "row_count": len(df)},
        priority=50,
        tags=["table", "data"],
    )


# =============================================================================
# Layer 3: PRESENT - 리포트 조립
# =============================================================================

def assemble_report(
    components: List[ReportComponent],
    title: str = "KOSIS 데이터 분석 리포트",
    subtitle: Optional[str] = None,
    template: str = "standard",
    output_path: Optional[str] = None,
) -> str:
    """
    최종 HTML 리포트를 조립합니다.

    모든 구성요소를 결합하여 완전한 HTML 문서를 생성합니다.

    Args:
        components: 구성요소 리스트 (ReportComponent)
        title: 리포트 제목
        subtitle: 부제목 (선택)
        template: 템플릿 스타일
                  - "standard": 기본
                  - "dashboard": 대시보드
                  - "article": 기사형
                  - "minimal": 미니멀
        output_path: 저장 경로 (선택, None이면 HTML 문자열 반환)

    Returns:
        HTML 문자열 또는 저장 경로

    Example:
        >>> report = assemble_report(
        ...     [headline, chart, insight, note],
        ...     title="서울 인구 분석",
        ...     output_path="report.html"
        ... )
    """
    # 우선순위 정렬
    sorted_components = sorted(components, key=lambda c: c.priority)

    # 템플릿별 스타일
    template_styles = {
        "standard": {
            "bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "max_width": "1200px",
        },
        "dashboard": {
            "bg": "#1a1a2e",
            "max_width": "1400px",
        },
        "article": {
            "bg": "#f5f5f5",
            "max_width": "800px",
        },
        "minimal": {
            "bg": "#ffffff",
            "max_width": "900px",
        },
    }
    style = template_styles.get(template, template_styles["standard"])

    subtitle_html = f'<p style="color: rgba(255,255,255,0.8); font-size: 1.1rem;">{subtitle}</p>' if subtitle else ""

    components_html = "\n".join(c.html for c in sorted_components)

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
            background: {style['bg']};
            min-height: 100vh;
            padding: 30px 20px;
            color: #333;
        }}

        .container {{
            max-width: {style['max_width']};
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}

        .header h1 {{
            font-size: 2.2rem;
            margin-bottom: 10px;
        }}

        .content {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}

        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.7);
            margin-top: 30px;
            font-size: 0.85rem;
        }}

        .chart-container {{
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            {subtitle_html}
        </div>

        <div class="content">
            {components_html}
        </div>

        <div class="footer">
            <p>Generated by KOSIS Data Processor | {now}</p>
            <p>Data Source: <a href="https://kosis.kr" style="color: rgba(255,255,255,0.9);">KOSIS (국가통계포털)</a></p>
        </div>
    </div>
</body>
</html>
'''

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        logger.info(f"리포트 저장: {path}")
        return str(path)

    return html


# =============================================================================
# 편의 함수
# =============================================================================

def quick_report(
    data: List[Dict[str, Any]],
    title: str = "데이터 분석 리포트",
    output_path: Optional[str] = None,
) -> str:
    """
    빠른 리포트 생성 (원클릭).

    데이터만 넣으면 자동으로 분석하고 리포트를 생성합니다.

    Args:
        data: KOSIS 데이터
        title: 리포트 제목
        output_path: 저장 경로

    Returns:
        HTML 문자열 또는 저장 경로
    """
    components = []

    # 1. KPI 카드들
    from .transform import KosisTransformer
    tx = KosisTransformer(data)

    # 총 데이터 수
    components.append(viz_kpi_card(
        value=len(data),
        label="총 데이터",
        icon="📊"
    ))

    # 기간 수
    periods = get_available_values(data, "PRD_DE")
    if periods:
        components.append(viz_kpi_card(
            value=len(periods),
            label=f"기간 ({periods[0]}~{periods[-1]})",
            icon="📅"
        ))

    # 분류 수
    regions = get_available_values(data, "C1_NM")
    if regions:
        components.append(viz_kpi_card(
            value=len(regions),
            label="분류 항목",
            icon="📍"
        ))

    # 카드 그리드
    kpi_grid = layout_card_grid(components[:3], columns=3)

    # 2. 추이 차트
    trend_chart = viz_line_trend(data, title="추이 분석")

    # 3. 비교 차트
    bar_chart = viz_bar_comparison(data, title="항목별 비교", top_n=10)

    # 4. 분석
    trend_analysis = analyze_trend(data)
    insight = text_insight(trend_analysis)

    # 5. 데이터 노트
    note = text_data_note(data)

    # 조립
    all_components = [kpi_grid, trend_chart, bar_chart, insight, note]

    return assemble_report(
        all_components,
        title=title,
        output_path=output_path,
    )
