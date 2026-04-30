"""KOSIS 메타데이터 XLS → JSON 변환기.

XLS 파일들을 Pydantic 모델로 파싱하여 JSON으로 저장.
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from .metadata_models import (
    Category,
    CategoryTree,
    DataSource,
    Indicator,
    IndicatorList,
    IndicatorsFile,
    PeriodType,
    StatisticsTable,
    Survey,
    SurveysFile,
    TablesFile,
    TablesMetadata,
)

# 파일별 데이터 소스 매핑
FILE_SOURCE_MAP = {
    "주제별통계.xls": DataSource.SUBJECT,
    "기관별통계.xls": DataSource.ORGANIZATION,
    "국제통계.xls": DataSource.INTERNATIONAL,
    "북한통계.xls": DataSource.NORTH_KOREA,
    "지역통계_기관별.xls": DataSource.REGIONAL,
    "e-지방지표(주제별).xls": DataSource.LOCAL_INDICATOR,
}

# 8컬럼 파일들 (TBL_ID 포함)
EIGHT_COLUMN_FILES = [
    "주제별통계.xls",
    "기관별통계.xls",
    "국제통계.xls",
    "북한통계.xls",
    "e-지방지표(주제별).xls",
]

# 7컬럼 파일들 (TBL_ID 미포함)
SEVEN_COLUMN_FILES = ["지역통계_기관별.xls"]


def parse_period(
    period_str: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[PeriodType]]:
    """수록기간 문자열 파싱.

    Args:
        period_str: "년 (2000 ~ 2024)" 또는 "월 (200801 ~ 202411)" 형식

    Returns:
        (start, end, period_type) 튜플
    """
    if pd.isna(period_str) or not period_str:
        return None, None, None

    period_str = str(period_str).strip()

    # 주기 추출
    period_type = None
    if period_str.startswith("년"):
        period_type = PeriodType.YEAR
    elif period_str.startswith("월"):
        period_type = PeriodType.MONTH
    elif period_str.startswith("분기"):
        period_type = PeriodType.QUARTER
    elif period_str.startswith("반기"):
        period_type = PeriodType.HALF

    # 기간 추출 (괄호 안의 숫자)
    match = re.search(r"\((\d+)\s*~\s*(\d+)\)", period_str)
    if match:
        return match.group(1), match.group(2), period_type

    return None, None, period_type


def parse_path_ids(path_id_str: Optional[str]) -> list[str]:
    """경로 ID 문자열 파싱.

    Args:
        path_id_str: "> 101 > 101_001 > " 형식

    Returns:
        ["101", "101_001"] 리스트
    """
    if pd.isna(path_id_str) or not path_id_str:
        return []

    # > 로 분리하고 빈 문자열 제거
    parts = [p.strip() for p in str(path_id_str).split(">")]
    return [p for p in parts if p]


def extract_list_id(path_ids: list[str]) -> Optional[str]:
    """경로 ID에서 LIST_ID 추출.

    Args:
        path_ids: ["101", "101_001"] 형식

    Returns:
        마지막 ID 또는 None
    """
    if not path_ids:
        return None
    return path_ids[-1] if path_ids else None


def generate_keywords(name: str, path: str, source: Optional[str]) -> list[str]:
    """검색 키워드 생성.

    Args:
        name: 통계표명
        path: 경로
        source: 출처

    Returns:
        키워드 리스트
    """
    keywords = set()

    # 이름에서 키워드 추출 (괄호 내용 포함)
    # 예: "고령인구비율(시도/시/군/구)" -> ["고령인구비율", "시도", "시", "군", "구"]
    name_parts = re.split(r"[()/_,\s]+", name)
    keywords.update(p for p in name_parts if len(p) >= 2)

    # 경로에서 키워드 추출
    if path:
        path_parts = re.split(r"[>()/_,\s]+", path)
        keywords.update(p for p in path_parts if len(p) >= 2)

    # 출처에서 키워드 추출
    if source and not pd.isna(source):
        source_parts = re.split(r"[「」()/_,\s]+", str(source))
        keywords.update(p for p in source_parts if len(p) >= 2)

    # 불용어 제거
    stopwords = {"통계표", "보기", "출처", "수록기간", "Level", "NaN", "nan"}
    keywords = keywords - stopwords

    return sorted(keywords)


def clean_value(val) -> Optional[str]:
    """값 정제 (NaN 처리)."""
    if pd.isna(val):
        return None
    return str(val).strip() if val else None


def parse_statistics_file(
    filepath: Path,
    data_source: DataSource,
    has_tbl_id: bool = True,
    include_categories: bool = False,
) -> tuple[list[StatisticsTable], list[Category]]:
    """통계표 XLS 파일 파싱.

    Args:
        filepath: XLS 파일 경로
        data_source: 데이터 출처
        has_tbl_id: TBL_ID 컬럼 포함 여부
        include_categories: TBL_ID 없는 카테고리 행 포함 여부

    Returns:
        (StatisticsTable 리스트, Category 리스트) 튜플
    """
    tables = []
    categories = []

    xl = pd.ExcelFile(filepath)
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name, header=None, skiprows=3)

        # 컬럼 설정
        if has_tbl_id and len(df.columns) >= 8:
            df.columns = [
                "Level",
                "통계명",
                "통계표조회",
                "출처",
                "수록기간",
                "경로",
                "경로(LIST_ID)",
                "통계표_아이디(TBL_ID)",
            ]
        elif len(df.columns) >= 7:
            df.columns = [
                "Level",
                "통계명",
                "통계표조회",
                "출처",
                "수록기간",
                "경로",
                "경로(LIST_ID)",
            ]
            df["통계표_아이디(TBL_ID)"] = None
        else:
            continue

        for _, row in df.iterrows():
            # 헤더 행 스킵
            if row["Level"] == "Level":
                continue

            # TBL_ID 확인
            tbl_id = clean_value(row.get("통계표_아이디(TBL_ID)"))
            name = clean_value(row["통계명"])

            # 필수 필드 검증
            if not name:
                continue

            # Level 파싱
            try:
                level_int = int(row["Level"])
            except (ValueError, TypeError):
                continue

            # 경로 ID 파싱
            path_ids = parse_path_ids(row.get("경로(LIST_ID)"))
            path = clean_value(row.get("경로")) or ""

            # TBL_ID가 없는 경우 (카테고리 행)
            if not tbl_id:
                if include_categories and path_ids:
                    cat_id = "-".join(path_ids)
                    parent_id = "-".join(path_ids[:-1]) if len(path_ids) > 1 else None
                    category = Category(
                        id=cat_id,
                        name=name,
                        level=level_int,
                        parent_id=parent_id,
                        path=path,
                        path_ids=path_ids,
                    )
                    categories.append(category)
                continue  # 테이블에는 추가하지 않음

            # 기간 파싱
            period_start, period_end, period_type = parse_period(row.get("수록기간"))

            # 키워드 생성
            source = clean_value(row.get("출처"))
            keywords = generate_keywords(name, path, source)

            table = StatisticsTable(
                tbl_id=tbl_id,
                name=name,
                source=source,
                data_source=data_source,
                level=level_int,
                path=path,
                path_ids=path_ids,
                list_id=extract_list_id(path_ids),
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                keywords=keywords,
            )
            tables.append(table)

    return tables, categories


def parse_indicators_file(filepath: Path) -> IndicatorsFile:
    """OpenAPI 지표 코드표 파싱.

    Args:
        filepath: OpenAPICodeList.xls 경로

    Returns:
        IndicatorsFile
    """
    indicators = []
    list_ids = []

    xl = pd.ExcelFile(filepath)

    # 지표명 및 지표ID 코드표
    if "지표명 및 지표ID 코드표" in xl.sheet_names:
        df = pd.read_excel(
            xl, sheet_name="지표명 및 지표ID 코드표", header=None, skiprows=3
        )
        df.columns = [
            "_",
            "순번",
            "부문",
            "세부부문",
            "세부지표명",
            "지표ID",
            "지역구분",
            "수록시작",
            "수록종료",
            "수록주기",
            "설명자료유무",
        ]

        for _, row in df.iterrows():
            if row["순번"] == "순번":  # 헤더 스킵
                continue

            indicator_id = clean_value(row["지표ID"])
            name = clean_value(row["세부지표명"])

            if not indicator_id or not name:
                continue

            # 주기 변환
            period_type = None
            cycle = clean_value(row["수록주기"])
            if cycle == "Y":
                period_type = PeriodType.YEAR
            elif cycle == "M":
                period_type = PeriodType.MONTH
            elif cycle == "Q":
                period_type = PeriodType.QUARTER

            indicator = Indicator(
                indicator_id=indicator_id,
                name=name,
                sector=clean_value(row["부문"]) or "",
                sub_sector=clean_value(row["세부부문"]) or "",
                region_type=clean_value(row["지역구분"]) or "",
                period_start=clean_value(row["수록시작"]),
                period_end=clean_value(row["수록종료"]),
                period_type=period_type,
                has_explanation=row["설명자료유무"] == "T",
            )
            indicators.append(indicator)

    # 목록ID 코드표
    if "목록ID 코드표" in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name="목록ID 코드표", header=None, skiprows=3)
        df.columns = ["_", "대분류", "중분류", "목록ID"]

        current_major = None
        for _, row in df.iterrows():
            if row["대분류"] == "대분류":  # 헤더 스킵
                continue

            major = clean_value(row["대분류"])
            if major:
                current_major = major

            list_id = clean_value(row["목록ID"])
            if not list_id:
                continue

            item = IndicatorList(
                list_id=list_id,
                major_category=current_major or "",
                minor_category=clean_value(row["중분류"]),
            )
            list_ids.append(item)

    return IndicatorsFile(indicators=indicators, list_ids=list_ids)


def parse_surveys_file(filepath: Path) -> SurveysFile:
    """통계설명자료 파싱.

    Args:
        filepath: 통계설명자료(조사).xls 경로

    Returns:
        SurveysFile
    """
    surveys = []
    by_org: dict[str, list[str]] = {}

    df = pd.read_excel(filepath, sheet_name="Sheet1", header=None, skiprows=2)
    df.columns = ["기관명", "조사명"]

    for _, row in df.iterrows():
        org = clean_value(row["기관명"])
        survey = clean_value(row["조사명"])

        if not org or not survey or org == "기관명":
            continue

        # 정규화
        org_norm = org.replace(" ", "").lower()
        survey_norm = survey.replace(" ", "").lower()

        surveys.append(
            Survey(
                organization=org,
                survey_name=survey,
                org_normalized=org_norm,
                survey_normalized=survey_norm,
            )
        )

        # 기관별 그룹화
        if org not in by_org:
            by_org[org] = []
        by_org[org].append(survey)

    return SurveysFile(surveys=surveys, by_organization=by_org)


def build_category_tree(tables: list[StatisticsTable]) -> CategoryTree:
    """통계표 목록에서 카테고리 트리 생성.

    Args:
        tables: 통계표 리스트

    Returns:
        CategoryTree
    """
    categories_by_source: dict[DataSource, dict[str, Category]] = {
        source: {} for source in DataSource
    }

    for table in tables:
        if not table.path:
            continue

        # 경로를 레벨별로 분해
        path_parts = [p.strip() for p in table.path.split(">")]

        for i, part in enumerate(path_parts):
            level = i + 1
            cat_id = (
                "_".join(table.path_ids[: i + 1])
                if i < len(table.path_ids)
                else f"cat_{i}"
            )
            parent_id = (
                "_".join(table.path_ids[:i])
                if i > 0 and i <= len(table.path_ids)
                else None
            )

            if cat_id not in categories_by_source[table.data_source]:
                categories_by_source[table.data_source][cat_id] = Category(
                    id=cat_id,
                    name=part,
                    level=level,
                    parent_id=parent_id,
                    path=" > ".join(path_parts[: i + 1]),
                    path_ids=table.path_ids[: i + 1] if i < len(table.path_ids) else [],
                )

            # 카운트 업데이트
            if level < len(path_parts):
                categories_by_source[table.data_source][cat_id].children_count += 1
            if not table.tbl_id.startswith("CAT_"):
                categories_by_source[table.data_source][cat_id].tables_count += 1

    return CategoryTree(
        subject=list(categories_by_source[DataSource.SUBJECT].values()),
        organization=list(categories_by_source[DataSource.ORGANIZATION].values()),
        international=list(categories_by_source[DataSource.INTERNATIONAL].values()),
        north_korea=list(categories_by_source[DataSource.NORTH_KOREA].values()),
        local_indicator=list(categories_by_source[DataSource.LOCAL_INDICATOR].values()),
    )


def convert_all(
    input_dir: Path,
    output_dir: Path,
    include_regional: bool = True,
    deduplicate: bool = True,
    include_categories: bool = True,
) -> dict:
    """모든 XLS 파일을 JSON으로 변환.

    Args:
        input_dir: XLS 파일 디렉토리
        output_dir: JSON 출력 디렉토리
        include_regional: 지역통계 포함 여부
        deduplicate: 중복 TBL_ID 제거 여부
        include_categories: 카테고리 행 추출 여부

    Returns:
        변환 결과 통계
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_tables: list[StatisticsTable] = []
    all_categories: list[Category] = []
    source_counts: dict[str, int] = {}

    # 8컬럼 파일 처리
    for filename in EIGHT_COLUMN_FILES:
        filepath = input_dir / filename
        if not filepath.exists():
            continue

        data_source = FILE_SOURCE_MAP[filename]
        tables, categories = parse_statistics_file(
            filepath,
            data_source,
            has_tbl_id=True,
            include_categories=include_categories,
        )
        all_tables.extend(tables)
        all_categories.extend(categories)
        source_counts[data_source.value] = len(tables)
        print(f"Parsed {filename}: {len(tables)} tables, {len(categories)} categories")

    # 7컬럼 파일 처리 (지역통계)
    if include_regional:
        for filename in SEVEN_COLUMN_FILES:
            filepath = input_dir / filename
            if not filepath.exists():
                continue

            data_source = FILE_SOURCE_MAP[filename]
            tables, categories = parse_statistics_file(
                filepath,
                data_source,
                has_tbl_id=False,
                include_categories=include_categories,
            )
            all_tables.extend(tables)
            all_categories.extend(categories)
            source_counts[data_source.value] = len(tables)
            print(
                f"Parsed {filename}: {len(tables)} tables, {len(categories)} categories"
            )

    # 중복 제거 (TBL_ID 기준, 첫 번째 것 유지)
    if deduplicate:
        seen_tbl_ids: set[str] = set()
        unique_tables: list[StatisticsTable] = []
        duplicates_removed = 0

        for table in all_tables:
            if table.tbl_id not in seen_tbl_ids:
                seen_tbl_ids.add(table.tbl_id)
                unique_tables.append(table)
            else:
                duplicates_removed += 1

        print(f"Deduplicated: removed {duplicates_removed} duplicates")
        all_tables = unique_tables

        # source_counts 재계산
        source_counts = {}
        for table in all_tables:
            src = (
                table.data_source.value
                if hasattr(table.data_source, "value")
                else table.data_source
            )
            source_counts[src] = source_counts.get(src, 0) + 1

    # tables.json 저장 (실제 통계표만)
    tables_file = TablesFile(
        tables=all_tables,
        metadata=TablesMetadata(
            version=date.today().isoformat(),
            total_count=len(all_tables),
            sources=source_counts,
        ),
    )

    with open(output_dir / "tables.json", "w", encoding="utf-8") as f:
        json.dump(tables_file.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"Saved tables.json: {len(all_tables)} tables (실제 통계표만)")

    # categories.json 저장 (XLS에서 직접 추출한 카테고리 + 경로 기반 트리)
    # XLS 카테고리 중복 제거
    seen_cat_ids: set[str] = set()
    unique_categories = []
    for cat in all_categories:
        if cat.id not in seen_cat_ids:
            seen_cat_ids.add(cat.id)
            unique_categories.append(cat)

    # 경로 기반 트리 생성 (테이블에서)
    category_tree = build_category_tree(all_tables)

    # XLS 카테고리를 트리에 추가 (data_source 구분은 경로로 추정)
    # 여기서는 간단히 subject에 추가
    category_tree.subject.extend(unique_categories)

    with open(output_dir / "categories.json", "w", encoding="utf-8") as f:
        json.dump(category_tree.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"Saved categories.json: {len(unique_categories)} categories from XLS")

    # indicators.json 저장
    for filename in [
        "OpenAPICodeList.xls",
        "OpenAPI 지표명 및 지표ID 코드표 (2025년 12월 14일).xls",
    ]:
        filepath = input_dir / filename
        if filepath.exists():
            indicators_file = parse_indicators_file(filepath)
            with open(output_dir / "indicators.json", "w", encoding="utf-8") as f:
                json.dump(indicators_file.model_dump(), f, ensure_ascii=False, indent=2)
            print(
                f"Saved indicators.json: {len(indicators_file.indicators)} indicators"
            )
            break

    # surveys.json 저장
    surveys_path = input_dir / "통계설명자료(조사).xls"
    if surveys_path.exists():
        surveys_file = parse_surveys_file(surveys_path)
        with open(output_dir / "surveys.json", "w", encoding="utf-8") as f:
            json.dump(surveys_file.model_dump(), f, ensure_ascii=False, indent=2)
        print(f"Saved surveys.json: {len(surveys_file.surveys)} surveys")

    return {
        "total_tables": len(all_tables),
        "source_counts": source_counts,
    }


if __name__ == "__main__":
    # CLI 실행
    input_dir = Path("data/metadata_files")
    output_dir = Path("data/metadata")

    result = convert_all(input_dir, output_dir)
    print(f"\nConversion complete: {result}")
