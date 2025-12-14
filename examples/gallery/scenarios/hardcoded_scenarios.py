"""
하드코딩 데이터 시나리오 정의.

엣지케이스 테스트 및 MCP 없이 동작하는 시나리오입니다.
"""

# 샘플 데이터셋 정의
SAMPLE_DATASETS = {
    # 정상 인구 데이터 (테스트용)
    "population": [
        {"PRD_DE": "2020", "C1_NM": "전국", "DT": 51829023, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2020", "C1_NM": "서울특별시", "DT": 9668465, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2020", "C1_NM": "부산광역시", "DT": 3391946, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2020", "C1_NM": "대구광역시", "DT": 2418346, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2020", "C1_NM": "인천광역시", "DT": 2942828, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2021", "C1_NM": "전국", "DT": 51638809, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2021", "C1_NM": "서울특별시", "DT": 9509458, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2021", "C1_NM": "부산광역시", "DT": 3350380, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2021", "C1_NM": "대구광역시", "DT": 2385412, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2021", "C1_NM": "인천광역시", "DT": 2948375, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2022", "C1_NM": "전국", "DT": 51439038, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2022", "C1_NM": "서울특별시", "DT": 9428372, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2022", "C1_NM": "부산광역시", "DT": 3314183, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2022", "C1_NM": "대구광역시", "DT": 2355458, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2022", "C1_NM": "인천광역시", "DT": 2956981, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "전국", "DT": 51325329, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": 9386239, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "부산광역시", "DT": 3293842, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "대구광역시", "DT": 2332721, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "인천광역시", "DT": 2965143, "ITM_NM": "총인구", "UNIT_NM": "명"},
    ],

    # 무역 데이터 (테스트용)
    "trade": [
        {"PRD_DE": "2023", "C1_NM": "반도체", "DT": 125600000000, "ITM_NM": "수출액", "UNIT_NM": "천달러"},
        {"PRD_DE": "2023", "C1_NM": "자동차", "DT": 87400000000, "ITM_NM": "수출액", "UNIT_NM": "천달러"},
        {"PRD_DE": "2023", "C1_NM": "석유화학", "DT": 45200000000, "ITM_NM": "수출액", "UNIT_NM": "천달러"},
        {"PRD_DE": "2023", "C1_NM": "철강", "DT": 32100000000, "ITM_NM": "수출액", "UNIT_NM": "천달러"},
        {"PRD_DE": "2023", "C1_NM": "선박", "DT": 28700000000, "ITM_NM": "수출액", "UNIT_NM": "천달러"},
    ],

    # 엣지케이스: 빈 데이터
    "edge_empty": [],

    # 엣지케이스: 단일 레코드
    "edge_single": [
        {"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": 9500000, "ITM_NM": "총인구", "UNIT_NM": "명"},
    ],

    # 엣지케이스: 결측치 포함
    "edge_null": [
        {"PRD_DE": "2023", "C1_NM": "서울", "DT": 9500000, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "부산", "DT": None, "ITM_NM": "총인구", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "대구", "DT": 2400000, "ITM_NM": None, "UNIT_NM": "명"},
        {"PRD_DE": None, "C1_NM": "인천", "DT": 2900000, "ITM_NM": "총인구", "UNIT_NM": "명"},
    ],

    # 엣지케이스: 극단값
    "edge_extreme": [
        {"PRD_DE": "2023", "C1_NM": "극대지역", "DT": 999999999999, "ITM_NM": "극대값", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "영지역", "DT": 0, "ITM_NM": "영값", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "음수지역", "DT": -100, "ITM_NM": "음수값", "UNIT_NM": "명"},
        {"PRD_DE": "2023", "C1_NM": "소수지역", "DT": 0.001, "ITM_NM": "소수값", "UNIT_NM": "명"},
    ],
}


# 하드코딩 데이터로 생성하는 시나리오
HARDCODED_SCENARIOS = {
    # 정상 데이터 시나리오
    "sample_trend": {
        "category": "샘플",
        "name": "인구 추이 분석 (샘플)",
        "data_key": "population",
        "query": "전국 인구 추이 분석",
        "analysis_type": "trend",
    },
    "sample_compare": {
        "category": "샘플",
        "name": "도시 인구 비교 (샘플)",
        "data_key": "population",
        "query": "서울과 부산 인구 비교",
        "analysis_type": "comparison",
    },
    "sample_ranking": {
        "category": "샘플",
        "name": "인구 순위 (샘플)",
        "data_key": "population",
        "query": "인구 상위 지역 순위",
        "analysis_type": "ranking",
    },
    "trade_ranking": {
        "category": "샘플",
        "name": "수출 품목 순위 (샘플)",
        "data_key": "trade",
        "query": "품목별 수출 현황 및 순위",
        "analysis_type": "ranking",
    },

    # 엣지케이스 시나리오
    "edge_empty": {
        "category": "엣지케이스",
        "name": "빈 데이터 처리",
        "data_key": "edge_empty",
        "query": "데이터 없음 처리 테스트",
        "analysis_type": "edge",
    },
    "edge_single": {
        "category": "엣지케이스",
        "name": "단일 레코드 처리",
        "data_key": "edge_single",
        "query": "단일 데이터 처리 테스트",
        "analysis_type": "edge",
    },
    "edge_null": {
        "category": "엣지케이스",
        "name": "결측치 처리",
        "data_key": "edge_null",
        "query": "결측치 처리 테스트",
        "analysis_type": "edge",
    },
    "edge_extreme": {
        "category": "엣지케이스",
        "name": "극단값 처리",
        "data_key": "edge_extreme",
        "query": "극단값 처리 테스트",
        "analysis_type": "edge",
    },
    "edge_long_query": {
        "category": "엣지케이스",
        "name": "긴 쿼리 처리",
        "data_key": "population",
        "query": "서울특별시와 부산광역시 및 대구광역시와 인천광역시의 2020년부터 2023년까지의 인구 변화 추이를 상세히 비교 분석하고 각 지역별 증감률과 순위 변동을 시각화해주세요",
        "analysis_type": "edge",
    },
    "edge_ambiguous": {
        "category": "엣지케이스",
        "name": "모호한 쿼리 처리",
        "data_key": "population",
        "query": "뭔가 분석해줘",
        "analysis_type": "edge",
    },
}
