# KOSIS MCP 서버 E2E 테스트

실제 유저 워크플로우를 시뮬레이션하는 E2E 테스트입니다.

## 테스트 환경 확인

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

서버 미실행 시:
```bash
DATABASE_URL="postgresql://kosis:kosis_dev_password@localhost:5432/kosis" \
KOSIS_ARTIFACTS_DIR="/tmp/kosis_artifacts" \
KOSIS_BASE_URL="http://localhost:8000" \
uv run uvicorn mcp_server.app:app --port 8000 &
```

---

## 시나리오 1: 지역별 인구 비교 분석

**유저 요청**: "서울, 부산, 대구의 최근 5년 인구 변화를 비교해주세요"

### 워크플로우

1. **검색** → `search_tables_hybrid`로 "시도별 인구" 검색
2. **메타데이터 확인** → `get_table_metadata`로 테이블 구조 파악
3. **데이터 조회** → `get_statistics_data`로 실데이터 조회
4. **필터링** → `filter_statistics`로 서울/부산/대구만 추출
5. **비교 분석** → `analyze_comparison`으로 지역간 비교
6. **시각화** → `execute_visualization`으로 비교 차트 생성
7. **테이블** → `execute_table`로 비교 테이블 생성
8. **리포트** → `execute_report`로 최종 조합

### 테스트 데이터

```python
# 3개 지역 x 5년 데이터
multi_region_data = [
    {"PRD_DE": "2019", "C1_NM": "서울특별시", "DT": "9729107"},
    {"PRD_DE": "2020", "C1_NM": "서울특별시", "DT": "9668465"},
    {"PRD_DE": "2021", "C1_NM": "서울특별시", "DT": "9509458"},
    {"PRD_DE": "2022", "C1_NM": "서울특별시", "DT": "9428372"},
    {"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": "9386320"},
    {"PRD_DE": "2019", "C1_NM": "부산광역시", "DT": "3413841"},
    {"PRD_DE": "2020", "C1_NM": "부산광역시", "DT": "3391946"},
    {"PRD_DE": "2021", "C1_NM": "부산광역시", "DT": "3350380"},
    {"PRD_DE": "2022", "C1_NM": "부산광역시", "DT": "3323509"},
    {"PRD_DE": "2023", "C1_NM": "부산광역시", "DT": "3293773"},
    {"PRD_DE": "2019", "C1_NM": "대구광역시", "DT": "2438031"},
    {"PRD_DE": "2020", "C1_NM": "대구광역시", "DT": "2418346"},
    {"PRD_DE": "2021", "C1_NM": "대구광역시", "DT": "2385412"},
    {"PRD_DE": "2022", "C1_NM": "대구광역시", "DT": "2367562"},
    {"PRD_DE": "2023", "C1_NM": "대구광역시", "DT": "2346003"},
]
```

### 실행할 코드

**1) 비교 분석 (`execute_analysis`)**
```python
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000

# 지역별 2019 vs 2023 비교
results = []
for region in df["C1_NM"].unique():
    region_df = df[df["C1_NM"] == region]
    pop_2019 = region_df[region_df["PRD_DE"] == "2019"]["DT"].iloc[0]
    pop_2023 = region_df[region_df["PRD_DE"] == "2023"]["DT"].iloc[0]
    change = calc_change_rate(pop_2023, pop_2019)
    results.append({
        "지역": region.replace("특별시", "").replace("광역시", ""),
        "2019년 (천 명)": f"{to_thousand(pop_2019):,.0f}",
        "2023년 (천 명)": f"{to_thousand(pop_2023):,.0f}",
        "변화율": f"{change:.1f}%",
    })

return {
    "summary": {"총 비교 지역": len(results), "분석 기간": "2019-2023"},
    "comparison": results,
    "insights": [
        "3개 광역시 모두 인구 감소 추세",
        "서울이 가장 큰 절대 감소량 기록",
        "대구의 감소율이 상대적으로 높음"
    ]
}
```

**2) 비교 차트 (`execute_visualization`)**
```python
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000
df["지역"] = df["C1_NM"].str.replace("특별시|광역시", "", regex=True)

chart = alt.Chart(df).mark_line(point=True, strokeWidth=2).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("인구_천명:Q", title="인구 (천 명)",
            axis=alt.Axis(format=",.0f"),
            scale=alt.Scale(zero=False)),
    color=alt.Color("지역:N", title="지역"),
    strokeDash=alt.StrokeDash("지역:N"),
).properties(
    title="수도권·광역시 인구 추이 비교 (2019-2023)",
    width=650, height=400
)

return save_chart(chart, "region_comparison.html")
```

**3) 비교 테이블 (`execute_table`)**
```python
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000
df["지역"] = df["C1_NM"].str.replace("특별시|광역시", "", regex=True)

# 피벗 테이블 생성
pivot = df.pivot(index="지역", columns="PRD_DE", values="인구_천명").reset_index()

return create_table(
    pivot,
    title="지역별 연도별 인구 (천 명)",
    number_format={col: ",.0f" for col in pivot.columns if col != "지역"},
)
```

**4) 최종 리포트 (`execute_report`)**
```python
return build_report(
    title="수도권·광역시 인구 비교 분석",
    analysis=analysis,
    charts=charts,
    tables=tables,
    source="통계청 KOSIS 인구총조사",
)
```

### 확인사항
- [ ] 3개 지역 데이터가 모두 처리됨
- [ ] 비교 차트에 3개 라인이 구분되어 표시
- [ ] 테이블이 피벗 형태로 연도별 컬럼
- [ ] 리포트에 인사이트 3개 이상 포함

---

## 시나리오 2: 대용량 데이터 + 청크 처리

**유저 요청**: "전국 17개 시도의 10년간 인구 데이터를 분석해주세요"

### 워크플로우

1. **대용량 조회** → `get_statistics_data`로 170건+ 데이터 조회
2. **저장 확인** → `list_stored_data`로 저장된 데이터 ID 확인
3. **청크 읽기** → `read_stored_data`로 필요한 부분만 조회
4. **집계** → `aggregate_statistics`로 연도별/지역별 집계
5. **추세 분석** → `analyze_trend`로 전체 추세 파악
6. **순위 분석** → `analyze_ranking`으로 증감률 순위

### 테스트 데이터 (17개 시도 x 10년 = 170건)

```python
# 시뮬레이션: 대용량 데이터 생성
import random
regions = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도",
    "경상남도", "제주특별자치도"
]
years = [str(y) for y in range(2014, 2024)]
base_pop = {
    "서울특별시": 10000000, "부산광역시": 3500000, "대구광역시": 2500000,
    "인천광역시": 2900000, "광주광역시": 1500000, "대전광역시": 1500000,
    "울산광역시": 1100000, "세종특별자치시": 300000, "경기도": 13000000,
    "강원특별자치도": 1500000, "충청북도": 1600000, "충청남도": 2100000,
    "전북특별자치도": 1800000, "전라남도": 1800000, "경상북도": 2600000,
    "경상남도": 3300000, "제주특별자치도": 670000
}

large_data = []
for region in regions:
    base = base_pop[region]
    for i, year in enumerate(years):
        # 연도별 약간의 변동 (-2% ~ +1%)
        factor = 1 + (random.random() * 0.03 - 0.02) * i
        pop = int(base * factor)
        large_data.append({"PRD_DE": year, "C1_NM": region, "DT": str(pop)})
```

### 실행할 도구 체인

**1) 집계 분석 (`aggregate_statistics`)**
- group_by: ["PRD_DE"]
- agg_field: "DT"
- agg_func: "sum"
→ 연도별 전국 총인구 산출

**2) 추세 분석 (`analyze_trend`)**
- time_field: "PRD_DE"
- value_field: "DT"
→ 10년간 인구 추세, CAGR 계산

**3) 순위 분석 (`analyze_ranking`)**
- value_field: "change_rate"
- top_n: 5
→ 인구 증가율 상위/하위 5개 지역

### 확인사항
- [ ] 170건 데이터 정상 처리
- [ ] 저장된 데이터 ID 반환
- [ ] 청크 단위 읽기 가능
- [ ] 연도별 집계 결과 정확
- [ ] 추세 분석에 CAGR 포함

---

## 시나리오 3: 복합 대시보드 리포트

**유저 요청**: "인구, 출산율, 고령화율을 종합한 인구구조 대시보드를 만들어주세요"

### 워크플로우

1. **다중 검색** → 3개 지표 각각 `search_tables_hybrid`
2. **다중 조회** → 각 지표 `get_statistics_data`
3. **다중 차트** → 3개 차트 생성 (라인, 막대, 영역)
4. **다중 테이블** → 3개 테이블 생성
5. **인사이트 연결** → 지표간 상관관계 분석
6. **대시보드 조합** → 하나의 리포트로 통합

### 테스트 데이터 (3개 지표)

```python
# 지표 1: 총인구 (천 명)
population_data = [
    {"PRD_DE": "2019", "ITM_NM": "총인구", "DT": "51849861"},
    {"PRD_DE": "2020", "ITM_NM": "총인구", "DT": "51829023"},
    {"PRD_DE": "2021", "ITM_NM": "총인구", "DT": "51744876"},
    {"PRD_DE": "2022", "ITM_NM": "총인구", "DT": "51628117"},
    {"PRD_DE": "2023", "ITM_NM": "총인구", "DT": "51325329"},
]

# 지표 2: 합계출산율
fertility_data = [
    {"PRD_DE": "2019", "ITM_NM": "합계출산율", "DT": "0.92", "UNIT_NM": "명"},
    {"PRD_DE": "2020", "ITM_NM": "합계출산율", "DT": "0.84", "UNIT_NM": "명"},
    {"PRD_DE": "2021", "ITM_NM": "합계출산율", "DT": "0.81", "UNIT_NM": "명"},
    {"PRD_DE": "2022", "ITM_NM": "합계출산율", "DT": "0.78", "UNIT_NM": "명"},
    {"PRD_DE": "2023", "ITM_NM": "합계출산율", "DT": "0.72", "UNIT_NM": "명"},
]

# 지표 3: 고령화율 (65세 이상 비율)
aging_data = [
    {"PRD_DE": "2019", "ITM_NM": "고령화율", "DT": "14.9", "UNIT_NM": "%"},
    {"PRD_DE": "2020", "ITM_NM": "고령화율", "DT": "15.7", "UNIT_NM": "%"},
    {"PRD_DE": "2021", "ITM_NM": "고령화율", "DT": "16.5", "UNIT_NM": "%"},
    {"PRD_DE": "2022", "ITM_NM": "고령화율", "DT": "17.5", "UNIT_NM": "%"},
    {"PRD_DE": "2023", "ITM_NM": "고령화율", "DT": "18.4", "UNIT_NM": "%"},
]
```

### 실행할 코드

**1) 총인구 라인 차트**
```python
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000

chart = alt.Chart(df).mark_area(
    line=True, color="#4C78A8", opacity=0.3
).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("인구_천명:Q", title="인구 (천 명)",
            axis=alt.Axis(format=",.0f")),
).properties(title="총인구 추이", width=400, height=250)

return save_chart(chart, "dashboard_population.html")
```

**2) 출산율 막대 차트**
```python
df = prepare_data(data, numeric_fields=["DT"])

chart = alt.Chart(df).mark_bar(color="#E45756").encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("DT:Q", title="합계출산율 (명)",
            scale=alt.Scale(domain=[0, 1.2])),
).properties(title="합계출산율 추이", width=400, height=250)

return save_chart(chart, "dashboard_fertility.html")
```

**3) 고령화율 라인 차트**
```python
df = prepare_data(data, numeric_fields=["DT"])

chart = alt.Chart(df).mark_line(
    point=True, color="#72B7B2", strokeWidth=3
).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("DT:Q", title="고령화율 (%)",
            scale=alt.Scale(domain=[10, 25])),
).properties(title="고령화율 추이", width=400, height=250)

return save_chart(chart, "dashboard_aging.html")
```

**4) 종합 분석 (`execute_analysis`)**
```python
return {
    "summary": {
        "2023년 총인구": "51,325천 명",
        "합계출산율": "0.72명 (역대 최저)",
        "고령화율": "18.4% (초고령사회 진입 임박)",
    },
    "insights": [
        "인구는 5년간 52만 명 감소 (연평균 -0.2%)",
        "출산율 0.72명으로 OECD 최하위 지속",
        "고령화율 18.4%로 초고령사회(20%) 2년 내 도달 전망",
        "출산율↓ + 고령화율↑ = 인구구조 악화 가속",
    ],
    "correlations": [
        {"지표1": "출산율", "지표2": "인구증가율", "관계": "강한 양의 상관"},
        {"지표1": "고령화율", "지표2": "출산율", "관계": "강한 음의 상관"},
    ]
}
```

**5) 종합 대시보드 (`execute_report`)**
```python
return build_report(
    title="대한민국 인구구조 대시보드 2023",
    analysis=analysis,
    charts=charts,  # 3개 차트 배열
    tables=tables,  # 각 지표 요약 테이블
    source="통계청 KOSIS, 인구동향조사",
)
```

### 확인사항
- [ ] 3개 지표 데이터 모두 처리
- [ ] 3개 차트가 각각 다른 스타일
- [ ] 분석에 지표간 상관관계 포함
- [ ] 리포트에 모든 요소 통합
- [ ] 숫자 포맷 일관성 (천 단위)

---

## 시나리오 4: 순위 분석 + Top N 리포트

**유저 요청**: "시도별 인구 증감률 순위를 보여주세요. 상위 5개, 하위 5개"

### 워크플로우

1. **데이터 조회** → 전체 시도 데이터
2. **순위 분석** → `analyze_ranking`
3. **양방향 막대 차트** → 증가/감소 구분
4. **Top/Bottom 테이블** → 상위/하위 분리

### 테스트 데이터

```python
ranking_data = [
    {"C1_NM": "세종특별자치시", "change_rate": 12.5},
    {"C1_NM": "경기도", "change_rate": 2.3},
    {"C1_NM": "인천광역시", "change_rate": 0.8},
    {"C1_NM": "제주특별자치도", "change_rate": 0.5},
    {"C1_NM": "충청남도", "change_rate": 0.2},
    {"C1_NM": "대전광역시", "change_rate": -1.2},
    {"C1_NM": "광주광역시", "change_rate": -1.8},
    {"C1_NM": "울산광역시", "change_rate": -2.1},
    {"C1_NM": "강원특별자치도", "change_rate": -2.5},
    {"C1_NM": "충청북도", "change_rate": -2.8},
    {"C1_NM": "서울특별시", "change_rate": -3.5},
    {"C1_NM": "부산광역시", "change_rate": -3.6},
    {"C1_NM": "대구광역시", "change_rate": -3.8},
    {"C1_NM": "전라남도", "change_rate": -4.2},
    {"C1_NM": "경상북도", "change_rate": -4.5},
    {"C1_NM": "경상남도", "change_rate": -4.8},
    {"C1_NM": "전북특별자치도", "change_rate": -5.2},
]
```

### 실행할 코드

**1) 양방향 막대 차트**
```python
df = pd.DataFrame(data)
df["지역"] = df["C1_NM"].str.replace("특별시|광역시|특별자치시|특별자치도|도", "", regex=True)
df["색상"] = df["change_rate"].apply(lambda x: "증가" if x > 0 else "감소")
df = df.sort_values("change_rate")

chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("change_rate:Q", title="인구 변화율 (%)",
            axis=alt.Axis(format=".1f")),
    y=alt.Y("지역:N", sort="-x", title=""),
    color=alt.Color("색상:N",
                    scale=alt.Scale(domain=["증가", "감소"],
                                  range=["#4C78A8", "#E45756"]),
                    legend=alt.Legend(title="구분")),
).properties(
    title="시도별 인구 변화율 순위 (2019-2023)",
    width=500, height=450
)

return save_chart(chart, "ranking_chart.html")
```

**2) Top 5 / Bottom 5 테이블**
```python
df = pd.DataFrame(data)
df["지역"] = df["C1_NM"].str.replace("특별시|광역시|특별자치시|특별자치도|도", "", regex=True)
df = df.sort_values("change_rate", ascending=False)

top5 = df.head(5)[["지역", "change_rate"]].copy()
top5["순위"] = range(1, 6)
top5 = top5[["순위", "지역", "change_rate"]]

bottom5 = df.tail(5)[["지역", "change_rate"]].copy()
bottom5["순위"] = range(13, 18)
bottom5 = bottom5[["순위", "지역", "change_rate"]]

# 두 테이블 생성
top_table = create_table(top5, title="인구 증가율 상위 5개 시도",
    columns={"change_rate": "변화율 (%)"}, number_format={"변화율 (%)": "+.1f"})
bottom_table = create_table(bottom5, title="인구 감소율 상위 5개 시도",
    columns={"change_rate": "변화율 (%)"}, number_format={"변화율 (%)": ".1f"})

return {"top5": top_table, "bottom5": bottom_table}
```

### 확인사항
- [ ] 17개 시도 순위 정렬
- [ ] 증가/감소 색상 구분
- [ ] Top 5 / Bottom 5 분리 테이블
- [ ] 변화율 소수점 1자리 포맷

---

## 테스트 결과 요약

| 시나리오 | 주요 테스트 항목 | 상태 |
|----------|------------------|------|
| 1. 지역 비교 | 다중 지역 데이터, 비교 차트/테이블 | |
| 2. 대용량 | 170건+ 처리, 청크, 집계 | |
| 3. 대시보드 | 다중 지표, 다중 차트, 상관분석 | |
| 4. 순위 | Top/Bottom N, 양방향 차트 | |

## 검증 포인트

1. **데이터 통합**: 여러 데이터 소스의 결과를 하나로 조합
2. **숫자 포맷**: 모든 숫자에 천 단위 구분자, 과학적 표기법 금지
3. **차트 다양성**: 라인, 막대, 영역, 비교 등 다양한 유형
4. **인사이트 연결**: 단순 수치가 아닌 의미있는 해석 포함
5. **URL 접근성**: 생성된 모든 아티팩트 URL 정상 접근
