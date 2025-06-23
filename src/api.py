import json
import time
from pathlib import Path
import re
import os

import requests
from dotenv import load_dotenv

_ = load_dotenv()

# --- 설정 ---
# TODO: KOSIS에서 발급받은 본인의 API 키를 입력하세요.
API_KEY = os.getenv("KOSIS_API_KEY")
BASE_URL = os.getenv("KOSIS_API_ENDPOINT")
if API_KEY is None:
    raise ValueError("")

BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

# --- 입출력 파일/폴더 설정 ---
INPUT_METADATA_FILE = Path("./kosis_data/kosis_metadata_final.json")
OUTPUT_DIR = Path("./kosis_data/processed_data")


def fix_and_parse_json(response_text):
    """
    KOSIS의 비표준 JSON 응답을 수정하고 파싱합니다.
    """
    if not response_text or response_text.strip() == "":
        return None
    try:
        # 키에 따옴표가 없는 경우를 처리하는 정규표현식
        corrected_text = re.sub(
            r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', response_text
        )
        return json.loads(corrected_text)
    except json.JSONDecodeError as e:
        print(f"  [오류] JSON 파싱 실패: {e}")
        print(f"    원본 응답의 일부: {response_text[:200]}...")
        return None


def transform_kosis_data(raw_data):
    """
    KOSIS 원시 데이터를 목표 형식으로 변환합니다.
    [{item: "", timestamp:"", value:""}]
    """
    processed_records = []
    if not raw_data:
        return processed_records

    for record in raw_data:
        # item 이름을 C1_NM, C2_NM, ..., ITM_NM을 조합하여 생성
        item_parts = []
        for i in range(1, 9):  # C1 ~ C8
            c_nm = record.get(f"C{i}_NM")
            if c_nm:
                item_parts.append(c_nm.strip())

        itm_nm = record.get("ITM_NM")
        if itm_nm:
            item_parts.append(itm_nm.strip())

        item_name = " - ".join(part for part in item_parts if part)

        processed_records.append(
            {
                "item": item_name,
                "timestamp": record.get("PRD_DE"),
                "value": record.get("DT"),
            }
        )
    return processed_records


def process_single_table(metadata):
    """
    하나의 메타데이터 항목에 대해 실제 데이터를 가져오고 최종 JSON을 생성합니다.
    """
    org_id = metadata.get("ORG_ID")
    tbl_id = metadata.get("TBL_ID")
    tbl_nm = metadata.get("TBL_NM")

    if not all([org_id, tbl_id, tbl_nm]):
        print(
            f"  [건너뛰기] 필수 메타데이터(ORG_ID, TBL_ID)가 없어 {tbl_nm} 처리를 건너뜁니다."
        )
        return

    print(f"--- '{tbl_nm}' ({tbl_id}) 처리 시작 ---")

    # 최적의 수록주기(prdSe) 탐색: 월 > 분기 > 반기 > 년
    period_priority = [("M", "월"), ("Q", "분기"), ("H", "반기"), ("Y", "년")]
    raw_data = None
    selected_period_name = ""

    for prd_se, prd_name in period_priority:
        params = {
            "method": "getList",
            "apiKey": API_KEY,
            "format": "json",
            "orgId": org_id,
            "tblId": tbl_id,
            "objL1": "ALL",
            "itmId": "ALL",
            "prdSe": prd_se,
            "startPrdDe": metadata.get("STRT_PRD_DE"),
            "endPrdDe": metadata.get("END_PRD_DE"),
        }

        try:
            print(f"  - 주기 '{prd_name}'({prd_se})로 데이터 요청 중...")
            response = requests.get(BASE_URL, params=params, timeout=60)
            response.raise_for_status()

            data = fix_and_parse_json(response.text)

            if data and "errMsg" not in data:
                raw_data = data
                selected_period_name = prd_name
                print(
                    f"  ✔ 성공: 주기 '{selected_period_name}'에서 데이터 {len(raw_data)}건을 찾았습니다."
                )
                break  # 데이터 찾으면 루프 종료
            else:
                print(f"  - 정보: 주기 '{prd_name}'에 해당하는 데이터가 없습니다.")

            time.sleep(1)  # API 서버 부하 방지

        except requests.exceptions.RequestException as e:
            print(f"  [오류] API 요청 실패: {e}")
            # 다음 주기로 계속 시도

    if not raw_data:
        print(
            f"  ❌ 실패: {tbl_nm}({tbl_id})에 대한 데이터를 어떤 주기에서도 가져올 수 없습니다."
        )
        return

    # KOSIS 원시 데이터를 목표 포맷으로 변환
    processed_data = transform_kosis_data(raw_data)

    # 최종 JSON 파일 구조 생성
    item_list = sorted(list(set(record["item"] for record in processed_data)))

    # TODO: 아래 title, description 등은 추후 Gemini 같은 LLM API를 호출하여
    # metadata['CONTENTS'] 또는 ITEM03 필드의 내용을 바탕으로 자동 생성하면 더 좋습니다.
    final_json = {
        "title": metadata.get("TBL_NM", ""),
        "description": metadata.get("CONTENTS", metadata.get("ITEM03", "")),
        "date_range": f"{metadata.get('STRT_PRD_DE')} ~ {metadata.get('END_PRD_DE')}",
        "item_list": item_list,
        "item_desc": "데이터의 분류 및 항목입니다. (예: 지역 - 성별 - 연령대 - 항목명)",
        "value_desc": f"측정된 수치값입니다. (수록주기: {selected_period_name})",
        "value_title": "값",  # API 응답에는 명시적인 값의 타이틀이 없으므로 일반적인 이름 사용
        "data": processed_data,
    }

    # 파일로 저장
    output_filename = f"{tbl_id}_processed.json"
    output_path = OUTPUT_DIR / output_filename

    try:
        output_path.parent.mkdir(exist_ok=True, parents=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_json, f, ensure_ascii=False, indent=4)
        print(f"  ✔ 최종 결과가 '{output_path}'에 저장되었습니다.\n")
    except Exception as e:
        print(f"  [오류] 최종 JSON 파일 저장 실패: {e}")


def main():
    """
    메인 실행 함수
    """
    if API_KEY == "<여기에 API 키를 입력하세요>" or not API_KEY:
        print("❌ 오류: 스크립트 상단의 API_KEY를 설정해주세요.")
        return

    if not INPUT_METADATA_FILE.exists():
        print(
            f"❌ 오류: 메타데이터 파일({INPUT_METADATA_FILE})이 없습니다. 이전 스크립트를 먼저 실행해주세요."
        )
        return

    with open(INPUT_METADATA_FILE, "r", encoding="utf-8") as f:
        all_metadata = json.load(f)

    print(f"총 {len(all_metadata)}개의 통계표에 대한 데이터 처리를 시작합니다.")

    for i, metadata in enumerate(all_metadata):
        print(f"[{i + 1}/{len(all_metadata)}]")
        process_single_table(metadata)


if __name__ == "__main__":
    main()
