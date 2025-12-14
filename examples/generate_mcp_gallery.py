#!/usr/bin/env python3
"""
MCP 패턴 기반 아티팩트 갤러리 생성.

다양한 KOSIS 데이터 카테고리에 대해 풍부한 HTML 리포트를 생성합니다.
모의 데이터를 사용하여 API 키 없이도 실행 가능합니다.

사용법:
    uv run python examples/generate_mcp_gallery.py
    uv run python examples/generate_mcp_gallery.py --category population
    uv run python examples/generate_mcp_gallery.py --live  # 실제 API 사용
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools.report_tools import (
    ReportComponent,
    viz_line_trend,
    viz_bar_comparison,
    viz_kpi_card,
    viz_pie_composition,
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    text_insight,
    text_data_note,
    layout_card_grid,
    layout_table,
    assemble_report,
    filter_data,
    aggregate_data,
)

# API 키 확인
USE_LIVE_API = bool(os.environ.get("KOSIS_API_KEY"))

# 출력 디렉토리
OUTPUT_DIR = Path(__file__).parent / "gallery" / "mcp_artifacts"


# =============================================================================
# 데이터 카테고리 정의
# =============================================================================

@dataclass
class DataCategory:
    """데이터 카테고리 정의."""
    id: str
    name: str
    icon: str
    description: str
    org_id: str
    tbl_id: str
    period_type: str  # Y, M, Q
    start_period: str
    end_period: str
    mock_generator: str  # 모의 데이터 생성기 이름
    analyses: List[str]  # 수행할 분석 유형


CATEGORIES = {
    # =========================================
    # A. 인구/가구
    # =========================================
    "pop_region": DataCategory(
        id="pop_region",
        name="시도별 인구 현황",
        icon="👥",
        description="전국 17개 시도의 인구 현황 및 변화 추이",
        org_id="101",
        tbl_id="DT_1B040A3",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="population_by_region",
        analyses=["trend", "comparison", "ranking"],
    ),
    "pop_age": DataCategory(
        id="pop_age",
        name="연령별 인구 구조",
        icon="👶👴",
        description="연령대별 인구 분포 및 고령화 추이",
        org_id="101",
        tbl_id="DT_1B040A5",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="population_by_age",
        analyses=["trend", "composition", "comparison"],
    ),
    "household": DataCategory(
        id="household",
        name="가구 현황",
        icon="🏠",
        description="가구 수 및 가구원 수 변화",
        org_id="101",
        tbl_id="DT_1B040B1",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="household",
        analyses=["trend", "comparison"],
    ),

    # =========================================
    # B. 경제/물가
    # =========================================
    "cpi_monthly": DataCategory(
        id="cpi_monthly",
        name="월별 소비자물가지수",
        icon="💰",
        description="2024년 월별 소비자물가지수 추이",
        org_id="101",
        tbl_id="DT_1J22001",
        period_type="M",
        start_period="202401",
        end_period="202412",
        mock_generator="cpi_monthly",
        analyses=["trend", "stats"],
    ),
    "cpi_category": DataCategory(
        id="cpi_category",
        name="품목별 물가지수",
        icon="🛒",
        description="품목별 소비자물가지수 비교",
        org_id="101",
        tbl_id="DT_1J22002",
        period_type="M",
        start_period="202401",
        end_period="202412",
        mock_generator="cpi_by_category",
        analyses=["comparison", "ranking"],
    ),
    "gdp": DataCategory(
        id="gdp",
        name="국내총생산(GDP)",
        icon="📈",
        description="연도별 GDP 및 경제성장률",
        org_id="101",
        tbl_id="DT_2KAA902",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="gdp",
        analyses=["trend", "stats"],
    ),

    # =========================================
    # C. 노동/고용
    # =========================================
    "employment": DataCategory(
        id="employment",
        name="고용률 추이",
        icon="💼",
        description="연도별 고용률 및 취업자 현황",
        org_id="101",
        tbl_id="DT_1ES2A01",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="employment",
        analyses=["trend", "comparison"],
    ),
    "unemployment": DataCategory(
        id="unemployment",
        name="실업률 현황",
        icon="📉",
        description="연도별/연령별 실업률 추이",
        org_id="101",
        tbl_id="DT_1ES2B01",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="unemployment",
        analyses=["trend", "comparison", "ranking"],
    ),
    "wage": DataCategory(
        id="wage",
        name="임금 현황",
        icon="💵",
        description="산업별 평균 임금 비교",
        org_id="101",
        tbl_id="DT_1ES3A01",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="wage",
        analyses=["trend", "comparison", "ranking"],
    ),

    # =========================================
    # D. 산업/기업
    # =========================================
    "industry_production": DataCategory(
        id="industry_production",
        name="제조업 생산지수",
        icon="🏭",
        description="제조업 생산지수 월별 추이",
        org_id="101",
        tbl_id="DT_1C84001",
        period_type="M",
        start_period="202401",
        end_period="202412",
        mock_generator="industry_production",
        analyses=["trend", "stats"],
    ),
    "business_count": DataCategory(
        id="business_count",
        name="사업체 현황",
        icon="🏢",
        description="산업별 사업체 수 및 종사자 수",
        org_id="101",
        tbl_id="DT_1K52B01",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="business_count",
        analyses=["trend", "comparison", "ranking"],
    ),

    # =========================================
    # E. 무역/수출입
    # =========================================
    "export_import": DataCategory(
        id="export_import",
        name="수출입 현황",
        icon="🚢",
        description="연도별 수출입 규모 및 무역수지",
        org_id="101",
        tbl_id="DT_1F12001",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="export_import",
        analyses=["trend", "comparison"],
    ),
    "export_by_country": DataCategory(
        id="export_by_country",
        name="국가별 수출",
        icon="🌍",
        description="주요 수출국별 수출액 비교",
        org_id="101",
        tbl_id="DT_1F12002",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="export_by_country",
        analyses=["comparison", "ranking", "composition"],
    ),

    # =========================================
    # F. 주거/건설
    # =========================================
    "housing_price": DataCategory(
        id="housing_price",
        name="주택가격 동향",
        icon="🏘️",
        description="지역별 주택가격지수 추이",
        org_id="101",
        tbl_id="DT_1J2A001",
        period_type="M",
        start_period="202401",
        end_period="202412",
        mock_generator="housing_price",
        analyses=["trend", "comparison", "ranking"],
    ),
    "construction": DataCategory(
        id="construction",
        name="건설투자 현황",
        icon="🏗️",
        description="건설투자 및 건축허가 추이",
        org_id="101",
        tbl_id="DT_1J2B001",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="construction",
        analyses=["trend", "stats"],
    ),

    # =========================================
    # G. 교육/문화
    # =========================================
    "education": DataCategory(
        id="education",
        name="학생 수 현황",
        icon="🎓",
        description="학교급별 학생 수 추이",
        org_id="101",
        tbl_id="DT_1B8A001",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="education",
        analyses=["trend", "comparison", "composition"],
    ),

    # =========================================
    # H. 보건/복지
    # =========================================
    "healthcare": DataCategory(
        id="healthcare",
        name="의료시설 현황",
        icon="🏥",
        description="지역별 의료시설 및 의료인력",
        org_id="101",
        tbl_id="DT_1Y7A001",
        period_type="Y",
        start_period="2019",
        end_period="2023",
        mock_generator="healthcare",
        analyses=["trend", "comparison", "ranking"],
    ),
}


# =============================================================================
# 모의 데이터 생성기
# =============================================================================

class MockDataGenerator:
    """모의 데이터 생성기."""

    REGIONS = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
        "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원도",
        "충청북도", "충청남도", "전라북도", "전라남도", "경상북도",
        "경상남도", "제주특별자치도",
    ]

    MONTHS_2024 = [f"2024{m:02d}" for m in range(1, 13)]
    YEARS = ["2019", "2020", "2021", "2022", "2023"]

    @classmethod
    def population_by_region(cls, cat: DataCategory) -> List[Dict]:
        """시도별 인구 데이터."""
        base_pop = {
            "서울특별시": 9411000, "부산광역시": 3314000, "대구광역시": 2357000,
            "인천광역시": 2978000, "광주광역시": 1433000, "대전광역시": 1445000,
            "울산광역시": 1106000, "세종특별자치시": 387000, "경기도": 13639000,
            "강원도": 1525000, "충청북도": 1598000, "충청남도": 2125000,
            "전라북도": 1763000, "전라남도": 1815000, "경상북도": 2597000,
            "경상남도": 3273000, "제주특별자치도": 674000,
        }
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for region in cls.REGIONS:
                pop = base_pop.get(region, 1000000)
                # 연도별 변동: 수도권 증가, 지방 감소 트렌드
                if region in ["경기도", "인천광역시", "세종특별자치시"]:
                    variation = 1 + year_idx * 0.015
                elif region in ["서울특별시"]:
                    variation = 1 - year_idx * 0.005
                else:
                    variation = 1 - year_idx * 0.008
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": region,
                    "ITM_NM": "총인구",
                    "DT": str(int(pop * variation)),
                    "UNIT_NM": "명",
                })
        return records

    @classmethod
    def population_by_age(cls, cat: DataCategory) -> List[Dict]:
        """연령별 인구 데이터."""
        age_groups = ["0-9세", "10-19세", "20-29세", "30-39세", "40-49세",
                      "50-59세", "60-69세", "70-79세", "80세 이상"]
        base_pop = [4200000, 4800000, 6500000, 6800000, 8100000,
                    8700000, 7200000, 4500000, 2300000]
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for i, age in enumerate(age_groups):
                # 고령화 트렌드
                if i >= 6:  # 60세 이상
                    variation = 1 + year_idx * 0.03
                elif i <= 2:  # 30세 미만
                    variation = 1 - year_idx * 0.02
                else:
                    variation = 1 - year_idx * 0.005
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": age,
                    "ITM_NM": "인구수",
                    "DT": str(int(base_pop[i] * variation)),
                    "UNIT_NM": "명",
                })
        return records

    @classmethod
    def household(cls, cat: DataCategory) -> List[Dict]:
        """가구 현황 데이터."""
        records = []
        base_household = 21000000
        base_person_per_hh = 2.37
        for year_idx, year in enumerate(cls.YEARS):
            # 1인 가구 증가 트렌드
            hh = int(base_household * (1 + year_idx * 0.015))
            ppd = round(base_person_per_hh - year_idx * 0.03, 2)
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "가구수",
                "DT": str(hh),
                "UNIT_NM": "가구",
            })
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "평균가구원수",
                "DT": str(ppd),
                "UNIT_NM": "명",
            })
        return records

    @classmethod
    def cpi_monthly(cls, cat: DataCategory) -> List[Dict]:
        """월별 소비자물가지수."""
        records = []
        base_cpi = 110.0
        for month_idx, month in enumerate(cls.MONTHS_2024):
            # 월별 변동 (계절성 + 상승 트렌드)
            seasonal = 0.5 * (1 if month_idx in [0, 1, 6, 7] else -0.5)
            cpi = base_cpi + month_idx * 0.3 + seasonal + random.uniform(-0.2, 0.2)
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": month,
                "C1_NM": "총지수",
                "ITM_NM": "소비자물가지수",
                "DT": f"{cpi:.1f}",
                "UNIT_NM": "2020=100",
            })
        return records

    @classmethod
    def cpi_by_category(cls, cat: DataCategory) -> List[Dict]:
        """품목별 물가지수."""
        categories = {
            "식료품": 115.2, "주거": 108.5, "교통": 112.8,
            "통신": 101.2, "교육": 106.3, "의료": 109.7,
            "의류": 104.5, "오락문화": 107.1,
        }
        records = []
        for month in cls.MONTHS_2024[-3:]:  # 최근 3개월만
            for cat_name, base_val in categories.items():
                val = base_val + random.uniform(-1, 2)
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": "품목별 물가지수",
                    "PRD_DE": month,
                    "C1_NM": cat_name,
                    "ITM_NM": "물가지수",
                    "DT": f"{val:.1f}",
                    "UNIT_NM": "2020=100",
                })
        return records

    @classmethod
    def gdp(cls, cat: DataCategory) -> List[Dict]:
        """GDP 데이터."""
        gdp_values = [1924, 1940, 2080, 2161, 2236]  # 조원
        growth_rates = [2.2, -0.7, 4.3, 2.6, 1.4]  # %
        records = []
        for i, year in enumerate(cls.YEARS):
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "국내총생산",
                "DT": str(int(gdp_values[i] * 1000)),
                "UNIT_NM": "십억원",
            })
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "경제성장률",
                "DT": str(growth_rates[i]),
                "UNIT_NM": "%",
            })
        return records

    @classmethod
    def employment(cls, cat: DataCategory) -> List[Dict]:
        """고용 데이터."""
        emp_rates = [60.9, 60.1, 60.5, 62.1, 62.6]
        employed = [27123, 26904, 27273, 28089, 28423]  # 천명
        records = []
        for i, year in enumerate(cls.YEARS):
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "고용률",
                "DT": str(emp_rates[i]),
                "UNIT_NM": "%",
            })
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "취업자수",
                "DT": str(employed[i] * 1000),
                "UNIT_NM": "명",
            })
        return records

    @classmethod
    def unemployment(cls, cat: DataCategory) -> List[Dict]:
        """실업률 데이터."""
        age_groups = ["15-29세", "30-39세", "40-49세", "50-59세", "60세 이상"]
        base_rates = [8.9, 3.2, 2.1, 2.5, 3.1]
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for i, age in enumerate(age_groups):
                # COVID 영향: 2020년 상승, 이후 회복
                if year == "2020":
                    rate = base_rates[i] * 1.15
                elif year == "2021":
                    rate = base_rates[i] * 1.05
                else:
                    rate = base_rates[i] * (1 - year_idx * 0.02)
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": age,
                    "ITM_NM": "실업률",
                    "DT": f"{rate:.1f}",
                    "UNIT_NM": "%",
                })
        return records

    @classmethod
    def wage(cls, cat: DataCategory) -> List[Dict]:
        """임금 데이터."""
        industries = {
            "제조업": 4200, "건설업": 3800, "금융보험업": 6500,
            "정보통신업": 5800, "도소매업": 3200, "숙박음식업": 2400,
            "교육서비스업": 4100, "보건복지업": 3500,
        }
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for ind, base_wage in industries.items():
                wage = int(base_wage * (1 + year_idx * 0.035))
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": ind,
                    "ITM_NM": "월평균임금",
                    "DT": str(wage * 1000),
                    "UNIT_NM": "원",
                })
        return records

    @classmethod
    def industry_production(cls, cat: DataCategory) -> List[Dict]:
        """제조업 생산지수."""
        records = []
        base_idx = 108.0
        for month_idx, month in enumerate(cls.MONTHS_2024):
            # 계절 변동 + 성장 트렌드
            seasonal = 3 * (1 if month_idx in [2, 3, 9, 10] else -1)
            idx = base_idx + month_idx * 0.5 + seasonal + random.uniform(-2, 2)
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": month,
                "C1_NM": "제조업",
                "ITM_NM": "생산지수",
                "DT": f"{idx:.1f}",
                "UNIT_NM": "2020=100",
            })
        return records

    @classmethod
    def business_count(cls, cat: DataCategory) -> List[Dict]:
        """사업체 현황."""
        industries = {
            "제조업": 420000, "건설업": 180000, "도소매업": 890000,
            "숙박음식업": 750000, "정보통신업": 95000, "금융보험업": 45000,
        }
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for ind, base_count in industries.items():
                count = int(base_count * (1 + year_idx * 0.02 + random.uniform(-0.01, 0.01)))
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": ind,
                    "ITM_NM": "사업체수",
                    "DT": str(count),
                    "UNIT_NM": "개",
                })
        return records

    @classmethod
    def export_import(cls, cat: DataCategory) -> List[Dict]:
        """수출입 현황."""
        exports = [542233, 512498, 644400, 683585, 632695]  # 백만달러
        imports = [503343, 467633, 615093, 731370, 642674]
        records = []
        for i, year in enumerate(cls.YEARS):
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "수출",
                "DT": str(exports[i]),
                "UNIT_NM": "백만달러",
            })
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "수입",
                "DT": str(imports[i]),
                "UNIT_NM": "백만달러",
            })
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "무역수지",
                "DT": str(exports[i] - imports[i]),
                "UNIT_NM": "백만달러",
            })
        return records

    @classmethod
    def export_by_country(cls, cat: DataCategory) -> List[Dict]:
        """국가별 수출."""
        countries = {
            "중국": 162125, "미국": 115678, "베트남": 60234,
            "일본": 30456, "홍콩": 32145, "대만": 21234,
            "인도": 18765, "싱가포르": 15234, "독일": 12345, "멕시코": 11234,
        }
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for country, base_val in countries.items():
                val = int(base_val * (1 + year_idx * 0.05 + random.uniform(-0.05, 0.05)))
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": country,
                    "ITM_NM": "수출액",
                    "DT": str(val),
                    "UNIT_NM": "백만달러",
                })
        return records

    @classmethod
    def housing_price(cls, cat: DataCategory) -> List[Dict]:
        """주택가격지수."""
        regions = ["서울", "경기", "인천", "부산", "대구", "광주", "대전"]
        base_idx = {"서울": 115, "경기": 112, "인천": 108, "부산": 105,
                    "대구": 103, "광주": 102, "대전": 104}
        records = []
        for month_idx, month in enumerate(cls.MONTHS_2024):
            for region in regions:
                idx = base_idx[region] + month_idx * 0.3 + random.uniform(-0.5, 0.5)
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": month,
                    "C1_NM": region,
                    "ITM_NM": "주택가격지수",
                    "DT": f"{idx:.1f}",
                    "UNIT_NM": "2021.6=100",
                })
        return records

    @classmethod
    def construction(cls, cat: DataCategory) -> List[Dict]:
        """건설투자."""
        values = [195000, 201000, 215000, 225000, 218000]  # 십억원
        records = []
        for i, year in enumerate(cls.YEARS):
            records.append({
                "TBL_ID": cat.tbl_id,
                "TBL_NM": cat.name,
                "PRD_DE": year,
                "C1_NM": "전국",
                "ITM_NM": "건설투자",
                "DT": str(values[i]),
                "UNIT_NM": "십억원",
            })
        return records

    @classmethod
    def education(cls, cat: DataCategory) -> List[Dict]:
        """교육 데이터."""
        levels = {"초등학교": 2670000, "중학교": 1320000, "고등학교": 1270000, "대학교": 1950000}
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for level, base_count in levels.items():
                # 학령인구 감소 트렌드
                count = int(base_count * (1 - year_idx * 0.025))
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": level,
                    "ITM_NM": "학생수",
                    "DT": str(count),
                    "UNIT_NM": "명",
                })
        return records

    @classmethod
    def healthcare(cls, cat: DataCategory) -> List[Dict]:
        """의료시설 데이터."""
        records = []
        for year_idx, year in enumerate(cls.YEARS):
            for region in cls.REGIONS[:10]:  # 상위 10개 지역
                base = 500 if region in ["서울특별시", "경기도"] else 200
                hospitals = int(base * (1 + year_idx * 0.03))
                records.append({
                    "TBL_ID": cat.tbl_id,
                    "TBL_NM": cat.name,
                    "PRD_DE": year,
                    "C1_NM": region,
                    "ITM_NM": "병원수",
                    "DT": str(hospitals),
                    "UNIT_NM": "개",
                })
        return records

    @classmethod
    def generate(cls, cat: DataCategory) -> List[Dict]:
        """카테고리에 맞는 모의 데이터 생성."""
        generator_name = cat.mock_generator
        generator = getattr(cls, generator_name, None)
        if generator:
            return generator(cat)
        return cls.population_by_region(cat)  # 기본값


# =============================================================================
# 리포트 생성기
# =============================================================================

def generate_report_for_category(cat: DataCategory, use_live: bool = False) -> str:
    """카테고리별 HTML 리포트 생성."""
    print(f"\n📊 {cat.icon} {cat.name} 리포트 생성 중...")

    # 데이터 조회 (실제 API 또는 모의)
    if use_live and USE_LIVE_API:
        from kosis_tools import StatisticsData
        client = StatisticsData()
        data = client.get_data(
            org_id=cat.org_id,
            tbl_id=cat.tbl_id,
            start_date=cat.start_period,
            end_date=cat.end_period,
            prd_se=cat.period_type,
        ) or []
    else:
        data = MockDataGenerator.generate(cat)

    if not data:
        print(f"   ⚠️ 데이터 없음")
        return ""

    print(f"   ✅ {len(data)}건 데이터 로드")

    # 컴포넌트 수집
    components: List[ReportComponent] = []

    # 리포트 헤더 (직접 HTML 생성)
    header_html = f"""
    <div style="text-align: center; margin-bottom: 30px; padding: 30px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                border-radius: 16px; color: white;">
        <div style="font-size: 3rem; margin-bottom: 10px;">{cat.icon}</div>
        <h1 style="font-size: 2rem; margin: 0 0 10px 0;
                   background: linear-gradient(90deg, #00d4ff, #7c3aed);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            {cat.name} 분석 리포트
        </h1>
        <p style="color: rgba(255,255,255,0.8); margin: 0 0 15px 0;">{cat.description}</p>
        <div style="display: flex; justify-content: center; gap: 20px; font-size: 0.9rem; color: rgba(255,255,255,0.6);">
            <span>📋 통계표: {cat.org_id}/{cat.tbl_id}</span>
            <span>📅 기간: {cat.start_period} ~ {cat.end_period}</span>
            <span>🕐 생성: {datetime.now().strftime("%Y.%m.%d")}</span>
        </div>
    </div>
    """
    header = ReportComponent(
        type="header",
        html=header_html,
        summary=f"{cat.name} 분석 리포트 헤더",
        priority=1,  # 가장 먼저 표시
    )
    components.append(header)

    # KPI 카드
    periods = sorted(set(r.get("PRD_DE", "") for r in data))
    categories_list = sorted(set(r.get("C1_NM", "") for r in data if r.get("C1_NM")))
    items = sorted(set(r.get("ITM_NM", "") for r in data if r.get("ITM_NM")))

    kpi_cards = [
        viz_kpi_card(value=len(data), label="총 데이터", icon="📊"),
        viz_kpi_card(value=len(periods), label=f"기간 ({periods[0]}~{periods[-1]})", icon="📅"),
        viz_kpi_card(value=len(categories_list), label="분류 항목", icon="📍"),
    ]
    components.append(layout_card_grid(kpi_cards, columns=3))

    # 분석별 시각화
    # 첫 번째 항목만 필터링 (여러 항목이 있는 경우)
    if items:
        main_item = items[0]
        filtered_data = [r for r in data if r.get("ITM_NM") == main_item]
    else:
        filtered_data = data

    # labels 딕셔너리 생성 (한글 라벨)
    labels = {
        "PRD_DE": "기간",
        "C1_NM": "분류",
        "DT": items[0] if items else "값",
    }

    # 추이 분석
    if "trend" in cat.analyses:
        try:
            trend_chart = viz_line_trend(
                filtered_data,
                x="PRD_DE",
                y="DT",
                color="C1_NM" if len(categories_list) <= 10 else None,
                title=f"{cat.name} 추이",
                labels=labels,
            )
            components.append(trend_chart)

            trend_analysis = analyze_trend(filtered_data)
            components.append(text_insight(trend_analysis))
        except Exception as e:
            print(f"   ⚠️ 추이 분석 실패: {e}")

    # 비교 분석
    if "comparison" in cat.analyses:
        try:
            # 최근 기간 데이터만
            latest_period = periods[-1]
            latest_data = [r for r in filtered_data if r.get("PRD_DE") == latest_period]

            if latest_data:
                bar_chart = viz_bar_comparison(
                    latest_data,
                    x="C1_NM",
                    y="DT",
                    title=f"{latest_period} {main_item if items else ''} 비교",
                    top_n=15,
                    labels=labels,
                )
                components.append(bar_chart)
        except Exception as e:
            print(f"   ⚠️ 비교 분석 실패: {e}")

    # 순위 분석
    if "ranking" in cat.analyses:
        try:
            ranking = analyze_ranking(filtered_data, top_n=10, period=periods[-1])
            if ranking.findings:
                findings_html = "<ul>" + "".join(f"<li>{f}</li>" for f in ranking.findings[:10]) + "</ul>"
                ranking_section = ReportComponent(
                    type="text",
                    html=f"""
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 12px; margin: 20px 0;">
                        <h3 style="margin: 0 0 15px 0; color: #333;">🏆 순위 분석</h3>
                        {findings_html}
                    </div>
                    """,
                    summary="순위 분석 결과",
                    priority=60,
                )
                components.append(ranking_section)
        except Exception as e:
            print(f"   ⚠️ 순위 분석 실패: {e}")

    # 구성 분석 (파이 차트)
    if "composition" in cat.analyses:
        try:
            latest_period = periods[-1]
            latest_data = [r for r in filtered_data if r.get("PRD_DE") == latest_period]
            if latest_data:
                pie_chart = viz_pie_composition(
                    latest_data[:10],  # 상위 10개
                    names="C1_NM",
                    values="DT",
                    title=f"{latest_period} 구성 비율",
                )
                components.append(pie_chart)
        except Exception as e:
            print(f"   ⚠️ 구성 분석 실패: {e}")

    # 통계 분석
    if "stats" in cat.analyses:
        try:
            stats = analyze_stats(filtered_data)
            if stats.findings:
                stats_html = "<ul>" + "".join(f"<li>{f}</li>" for f in stats.findings[:5]) + "</ul>"
                stats_section = ReportComponent(
                    type="text",
                    html=f"""
                    <div style="background: #e8f4f8; padding: 20px; border-radius: 12px; margin: 20px 0;">
                        <h3 style="margin: 0 0 15px 0; color: #333;">📈 기술 통계</h3>
                        {stats_html}
                    </div>
                    """,
                    summary="기술 통계 분석",
                    priority=65,
                )
                components.append(stats_section)
        except Exception as e:
            print(f"   ⚠️ 통계 분석 실패: {e}")

    # 데이터 테이블
    table_data = filtered_data[:20]
    if table_data:
        table = layout_table(
            table_data,
            columns=["PRD_DE", "C1_NM", "DT", "ITM_NM"],
            column_labels={"PRD_DE": "기간", "C1_NM": "분류", "DT": "값", "ITM_NM": "항목"},
        )
        components.append(table)

    # 데이터 노트
    components.append(text_data_note(data))

    # MCP 패턴 안내
    mcp_note = ReportComponent(
        type="text",
        html="""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 25px; border-radius: 12px; margin: 20px 0; color: white;">
            <h3 style="margin: 0 0 15px 0;">💡 MCP 패턴 안내</h3>
            <p>이 리포트는 MCP(Model Context Protocol) 패턴을 따라 생성되었습니다.</p>
            <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; margin: 15px 0;">
                <strong>사용된 패턴:</strong>
                <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                    <li><code>view="summary"</code>: 메타데이터만 조회 (토큰 98% 절약)</li>
                    <li><code>analyze_*</code>: 서버사이드 분석 (데이터 미전송)</li>
                    <li><code>viz_*</code>: 서버사이드 시각화 (결과만 반환)</li>
                </ul>
            </div>
            <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px;">
                <strong>LLM 호출 예시:</strong>
                <pre style="margin: 10px 0 0 0; font-size: 0.85rem; overflow-x: auto;"><code># 1. 요약 조회
summary = get_statistics_data("101", "DT_1B040A3", "2019", "2023", view="summary")

# 2. 서버사이드 분석
trend = analyze_data_trend(data)

# 3. 리포트 생성
report = create_quick_report(data, "인구 분석")</code></pre>
            </div>
        </div>
        """,
        summary="MCP 패턴 안내",
        priority=90,
    )
    components.append(mcp_note)

    # 리포트 조립
    output_path = OUTPUT_DIR / f"{cat.id}_report.html"
    html = assemble_report(
        components,
        title=f"{cat.icon} {cat.name}",
        output_path=str(output_path),
    )

    print(f"   ✅ 저장: {output_path}")
    return str(output_path)


def generate_gallery_index(generated_files: List[str]) -> str:
    """갤러리 인덱스 페이지 생성."""
    html = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KOSIS MCP 아티팩트 갤러리</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

        * { box-sizing: border-box; }

        body {
            font-family: 'Noto Sans KR', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            margin: 0;
            padding: 40px 20px;
            color: white;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        h1 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .subtitle {
            text-align: center;
            color: rgba(255,255,255,0.7);
            margin-bottom: 20px;
            font-size: 1.1rem;
        }

        .mcp-badge {
            text-align: center;
            margin-bottom: 40px;
        }

        .mcp-badge span {
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 500;
        }

        .stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 40px;
            flex-wrap: wrap;
        }

        .stat {
            text-align: center;
        }

        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stat-label {
            color: rgba(255,255,255,0.6);
            font-size: 0.9rem;
        }

        .category-section {
            margin-bottom: 40px;
        }

        .category-title {
            font-size: 1.3rem;
            margin-bottom: 20px;
            padding-left: 10px;
            border-left: 4px solid #7c3aed;
        }

        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }

        .card {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 25px;
            transition: all 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(124, 58, 237, 0.5);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }

        .card-icon {
            font-size: 2rem;
            margin-bottom: 10px;
        }

        .card h3 {
            margin: 0 0 10px 0;
            font-size: 1.1rem;
        }

        .card p {
            color: rgba(255,255,255,0.6);
            font-size: 0.9rem;
            margin: 0 0 15px 0;
            line-height: 1.5;
        }

        .card a {
            display: inline-block;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: opacity 0.2s;
        }

        .card a:hover {
            opacity: 0.9;
        }

        .footer {
            text-align: center;
            margin-top: 60px;
            color: rgba(255,255,255,0.4);
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 KOSIS MCP 아티팩트 갤러리</h1>
        <p class="subtitle">MCP 패턴 기반 데이터 분석 리포트 모음</p>

        <div class="mcp-badge">
            <span>🚀 MCP 패턴: 데이터는 서버에, 요약만 모델에!</span>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">''' + str(len(generated_files)) + '''</div>
                <div class="stat-label">리포트 수</div>
            </div>
            <div class="stat">
                <div class="stat-value">''' + str(len(CATEGORIES)) + '''</div>
                <div class="stat-label">데이터 카테고리</div>
            </div>
            <div class="stat">
                <div class="stat-value">98.7%</div>
                <div class="stat-label">토큰 절감률</div>
            </div>
        </div>

        <div class="gallery">
'''

    # 카테고리별 카드 생성
    for cat_id, cat in CATEGORIES.items():
        filename = f"{cat_id}_report.html"
        filepath = OUTPUT_DIR / filename

        if filepath.exists():
            html += f'''
            <div class="card">
                <div class="card-icon">{cat.icon}</div>
                <h3>{cat.name}</h3>
                <p>{cat.description}</p>
                <a href="{filename}" target="_blank">리포트 보기 →</a>
            </div>
'''

    html += '''
        </div>

        <div class="footer">
            <p>Generated with KOSIS MCP Server | ''' + datetime.now().strftime("%Y-%m-%d %H:%M") + '''</p>
            <p>MCP Pattern: view="summary" → analyze_* → viz_* → assemble_report</p>
        </div>
    </div>
</body>
</html>
'''

    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return str(index_path)


# =============================================================================
# 메인
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MCP 패턴 기반 아티팩트 갤러리 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s                        # 모든 카테고리 생성
  %(prog)s --category pop_region  # 특정 카테고리만
  %(prog)s --live                 # 실제 API 사용
  %(prog)s --list                 # 카테고리 목록
        """,
    )
    parser.add_argument(
        "--category", "-c",
        choices=list(CATEGORIES.keys()),
        help="생성할 카테고리",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="실제 KOSIS API 사용",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="카테고리 목록 출력",
    )

    args = parser.parse_args()

    if args.list:
        print("\n📋 사용 가능한 카테고리:")
        print("-" * 60)
        for cat_id, cat in CATEGORIES.items():
            print(f"  {cat.icon} {cat_id:20} - {cat.name}")
        print("-" * 60)
        print(f"  총 {len(CATEGORIES)}개 카테고리")
        return

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    use_live = args.live and USE_LIVE_API
    data_mode = "실제 API" if use_live else "모의 데이터"

    print("=" * 70)
    print("  🎨 KOSIS MCP 아티팩트 갤러리 생성기")
    print(f"  데이터: {data_mode}")
    print(f"  출력: {OUTPUT_DIR}")
    print("=" * 70)

    generated_files = []

    if args.category:
        # 특정 카테고리만
        cat = CATEGORIES[args.category]
        result = generate_report_for_category(cat, use_live)
        if result:
            generated_files.append(result)
    else:
        # 모든 카테고리
        for cat_id, cat in CATEGORIES.items():
            try:
                result = generate_report_for_category(cat, use_live)
                if result:
                    generated_files.append(result)
            except Exception as e:
                print(f"   ❌ {cat_id} 실패: {e}")

    # 인덱스 페이지 생성
    if generated_files:
        index_path = generate_gallery_index(generated_files)
        print(f"\n📁 인덱스 페이지: {index_path}")

    print("\n" + "=" * 70)
    print(f"  ✅ 총 {len(generated_files)}개 리포트 생성 완료")
    print(f"  📂 {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
