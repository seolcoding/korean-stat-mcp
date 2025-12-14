# MCP 대용량 데이터 처리 패턴

> API 응답이 LLM 컨텍스트를 초과하지 않도록 하는 모범사례

## 핵심 원칙: 데이터는 서버에, 요약만 모델에

```
┌─────────────────────────────────────────────────────────────────┐
│                    ❌ 안티패턴 (피해야 할 구현)                   │
├─────────────────────────────────────────────────────────────────┤
│  Tool Call → API (3,459건) → 전체 데이터 → LLM 컨텍스트         │
│                                    ↑                            │
│                             💥 토큰 폭발                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ✅ 권장 패턴                                  │
├─────────────────────────────────────────────────────────────────┤
│  Tool Call → API (3,459건) → 서버 메모리/캐시 저장               │
│                                    ↓                            │
│                            요약 + 참조ID → LLM 컨텍스트          │
│                                    ↓                            │
│                    필요시 read_chunk(id, page) 호출              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 패턴 1: Chunky-MCP 패턴 (참조 기반)

대용량 응답을 청킹하고 참조 ID로 접근하는 패턴.

```python
from chunky_mcp_utils import handle_large_response

_data_store: Dict[str, Any] = {}
_chunker = DataChunker(chunk_size=50)

@mcp.tool()
def get_statistics_data(org_id: str, tbl_id: str, ...) -> str:
    """통계 데이터를 조회합니다."""
    data = api.fetch_data(org_id, tbl_id, ...)  # 3,459건

    return handle_large_response(
        data,
        tool_name="get_statistics_data",
        chunker=_chunker
    )
    # 반환값:
    # {
    #   "status": "chunked",
    #   "data_id": "abc123",
    #   "total_records": 3459,
    #   "total_chunks": 70,
    #   "summary": {...},
    #   "hint": "read_data_chunk('abc123', 0)으로 첫 청크 조회"
    # }

@mcp.tool()
def read_data_chunk(data_id: str, chunk_index: int) -> str:
    """저장된 데이터의 특정 청크를 읽습니다."""
    chunk = _chunker.get_chunk(data_id, chunk_index)
    return json.dumps({
        "chunk_index": chunk_index,
        "data": chunk,
        "has_more": chunk_index < _chunker.total_chunks(data_id) - 1
    })
```

**참고**: https://github.com/ebwinters/chunky-mcp

---

## 패턴 2: Resource URI 패턴 (MCP 표준)

데이터를 MCP Resource로 저장하고 URI로 참조하는 패턴.

```python
_resource_cache: Dict[str, List[Dict]] = {}

@mcp.tool()
def get_statistics_data(org_id: str, tbl_id: str, ...) -> str:
    """통계 데이터를 조회하고 리소스로 저장합니다."""
    data = api.fetch_data(org_id, tbl_id, ...)

    resource_id = f"{org_id}_{tbl_id}_{uuid4().hex[:8]}"
    _resource_cache[resource_id] = data

    return json.dumps({
        "resource_uri": f"kosis://data/{resource_id}",
        "summary": format_summary(data),
        "access": "read_resource('kosis://data/{resource_id}')로 전체 데이터 접근"
    })

@mcp.resource("kosis://data/{resource_id}")
def get_cached_data(resource_id: str) -> str:
    """캐시된 데이터를 리소스로 제공합니다."""
    if resource_id not in _resource_cache:
        raise ValueError("Resource not found or expired")
    return json.dumps(_resource_cache[resource_id])
```

---

## 패턴 3: Smart Summary + Drill-down 패턴 (권장)

view 파라미터로 응답 크기를 제어하는 패턴.

```python
@mcp.tool()
def get_statistics_data(
    org_id: str,
    tbl_id: str,
    start_date: str,
    end_date: str,
    view: str = "summary",  # "summary" | "sample" | "chunk" | "full"
    chunk_index: int = 0,
    chunk_size: int = 50,
) -> str:
    """
    통계 데이터를 조회합니다.

    view 옵션:
    - "summary": 메타데이터 + 집계 요약만 (기본, 컨텍스트 최소화)
    - "sample": 요약 + 최근 기간 샘플 20건
    - "chunk": 특정 청크만 (chunk_index로 지정)
    - "full": 전체 데이터 (주의: 대용량)
    """
    data = api.fetch_data(org_id, tbl_id, start_date, end_date)

    if view == "summary":
        return json.dumps({
            "total_records": len(data),
            "metadata": extract_metadata(data),
            "aggregations": {
                "by_period": aggregate_by_period(data),
                "by_category": aggregate_by_category(data)[:10],
            },
            "statistics": calculate_stats(data),
            "available_views": ["sample", "chunk", "full"],
            "next_action": "더 상세한 데이터가 필요하면 view='sample' 또는 view='chunk' 사용"
        })

    elif view == "sample":
        sample = get_latest_sample(data, limit=20)
        return json.dumps({
            "total_records": len(data),
            "sample_count": len(sample),
            "data": sample,
        })

    elif view == "chunk":
        start = chunk_index * chunk_size
        end = start + chunk_size
        chunk = data[start:end]
        return json.dumps({
            "chunk_index": chunk_index,
            "chunk_size": len(chunk),
            "total_chunks": (len(data) + chunk_size - 1) // chunk_size,
            "data": chunk,
            "has_more": end < len(data)
        })

    else:  # full
        return json.dumps({"warning": f"전체 {len(data)}건", "data": data})
```

---

## 패턴 4: Server-Side Processing 패턴

서버에서 데이터를 처리하고 결과만 반환하는 패턴.

```python
@mcp.tool()
def query_statistics(
    org_id: str,
    tbl_id: str,
    query: str,  # "top 10 by value", "filter region=서울", "aggregate by year"
) -> str:
    """
    서버에서 데이터를 처리하고 결과만 반환합니다.
    전체 데이터가 컨텍스트에 들어가지 않습니다.

    query 예시:
    - "top 10 by value": 상위 10개
    - "filter region=서울": 서울 데이터만
    - "aggregate by year": 연도별 집계
    - "growth rate": 성장률 계산
    """
    data = api.fetch_data(org_id, tbl_id, ...)  # 서버 메모리에만
    result = process_query(data, query)  # 처리된 결과만

    return json.dumps({
        "query": query,
        "original_count": len(data),
        "result_count": len(result),
        "result": result,
    })
```

---

## 토큰 절감 효과

| 패턴 | 3,459건 데이터 | 컨텍스트 사용량 | 절감률 |
|------|---------------|----------------|--------|
| 전체 반환 (안티패턴) | ~150,000 토큰 | 150,000 | - |
| format_data_for_llm | ~3,000 토큰 | 3,000 | 98% |
| summary only | ~500 토큰 | 500 | 99.7% |
| chunk (50건) | ~2,500 토큰 | 2,500 | 98.3% |
| server-side query | ~200 토큰 | 200 | 99.9% |

---

## MCP 도구 설계 5대 원칙

1. **적절한 추상화 레벨**: 세분화된 API 대신 작업 단위 도구
2. **스마트 네임스페이싱**: 서비스별 명확한 구분 (`kosis_search_*`)
3. **의미 있는 컨텍스트 반환**: 기술적 세부사항 최소화
4. **토큰 효율성 최적화**: 페이지네이션, 필터링, 요약 모드
5. **명확한 도구 설명**: LLM이 이해할 수 있는 자연어 설명

---

## 참고 자료

- [chunky-mcp](https://github.com/ebwinters/chunky-mcp) - Large response chunking
- [Large File MCP](https://github.com/willianpinho/large-file-mcp) - Intelligent chunking
- [MCP Pagination Spec](https://modelcontextprotocol.io/specification/2025-03-26/server/utilities/pagination)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [MCP Best Practices](https://modelcontextprotocol.info/docs/best-practices/)
- [FastMCP Resources](https://gofastmcp.com/servers/resources)
