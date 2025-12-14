"""
MCP 호출 시나리오 정의.

실제 KOSIS API를 통해 데이터를 조회하는 시나리오입니다.
"""

# MCP를 통해 실제 데이터를 조회하는 시나리오
MCP_SCENARIOS = {
    # A. 인구/가구
    "pop_trend_national": {
        "category": "인구/가구",
        "name": "전국 인구 추이 분석",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",
        "start_date": "2019",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "전국 인구 추이 분석",
        "analysis_type": "trend",
    },
    "pop_compare_metro": {
        "category": "인구/가구",
        "name": "수도권 인구 비교",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",
        "start_date": "2020",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "서울과 부산 인구 비교",
        "analysis_type": "comparison",
    },
    "pop_ranking_region": {
        "category": "인구/가구",
        "name": "인구 순위 분석",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",
        "start_date": "2023",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "인구 상위 10개 시도 순위",
        "analysis_type": "ranking",
    },

    # B. 경제/물가
    "cpi_trend": {
        "category": "경제/물가",
        "name": "소비자물가지수 추이",
        "org_id": "101",
        "tbl_id": "DT_1J22001",
        "start_date": "202401",
        "end_date": "202412",
        "prd_se": "M",
        "query": "2024년 월별 소비자물가지수 추이",
        "analysis_type": "trend",
    },

    # C. 노동/고용
    "employ_rate": {
        "category": "노동/고용",
        "name": "고용률 추이",
        "org_id": "101",
        "tbl_id": "DT_1ES2A01",
        "start_date": "2019",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "연도별 고용률 추이 분석",
        "analysis_type": "trend",
    },

    # D. 산업/기업 (참고: 실제 테이블 ID 확인 필요)
    "manufacture_prod": {
        "category": "산업/기업",
        "name": "제조업 생산지수",
        "org_id": "101",
        "tbl_id": "DT_1C84001",
        "start_date": "2020",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "제조업 생산지수 추이",
        "analysis_type": "trend",
    },

    # E. 무역/수출입 (참고: 실제 테이블 ID 확인 필요)
    "export_total": {
        "category": "무역/수출입",
        "name": "수출액 추이",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",  # 임시: 실제 무역 테이블로 교체 필요
        "start_date": "2020",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "연도별 수출액 추이",
        "analysis_type": "trend",
    },

    # F. 심층 분석
    "deep_analysis": {
        "category": "심층분석",
        "name": "상세 인구 분석",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",
        "start_date": "2019",
        "end_date": "2023",
        "prd_se": "Y",
        "query": "서울 인구 변화를 자세히 분석해주세요",
        "analysis_type": "deep",
    },
}
