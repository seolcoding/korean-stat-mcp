#!/usr/bin/env python3
"""Build a local one-page KOSIS data visualization dashboard."""

from __future__ import annotations

import base64
import html
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kosis-onepager"
ITEMS = OUT / "items"
ASSETS = OUT / "assets"
DETAILS = OUT / "details"
LIVE = OUT / "live"


KOREAN_META = {
    "fertility": {
        "title": "합계출산율",
        "unit": "합계출산율: 여성 1명당 출생아 수 / 연령별 출산율: 여성 1천 명당 출생아 수",
        "insight": "전국 합계출산율은 2014년 1.205에서 2023년 0.721로 낮아졌다. 30대 초반 출산율도 함께 확인해야 추세의 중심 연령대를 볼 수 있다.",
    },
    "housing": {
        "title": "전국 주택매매가격 변동률",
        "unit": "월간 변동률 %",
        "insight": "전국 주택매매가격 변동률은 2021년 상승 폭이 컸고, 2022년 하락 구간을 거친 뒤 2023년 말에는 약한 하락세로 마무리됐다.",
    },
    "unemployment": {
        "title": "실업률과 경제활동인구",
        "unit": "실업률 %, 경제활동인구 천 명",
        "insight": "실업률은 2020년 고점 이후 낮아졌고 2024년에는 2.8% 수준이다. 경제활동인구는 장기적으로 증가했다.",
    },
    "cpi": {
        "title": "소비자물가 등락률",
        "unit": "전년 대비 %",
        "insight": "소비자물가 등락률은 2022년에 5.1%로 정점을 찍은 뒤 2024년 2.3%로 둔화됐다.",
    },
    "elderly": {
        "title": "65세 이상 인구",
        "unit": "명 / 전체 인구 대비 %",
        "insight": "65세 이상 인구는 2024년 1,025만 명을 넘었고, 전체 인구 대비 비중은 20.0%에 도달했다.",
    },
    "single_household": {
        "title": "1인 가구",
        "unit": "가구 / 일반가구 대비 %",
        "insight": "전국 1인 가구는 2024년 804만 가구로, 일반가구의 36.1%를 차지한다. 2015년 이후 가구 수와 비중이 모두 크게 늘었다.",
    },
    "tourism": {
        "title": "외래 관광객",
        "unit": "천 명",
        "insight": "외래 관광객 장기 추이는 팬데믹 충격과 회복 국면을 함께 보여준다.",
    },
    "energy": {
        "title": "재생에너지 발전량",
        "unit": "TWh",
        "insight": "재생에너지 발전량은 중장기적으로 증가했지만 전력 구성 내 비중 해석이 함께 필요하다.",
    },
    "education": {
        "title": "초등학생 수",
        "unit": "명",
        "insight": "초등학생 수는 저출산 효과가 시차를 두고 교육 현장으로 이동하는 지표다.",
    },
    "wage": {
        "title": "평균소득",
        "unit": "만원",
        "insight": "평균소득은 상승하더라도 분포와 중위값을 함께 봐야 생활 체감과의 차이를 줄일 수 있다.",
    },
}


def ensure_dirs() -> None:
    ITEMS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    DETAILS.mkdir(parents=True, exist_ok=True)


def load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def live_result(item: dict[str, Any]) -> dict[str, Any] | None:
    path = LIVE / f"{item['id']}.json"
    if not path.exists():
        return None
    return load_json(path)


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).replace(",", "").strip()
    if s in {"", "-", "*", "..."}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def clean_label(value: Any) -> str:
    return re.sub(r"<[^>]+>|＜br＞", " ", str(value or "")).strip()


def period_range(points: list[dict[str, Any]]) -> str:
    periods = [str(p["period"]) for p in points if p.get("period")]
    if not periods:
        return ""
    return f"{min(periods)}-{max(periods)}"


def latest(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(points, key=lambda p: str(p["period"])) if points else None


def first(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    return min(points, key=lambda p: str(p["period"])) if points else None


def compact_points(rows: list[dict[str, Any]], *, label_filter: str | None = None, region: str | None = None) -> list[dict[str, Any]]:
    by_period: dict[str, float] = {}
    for row in rows:
        if label_filter and label_filter not in clean_label(row.get("ITM_NM")):
            continue
        if region and clean_label(row.get("C1_NM")) != region:
            continue
        period = str(row.get("PRD_DE") or "")
        value = to_float(row.get("DT"))
        if period and value is not None:
            by_period[period] = value
    return [{"period": p, "value": by_period[p]} for p in sorted(by_period)]


def make_item(
    *,
    id: str,
    title: str,
    source_file: str,
    records: int,
    table_ids: list[str],
    unit: str,
    points: list[dict[str, Any]],
    insight: str,
    label: str = "전국",
) -> dict[str, Any]:
    a = first(points)
    z = latest(points)
    kpis = []
    if z:
        kpis.append({"label": "최신값", "value": round(z["value"], 2), "unit": unit, "detail": str(z["period"])})
    if a and z and a["value"]:
        change = (z["value"] - a["value"]) / abs(a["value"]) * 100
        kpis.append({"label": "기간 변화율", "value": round(change, 1), "unit": "%", "detail": f"{a['period']} 대비"})
    return {
        "id": id,
        "title": title,
        "source_file": source_file,
        "records": records,
        "table_ids": sorted(set(table_ids)),
        "period_range": period_range(points),
        "unit": unit,
        "series": [{"label": label, "values": points[-16:]}],
        "kpis": kpis,
        "insight": insight,
    }


def generate_main_items() -> None:
    # These four were not assigned to workers because the agent pool limit was 6.
    tourism = load_json(ROOT / "kosis-reports/data/report_008_tourism.json")
    tourism_points = compact_points(tourism["inbound_outbound"], label_filter="외래 관광객", region=None)
    (ITEMS / "tourism.json").write_text(
        json.dumps(
            make_item(
                id="tourism",
                title="관광 유입",
                source_file="kosis-reports/data/report_008_tourism.json",
                records=sum(len(v) for v in tourism.values()),
                table_ids=[r["TBL_ID"] for r in tourism["inbound_outbound"][:1] + tourism["visitor_arrivals"][:1]],
                unit="1000명",
                points=tourism_points,
                insight="외래 관광객 장기 추이는 팬데믹 충격과 회복 국면을 함께 보여준다.",
                label="외래 관광객",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    energy = load_json(ROOT / "kosis-reports/data/report_010_processed.json")
    energy_points = [{"period": str(x["year"]), "value": to_float(x.get("value"))} for x in energy["charts"]["renewable_trend"]]
    energy_points = [x for x in energy_points if x["value"] is not None]
    (ITEMS / "energy.json").write_text(
        json.dumps(
            make_item(
                id="energy",
                title="재생에너지",
                source_file="kosis-reports/data/report_010_processed.json",
                records=len(energy_points),
                table_ids=["DT_38804_B03"],
                unit="TWh",
                points=energy_points,
                insight="재생에너지 발전량은 중장기적으로 증가했지만 전력 구성 내 비중 해석이 함께 필요하다.",
                label="재생에너지 발전량",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    education = load_json(ROOT / "kosis-reports/data/report_016_education.json")
    edu_points = compact_points(education["elementary_students"], label_filter="학생수", region="전국")
    (ITEMS / "education.json").write_text(
        json.dumps(
            make_item(
                id="education",
                title="초등학생 수",
                source_file="kosis-reports/data/report_016_education.json",
                records=sum(len(v) for k, v in education.items() if isinstance(v, list)),
                table_ids=["DT_1YL21241"],
                unit="명",
                points=edu_points,
                insight="초등학생 수는 저출산 효과가 시차를 두고 교육 현장으로 이동하는 지표다.",
                label="전국 초등학생",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    wage = load_json(ROOT / "kosis-reports/data/report_018_wage.json")
    wage_rows = wage["datasets"]["income_distribution"]["data"]
    wage_points = compact_points(wage_rows, label_filter="평균소득", region="데이터")
    (ITEMS / "wage.json").write_text(
        json.dumps(
            make_item(
                id="wage",
                title="평균소득",
                source_file="kosis-reports/data/report_018_wage.json",
                records=sum(len(v["data"]) for v in wage["datasets"].values()),
                table_ids=[v["table_id"] for v in wage["datasets"].values()],
                unit="만원",
                points=wage_points,
                insight="평균소득은 상승하더라도 분포와 중위값을 함께 봐야 생활 체감과의 차이를 줄일 수 있다.",
                label="평균소득",
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


IMAGE_PROMPTS = {
    "fertility": "Clean editorial data illustration of South Korea fertility decline, minimalist vector-like infographic, warm human-centered tone, no text, 16:9.",
    "housing": "Clean editorial data illustration of Korean housing price movement, apartment skyline and chart lines, no text, 16:9.",
    "unemployment": "Clean editorial data illustration of employment and job market statistics, people and line graph, no text, 16:9.",
    "cpi": "Clean editorial data illustration of inflation and consumer prices, grocery basket and rising index chart, no text, 16:9.",
    "elderly": "Clean editorial data illustration of aging population in Korea, seniors and demographic chart, no text, 16:9.",
    "single_household": "Clean editorial data illustration of one-person households, compact apartment interior and statistics chart, no text, 16:9.",
    "tourism": "Clean editorial data illustration of tourism flows to Korea, airport arrival stream and map lines, no text, 16:9.",
    "energy": "Clean editorial data illustration of renewable energy transition, solar panels wind power and chart, no text, 16:9.",
    "education": "Clean editorial data illustration of changing student population, classroom and demographic chart, no text, 16:9.",
    "wage": "Clean editorial data illustration of wage and income trends, pay slip and upward chart, no text, 16:9.",
}


def fallback_svg(item: dict[str, Any]) -> Path:
    path = ASSETS / f"{item['id']}.svg"
    title = html.escape(item["title"])
    insight = html.escape(item.get("insight", ""))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
<defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#0f766e"/><stop offset="0.55" stop-color="#2563eb"/><stop offset="1" stop-color="#111827"/></linearGradient></defs>
<rect width="1200" height="675" fill="url(#g)"/>
<g opacity=".18" fill="none" stroke="#fff" stroke-width="9">
<path d="M90 510 C260 330 350 470 510 300 S780 250 1110 145"/>
<path d="M90 560 C300 420 410 520 570 390 S820 335 1110 245"/>
</g>
<circle cx="930" cy="180" r="110" fill="#ffffff" opacity=".14"/>
<circle cx="240" cy="500" r="160" fill="#ffffff" opacity=".10"/>
<text x="72" y="112" font-family="Arial, sans-serif" font-size="56" font-weight="700" fill="#fff">{title}</text>
<text x="72" y="590" font-family="Arial, sans-serif" font-size="24" fill="#e5f3ff">{insight[:80]}</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")
    return path


def generate_image(item: dict[str, Any]) -> tuple[str, str]:
    target = ASSETS / f"{item['id']}.png"
    if target.exists() and target.stat().st_size > 1000:
        return item["id"], f"assets/{target.name}"
    prompt = IMAGE_PROMPTS.get(item["id"], f"KOSIS data visualization concept for {item['title']}, no text, 16:9")
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI

            client = OpenAI()
            result = client.images.generate(
                model=os.environ.get("KOSIS_IMAGE_MODEL", "gpt-image-2"),
                prompt=prompt,
                size="1536x1024",
                n=1,
            )
            b64 = result.data[0].b64_json
            if b64:
                target.write_bytes(base64.b64decode(b64))
                return item["id"], f"assets/{target.name}"
        except Exception as exc:
            print(f"image generation failed for {item['id']}: {exc}", file=sys.stderr)
    return item["id"], f"assets/{fallback_svg(item).name}"


def fmt_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return str(value)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def display_title(item: dict[str, Any]) -> str:
    return KOREAN_META.get(item["id"], {}).get("title", safe_text(item.get("title", "")))


def display_unit(item: dict[str, Any]) -> str:
    return KOREAN_META.get(item["id"], {}).get("unit", unit_text(item.get("unit", "")))


def table_unit(item: dict[str, Any]) -> str:
    mapping = {
        "fertility": "출산율",
        "housing": "월간 %",
        "unemployment": "%",
        "cpi": "%",
        "elderly": "명",
        "single_household": "가구",
        "tourism": "천 명",
        "energy": "TWh",
        "education": "명",
        "wage": "만원",
    }
    return mapping.get(item["id"], display_unit(item))


def display_insight(item: dict[str, Any]) -> str:
    return KOREAN_META.get(item["id"], {}).get("insight", safe_text(item.get("insight", "")))


def unit_text(value: Any) -> str:
    if isinstance(value, dict):
        return " / ".join(f"{translate_key(k)} {v}" for k, v in value.items())
    if isinstance(value, list):
        return " / ".join(map(str, value))
    return str(value or "")


def translate_key(value: Any) -> str:
    mapping = {
        "frequency": "주기",
        "monthly": "월간",
        "annual": "연간",
        "start": "시작",
        "end": "종료",
        "elderly_population": "65세 이상 인구",
        "total_population": "전체 인구",
        "elderly_share": "65세 이상 비중",
        "single_households": "1인 가구",
        "total_households": "일반가구",
        "single_household_share_pct": "1인 가구 비중",
        "unemployment_rate": "실업률",
        "economically_active_population": "경제활동인구",
        "thousand persons": "천 명",
        "households": "가구",
        "births per woman": "여성 1명당 출생아 수",
        "births per 1,000 women": "여성 1천 명당 출생아 수",
        "Total fertility rate": "합계출산율",
        "Latest total fertility rate": "최신 합계출산율",
        "Total fertility rate change": "합계출산율 변화",
        "Highest 2023 age-specific fertility rate": "2023년 최고 연령별 출산율",
        "Age 40-44 change": "40~44세 출산율 변화",
        "positive_months": "상승 월수",
        "negative_months": "하락 월수",
        "flat_months": "보합 월수",
        "unemployment_rate_change_2015_to_2024": "실업률 변화",
        "unemployment_rate_change_2023_to_2024": "전년 대비 실업률 변화",
        "economically_active_population_change_2015_to_2024": "경제활동인구 변화",
        "population_change_since_2015": "65세 이상 인구 증가",
        "population_growth_since_2015_pct": "65세 이상 인구 증가율",
        "share_change_since_2015_pp": "65세 이상 비중 변화",
        "count_change_since_start": "1인 가구 증가",
        "count_growth_pct_since_start": "1인 가구 증가율",
        "share_change_pp_since_start": "1인 가구 비중 변화",
        "yoy_count_change": "전년 대비 1인 가구 증가",
        "yoy_share_change_pp": "전년 대비 비중 변화",
        "Whole country": "전국",
        "from": "",
        "to": "~",
    }
    return mapping.get(str(value), str(value))


def translate_phrase(value: Any) -> str:
    text = str(value or "")
    replacements = {
        "births per woman": "여성 1명당 출생아 수",
        "births per 1,000 women": "여성 1천 명당 출생아 수",
        "Whole country": "전국",
        "whole country": "전국",
        "Latest total fertility rate": "최신 합계출산율",
        "Total fertility rate change": "합계출산율 변화",
        "Total fertility rate": "합계출산율",
        "Age-specific fertility rate": "연령별 출산율",
        "Age 30-34": "30~34세",
        "Age 40-44": "40~44세",
        "2014 to 2023": "2014~2023",
        "from ": "",
        " to ": " → ",
        "monthly": "월간",
        "annual": "연간",
        "thousand persons": "천 명",
        "households": "가구",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def display_period(item: dict[str, Any], points: list[dict[str, Any]]) -> str:
    period = item.get("period_range")
    if isinstance(period, dict):
        start = period.get("start")
        end = period.get("end")
        freq = translate_key(period.get("frequency", ""))
        if start and end and freq:
            return f"{start}~{end} · {freq}"
        if start and end:
            return f"{start}~{end}"
    if isinstance(period, str) and period:
        return period.replace("-", "~")
    return period_range(points).replace("-", "~")


def record_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def primary_series(item: dict[str, Any]) -> list[dict[str, Any]]:
    series = item.get("series")
    if isinstance(series, list) and series:
        first_series = series[0]
        if isinstance(first_series, dict):
            if isinstance(first_series.get("values"), list):
                return first_series["values"]
            if isinstance(first_series.get("points"), list):
                return first_series["points"]
            if isinstance(first_series.get("records"), list):
                return first_series["records"]
            if "year" in first_series:
                points = []
                for row in series:
                    value = row.get("value", row.get("annual_compounded_change_pct", row.get("avg_monthly_change_pct")))
                    value = to_float(value)
                    if value is not None:
                        points.append({"period": str(row.get("year")), "value": value})
                return points
    if isinstance(series, dict):
        for value in series.values():
            if isinstance(value, list) and value:
                return value
    return []


def all_series(item: dict[str, Any]) -> list[dict[str, Any]]:
    series = item.get("series")
    normalized: list[dict[str, Any]] = []
    if isinstance(series, list):
        for index, entry in enumerate(series, start=1):
            if not isinstance(entry, dict):
                continue
            values = entry.get("values") or entry.get("points") or entry.get("records")
            if isinstance(values, list):
                normalized.append({
                    "label": translate_phrase(entry.get("label") or entry.get("item") or f"시계열 {index}"),
                    "unit": translate_phrase(entry.get("unit") or table_unit(item)),
                    "values": values,
                })
            elif "year" in entry:
                points = []
                for row in series:
                    if not isinstance(row, dict):
                        continue
                    value = row.get("value", row.get("annual_compounded_change_pct", row.get("avg_monthly_change_pct")))
                    value = to_float(value)
                    if value is not None:
                        points.append({"period": str(row.get("year")), "value": value})
                normalized.append({"label": display_title(item), "unit": table_unit(item), "values": points})
                break
    elif isinstance(series, dict):
        for key, values in series.items():
            if isinstance(values, list):
                normalized.append({"label": translate_key(key), "unit": table_unit(item), "values": values})
    if not normalized:
        normalized.append({"label": display_title(item), "unit": table_unit(item), "values": primary_series(item)})
    return normalized


def normalize_kpis(item: dict[str, Any], points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kpis = item.get("kpis")
    if isinstance(kpis, list):
        return [
            {
                **kpi,
                "label": translate_phrase(kpi.get("label", "지표")),
                "unit": translate_phrase(kpi.get("unit", display_unit(item))),
                "detail": translate_phrase(kpi.get("detail", "")),
            }
            for kpi in kpis
            if isinstance(kpi, dict)
        ]
    if isinstance(kpis, dict):
        normalized: list[dict[str, Any]] = []
        if "latest" in kpis and isinstance(kpis["latest"], dict):
            latest_kpi = kpis["latest"]
            normalized.append({
                "label": "최신값",
                "value": latest_kpi.get("value"),
                "unit": display_unit(item),
                "detail": latest_kpi.get("period", ""),
            })
        elif "latest_period" in kpis:
            value_key = next((k for k in kpis if k.startswith("latest_") and k != "latest_period"), None)
            normalized.append({
                "label": translate_key(value_key.replace("latest_", "") if value_key else "최신값"),
                "value": kpis.get(value_key) if value_key else "",
                "unit": display_unit(item),
                "detail": kpis.get("latest_period", ""),
            })
        elif "latest_month" in kpis and isinstance(kpis["latest_month"], dict):
            normalized.append({
                "label": "최신 월간값",
                "value": kpis["latest_month"].get("change_pct"),
                "unit": "%",
                "detail": kpis["latest_month"].get("period", ""),
            })
        elif "latest_year" in kpis:
            normalized.append({
                "label": "최신값",
                "value": kpis.get("latest_unemployment_rate"),
                "unit": "%",
                "detail": kpis.get("latest_year", ""),
            })
        for key, value in kpis.items():
            if len(normalized) >= 2:
                break
            if isinstance(value, (int, float)) and not key.startswith("latest_"):
                normalized.append({
                    "label": translate_key(key),
                    "value": value,
                    "unit": "%" if "pct" in key or "rate" in key or "share" in key else display_unit(item),
                    "detail": display_period(item, points),
                })
        if normalized:
            return normalized
    z = latest(points)
    a = first(points)
    fallback = []
    if z:
        fallback.append({"label": "최신값", "value": z["value"], "unit": item.get("unit", ""), "detail": z["period"]})
    if a and z and a["value"]:
        fallback.append({"label": "기간 변화율", "value": round((z["value"] - a["value"]) / abs(a["value"]) * 100, 1), "unit": "%", "detail": f"{a['period']} 대비"})
    return fallback


def sparkline(points: list[dict[str, Any]]) -> str:
    if len(points) < 2:
        return ""
    values = [p["value"] for p in points if p.get("value") is not None]
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    coords = []
    width, height = 280, 84
    for i, p in enumerate(points):
        x = i * width / max(1, len(points) - 1)
        y = height - ((p["value"] - lo) / span * height)
        coords.append(f"{x:.1f},{y:.1f}")
    return f"""<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none">
<polyline points="{' '.join(coords)}"></polyline>
</svg>"""


def source_links(item: dict[str, Any], *, item_prefix: str = "items/", source_prefix: str = "../../") -> str:
    item_file = f"{item_prefix}{item['id']}.json"
    source_file = safe_text(item.get("source_file", ""))
    source_href = source_prefix + source_file if source_file else ""
    table_ids = ", ".join(map(str, item.get("table_ids", [])))
    links = [f'<a href="{html.escape(item_file)}">가공 데이터</a>']
    if source_file:
        links.append(f'<a href="{html.escape(source_href)}">원천 데이터 파일</a>')
    if table_ids:
        links.append(f'<span>통계표 ID: {html.escape(table_ids)}</span>')
    return " · ".join(links)


def data_table(points: list[dict[str, Any]], unit: str) -> str:
    rows = []
    for point in points[-10:]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(point.get('period', '')))}</td>"
            f"<td>{html.escape(fmt_value(point.get('value', '')))}</td>"
            f"<td>{html.escape(unit)}</td>"
            "</tr>"
        )
    if not rows:
        return "<p class=\"empty\">표시할 수치 데이터가 없습니다.</p>"
    return (
        '<table class="data-table"><thead><tr><th>기간</th><th>값</th><th>단위</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def data_table_full(points: list[dict[str, Any]], unit: str) -> str:
    rows = []
    for point in points:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(point.get('period', '')))}</td>"
            f"<td>{html.escape(fmt_value(point.get('value', '')))}</td>"
            f"<td>{html.escape(unit)}</td>"
            "</tr>"
        )
    if not rows:
        return "<p class=\"empty\">표시할 수치 데이터가 없습니다.</p>"
    return (
        '<table class="data-table"><thead><tr><th>기간</th><th>값</th><th>단위</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def live_badge(item: dict[str, Any]) -> str:
    live = live_result(item)
    if not live:
        return '<span class="live-badge pending">실시간 API 미검증</span>'
    if live.get("status") == "ok":
        count = live.get("record_count", 0)
        return f'<span class="live-badge ok">실시간 KOSIS API 검증 완료 · {html.escape(str(count))}건</span>'
    return f'<span class="live-badge pending">실시간 API 확인 필요 · {html.escape(str(live.get("status", "")))}</span>'


def live_panel(item: dict[str, Any]) -> str:
    live = live_result(item)
    if not live:
        return """
<section class="panel">
  <h2>실시간 API 검증</h2>
  <p>아직 실시간 KOSIS API 검증 결과가 없습니다.</p>
</section>"""
    params = live.get("params", {})
    param_rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in params.items()
    )
    sample = live.get("sample") or []
    sample_rows = []
    for row in sample[:5]:
        sample_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('PRD_DE', '')))}</td>"
            f"<td>{html.escape(clean_label(row.get('ITM_NM', '')))}</td>"
            f"<td>{html.escape(clean_label(row.get('C1_NM', '')))}</td>"
            f"<td>{html.escape(str(row.get('DT', '')))}</td>"
            f"<td>{html.escape(str(row.get('UNIT_NM', '')))}</td>"
            "</tr>"
        )
    sample_table = (
        '<table class="data-table"><thead><tr><th>기간</th><th>항목</th><th>분류</th><th>값</th><th>단위</th></tr></thead>'
        f"<tbody>{''.join(sample_rows)}</tbody></table>"
        if sample_rows
        else "<p>응답 샘플이 없습니다.</p>"
    )
    return f"""
<section class="panel">
  <h2>실시간 KOSIS API 검증</h2>
  <p>{live_badge(item)}</p>
  <p class="source-line">엔드포인트: <a href="{html.escape(live.get('endpoint', ''))}">{html.escape(live.get('endpoint', ''))}</a></p>
  <h3>호출 파라미터</h3>
  <table class="data-table"><tbody>{param_rows}</tbody></table>
  <h3>응답 샘플</h3>
  {sample_table}
</section>"""


def kpi_block(kpis: list[dict[str, Any]]) -> str:
    cells = []
    for kpi in kpis[:2]:
        label = translate_phrase(kpi.get("label", "지표"))
        value = fmt_value(kpi.get("value", ""))
        unit = translate_phrase(kpi.get("unit", ""))
        detail = translate_phrase(kpi.get("detail", ""))
        cells.append(
            '<div class="kpi-cell">'
            f'<span class="kpi-label">{html.escape(label)}</span>'
            f"<strong>{html.escape(value)}</strong>"
            f"<em>{html.escape(' · '.join(x for x in [unit, detail] if x))}</em>"
            "</div>"
        )
    return "".join(cells)


def deep_dive_copy(item: dict[str, Any], points: list[dict[str, Any]], kpis: list[dict[str, Any]]) -> str:
    title = display_title(item)
    period = display_period(item, points)
    unit = display_unit(item)
    z = latest(points)
    a = first(points)
    direction = ""
    if a and z:
        if z["value"] > a["value"]:
            direction = "상승"
        elif z["value"] < a["value"]:
            direction = "하락"
        else:
            direction = "보합"
    latest_sentence = ""
    if z:
        latest_sentence = f"최신 관측치는 {z['period']}년 기준 {fmt_value(z['value'])}입니다."
    change_sentence = ""
    if a and z and a["value"]:
        change = (z["value"] - a["value"]) / abs(a["value"]) * 100
        change_sentence = f"{a['period']}년 대비 {z['period']}년 값은 {fmt_value(change)}% {direction}했습니다."
    return (
        f"{title} 데이터는 {period} 범위의 {unit} 지표를 바탕으로 요약했습니다. "
        f"{latest_sentence} {change_sentence} "
        f"{display_insight(item)} 세부 표에서는 원천 파일에서 추출한 기간별 값을 직접 확인할 수 있습니다."
    )


def build_detail_pages(items: list[dict[str, Any]], image_paths: dict[str, str]) -> None:
    for item in items:
        series = primary_series(item)
        kpis = normalize_kpis(item, series)
        period = display_period(item, series)
        unit = display_unit(item)
        title = display_title(item)
        all_tables = []
        for entry in all_series(item):
            values = entry.get("values", [])
            if not isinstance(values, list):
                continue
            all_tables.append(
                f"""
<section class="panel">
  <h2>{html.escape(entry.get('label', title))}</h2>
  {sparkline(values)}
  {data_table_full(values, translate_phrase(entry.get('unit') or table_unit(item)))}
</section>"""
            )
        image_src = "../" + image_paths.get(item["id"], "")
        detail_doc = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)} 딥 다이브</title>
<style>
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:#17202a; background:#f5f7fb; }}
a {{ color:#2563eb; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
header {{ padding:28px 40px; background:#fff; border-bottom:1px solid #d8dee9; }}
.back {{ display:inline-block; margin-bottom:18px; color:#0f766e; font-weight:700; }}
.hero {{ display:grid; grid-template-columns:360px minmax(0, 1fr); gap:28px; align-items:stretch; }}
.hero img {{ width:100%; height:100%; min-height:280px; object-fit:cover; border-radius:8px; background:#0f172a; }}
h1 {{ margin:0 0 10px; font-size:42px; letter-spacing:0; }}
.meta {{ color:#64748b; font-size:14px; margin-bottom:18px; }}
.kpis {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin:18px 0; }}
.kpi-cell {{ padding:14px 16px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; }}
.kpi-label {{ display:block; color:#475569; font-size:13px; }}
.kpis strong {{ display:block; font-size:30px; color:#0f766e; margin-top:4px; }}
.kpis em {{ display:block; color:#64748b; font-style:normal; font-size:13px; line-height:1.4; }}
p {{ line-height:1.7; }}
main {{ padding:28px 40px 56px; display:grid; gap:18px; }}
.panel {{ background:#fff; border:1px solid #d8dee9; border-radius:8px; padding:22px; }}
.panel h2 {{ margin:0 0 14px; font-size:22px; }}
.source-line {{ color:#64748b; line-height:1.6; }}
.spark {{ width:100%; height:120px; margin:8px 0 18px; overflow:visible; }}
.spark polyline {{ fill:none; stroke:#2563eb; stroke-width:4; stroke-linecap:round; stroke-linejoin:round; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.data-table th, .data-table td {{ padding:8px 10px; border-bottom:1px solid #e2e8f0; text-align:right; }}
.data-table th:first-child, .data-table td:first-child {{ text-align:left; }}
.data-table th {{ color:#475569; background:#f8fafc; }}
@media (max-width:900px) {{
  header, main {{ padding-left:18px; padding-right:18px; }}
  .hero {{ grid-template-columns:1fr; }}
  h1 {{ font-size:32px; }}
  .kpis {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
<header>
  <a class="back" href="../index.html">← 원페이지로 돌아가기</a>
  <div class="hero">
    <img src="{html.escape(image_src)}" alt="" />
    <div>
      <div class="meta">{html.escape(period)} · {html.escape(unit)}</div>
      <h1>{html.escape(title)} 딥 다이브</h1>
      <p>{live_badge(item)}</p>
      <div class="kpis">{kpi_block(kpis)}</div>
      <p>{html.escape(deep_dive_copy(item, series, kpis))}</p>
    </div>
  </div>
</header>
<main>
  <section class="panel">
    <h2>원본 출처</h2>
    <div class="source-line">{source_links(item, item_prefix="../items/", source_prefix="../../../")}</div>
  </section>
  {live_panel(item)}
  {''.join(all_tables)}
</main>
</body>
</html>"""
        (DETAILS / f"{item['id']}.html").write_text(detail_doc, encoding="utf-8")


def build_html(items: list[dict[str, Any]], image_paths: dict[str, str]) -> None:
    cards = []
    for item in items:
        series = primary_series(item)
        kpis = normalize_kpis(item, series)
        kpi = kpis[0] if kpis else {}
        change = kpis[1] if len(kpis) > 1 else {}
        period = display_period(item, series)
        unit = display_unit(item)
        cards.append(f"""
<article class="card" id="{html.escape(item['id'])}" data-href="details/{html.escape(item['id'])}.html" tabindex="0" role="link" aria-label="{html.escape(display_title(item))} 딥 다이브 보기">
  <img src="{html.escape(image_paths.get(item['id'], ''))}" alt="" />
  <div class="body">
    <div class="meta">{html.escape(period)} · {html.escape(unit)}</div>
    <h2>{html.escape(display_title(item))}</h2>
    {live_badge(item)}
    <div class="kpis">{kpi_block([kpi, change] if change else [kpi])}</div>
    {sparkline(series)}
    <p>{html.escape(display_insight(item))}</p>
    <a class="deep-link" href="details/{html.escape(item['id'])}.html">딥 다이브 분석 보기 →</a>
    <details>
      <summary>원본 출처와 데이터 확인</summary>
      <div class="source-line">{source_links(item)}</div>
      {data_table(series, table_unit(item))}
    </details>
  </div>
</article>""")

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>KOSIS 데이터 10면 원페이지</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:#17202a; background:#f5f7fb; }}
header {{ padding:48px 40px 28px; background:#ffffff; border-bottom:1px solid #d8dee9; }}
h1 {{ margin:0; font-size:42px; letter-spacing:0; }}
header p {{ max-width:980px; line-height:1.6; color:#475569; }}
.summary {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:12px; margin-top:24px; }}
.summary div {{ padding:16px; background:#eef6f4; border:1px solid #cfe7e1; border-radius:8px; }}
.summary strong {{ display:block; font-size:26px; color:#0f766e; }}
main {{ padding:28px 40px 56px; display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:18px; }}
.card {{ background:#fff; border:1px solid #d8dee9; border-radius:8px; overflow:hidden; display:grid; grid-template-columns:220px minmax(0, 1fr); min-height:300px; cursor:pointer; transition:border-color .15s ease, transform .15s ease; }}
.card:hover {{ border-color:#0f766e; transform:translateY(-1px); }}
.card img {{ width:100%; height:100%; object-fit:cover; background:#0f172a; }}
.body {{ padding:20px; min-width:0; }}
.meta, .source-line {{ color:#64748b; font-size:12px; }}
h2 {{ margin:6px 0 12px; font-size:24px; }}
.kpis {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-bottom:14px; }}
.kpi-cell {{ min-width:0; padding:10px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; }}
.kpi-label {{ display:block; color:#475569; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.kpis strong {{ display:block; font-size:26px; color:#0f766e; margin-top:2px; }}
.kpis em {{ display:block; color:#64748b; font-style:normal; font-size:12px; line-height:1.35; }}
.spark {{ width:100%; height:84px; margin:8px 0 14px; overflow:visible; }}
.spark polyline {{ fill:none; stroke:#2563eb; stroke-width:4; stroke-linecap:round; stroke-linejoin:round; }}
p {{ line-height:1.55; margin:0 0 12px; }}
.deep-link {{ display:inline-block; margin:0 0 8px; color:#2563eb; font-weight:700; font-size:13px; }}
details {{ margin-top:12px; border-top:1px solid #e2e8f0; padding-top:10px; }}
summary {{ cursor:pointer; color:#0f766e; font-weight:700; font-size:13px; }}
.source-line {{ margin:9px 0; line-height:1.5; }}
.source-line a {{ color:#2563eb; text-decoration:none; }}
.source-line a:hover {{ text-decoration:underline; }}
.live-badge {{ display:inline-block; margin:0 0 10px; padding:5px 8px; border-radius:999px; font-size:12px; font-weight:700; }}
.live-badge.ok {{ color:#0f766e; background:#e7f7f1; border:1px solid #b7e4d3; }}
.live-badge.pending {{ color:#92400e; background:#fff7ed; border:1px solid #fed7aa; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.data-table th, .data-table td {{ padding:7px 8px; border-bottom:1px solid #e2e8f0; text-align:right; }}
.data-table th:first-child, .data-table td:first-child {{ text-align:left; }}
.data-table th {{ color:#475569; background:#f8fafc; }}
.empty {{ color:#64748b; font-size:13px; }}
footer {{ padding:22px 40px; color:#64748b; border-top:1px solid #d8dee9; background:#fff; }}
@media (max-width: 900px) {{
  main {{ grid-template-columns:1fr; padding:18px; }}
  header {{ padding:32px 18px 20px; }}
  .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .card {{ grid-template-columns:1fr; }}
  .card img {{ height:210px; }}
  h1 {{ font-size:32px; }}
}}
</style>
</head>
<body>
<header>
  <h1>KOSIS 데이터 10면 추출 · 시각화 원페이지</h1>
  <p>로컬 저장소의 KOSIS 추출 데이터 10종을 요약하고, KOSIS 공식 API로 원천 응답을 대조했습니다. 각 주제는 요약 카드에서 원본 출처를 확인하고, 클릭하면 세부 딥 다이브 분석 문서로 이동합니다.</p>
  <section class="summary">
    <div><strong>{len(items)}</strong>데이터 주제</div>
    <div><strong>{sum(record_count(i.get('records')) for i in items):,}</strong>원천 레코드</div>
    <div><strong>{sum(len(i.get('table_ids', [])) for i in items)}</strong>테이블 참조</div>
    <div><strong>{time.strftime('%Y-%m-%d')}</strong>생성일</div>
  </section>
</header>
<main>
{''.join(cards)}
</main>
<footer>로컬 생성 경로: outputs/kosis-onepager · 이미지 모델: {html.escape(os.environ.get('KOSIS_IMAGE_MODEL', 'gpt-image-2'))}</footer>
<script>
document.querySelectorAll('.card[data-href]').forEach((card) => {{
  const go = () => {{ window.location.href = card.dataset.href; }};
  card.addEventListener('click', (event) => {{
    if (event.target.closest('a, details, summary, table')) return;
    go();
  }});
  card.addEventListener('keydown', (event) => {{
    if (event.key === 'Enter' || event.key === ' ') {{
      event.preventDefault();
      go();
    }}
  }});
}});
</script>
</body>
</html>"""
    (OUT / "index.html").write_text(html_doc, encoding="utf-8")


def main() -> int:
    ensure_dirs()
    generate_main_items()
    item_paths = sorted(ITEMS.glob("*.json"))
    items = [load_json(p) for p in item_paths]
    desired = ["fertility", "housing", "unemployment", "cpi", "elderly", "single_household", "tourism", "energy", "education", "wage"]
    items_by_id = {i["id"]: i for i in items}
    missing = [x for x in desired if x not in items_by_id]
    if missing:
        print(f"Missing items: {missing}", file=sys.stderr)
    ordered = [items_by_id[x] for x in desired if x in items_by_id]
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(generate_image, item) for item in ordered]
        image_paths = dict(f.result() for f in as_completed(futures))
    build_detail_pages(ordered, image_paths)
    build_html(ordered, image_paths)
    print(OUT / "index.html")
    return 0 if len(ordered) == len(desired) else 1


if __name__ == "__main__":
    raise SystemExit(main())
