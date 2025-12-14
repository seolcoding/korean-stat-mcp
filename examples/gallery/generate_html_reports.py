"""
HTML 아티팩트 생성 스크립트.

이 스크립트는 다양한 시나리오별 HTML 보고서를 자동 생성합니다.
각 시나리오는 인터랙티브한 Plotly 차트가 포함된 단일 HTML 파일로 출력됩니다.

사용 방법:
    # 모든 시나리오 생성
    uv run python examples/gallery/generate_html_reports.py

    # 특정 시나리오만 생성
    uv run python examples/gallery/generate_html_reports.py --scenario population

    # 커스텀 쿼리로 생성
    uv run python examples/gallery/generate_html_reports.py --query "서울과 부산 인구 비교"

출력:
    examples/gallery/output/
    ├── population_analysis.html
    ├── cpi_analysis.html
    ├── employment_analysis.html
    └── custom_report.html
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools import StatisticsData, ReportGenerator, generate_html_report


# 시나리오 정의
SCENARIOS = {
    "population": {
        "name": "인구 통계 분석",
        "description": "행정구역별 인구수 추이 분석",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",
        "start_date": "2019",
        "end_date": "2023",
        "prd_se": "Y",
        "queries": [
            "전체 인구 추이 분석",
            "서울과 부산 인구 비교",
            "인구 상위 10개 지역 순위",
        ],
    },
    "cpi": {
        "name": "소비자물가지수 분석",
        "description": "월별 소비자물가지수 추이 분석",
        "org_id": "101",
        "tbl_id": "DT_1J22001",
        "start_date": "202301",
        "end_date": "202412",
        "prd_se": "M",
        "queries": [
            "최근 물가 추이 분석",
            "월별 물가 변동률",
        ],
    },
    "employment": {
        "name": "고용 통계 분석",
        "description": "경제활동인구 현황 분석",
        "org_id": "101",
        "tbl_id": "DT_1ES2A01",
        "start_date": "2019",
        "end_date": "2023",
        "prd_se": "Y",
        "queries": [
            "연도별 고용 추이",
            "경제활동인구 변화",
        ],
    },
}


def fetch_data(scenario: dict) -> list:
    """시나리오 데이터 조회"""
    print(f"\n📊 데이터 조회: {scenario['name']}")
    print(f"   테이블: {scenario['tbl_id']}")
    print(f"   기간: {scenario['start_date']} ~ {scenario['end_date']}")

    data_client = StatisticsData()
    records = data_client.get_data(
        org_id=scenario["org_id"],
        tbl_id=scenario["tbl_id"],
        start_date=scenario["start_date"],
        end_date=scenario["end_date"],
        prd_se=scenario["prd_se"],
    )

    if records:
        print(f"   ✅ {len(records):,}건 조회 완료")
    else:
        print("   ❌ 데이터 조회 실패")

    return records or []


def generate_scenario_reports(scenario_key: str, output_dir: Path) -> list:
    """시나리오별 HTML 보고서 생성"""
    scenario = SCENARIOS.get(scenario_key)
    if not scenario:
        print(f"❌ 알 수 없는 시나리오: {scenario_key}")
        return []

    records = fetch_data(scenario)
    if not records:
        return []

    generated_files = []
    generator = ReportGenerator(records)

    # 각 쿼리별 보고서 생성
    for idx, query in enumerate(scenario["queries"], 1):
        print(f"\n📝 HTML 생성 중: {query}")

        filename = f"{scenario_key}_{idx:02d}.html"
        output_path = output_dir / filename

        try:
            saved_path = generator.generate_html(
                user_query=query,
                output_path=output_path,
                title=f"{scenario['name']}: {query}",
            )
            print(f"   ✅ 저장: {saved_path}")
            generated_files.append(saved_path)
        except Exception as e:
            print(f"   ❌ 오류: {e}")

    return generated_files


def generate_custom_report(query: str, output_dir: Path) -> str:
    """커스텀 쿼리 보고서 생성"""
    # 기본 인구 데이터 사용
    scenario = SCENARIOS["population"]
    records = fetch_data(scenario)
    if not records:
        return None

    print(f"\n📝 커스텀 HTML 생성: {query}")
    output_path = output_dir / "custom_report.html"

    try:
        saved_path = generate_html_report(
            data=records,
            user_query=query,
            output_path=str(output_path),
            title=f"커스텀 분석: {query}",
        )
        print(f"   ✅ 저장: {saved_path}")
        return saved_path
    except Exception as e:
        print(f"   ❌ 오류: {e}")
        return None


def generate_index_html(output_dir: Path, generated_files: list) -> str:
    """인덱스 페이지 생성"""
    html = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KOSIS 분석 갤러리</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

        body {
            font-family: 'Noto Sans KR', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
            padding: 40px 20px;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
        }

        h1 {
            color: white;
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 10px;
        }

        .subtitle {
            color: rgba(255,255,255,0.8);
            text-align: center;
            margin-bottom: 40px;
        }

        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .card {
            background: white;
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
        }

        .card h3 {
            color: #333;
            margin-bottom: 15px;
        }

        .card a {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            margin-top: 10px;
        }

        .card a:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 KOSIS 분석 갤러리</h1>
        <p class="subtitle">인터랙티브 데이터 분석 보고서 모음</p>

        <div class="gallery">
'''

    for filepath in generated_files:
        filename = Path(filepath).name
        # 파일명에서 제목 추출
        title = filename.replace(".html", "").replace("_", " ").title()

        html += f'''
            <div class="card">
                <h3>📈 {title}</h3>
                <p>인터랙티브 차트가 포함된 분석 보고서</p>
                <a href="{filename}" target="_blank">보고서 열기 →</a>
            </div>
'''

    html += '''
        </div>
    </div>
</body>
</html>
'''

    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return str(index_path)


def main():
    parser = argparse.ArgumentParser(
        description="KOSIS HTML 아티팩트 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s                           # 모든 시나리오 생성
  %(prog)s --scenario population     # 인구 시나리오만
  %(prog)s --query "서울 인구 분석"  # 커스텀 쿼리
        """,
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()),
        help="생성할 시나리오 (기본: 전체)",
    )
    parser.add_argument(
        "--query", "-q",
        help="커스텀 분석 쿼리",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="출력 디렉토리 (기본: examples/gallery/output)",
    )

    args = parser.parse_args()

    # 출력 디렉토리
    output_dir = Path(args.output) if args.output else Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🎨 KOSIS HTML 아티팩트 생성기")
    print("=" * 60)

    generated_files = []

    if args.query:
        # 커스텀 쿼리
        result = generate_custom_report(args.query, output_dir)
        if result:
            generated_files.append(result)
    elif args.scenario:
        # 특정 시나리오
        generated_files.extend(generate_scenario_reports(args.scenario, output_dir))
    else:
        # 전체 시나리오
        for scenario_key in SCENARIOS:
            generated_files.extend(generate_scenario_reports(scenario_key, output_dir))

    # 인덱스 페이지 생성
    if generated_files:
        index_path = generate_index_html(output_dir, generated_files)
        print(f"\n📁 인덱스 페이지: {index_path}")

    print("\n" + "=" * 60)
    print(f"✅ 총 {len(generated_files)}개 HTML 파일 생성 완료")
    print(f"📂 출력 디렉토리: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
