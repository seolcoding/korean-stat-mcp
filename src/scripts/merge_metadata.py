#!/usr/bin/env python3
"""
CSV 파일에 KOSIS 메타데이터를 추가하는 스크립트
TBL_ID 컬럼을 기준으로 JSON 파일의 데이터를 CSV에 병합합니다.
"""

import csv
import json
import argparse
from pathlib import Path
import sys


def merge_kosis_metadata(csv_path, json_path, output_path=None):
    """
    CSV 파일에 JSON 메타데이터를 추가합니다.

    Args:
        csv_path: 입력 CSV 파일 경로
        json_path: KOSIS 메타데이터 JSON 파일 경로
        output_path: 출력 CSV 파일 경로 (None인 경우 자동 생성)
    """
    # 출력 파일 경로 설정
    if output_path is None:
        csv_path_obj = Path(csv_path)
        output_path = csv_path_obj.parent / f"{csv_path_obj.stem}_with_metadata.csv"

    # JSON 데이터 읽기
    print(f"JSON 파일 읽는 중: {json_path}")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        print(f"JSON 항목 수: {len(json_data):,}")
    except Exception as e:
        print(f"JSON 파일 읽기 오류: {e}")
        sys.exit(1)

    # TBL_ID를 키로 하는 lookup 딕셔너리 생성
    json_lookup = {item["TBL_ID"]: item for item in json_data}

    # 추가할 컬럼 정의
    additional_columns = [
        "STAT_ID",  # 통계 ID
        "STAT_NM",  # 통계명
        "ORG_ID",  # 기관 ID
        "ORG_NM",  # 기관명
        "VW_CD",  # 뷰 코드
        "MT_ATITLE",  # 메타 타이틀
        "FULL_PATH_ID",  # 전체 경로 ID
        "LINK_URL",  # 링크 URL
    ]

    # CSV 읽고 처리하기
    print(f"\nCSV 파일 읽는 중: {csv_path}")
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames
        print(f"CSV 행 수: {len(rows):,}")
    except Exception as e:
        print(f"CSV 파일 읽기 오류: {e}")
        sys.exit(1)

    # 새 필드명 생성 (기존 필드 + 추가 필드)
    new_fieldnames = fieldnames + additional_columns

    # 각 행에 메타데이터 추가
    matched_count = 0
    for row in rows:
        tbl_id = row.get("통계표 아이디(TBL_ID)", "").strip()

        if tbl_id and tbl_id in json_lookup:
            # 매칭되는 데이터가 있으면 추가
            matched_data = json_lookup[tbl_id]
            for col in additional_columns:
                row[col] = matched_data.get(col, "")
            matched_count += 1
        else:
            # 매칭되지 않으면 빈 값으로 추가
            for col in additional_columns:
                row[col] = ""

    # 결과를 새 CSV 파일로 저장
    print(f"\n결과 저장 중: {output_path}")
    try:
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=new_fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("저장 완료!")
    except Exception as e:
        print(f"CSV 파일 저장 오류: {e}")
        sys.exit(1)

    # 결과 요약
    print("\n=== 처리 결과 ===")
    print(f"전체 행 수: {len(rows):,}")
    print(f"매칭된 행 수: {matched_count:,}")
    print(f"매칭되지 않은 행 수: {len(rows) - matched_count:,}")
    print(f"매칭률: {matched_count / len(rows) * 100:.1f}%")
    print("\n추가된 컬럼:")
    for col in additional_columns:
        print(f"  - {col}")


def main():
    parser = argparse.ArgumentParser(
        description="CSV 파일에 KOSIS 메타데이터를 추가합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
python merge_metadata.py data/regional_index_data_list.csv
kosis_data/kosis_metadata_intermediate.json
python merge_metadata.py input.csv metadata.json -o output.csv
        """,
    )

    parser.add_argument("csv_file", help="입력 CSV 파일 경로")
    parser.add_argument("json_file", help="KOSIS 메타데이터 JSON 파일 경로")
    parser.add_argument(
        "-o",
        "--output",
        help="출력 CSV 파일 경로 (기본값: 입력파일명_with_metadata.csv)",
    )

    args = parser.parse_args()

    # 파일 존재 확인
    if not Path(args.csv_file).exists():
        print(f"오류: CSV 파일을 찾을 수 없습니다: {args.csv_file}")
        sys.exit(1)

    if not Path(args.json_file).exists():
        print(f"오류: JSON 파일을 찾을 수 없습니다: {args.json_file}")
        sys.exit(1)

    # 병합 실행
    merge_kosis_metadata(args.csv_file, args.json_file, args.output)


if __name__ == "__main__":
    main()
