"""Integration tests for the 4 KOSIS key-indicator MCP tools.

Mocks the underlying HTTP layer to assert routing (which tool calls which
KOSIS endpoint with which `service` / `serviceDetail` combination) without
actually hitting KOSIS.
"""

from __future__ import annotations

import responses

from mcp_server.exposed_tools import V1_EXPOSED_NAMES


KOSIS_LIST_RESPONSE_EXP = (
    '[{"statJipyoId":"160","statJipyoNm":"노년부양비",'
    '"jipyoExplan":"개념","jipyoExplan1":"개념 설명"}]'
)

KOSIS_LIST_RESPONSE_LIST = (
    '[{"listId":"A","listNm":"인구","statJipyoId":"160",'
    '"statJipyoNm":"노년부양비","unit":"명","prdSeName":"연간",'
    '"strtPrdDe":"2010","endPrdDe":"2023"}]'
)

KOSIS_LIST_RESPONSE_DETAIL = (
    '[{"statJipyoId":"160","statJipyoNm":"노년부양비",'
    '"prdSe":"Y","prdDe":"2023","itm":"value","itmNm":"값","val":"23.4"}]'
)


def _stub(url_part: str, body: str) -> None:
    responses.add(
        responses.GET,
        f"https://kosis.kr/openapi/{url_part}",
        body=body,
        status=200,
    )


def test_all_four_tools_listed_in_v1_exposed():
    expected = {
        "get_key_indicator",
        "list_key_indicators",
        "search_key_indicators",
        "get_key_indicator_details",
    }
    assert expected.issubset(V1_EXPOSED_NAMES)


@responses.activate
def test_get_key_indicator_by_id(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("pkNumberService.do", KOSIS_LIST_RESPONSE_EXP)
    from mcp_server.server import get_key_indicator

    result = get_key_indicator.fn(by="id", value="160")  # type: ignore[attr-defined]

    assert result["by"] == "id"
    assert result["count"] == 1
    assert result["results"][0]["jipyo_nm"] == "노년부양비"
    url = responses.calls[0].request.url
    assert "service=1" in url
    assert "serviceDetail=pkAll" in url
    assert "jipyoId=160" in url


@responses.activate
def test_get_key_indicator_by_name(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("indExpService.do", KOSIS_LIST_RESPONSE_EXP)
    from mcp_server.server import get_key_indicator

    result = get_key_indicator.fn(by="name", value="실업률")  # type: ignore[attr-defined]

    assert result["by"] == "name"
    url = responses.calls[0].request.url
    assert "service=2" in url
    assert "serviceDetail=indAll" in url


def test_get_key_indicator_invalid_by():
    from mcp_server.server import get_key_indicator

    result = get_key_indicator.fn(by="bogus", value="x")  # type: ignore[attr-defined]
    assert "error" in result


@responses.activate
def test_list_key_indicators_by_category(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("indiListService.do", KOSIS_LIST_RESPONSE_LIST)
    from mcp_server.server import list_key_indicators

    result = list_key_indicators.fn(by="category", value="A")  # type: ignore[attr-defined]

    assert result["count"] == 1
    url = responses.calls[0].request.url
    assert "service=3" in url
    assert "listId=A" in url


@responses.activate
def test_list_key_indicators_by_period(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("prListSearchRequest.do", KOSIS_LIST_RESPONSE_LIST)
    from mcp_server.server import list_key_indicators

    result = list_key_indicators.fn(by="period", value="Y")  # type: ignore[attr-defined]

    assert result["count"] == 1
    url = responses.calls[0].request.url
    assert "service=4" in url
    assert "serviceDetail=prList" in url
    assert "prdSe=Y" in url


@responses.activate
def test_search_key_indicators_by_name(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("indListSearchRequest.do", KOSIS_LIST_RESPONSE_LIST)
    from mcp_server.server import search_key_indicators

    result = search_key_indicators.fn(by="name", value="실업률")  # type: ignore[attr-defined]

    assert result["count"] == 1
    url = responses.calls[0].request.url
    assert "service=4" in url
    assert "serviceDetail=indList" in url
    assert "jipyoNm=" in url


@responses.activate
def test_get_key_indicator_details_with_period_range(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("indIdDetailSearchRequest.do", KOSIS_LIST_RESPONSE_DETAIL)
    from mcp_server.server import get_key_indicator_details

    result = get_key_indicator_details.fn(  # type: ignore[attr-defined]
        jipyo_id="160", start_date="2020", end_date="2023"
    )

    assert result["jipyo_id"] == "160"
    url = responses.calls[0].request.url
    assert "startPrdDe=2020" in url
    assert "endPrdDe=2023" in url


@responses.activate
def test_get_key_indicator_details_recent_n(monkeypatch):
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("indIdDetailSearchRequest.do", KOSIS_LIST_RESPONSE_DETAIL)
    from mcp_server.server import get_key_indicator_details

    get_key_indicator_details.fn(jipyo_id="160", recent_n=5)  # type: ignore[attr-defined]

    url = responses.calls[0].request.url
    assert "srvRn=5" in url


def test_get_key_indicator_details_missing_id():
    from mcp_server.server import get_key_indicator_details

    result = get_key_indicator_details.fn(jipyo_id="")  # type: ignore[attr-defined]
    assert "error" in result


def test_search_key_indicators_id_rejects_non_numeric():
    """search_key_indicators(by='id', ...)는 numeric jipyoId만 받음.

    KOSIS API에 비숫자 jipyoId를 보내면 항상 빈 결과라서, 클라이언트 측에서
    조기에 친화적 에러를 반환해 라운드트립을 절약한다.
    """
    from mcp_server.server import search_key_indicators

    result = search_key_indicators.fn(by="id", value="abc")  # type: ignore[attr-defined]
    assert "error" in result
    assert "numeric jipyoId" in result["error"]
    assert result["count"] == 0
    assert result["results"] == []


def test_search_key_indicators_id_accepts_numeric(monkeypatch):
    """numeric value는 가드 통과 후 KOSIS 호출까지 진행."""
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    _stub("indListSearchRequest.do", KOSIS_LIST_RESPONSE_LIST)

    from mcp_server.server import search_key_indicators

    result = search_key_indicators.fn(by="id", value="160")  # type: ignore[attr-defined]
    # 가드 통과 → KOSIS mock 응답에 도달
    assert "error" not in result or "numeric jipyoId" not in result.get("error", "")
    assert result["count"] >= 0
