#!/usr/bin/env python3
"""
인간 중심 데이터 스토리텔링 리포트 생성기.

"데이터가 있으니까 보여주자" ❌
"사람들이 궁금해하는 질문에 답하자" ✅

The Pudding, NYT Upshot 스타일의 스토리텔링 접근법:
1. 질문으로 시작 (Hook)
2. 핵심 인사이트 먼저 (Sledgehammer stat)
3. 점진적 공개 (Progressive disclosure)
4. 개인화 (Personal relevance)
5. 맥락 제공 (Context)
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import html

# 출력 디렉토리
OUTPUT_DIR = Path(__file__).parent / "gallery" / "stories"


@dataclass
class StorySection:
    """스토리 섹션."""
    type: str  # hook, insight, chart, comparison, conclusion, interactive
    content: str  # HTML content
    data: Optional[Dict] = None


@dataclass
class DataStory:
    """데이터 스토리 정의."""
    id: str
    question: str  # 인간의 질문
    hook: str  # 감정적 훅
    subtitle: str
    sections: List[StorySection] = field(default_factory=list)


# =============================================================================
# 모의 데이터 생성기 (실제로는 MCP 도구가 이 역할)
# =============================================================================

class StoryDataGenerator:
    """스토리용 데이터 생성."""

    REGIONS = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
               "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]

    @classmethod
    def population_migration(cls) -> Dict:
        """인구 이동 데이터."""
        # 서울 → 경기 이동이 가장 많음
        return {
            "서울_순유출": 78543,
            "경기_순유입": 112340,
            "인천_순유입": 23450,
            "세종_순유입": 18920,
            "부산_순유출": 15230,
            "flows": [
                {"from": "서울", "to": "경기", "count": 245000, "reason": "주거비"},
                {"from": "서울", "to": "인천", "count": 67000, "reason": "주거비"},
                {"from": "서울", "to": "세종", "count": 12000, "reason": "직장"},
                {"from": "부산", "to": "서울", "count": 34000, "reason": "취업"},
                {"from": "지방", "to": "수도권", "count": 89000, "reason": "교육/취업"},
            ],
            "yearly_trend": {
                "2019": -52000,
                "2020": -61000,
                "2021": -78000,
                "2022": -85000,
                "2023": -78543,
            },
            "top_destinations": [
                {"region": "경기 남부 (화성, 평택)", "share": 34.2},
                {"region": "경기 북부 (파주, 김포)", "share": 22.1},
                {"region": "인천 (송도, 청라)", "share": 15.8},
                {"region": "세종", "share": 8.4},
            ]
        }

    @classmethod
    def salary_distribution(cls) -> Dict:
        """임금 분포 데이터."""
        return {
            "median": 3500,  # 만원
            "mean": 4120,
            "percentiles": {
                "10": 2100,
                "25": 2800,
                "50": 3500,
                "75": 4800,
                "90": 7200,
                "99": 15000,
            },
            "by_age": {
                "20대": {"median": 2800, "mean": 3100},
                "30대": {"median": 3800, "mean": 4200},
                "40대": {"median": 4200, "mean": 4800},
                "50대": {"median": 3900, "mean": 4500},
                "60대": {"median": 2800, "mean": 3200},
            },
            "by_industry": {
                "금융보험": {"median": 6500, "rank": 1},
                "정보통신": {"median": 5800, "rank": 2},
                "전문과학": {"median": 4800, "rank": 3},
                "제조업": {"median": 4200, "rank": 4},
                "건설업": {"median": 3800, "rank": 5},
                "도소매": {"median": 3200, "rank": 6},
                "숙박음식": {"median": 2400, "rank": 7},
            },
            "vs_10years_ago": {
                "nominal_growth": 45.2,  # 명목 증가율 %
                "real_growth": 12.3,  # 실질 증가율 %
                "inflation_eaten": 32.9,  # 물가에 잠식된 부분
            }
        }

    @classmethod
    def housing_decision(cls) -> Dict:
        """주택 구매 의사결정 데이터."""
        return {
            "current_index": 118.5,  # 2021.6=100 기준
            "yearly_change": 2.3,  # %
            "monthly_change": 0.15,
            "historical": {
                "2019": 95.2,
                "2020": 100.0,
                "2021_peak": 125.3,
                "2022": 121.8,
                "2023": 116.2,
                "2024": 118.5,
            },
            "by_region": {
                "서울": {"index": 128.5, "change": 3.2, "msg": "반등 중"},
                "경기": {"index": 115.2, "change": 1.8, "msg": "완만한 상승"},
                "인천": {"index": 108.3, "change": -0.5, "msg": "보합"},
                "부산": {"index": 105.1, "change": -2.1, "msg": "하락 지속"},
                "대구": {"index": 98.7, "change": -4.2, "msg": "하락폭 확대"},
            },
            "rent_vs_buy": {
                "서울_평균_매매": 110000,  # 만원
                "서울_평균_전세": 55000,
                "월세_전환율": 4.5,  # %
                "예상_보유기간_손익분기": 7.2,  # 년
            },
            "expert_signals": [
                {"signal": "금리 인하 기대", "direction": "상승", "weight": 0.3},
                {"signal": "인구 감소", "direction": "하락", "weight": 0.2},
                {"signal": "공급 부족", "direction": "상승", "weight": 0.25},
                {"signal": "가계부채 부담", "direction": "하락", "weight": 0.25},
            ]
        }

    @classmethod
    def grocery_inflation(cls) -> Dict:
        """장바구니 물가 데이터."""
        return {
            "total_cpi": 113.8,
            "food_cpi": 121.5,
            "items": [
                {"name": "사과", "change": 45.2, "price_now": 12000, "price_year_ago": 8300, "icon": "🍎"},
                {"name": "배추", "change": 32.1, "price_now": 8500, "price_year_ago": 6400, "icon": "🥬"},
                {"name": "계란 30구", "change": 18.5, "price_now": 8900, "price_year_ago": 7500, "icon": "🥚"},
                {"name": "삼겹살 100g", "change": 12.3, "price_now": 2800, "price_year_ago": 2500, "icon": "🥓"},
                {"name": "쌀 10kg", "change": 8.7, "price_now": 32000, "price_year_ago": 29500, "icon": "🍚"},
                {"name": "우유 1L", "change": 5.2, "price_now": 2800, "price_year_ago": 2660, "icon": "🥛"},
                {"name": "라면 5개입", "change": -2.1, "price_now": 4500, "price_year_ago": 4600, "icon": "🍜"},
            ],
            "basket_total": {
                "year_ago": 45000,
                "now": 52800,
                "increase": 17.3,
            },
            "income_impact": {
                "min_wage_worker": 8.2,  # 소득 대비 식비 증가분 %
                "avg_worker": 3.1,
                "high_income": 1.2,
            }
        }

    @classmethod
    def youth_unemployment(cls) -> Dict:
        """청년 실업 데이터."""
        return {
            "current_rate": 6.8,  # %
            "overall_rate": 2.9,
            "ratio": 2.34,  # 청년/전체 비율
            "by_age": {
                "15-19": 9.2,
                "20-24": 7.8,
                "25-29": 5.9,
                "30-34": 3.2,
                "35-39": 2.4,
            },
            "historical": {
                "2014": 9.0,
                "2016": 9.8,
                "2018": 9.5,
                "2020": 9.0,  # 코로나
                "2022": 6.4,
                "2024": 6.8,
            },
            "international": {
                "한국": 6.8,
                "일본": 4.2,
                "미국": 7.5,
                "독일": 5.8,
                "프랑스": 17.2,
                "스페인": 28.5,
                "OECD평균": 10.5,
            },
            "quality_issues": {
                "비정규직_비율": 38.5,
                "체감실업률": 21.3,  # 확장실업률
                "취업준비생": 720000,  # 명
                "니트족": 450000,
            }
        }


# =============================================================================
# 스토리 빌더
# =============================================================================

def build_story_1_migration() -> str:
    """스토리 1: 서울 떠나는 사람들, 어디로 가고 있을까?"""
    data = StoryDataGenerator.population_migration()

    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>서울 떠나는 사람들, 어디로 가고 있을까?</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Noto Sans KR', sans-serif;
            background: #0a0a0a;
            color: #fff;
            line-height: 1.8;
        }}

        /* Hero Section */
        .hero {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(180deg, #0a0a0a 0%, #1a1a2e 100%);
            position: relative;
        }}

        .hero::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            opacity: 0.5;
        }}

        .hero-content {{
            position: relative;
            z-index: 1;
            max-width: 900px;
        }}

        .question {{
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 900;
            margin-bottom: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f64f59 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .hook {{
            font-size: 1.3rem;
            color: rgba(255,255,255,0.7);
            max-width: 600px;
            margin: 0 auto 50px;
        }}

        .scroll-hint {{
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%);
            animation: bounce 2s infinite;
            color: rgba(255,255,255,0.5);
        }}

        @keyframes bounce {{
            0%, 20%, 50%, 80%, 100% {{ transform: translateX(-50%) translateY(0); }}
            40% {{ transform: translateX(-50%) translateY(-20px); }}
            60% {{ transform: translateX(-50%) translateY(-10px); }}
        }}

        /* Sledgehammer Stat */
        .sledgehammer {{
            min-height: 80vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 60px 20px;
            background: #0f0f1a;
        }}

        .big-number {{
            font-size: clamp(5rem, 15vw, 12rem);
            font-weight: 900;
            color: #f64f59;
            line-height: 1;
        }}

        .big-number-unit {{
            font-size: clamp(1.5rem, 4vw, 2.5rem);
            color: rgba(255,255,255,0.6);
            margin-top: 10px;
        }}

        .big-number-context {{
            font-size: 1.2rem;
            color: rgba(255,255,255,0.5);
            margin-top: 30px;
            max-width: 500px;
            text-align: center;
        }}

        /* Story Section */
        .story-section {{
            padding: 100px 20px;
            max-width: 800px;
            margin: 0 auto;
        }}

        .section-title {{
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 30px;
            color: #667eea;
        }}

        .section-text {{
            font-size: 1.1rem;
            color: rgba(255,255,255,0.8);
            margin-bottom: 40px;
        }}

        /* Flow Visualization */
        .flow-container {{
            background: rgba(255,255,255,0.03);
            border-radius: 20px;
            padding: 40px;
            margin: 40px 0;
        }}

        .flow-item {{
            display: flex;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        .flow-item:last-child {{
            border-bottom: none;
        }}

        .flow-from {{
            width: 80px;
            text-align: center;
            font-weight: 700;
            color: #f64f59;
        }}

        .flow-arrow {{
            flex: 1;
            height: 4px;
            background: linear-gradient(90deg, #f64f59, #667eea);
            margin: 0 20px;
            position: relative;
        }}

        .flow-arrow::after {{
            content: '→';
            position: absolute;
            right: -10px;
            top: -12px;
            color: #667eea;
            font-size: 1.5rem;
        }}

        .flow-count {{
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.9rem;
            color: rgba(255,255,255,0.6);
        }}

        .flow-to {{
            width: 100px;
            text-align: center;
            font-weight: 700;
            color: #667eea;
        }}

        .flow-reason {{
            width: 80px;
            text-align: right;
            font-size: 0.85rem;
            color: rgba(255,255,255,0.5);
        }}

        /* Trend Chart */
        .trend-container {{
            background: rgba(255,255,255,0.03);
            border-radius: 20px;
            padding: 30px;
            margin: 40px 0;
        }}

        .trend-title {{
            font-size: 1.1rem;
            color: rgba(255,255,255,0.6);
            margin-bottom: 20px;
            text-align: center;
        }}

        .trend-bars {{
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            height: 200px;
            padding: 20px 0;
        }}

        .trend-bar-wrapper {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
        }}

        .trend-bar {{
            width: 40px;
            background: linear-gradient(180deg, #f64f59, #c471ed);
            border-radius: 4px 4px 0 0;
            transition: height 0.5s ease;
        }}

        .trend-label {{
            margin-top: 10px;
            font-size: 0.85rem;
            color: rgba(255,255,255,0.5);
        }}

        .trend-value {{
            margin-top: 5px;
            font-size: 0.9rem;
            font-weight: 700;
            color: #f64f59;
        }}

        /* Destination Cards */
        .dest-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 40px 0;
        }}

        .dest-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            transition: transform 0.3s, background 0.3s;
        }}

        .dest-card:hover {{
            transform: translateY(-5px);
            background: rgba(255,255,255,0.08);
        }}

        .dest-rank {{
            font-size: 3rem;
            font-weight: 900;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .dest-name {{
            font-size: 1rem;
            margin: 10px 0;
            color: rgba(255,255,255,0.9);
        }}

        .dest-share {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #667eea;
        }}

        /* Conclusion */
        .conclusion {{
            min-height: 60vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 80px 20px;
            background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
            text-align: center;
        }}

        .conclusion-text {{
            font-size: 1.5rem;
            max-width: 700px;
            color: rgba(255,255,255,0.8);
            margin-bottom: 40px;
        }}

        .conclusion-highlight {{
            color: #667eea;
            font-weight: 700;
        }}

        /* Footer */
        .footer {{
            padding: 40px 20px;
            text-align: center;
            color: rgba(255,255,255,0.3);
            font-size: 0.85rem;
            background: #0a0a0a;
        }}

        .data-source {{
            margin-top: 10px;
        }}

        .mcp-badge {{
            display: inline-block;
            background: linear-gradient(90deg, #667eea, #764ba2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <!-- Hero: 질문으로 시작 -->
    <section class="hero">
        <div class="hero-content">
            <h1 class="question">서울 떠나는 사람들,<br>어디로 가고 있을까?</h1>
            <p class="hook">
                2023년, 역대 최대 규모의 인구가 서울을 떠났습니다.<br>
                그들은 왜, 어디로 갔을까요?
            </p>
        </div>
        <div class="scroll-hint">
            <span style="font-size: 2rem;">↓</span><br>
            <span style="font-size: 0.9rem;">스크롤하여 계속</span>
        </div>
    </section>

    <!-- Sledgehammer Stat: 핵심 숫자 먼저 -->
    <section class="sledgehammer">
        <div class="big-number">-{data['서울_순유출']:,}</div>
        <div class="big-number-unit">명의 순유출</div>
        <p class="big-number-context">
            2023년 한 해 동안 서울을 떠난 사람에서 들어온 사람을 뺀 숫자입니다.
            하루 평균 <strong style="color: #f64f59;">215명</strong>이 서울을 떠난 셈입니다.
        </p>
    </section>

    <!-- Story Section 1: 어디로? -->
    <section class="story-section">
        <h2 class="section-title">그래서, 어디로 갔을까?</h2>
        <p class="section-text">
            서울을 떠난 사람들의 행선지를 추적했습니다.
            결과는 예상대로... 그리고 예상 밖이었습니다.
        </p>

        <div class="dest-grid">
            {"".join(f'''
            <div class="dest-card">
                <div class="dest-rank">#{i+1}</div>
                <div class="dest-name">{d['region']}</div>
                <div class="dest-share">{d['share']}%</div>
            </div>
            ''' for i, d in enumerate(data['top_destinations']))}
        </div>

        <p class="section-text">
            <strong style="color: #667eea;">경기 남부</strong>가 압도적 1위입니다.
            화성, 평택, 동탄 — 이른바 '신도시'로의 이동이 가장 많았습니다.
        </p>
    </section>

    <!-- Story Section 2: 왜? -->
    <section class="story-section">
        <h2 class="section-title">왜 떠날까?</h2>
        <p class="section-text">
            인구 이동의 이유를 데이터로 살펴보면,
            단 하나의 키워드로 수렴합니다.
        </p>

        <div class="flow-container">
            {"".join(f'''
            <div class="flow-item">
                <div class="flow-from">{f['from']}</div>
                <div class="flow-arrow">
                    <span class="flow-count">{f['count']:,}명</span>
                </div>
                <div class="flow-to">{f['to']}</div>
                <div class="flow-reason">#{f['reason']}</div>
            </div>
            ''' for f in data['flows'][:4])}
        </div>

        <p class="section-text" style="text-align: center; font-size: 1.5rem; color: #f64f59; font-weight: 700;">
            "주거비"
        </p>
        <p class="section-text" style="text-align: center;">
            서울 아파트 평균 매매가 11억, 전세 5.5억.<br>
            같은 돈이면 경기도에서 더 넓은 집을 살 수 있습니다.
        </p>
    </section>

    <!-- Story Section 3: 추세 -->
    <section class="story-section">
        <h2 class="section-title">이 추세, 계속될까?</h2>
        <p class="section-text">
            서울 인구 순유출은 5년 연속 증가하다 2023년 처음으로 소폭 감소했습니다.
        </p>

        <div class="trend-container">
            <div class="trend-title">서울 연간 순유출 추이 (명)</div>
            <div class="trend-bars">
                {"".join(f'''
                <div class="trend-bar-wrapper">
                    <div class="trend-bar" style="height: {abs(v)/1000}px;"></div>
                    <div class="trend-label">{y}</div>
                    <div class="trend-value">-{abs(v):,}</div>
                </div>
                ''' for y, v in data['yearly_trend'].items())}
            </div>
        </div>

        <p class="section-text">
            전문가들은 <strong style="color: #667eea;">GTX 개통</strong>과
            <strong style="color: #667eea;">금리 인하</strong>가 이 추세에 영향을 줄 것으로 전망합니다.
            서울 접근성이 좋아지면 수도권 외곽으로의 이동은 더 가속화될 수 있습니다.
        </p>
    </section>

    <!-- Conclusion -->
    <section class="conclusion">
        <p class="conclusion-text">
            서울은 더 이상 <span class="conclusion-highlight">'모이는 도시'</span>가 아닙니다.<br><br>
            높은 주거비를 피해 사람들은 경기도로, 인천으로 흩어지고 있습니다.
            이것은 단순한 이동이 아니라, <span class="conclusion-highlight">라이프스타일의 변화</span>입니다.
        </p>
        <p style="color: rgba(255,255,255,0.5); font-size: 1rem;">
            당신의 선택은 어디인가요?
        </p>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div>데이터로 보는 대한민국</div>
        <div class="data-source">출처: KOSIS 국가통계포털 (통계청 인구이동통계)</div>
        <div class="mcp-badge">🚀 MCP 기반 데이터 스토리텔링</div>
        <div style="margin-top: 15px;">Generated: {datetime.now().strftime("%Y-%m-%d")}</div>
    </footer>
</body>
</html>'''

    return html_content


def build_story_2_salary() -> str:
    """스토리 2: 내 월급, 평균 대비 어디쯤일까?"""
    data = StoryDataGenerator.salary_distribution()

    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>내 월급, 어디쯤일까?</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Noto Sans KR', sans-serif;
            background: #0a0a0a;
            color: #fff;
            line-height: 1.8;
        }}

        .hero {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(180deg, #0a0a0a 0%, #0f1922 100%);
        }}

        .question {{
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 900;
            margin-bottom: 30px;
            background: linear-gradient(135deg, #00d4aa 0%, #00b4d8 50%, #0077b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .hook {{
            font-size: 1.3rem;
            color: rgba(255,255,255,0.7);
            max-width: 600px;
            margin: 0 auto 50px;
        }}

        /* Interactive Input */
        .input-section {{
            min-height: 80vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 60px 20px;
            background: #0f1922;
        }}

        .input-container {{
            background: rgba(255,255,255,0.05);
            border-radius: 24px;
            padding: 50px;
            max-width: 500px;
            width: 100%;
        }}

        .input-label {{
            font-size: 1.1rem;
            color: rgba(255,255,255,0.7);
            margin-bottom: 15px;
            display: block;
        }}

        .salary-input {{
            width: 100%;
            padding: 20px;
            font-size: 2rem;
            font-weight: 700;
            text-align: center;
            background: rgba(255,255,255,0.1);
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 12px;
            color: #00d4aa;
            outline: none;
            transition: border-color 0.3s;
        }}

        .salary-input:focus {{
            border-color: #00d4aa;
        }}

        .input-hint {{
            font-size: 0.9rem;
            color: rgba(255,255,255,0.4);
            margin-top: 10px;
            text-align: center;
        }}

        .check-btn {{
            width: 100%;
            padding: 18px;
            margin-top: 30px;
            font-size: 1.1rem;
            font-weight: 700;
            background: linear-gradient(90deg, #00d4aa, #00b4d8);
            border: none;
            border-radius: 12px;
            color: #000;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .check-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 212, 170, 0.3);
        }}

        /* Result Section */
        .result-section {{
            display: none;
            min-height: 100vh;
            padding: 80px 20px;
            background: linear-gradient(180deg, #0f1922 0%, #0a0a0a 100%);
        }}

        .result-section.active {{
            display: block;
        }}

        .result-container {{
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }}

        .percentile-display {{
            margin: 60px 0;
        }}

        .percentile-number {{
            font-size: clamp(4rem, 12vw, 8rem);
            font-weight: 900;
            background: linear-gradient(135deg, #00d4aa, #00b4d8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .percentile-label {{
            font-size: 1.3rem;
            color: rgba(255,255,255,0.6);
            margin-top: 10px;
        }}

        .percentile-meaning {{
            font-size: 1.1rem;
            color: rgba(255,255,255,0.8);
            max-width: 500px;
            margin: 30px auto;
            padding: 25px;
            background: rgba(0, 212, 170, 0.1);
            border-radius: 16px;
            border-left: 4px solid #00d4aa;
        }}

        /* Distribution Chart */
        .distribution {{
            margin: 60px 0;
            padding: 40px;
            background: rgba(255,255,255,0.03);
            border-radius: 20px;
        }}

        .dist-title {{
            font-size: 1.2rem;
            color: rgba(255,255,255,0.6);
            margin-bottom: 30px;
        }}

        .dist-bar-container {{
            position: relative;
            height: 60px;
            background: linear-gradient(90deg, #1a3a4a, #0f1922);
            border-radius: 30px;
            overflow: hidden;
        }}

        .dist-bar {{
            height: 100%;
            background: linear-gradient(90deg, #00d4aa, #00b4d8);
            border-radius: 30px;
            transition: width 1s ease;
        }}

        .dist-marker {{
            position: absolute;
            top: -30px;
            transform: translateX(-50%);
            font-size: 1.5rem;
        }}

        .dist-labels {{
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            font-size: 0.9rem;
            color: rgba(255,255,255,0.5);
        }}

        /* Comparison Cards */
        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin: 40px 0;
        }}

        .comp-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
        }}

        .comp-percentile {{
            font-size: 0.85rem;
            color: rgba(255,255,255,0.5);
        }}

        .comp-amount {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #00d4aa;
            margin: 8px 0;
        }}

        .comp-label {{
            font-size: 0.85rem;
            color: rgba(255,255,255,0.6);
        }}

        /* Context Section */
        .context-section {{
            padding: 80px 20px;
            max-width: 800px;
            margin: 0 auto;
        }}

        .context-title {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #00d4aa;
            margin-bottom: 30px;
        }}

        .context-text {{
            font-size: 1.1rem;
            color: rgba(255,255,255,0.8);
            margin-bottom: 30px;
        }}

        .industry-list {{
            list-style: none;
        }}

        .industry-item {{
            display: flex;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        .industry-rank {{
            width: 40px;
            font-size: 1.2rem;
            font-weight: 700;
            color: #00b4d8;
        }}

        .industry-name {{
            flex: 1;
            color: rgba(255,255,255,0.8);
        }}

        .industry-salary {{
            font-weight: 700;
            color: #00d4aa;
        }}

        /* Footer */
        .footer {{
            padding: 40px 20px;
            text-align: center;
            color: rgba(255,255,255,0.3);
            font-size: 0.85rem;
            background: #0a0a0a;
        }}

        .mcp-badge {{
            display: inline-block;
            background: linear-gradient(90deg, #00d4aa, #00b4d8);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            color: #000;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <!-- Hero -->
    <section class="hero">
        <h1 class="question">내 월급,<br>어디쯤일까?</h1>
        <p class="hook">
            "평균 연봉 4천만원"이라는 뉴스를 볼 때마다 드는 생각.<br>
            "나는 평균도 못 받나?" 진짜 그런지 확인해봅시다.
        </p>
        <div style="margin-top: 50px; color: rgba(255,255,255,0.5);">
            <span style="font-size: 2rem;">↓</span><br>
            <span style="font-size: 0.9rem;">내 위치 확인하기</span>
        </div>
    </section>

    <!-- Interactive Input -->
    <section class="input-section">
        <div class="input-container">
            <label class="input-label">월급(세전)을 입력하세요</label>
            <input type="text" class="salary-input" id="salaryInput" placeholder="350" oninput="formatNumber(this)">
            <p class="input-hint">단위: 만원 (예: 350 = 350만원)</p>
            <button class="check-btn" onclick="checkSalary()">내 위치 확인하기</button>
        </div>
    </section>

    <!-- Result Section -->
    <section class="result-section" id="resultSection">
        <div class="result-container">
            <h2 style="font-size: 1.5rem; color: rgba(255,255,255,0.6); margin-bottom: 20px;">당신의 월급은</h2>

            <div class="percentile-display">
                <div class="percentile-number" id="percentileNumber">상위 45%</div>
                <p class="percentile-label">전체 근로자 중</p>
            </div>

            <div class="percentile-meaning" id="percentileMeaning">
                100명 중 45번째로 높은 월급을 받고 있습니다.
            </div>

            <!-- Distribution Visualization -->
            <div class="distribution">
                <div class="dist-title">전체 임금 분포에서 당신의 위치</div>
                <div class="dist-bar-container">
                    <div class="dist-bar" id="distBar" style="width: 0%;"></div>
                    <div class="dist-marker" id="distMarker" style="left: 0%;">📍</div>
                </div>
                <div class="dist-labels">
                    <span>하위 10%: {data['percentiles']['10']}만원</span>
                    <span>중위: {data['median']}만원</span>
                    <span>상위 10%: {data['percentiles']['90']}만원</span>
                </div>
            </div>

            <!-- Comparison -->
            <h3 style="font-size: 1.3rem; color: rgba(255,255,255,0.6); margin: 50px 0 30px;">비교해보면</h3>
            <div class="comparison-grid">
                <div class="comp-card">
                    <div class="comp-percentile">하위 10%</div>
                    <div class="comp-amount">{data['percentiles']['10']}만</div>
                    <div class="comp-label">최저 수준</div>
                </div>
                <div class="comp-card">
                    <div class="comp-percentile">하위 25%</div>
                    <div class="comp-amount">{data['percentiles']['25']}만</div>
                    <div class="comp-label">4분위</div>
                </div>
                <div class="comp-card" style="border: 2px solid #00d4aa;">
                    <div class="comp-percentile">중위값</div>
                    <div class="comp-amount">{data['median']}만</div>
                    <div class="comp-label">딱 중간</div>
                </div>
                <div class="comp-card">
                    <div class="comp-percentile">평균</div>
                    <div class="comp-amount">{data['mean']}만</div>
                    <div class="comp-label">고소득자 포함</div>
                </div>
                <div class="comp-card">
                    <div class="comp-percentile">상위 25%</div>
                    <div class="comp-amount">{data['percentiles']['75']}만</div>
                    <div class="comp-label">4분위</div>
                </div>
                <div class="comp-card">
                    <div class="comp-percentile">상위 10%</div>
                    <div class="comp-amount">{data['percentiles']['90']}만</div>
                    <div class="comp-label">고소득</div>
                </div>
            </div>
        </div>
    </section>

    <!-- Context Section -->
    <section class="context-section">
        <h2 class="context-title">잠깐, "평균"의 함정</h2>
        <p class="context-text">
            뉴스에서 자주 보는 "평균 월급 {data['mean']}만원".<br>
            하지만 <strong style="color: #00d4aa;">절반 이상</strong>의 근로자는 이 평균에 못 미칩니다.
        </p>
        <p class="context-text">
            왜? 소수의 고소득자가 평균을 끌어올리기 때문입니다.<br>
            그래서 <strong style="color: #00d4aa;">"중위값"</strong>이 더 현실적인 지표입니다.
        </p>

        <div style="background: rgba(0,212,170,0.1); padding: 25px; border-radius: 16px; margin: 30px 0;">
            <div style="font-size: 1.2rem; margin-bottom: 10px;">💡 알아두세요</div>
            <div style="color: rgba(255,255,255,0.8);">
                <strong>평균</strong>: {data['mean']}만원 (고소득자 영향 받음)<br>
                <strong>중위</strong>: {data['median']}만원 (딱 중간, 더 현실적)
            </div>
        </div>

        <h3 style="font-size: 1.3rem; color: #00d4aa; margin: 50px 0 20px;">업종별 중위 월급</h3>
        <ul class="industry-list">
            {"".join(f'''
            <li class="industry-item">
                <span class="industry-rank">#{v['rank']}</span>
                <span class="industry-name">{k}</span>
                <span class="industry-salary">{v['median']}만원</span>
            </li>
            ''' for k, v in data['by_industry'].items())}
        </ul>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div>데이터로 보는 대한민국</div>
        <div style="margin-top: 10px;">출처: KOSIS 국가통계포털 (고용노동부 임금구조기본통계)</div>
        <div class="mcp-badge">🚀 MCP 기반 데이터 스토리텔링</div>
    </footer>

    <script>
        function formatNumber(input) {{
            let value = input.value.replace(/[^0-9]/g, '');
            input.value = value;
        }}

        function checkSalary() {{
            const salary = parseInt(document.getElementById('salaryInput').value) || 0;
            const resultSection = document.getElementById('resultSection');

            // Percentile calculation (simplified)
            const percentiles = {json.dumps(data['percentiles'])};
            let percentile = 50;

            if (salary <= percentiles['10']) percentile = 90 + (10 * (salary / percentiles['10']));
            else if (salary <= percentiles['25']) percentile = 75 + (15 * ((salary - percentiles['10']) / (percentiles['25'] - percentiles['10'])));
            else if (salary <= percentiles['50']) percentile = 50 + (25 * ((salary - percentiles['25']) / (percentiles['50'] - percentiles['25'])));
            else if (salary <= percentiles['75']) percentile = 25 + (25 * ((salary - percentiles['50']) / (percentiles['75'] - percentiles['50'])));
            else if (salary <= percentiles['90']) percentile = 10 + (15 * ((salary - percentiles['75']) / (percentiles['90'] - percentiles['75'])));
            else percentile = Math.max(1, 10 - (10 * ((salary - percentiles['90']) / (percentiles['99'] - percentiles['90']))));

            percentile = Math.round(Math.max(1, Math.min(99, percentile)));

            // Update display
            document.getElementById('percentileNumber').textContent = `상위 ${{100 - percentile}}%`;
            document.getElementById('percentileMeaning').innerHTML =
                `100명 중 <strong style="color: #00d4aa;">${{100 - percentile}}번째</strong>로 높은 월급을 받고 있습니다.`;

            // Update distribution bar
            const barWidth = 100 - percentile;
            document.getElementById('distBar').style.width = barWidth + '%';
            document.getElementById('distMarker').style.left = barWidth + '%';

            // Show result section
            resultSection.classList.add('active');
            resultSection.scrollIntoView({{ behavior: 'smooth' }});
        }}
    </script>
</body>
</html>'''

    return html_content


def build_story_3_grocery() -> str:
    """스토리 3: 장바구니 물가, 1년 전과 얼마나 달라졌나"""
    data = StoryDataGenerator.grocery_inflation()

    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>장바구니 물가, 1년 전과 얼마나 달라졌나</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Noto Sans KR', sans-serif;
            background: #fffbf5;
            color: #2d2d2d;
            line-height: 1.8;
        }}

        .hero {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(180deg, #fff8ee 0%, #fffbf5 100%);
        }}

        .question {{
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 900;
            margin-bottom: 30px;
            color: #d63031;
        }}

        .hook {{
            font-size: 1.2rem;
            color: #636363;
            max-width: 500px;
            margin-bottom: 50px;
        }}

        .basket-icon {{
            font-size: 5rem;
            margin-bottom: 30px;
        }}

        /* Sledgehammer */
        .sledgehammer {{
            padding: 100px 20px;
            text-align: center;
            background: #fff;
        }}

        .big-compare {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 30px;
            flex-wrap: wrap;
        }}

        .compare-box {{
            padding: 40px;
            border-radius: 20px;
        }}

        .compare-label {{
            font-size: 1rem;
            color: #888;
            margin-bottom: 10px;
        }}

        .compare-value {{
            font-size: 3.5rem;
            font-weight: 900;
        }}

        .compare-box.before {{
            background: #f5f5f5;
        }}

        .compare-box.before .compare-value {{
            color: #666;
        }}

        .compare-box.after {{
            background: linear-gradient(135deg, #ff7675, #d63031);
            color: white;
        }}

        .compare-arrow {{
            font-size: 3rem;
            color: #d63031;
        }}

        .increase-badge {{
            display: inline-block;
            background: #d63031;
            color: white;
            padding: 15px 30px;
            border-radius: 30px;
            font-size: 1.5rem;
            font-weight: 700;
            margin-top: 40px;
        }}

        /* Items Section */
        .items-section {{
            padding: 80px 20px;
            max-width: 900px;
            margin: 0 auto;
        }}

        .section-title {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #2d2d2d;
            margin-bottom: 40px;
            text-align: center;
        }}

        .item-grid {{
            display: grid;
            gap: 15px;
        }}

        .item-card {{
            display: flex;
            align-items: center;
            padding: 20px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}

        .item-icon {{
            font-size: 2.5rem;
            margin-right: 20px;
        }}

        .item-info {{
            flex: 1;
        }}

        .item-name {{
            font-weight: 700;
            font-size: 1.1rem;
            margin-bottom: 5px;
        }}

        .item-prices {{
            font-size: 0.9rem;
            color: #888;
        }}

        .item-change {{
            text-align: right;
        }}

        .change-value {{
            font-size: 1.5rem;
            font-weight: 900;
        }}

        .change-value.up {{
            color: #d63031;
        }}

        .change-value.down {{
            color: #00b894;
        }}

        .change-bar {{
            width: 100px;
            height: 8px;
            background: #eee;
            border-radius: 4px;
            margin-top: 8px;
            overflow: hidden;
        }}

        .change-bar-fill {{
            height: 100%;
            border-radius: 4px;
        }}

        .change-bar-fill.up {{
            background: linear-gradient(90deg, #ff7675, #d63031);
        }}

        .change-bar-fill.down {{
            background: #00b894;
        }}

        /* Impact Section */
        .impact-section {{
            padding: 80px 20px;
            background: #2d2d2d;
            color: white;
        }}

        .impact-container {{
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }}

        .impact-title {{
            font-size: 1.8rem;
            margin-bottom: 50px;
        }}

        .impact-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .impact-card {{
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 30px;
        }}

        .impact-emoji {{
            font-size: 2.5rem;
            margin-bottom: 15px;
        }}

        .impact-label {{
            color: rgba(255,255,255,0.6);
            font-size: 0.9rem;
            margin-bottom: 10px;
        }}

        .impact-value {{
            font-size: 2rem;
            font-weight: 900;
            color: #ff7675;
        }}

        .impact-desc {{
            font-size: 0.85rem;
            color: rgba(255,255,255,0.5);
            margin-top: 10px;
        }}

        /* Footer */
        .footer {{
            padding: 40px 20px;
            text-align: center;
            color: #888;
            font-size: 0.85rem;
        }}

        .mcp-badge {{
            display: inline-block;
            background: linear-gradient(90deg, #ff7675, #d63031);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            color: white;
            margin-top: 15px;
        }}
    </style>
</head>
<body>
    <!-- Hero -->
    <section class="hero">
        <div class="basket-icon">🛒</div>
        <h1 class="question">장바구니 물가,<br>1년 전과 얼마나 달라졌나</h1>
        <p class="hook">
            마트에 갈 때마다 "또 올랐네..." 하는 느낌.<br>
            진짜 그런지, 데이터로 확인해봤습니다.
        </p>
    </section>

    <!-- Sledgehammer -->
    <section class="sledgehammer">
        <h2 style="font-size: 1.3rem; color: #888; margin-bottom: 40px;">일주일치 장보기 비용</h2>

        <div class="big-compare">
            <div class="compare-box before">
                <div class="compare-label">1년 전</div>
                <div class="compare-value">{data['basket_total']['year_ago']:,}원</div>
            </div>

            <div class="compare-arrow">→</div>

            <div class="compare-box after">
                <div class="compare-label">지금</div>
                <div class="compare-value">{data['basket_total']['now']:,}원</div>
            </div>
        </div>

        <div class="increase-badge">+{data['basket_total']['increase']}% 상승</div>

        <p style="margin-top: 40px; color: #888; max-width: 500px; margin-left: auto; margin-right: auto;">
            같은 품목을 같은 양만큼 샀을 때,<br>
            1년 전보다 <strong style="color: #d63031;">{data['basket_total']['now'] - data['basket_total']['year_ago']:,}원</strong>을 더 내야 합니다.
        </p>
    </section>

    <!-- Items -->
    <section class="items-section">
        <h2 class="section-title">품목별로 보면</h2>

        <div class="item-grid">
            {"".join(f'''
            <div class="item-card">
                <div class="item-icon">{item['icon']}</div>
                <div class="item-info">
                    <div class="item-name">{item['name']}</div>
                    <div class="item-prices">{item['price_year_ago']:,}원 → {item['price_now']:,}원</div>
                </div>
                <div class="item-change">
                    <div class="change-value {'up' if item['change'] > 0 else 'down'}">
                        {'+' if item['change'] > 0 else ''}{item['change']}%
                    </div>
                    <div class="change-bar">
                        <div class="change-bar-fill {'up' if item['change'] > 0 else 'down'}"
                             style="width: {min(abs(item['change']) * 2, 100)}%;"></div>
                    </div>
                </div>
            </div>
            ''' for item in data['items'])}
        </div>

        <p style="text-align: center; margin-top: 40px; color: #888;">
            🍎 사과가 <strong style="color: #d63031;">+{data['items'][0]['change']}%</strong>로 가장 많이 올랐습니다.<br>
            기후변화로 인한 작황 부진이 원인입니다.
        </p>
    </section>

    <!-- Impact -->
    <section class="impact-section">
        <div class="impact-container">
            <h2 class="impact-title">누구에게 더 아플까?</h2>

            <div class="impact-cards">
                <div class="impact-card">
                    <div class="impact-emoji">😰</div>
                    <div class="impact-label">최저임금 근로자</div>
                    <div class="impact-value">+{data['income_impact']['min_wage_worker']}%</div>
                    <div class="impact-desc">소득 대비 식비 증가분</div>
                </div>

                <div class="impact-card">
                    <div class="impact-emoji">😐</div>
                    <div class="impact-label">평균 소득자</div>
                    <div class="impact-value">+{data['income_impact']['avg_worker']}%</div>
                    <div class="impact-desc">소득 대비 식비 증가분</div>
                </div>

                <div class="impact-card">
                    <div class="impact-emoji">😊</div>
                    <div class="impact-label">고소득자</div>
                    <div class="impact-value">+{data['income_impact']['high_income']}%</div>
                    <div class="impact-desc">소득 대비 식비 증가분</div>
                </div>
            </div>

            <p style="margin-top: 50px; color: rgba(255,255,255,0.7); max-width: 600px; margin-left: auto; margin-right: auto;">
                물가 상승은 <strong style="color: #ff7675;">저소득층에게 더 큰 타격</strong>을 줍니다.<br>
                소득의 더 많은 부분을 식비에 쓰기 때문입니다.
            </p>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div>데이터로 보는 대한민국</div>
        <div style="margin-top: 10px;">출처: KOSIS 국가통계포털 (통계청 소비자물가조사)</div>
        <div class="mcp-badge">🚀 MCP 기반 데이터 스토리텔링</div>
    </footer>
</body>
</html>'''

    return html_content


def generate_index(stories: List[Dict]) -> str:
    """스토리 인덱스 페이지 생성."""
    cards_html = ""
    for story in stories:
        cards_html += f'''
        <a href="{story['filename']}" class="story-card" style="--accent: {story['color']};">
            <div class="story-icon">{story['icon']}</div>
            <h2 class="story-question">{story['question']}</h2>
            <p class="story-hook">{story['hook']}</p>
            <div class="story-cta">읽어보기 →</div>
        </a>
        '''

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>데이터로 답하는 질문들</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Noto Sans KR', sans-serif;
            background: #0a0a0a;
            color: #fff;
            min-height: 100vh;
            padding: 60px 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        h1 {{
            font-size: 2.5rem;
            text-align: center;
            margin-bottom: 20px;
            font-weight: 900;
        }}

        .subtitle {{
            text-align: center;
            color: rgba(255,255,255,0.6);
            margin-bottom: 60px;
            font-size: 1.1rem;
        }}

        .stories-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
        }}

        .story-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 24px;
            padding: 40px;
            text-decoration: none;
            color: inherit;
            transition: all 0.3s ease;
            display: block;
        }}

        .story-card:hover {{
            transform: translateY(-10px);
            border-color: var(--accent);
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        }}

        .story-icon {{
            font-size: 3rem;
            margin-bottom: 20px;
        }}

        .story-question {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 15px;
            color: var(--accent);
        }}

        .story-hook {{
            color: rgba(255,255,255,0.6);
            font-size: 1rem;
            margin-bottom: 25px;
            line-height: 1.6;
        }}

        .story-cta {{
            color: var(--accent);
            font-weight: 500;
        }}

        .footer {{
            text-align: center;
            margin-top: 80px;
            color: rgba(255,255,255,0.3);
            font-size: 0.85rem;
        }}

        .mcp-info {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 30px;
            margin-top: 30px;
            text-align: left;
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
        }}

        .mcp-info h3 {{
            color: #667eea;
            margin-bottom: 15px;
        }}

        .mcp-info p {{
            color: rgba(255,255,255,0.6);
            font-size: 0.95rem;
            line-height: 1.7;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>데이터로 답하는 질문들</h1>
        <p class="subtitle">
            "그래서 어쩌라고?"가 아닌, "아, 그렇구나!"를 위한 데이터 스토리
        </p>

        <div class="stories-grid">
            {cards_html}
        </div>

        <footer class="footer">
            <div>KOSIS 데이터 기반 스토리텔링</div>

            <div class="mcp-info">
                <h3>🚀 MCP 기반 데이터 스토리텔링</h3>
                <p>
                    이 리포트들은 MCP(Model Context Protocol)를 통해 생성되었습니다.<br><br>
                    <strong>핵심 원칙:</strong><br>
                    1. 데이터가 아닌 <em>질문</em>으로 시작<br>
                    2. 핵심 인사이트를 <em>먼저</em> 보여주기 (Sledgehammer stat)<br>
                    3. 개인화된 <em>맥락</em> 제공<br>
                    4. 스토리 <em>흐름</em>으로 이해 돕기
                </p>
            </div>

            <div style="margin-top: 30px;">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
        </footer>
    </div>
</body>
</html>'''


def main():
    """메인 실행."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  📖 인간 중심 데이터 스토리텔링 리포트 생성")
    print("=" * 70)

    stories = []

    # Story 1: 인구 이동
    print("\n📍 스토리 1: 서울 떠나는 사람들...")
    html1 = build_story_1_migration()
    path1 = OUTPUT_DIR / "story_migration.html"
    path1.write_text(html1, encoding="utf-8")
    print(f"   ✅ {path1}")
    stories.append({
        "filename": "story_migration.html",
        "question": "서울 떠나는 사람들, 어디로 가고 있을까?",
        "hook": "2023년 역대 최대 인구가 서울을 떠났습니다. 그들의 행선지와 이유를 추적했습니다.",
        "icon": "🏃",
        "color": "#f64f59",
    })

    # Story 2: 월급
    print("\n💰 스토리 2: 내 월급 위치...")
    html2 = build_story_2_salary()
    path2 = OUTPUT_DIR / "story_salary.html"
    path2.write_text(html2, encoding="utf-8")
    print(f"   ✅ {path2}")
    stories.append({
        "filename": "story_salary.html",
        "question": "내 월급, 어디쯤일까?",
        "hook": "'평균 연봉 4천' 뉴스를 볼 때마다 드는 의문. 내 위치를 직접 확인해보세요.",
        "icon": "💵",
        "color": "#00d4aa",
    })

    # Story 3: 장바구니 물가
    print("\n🛒 스토리 3: 장바구니 물가...")
    html3 = build_story_3_grocery()
    path3 = OUTPUT_DIR / "story_grocery.html"
    path3.write_text(html3, encoding="utf-8")
    print(f"   ✅ {path3}")
    stories.append({
        "filename": "story_grocery.html",
        "question": "장바구니 물가, 1년 전과 얼마나 달라졌나",
        "hook": "마트 갈 때마다 '또 올랐네...' 느낌. 진짜 그런지 품목별로 확인해봤습니다.",
        "icon": "🛒",
        "color": "#d63031",
    })

    # Index
    print("\n📚 인덱스 페이지 생성...")
    index_html = generate_index(stories)
    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    print(f"   ✅ {index_path}")

    print("\n" + "=" * 70)
    print(f"  ✅ 총 {len(stories)}개 스토리 생성 완료")
    print(f"  📂 {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
