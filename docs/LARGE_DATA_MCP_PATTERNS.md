# 대용량 데이터 MCP 처리 패턴

> KOSIS MCP 서버에서 대용량 통계 데이터를 효율적으로 처리하기 위한 패턴 정리

## 목차

1. [문제 정의](#1-문제-정의)
2. [해결책: 코드 실행 패턴](#2-해결책-코드-실행-패턴)
3. [세 가지 접근법](#3-세-가지-접근법)
4. [KOSIS MCP 적용 방안](#4-kosis-mcp-적용-방안)
5. [참고 자료](#5-참고-자료)

---

## 1. 문제 정의

### 전통적인 MCP 도구 호출 방식의 한계

```
┌─────────────┐     도구 호출      ┌─────────────┐
│             │ ───────────────▶  │             │
│   LLM       │                   │  MCP 서버    │
│  (Claude)   │ ◀─────────────── │   (KOSIS)   │
│             │   전체 데이터 반환  │             │
└─────────────┘                   └─────────────┘
       │
       ▼
   컨텍스트 오버플로우! 💥
```

**예시 상황:**

```python
# LLM이 이런 도구를 호출한다고 가정
result = get_statistics_data(
    table_id="DT_1B040A3",      # 인구 통계
    period="2000:2024",         # 25년치 데이터
    region="all"                # 전국 + 17개 시도
)

# 결과: 수십만 행, 10MB+ JSON
# → LLM 컨텍스트(200K 토큰)에 넣으면 즉시 한계 도달
```

### 핵심 문제

| 문제 | 설명 |
|------|------|
| **컨텍스트 한계** | Claude: ~200K 토큰, GPT-4: ~128K 토큰. 10MB JSON ≈ 250만 토큰 |
| **비용 폭발** | 토큰당 과금. 불필요한 원시 데이터 = 비용 낭비 |
| **처리 속도** | 대용량 텍스트 파싱 = 느린 응답 시간 |
| **정확도 저하** | 긴 컨텍스트에서 LLM "lost in the middle" 현상 발생 |

---

## 2. 해결책: 코드 실행 패턴

### 핵심 아이디어

> **"LLM이 도구를 직접 호출하는 대신, 코드를 작성하게 하라"**

```
┌─────────────┐                    ┌─────────────┐
│             │   코드 작성         │             │
│   LLM       │ ─────────────────▶ │  샌드박스    │
│  (Claude)   │                    │  실행 환경   │
│             │ ◀───────────────── │             │
│             │   결과만 반환       │             │
└─────────────┘   (요약/집계)       └─────────────┘
       │                                  │
       │                                  │ 데이터 접근
       │                                  ▼
       │                           ┌─────────────┐
       │                           │  MCP 서버    │
       │                           │   (KOSIS)   │
       └───────────────────────────┤  대용량 데이터│
             결과만 필요!           └─────────────┘
```

### 토큰 효율성 비교

**Anthropic 엔지니어링 블로그 실측 데이터:**

| 방식 | 토큰 사용량 | 비율 |
|------|------------|------|
| 전통적 도구 호출 | 77,174 토큰 | 100% |
| 코드 실행 패턴 | **982 토큰** | **1.3%** |

> **98.7% 토큰 절감!**
>
> 출처: [Anthropic Engineering - Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)

---

## 3. 세 가지 접근법

### 3.1 Anthropic의 코드 실행 패턴

> 출처: https://www.anthropic.com/engineering/code-execution-with-mcp

**개념:**

MCP 서버가 코드 실행 도구를 제공. LLM은 데이터를 직접 받는 대신,
데이터를 처리하는 코드를 작성하여 실행을 요청.

**작동 방식:**

```
1. LLM: "서울시 인구 추이를 분석해줘"

2. LLM이 코드 작성:
   ```python
   import pandas as pd

   # MCP 서버 내부에서 데이터 로드
   df = load_kosis_data("DT_1B040A3", region="11")  # 서울

   # 분석 수행 (서버 내에서!)
   trend = df.groupby('year')['population'].mean()
   change_rate = trend.pct_change() * 100

   # 결과만 반환
   return {
       "summary": f"서울 인구 {trend.iloc[-1]:,.0f}명 (최근)",
       "trend": trend.tail(5).to_dict(),
       "avg_change": f"{change_rate.mean():.2f}%/년"
   }
   ```

3. 서버: 코드 실행 → 결과만 LLM에 반환

4. LLM: 결과 기반으로 사용자에게 답변
```

**장점:**
- 토큰 98.7% 절감
- 복잡한 분석 로직 표현 가능
- LLM의 코딩 능력 활용

**단점:**
- 샌드박스 보안 필요
- 코드 실행 오류 처리 복잡
- LLM이 올바른 코드를 생성해야 함

---

### 3.2 Cloudflare의 Code Mode

> 출처: https://blog.cloudflare.com/code-mode/

**개념:**

MCP 도구들을 TypeScript API로 변환. LLM이 이 API를 사용하는
TypeScript 코드를 작성하면, 서버가 실행.

**작동 방식:**

```
1. MCP 도구 정의:
   - search_statistics(keyword: string)
   - get_statistics_data(table_id: string, ...)
   - aggregate_statistics(data: any, method: string)

2. Code Mode가 자동 변환:
   ```typescript
   // 자동 생성된 TypeScript API
   interface KosisAPI {
     searchStatistics(keyword: string): Promise<Table[]>;
     getStatisticsData(tableId: string, ...): Promise<DataRow[]>;
     aggregateStatistics(data: DataRow[], method: string): Promise<Summary>;
   }
   ```

3. LLM이 TypeScript 코드 작성:
   ```typescript
   async function analyze() {
     // 테이블 검색
     const tables = await kosis.searchStatistics("인구");

     // 데이터 조회
     const data = await kosis.getStatisticsData(tables[0].id, {
       period: "2020:2024"
     });

     // 집계
     const summary = await kosis.aggregateStatistics(data, "yearly_avg");

     return summary;  // 이것만 LLM에 반환
   }
   ```

4. 서버에서 실행 → 최종 결과만 반환
```

**장점:**
- 타입 안전성 (TypeScript)
- 기존 MCP 도구 재사용
- IDE 자동완성 활용 가능

**단점:**
- TypeScript 런타임 필요
- Cloudflare Workers 의존성 (원본 구현)

---

### 3.3 Code Sandbox MCP

> 출처: https://www.philschmid.de/code-sandbox-mcp

**개념:**

Docker 기반 격리된 샌드박스에서 LLM 생성 코드 실행.
보안과 유연성의 균형.

**아키텍처:**

```
┌─────────────────────────────────────────────────┐
│                   호스트 시스템                  │
│  ┌───────────────┐      ┌───────────────────┐  │
│  │               │      │   Docker 컨테이너  │  │
│  │   LLM 클라이언트 │◀────▶│  ┌─────────────┐ │  │
│  │   (Claude)    │      │  │ Python 환경  │ │  │
│  │               │      │  │ + pandas     │ │  │
│  └───────────────┘      │  │ + numpy      │ │  │
│         │               │  │ + plotly     │ │  │
│         │               │  └─────────────┘ │  │
│         │               │         │        │  │
│         │               │         ▼        │  │
│         │               │  ┌─────────────┐ │  │
│         │               │  │ 마운트된     │ │  │
│         │               │  │ 데이터 볼륨  │ │  │
│         │               │  │ (읽기 전용) │ │  │
│         │               │  └─────────────┘ │  │
│         │               └───────────────────┘  │
│         │                        │             │
│         │◀───────────────────────┘             │
│         │    결과만 반환                        │
└─────────────────────────────────────────────────┘
```

**보안 계층:**

```yaml
# Docker 샌드박스 설정 예시
sandbox:
  # 네트워크 격리
  network_mode: none

  # 읽기 전용 파일시스템
  read_only: true

  # 리소스 제한
  mem_limit: 512m
  cpu_period: 100000
  cpu_quota: 50000  # 50% CPU

  # 실행 시간 제한
  timeout: 30s

  # 마운트 포인트 (데이터만 읽기 전용)
  volumes:
    - ./data:/data:ro
```

**장점:**
- 강력한 보안 격리
- 모든 언어/라이브러리 지원
- 자원 사용량 제어 가능

**단점:**
- Docker 오버헤드
- 초기 설정 복잡
- 콜드 스타트 지연

---

## 4. KOSIS MCP 적용 방안

### 현재 구조의 한계

현재 `server.py`의 도구 구조:

```python
# Layer 2: FETCH - 문제 지점!
@mcp.tool()
async def get_statistics_data(table_id: str, ...):
    """통계 데이터 조회 - 전체 데이터 반환"""
    data = await fetch_from_kosis(table_id, ...)
    return data  # 🚨 10MB+ 가능!
```

### 제안: 하이브리드 접근법

KOSIS 데이터 특성을 고려한 실용적 설계:

```
┌─────────────────────────────────────────────────────────────┐
│                    KOSIS MCP 서버 v2                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐                                           │
│  │ Layer 1     │  search_statistics, browse_categories     │
│  │ DISCOVER    │  → 메타데이터만 (작음, 그대로 유지)         │
│  └─────────────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │ Layer 2     │  get_statistics_data                      │
│  │ FETCH       │  → 옵션 A: 샘플만 반환 (기본)              │
│  │             │  → 옵션 B: 파일로 저장 후 경로 반환         │
│  └─────────────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Layer 3: CODE EXECUTION (신규)                      │   │
│  │                                                     │   │
│  │  execute_analysis_code(                            │   │
│  │    code: str,           # LLM이 작성한 Python 코드  │   │
│  │    data_refs: list[str] # 사용할 데이터 참조        │   │
│  │  ) → AnalysisResult                                │   │
│  │                                                     │   │
│  │  사전 정의된 분석 함수들:                            │   │
│  │  - load_data(ref) → DataFrame                      │   │
│  │  - aggregate(df, method) → Summary                 │   │
│  │  - visualize(df, chart_type) → ImagePath           │   │
│  │  - compare(df1, df2, keys) → ComparisonResult      │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │ Layer 4     │  결과 + 시각화 반환                        │
│  │ PRESENT     │  (토큰 친화적 크기)                        │
│  └─────────────┘                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 구현 예시

```python
# server.py 확장

from typing import Any
import pandas as pd
import io
import sys

# 데이터 캐시 (세션 내 재사용)
_data_cache: dict[str, pd.DataFrame] = {}

@mcp.tool()
async def fetch_and_store(
    table_id: str,
    period: str | None = None,
    region: str | None = None,
) -> dict:
    """
    데이터를 조회하여 서버 메모리에 저장.
    전체 데이터가 아닌 참조 ID와 요약만 반환.
    """
    # KOSIS API 호출
    data = await fetch_from_kosis(table_id, period, region)
    df = pd.DataFrame(data)

    # 캐시에 저장
    ref_id = f"{table_id}_{period}_{region}"
    _data_cache[ref_id] = df

    # 요약만 반환 (토큰 절약!)
    return {
        "ref_id": ref_id,
        "rows": len(df),
        "columns": list(df.columns),
        "sample": df.head(3).to_dict(orient="records"),
        "period_range": f"{df['PRD_DE'].min()} ~ {df['PRD_DE'].max()}",
        "hint": "execute_analysis를 사용하여 이 데이터를 분석하세요"
    }


@mcp.tool()
async def execute_analysis(
    code: str,
    data_refs: list[str],
) -> dict:
    """
    LLM이 작성한 Python 코드를 실행하여 분석 수행.

    사용 가능한 함수:
    - load_data(ref_id) → DataFrame
    - save_result(name, data) → 결과 저장
    - create_chart(df, chart_type, **kwargs) → 차트 경로

    Args:
        code: 실행할 Python 코드
        data_refs: 사용할 데이터 참조 ID 목록

    Returns:
        실행 결과 (요약, 차트 경로 등)
    """
    # 안전한 실행 환경 구성
    safe_globals = {
        "pd": pd,
        "load_data": lambda ref: _data_cache.get(ref),
        "save_result": _save_result,
        "create_chart": _create_chart,
        # 위험한 함수들 제외
        "__builtins__": {
            "len": len, "sum": sum, "min": min, "max": max,
            "range": range, "enumerate": enumerate, "zip": zip,
            "dict": dict, "list": list, "str": str, "int": int, "float": float,
            "print": print, "round": round, "sorted": sorted,
        }
    }

    # 출력 캡처
    captured_output = io.StringIO()
    sys.stdout = captured_output

    results = {"outputs": [], "charts": [], "errors": []}

    try:
        exec(code, safe_globals, {"results": results})
        results["stdout"] = captured_output.getvalue()
    except Exception as e:
        results["errors"].append(str(e))
    finally:
        sys.stdout = sys.__stdout__

    return results
```

### 워크플로우 예시

```
사용자: "서울과 부산의 2020-2024 인구 변화를 비교해줘"

1. LLM → fetch_and_store 호출 (서울)
   응답: {"ref_id": "pop_seoul", "rows": 500, "sample": [...]}

2. LLM → fetch_and_store 호출 (부산)
   응답: {"ref_id": "pop_busan", "rows": 480, "sample": [...]}

3. LLM이 분석 코드 작성 → execute_analysis 호출:
   ```python
   seoul = load_data("pop_seoul")
   busan = load_data("pop_busan")

   # 연도별 집계
   seoul_yearly = seoul.groupby('PRD_DE')['DT'].sum()
   busan_yearly = busan.groupby('PRD_DE')['DT'].sum()

   # 비교 테이블
   comparison = pd.DataFrame({
       '서울': seoul_yearly,
       '부산': busan_yearly,
       '차이': seoul_yearly - busan_yearly
   })

   # 차트 생성
   chart_path = create_chart(comparison, 'line', title='서울 vs 부산 인구')

   save_result("comparison", comparison.tail(5).to_dict())
   save_result("chart", chart_path)
   ```

   응답: {
     "outputs": [
       {"name": "comparison", "data": {...}},
       {"name": "chart", "data": "/tmp/charts/comparison_123.png"}
     ]
   }

4. LLM이 결과를 사용자에게 설명
```

### 보안 고려사항

```python
# 코드 실행 전 검증
BLOCKED_PATTERNS = [
    r'import\s+os',
    r'import\s+subprocess',
    r'import\s+sys',
    r'open\s*\(',
    r'eval\s*\(',
    r'exec\s*\(',
    r'__import__',
    r'globals\s*\(',
    r'locals\s*\(',
]

def validate_code(code: str) -> tuple[bool, str | None]:
    """코드 안전성 검증"""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, f"금지된 패턴: {pattern}"
    return True, None
```

---

## 5. 참고 자료

### 공식 문서 및 블로그

| 제목 | 출처 | URL |
|------|------|-----|
| Code execution with MCP | Anthropic Engineering | https://www.anthropic.com/engineering/code-execution-with-mcp |
| Code Mode: the better way to use MCP | Cloudflare Blog | https://blog.cloudflare.com/code-mode/ |
| Code Sandbox MCP | Philipp Schmid | https://www.philschmid.de/code-sandbox-mcp |
| MCP Specification | Anthropic | https://modelcontextprotocol.io/ |

### 핵심 인사이트 요약

1. **Anthropic (98.7% 토큰 절감)**
   > "Instead of passing raw data through the conversation, the agent writes code that processes data server-side and returns only the relevant results."

2. **Cloudflare (Code Mode)**
   > "Rather than having the LLM make dozens of tool calls, Code Mode lets the LLM write TypeScript code that uses your MCP tools as a typed API."

3. **Code Sandbox MCP**
   > "Secure, containerized execution environment where LLM-generated code runs with access to data but without access to the host system."

---

## 체크리스트: KOSIS MCP v2 구현

- [ ] `fetch_and_store` 도구 구현 (데이터 캐싱)
- [ ] `execute_analysis` 도구 구현 (코드 실행)
- [ ] 코드 검증 레이어 추가
- [ ] 샌드박스 환경 구성 (선택적 Docker)
- [ ] 사전 정의 함수 라이브러리 구축
- [ ] 차트 생성 유틸리티 통합
- [ ] 에러 핸들링 및 타임아웃 설정
- [ ] 테스트 케이스 작성

---

*문서 작성일: 2025-12-15*
*작성자: Claude Code*
