import re
import requests
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

_ = load_dotenv()  # .env 파일에서 환경 변수 로드

# --- 설정 ---
API_KEY = os.getenv("KOSIS_API_KEY")
SEARCH_KEYWORDS = [
    " ",
    "통계",
    "지방",
    "지표",
    "데이터",
    "자료",
    "인구",
    "건강",
    "노령",
    "평균",
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
]
BASE_URL = "https://kosis.kr/openapi/statisticsSearch.do"
RESULTS_PER_PAGE = 5000  # API가 지원하는 최대치 또는 적절한 값으로 설정

# --- 출력 파일 설정 ---
OUTPUT_DIR = Path("./kosis_data")
INTERMEDIATE_FILE = OUTPUT_DIR / "kosis_metadata_intermediate.json"
FINAL_FILE = OUTPUT_DIR / "kosis_metadata_final.json"


def extract_search_keywords():
    df = pd.read_csv("./data/regional_index_data_list.csv")
    names = df["통계명"].unique()
    print(names)
    result = set()
    for name in names:
        name = name.strip()
        name = name.split("(")[0]
        result.update(name.split(" "))
    return result


SEARCH_KEYWORDS = extract_search_keywords().union(set(SEARCH_KEYWORDS))
SEARCH_KEYWORDS = sorted(list(SEARCH_KEYWORDS))
print(f"검색어 목록: {SEARCH_KEYWORDS}")


def save_to_json(data, file_path):
    """
    데이터를 JSON 파일로 저장하는 헬퍼 함수.
    ensure_ascii=False로 한글 깨짐을 방지합니다.
    """
    try:
        file_path.parent.mkdir(exist_ok=True, parents=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"  [오류] 파일 저장 중 문제 발생: {file_path}, {e}")


def collect_kosis_metadata():
    """
    KOSIS API를 호출하여 통계 메타데이터를 수집하는 메인 함수.
    """
    if API_KEY == "<여기에 API 키를 입력하세요>" or not API_KEY:
        print("❌ 오류: API_KEY를 설정해주세요.")
        return

    final_results = []
    seen_tbl_nm = set()  # TBL_NM을 기준으로 중복을 체크하기 위한 set

    print("KOSIS 통계 메타데이터 수집을 시작합니다.")

    # 기존 중간 저장 파일이 있다면 불러오기
    if INTERMEDIATE_FILE.exists():
        print(f"'{INTERMEDIATE_FILE}' 파일에서 기존 데이터를 불러옵니다.")
        with open(INTERMEDIATE_FILE, "r", encoding="utf-8") as f:
            final_results = json.load(f)
            for item in final_results:
                seen_tbl_nm.add(item.get("TBL_NM"))
        print(f"  -> 총 {len(final_results)}개의 데이터를 불러왔습니다.")

    # 각 검색어에 대해 API 호출 시작
    for keyword in SEARCH_KEYWORDS:
        page_num = 1
        print(f"\n--- 검색어 '{keyword}' 처리 시작 ---")

        while True:
            params = {
                "method": "getList",
                "apiKey": API_KEY,
                "format": "json",
                "searchNm": keyword,
                "resultCount": RESULTS_PER_PAGE,
                "startCount": page_num,
                "content": "json",
            }

            try:
                print(
                    f"  - 페이지 {page_num} 요청 중... (현재까지 수집된 고유 통계: {len(final_results)}개)"
                )

                response = requests.get(BASE_URL, params=params, timeout=30)
                corrected_text = re.sub(
                    r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', response.text
                )
                response.raise_for_status()  # 200 OKㅏ 아니면 오류 발생

                data = json.loads(corrected_text)

                # API 응답에 오류 메시지가 포함된 경우
                if "errMsg" in data:
                    print(f"  [API 오류] {data['errMsg']}. 다음 검색어로 넘어갑니다.")
                    break

                # 결과가 비어있으면 해당 검색어에 대한 수집 종료
                if not data:
                    print("  - 더 이상 결과가 없어 다음 검색어로 넘어갑니다.")
                    break

                new_items_count = 0
                for item in data:
                    tbl_nm = item.get("TBL_NM")
                    if tbl_nm and tbl_nm not in seen_tbl_nm:
                        seen_tbl_nm.add(tbl_nm)
                        final_results.append(item)
                        new_items_count += 1

                print(
                    f"  - 페이지 {page_num} 처리 완료. {new_items_count}개의 새로운 통계를 추가했습니다."
                )

                # 중간 저장
                save_to_json(final_results, INTERMEDIATE_FILE)

                page_num += 1
                time.sleep(1)  # API 서버 부하를 줄이기 위한 약간의 딜레이

            except requests.exceptions.RequestException as e:
                print(f"  [네트워크 오류] {e}. 다음 검색어로 넘어갑니다.")
                time.sleep(10)
                continue
            except json.JSONDecodeError:
                print(
                    "  [오류] JSON 파싱 실패. 응답이 올바른 JSON 형식이 아닙니다. 다음 검색어로 넘어갑니다."
                )
                break
            except Exception as e:
                print(f"  [알 수 없는 오류] {e}. 다음 검색어로 넘어갑니다.")
                break

    # 최종 결과 저장
    print("\n--- 모든 검색어 처리 완료 ---")
    print(f"총 {len(final_results)}개의 고유한 통계 메타데이터를 수집했습니다.")
    save_to_json(final_results, FINAL_FILE)
    print(f"최종 결과가 '{FINAL_FILE}' 파일에 저장되었습니다.")


if __name__ == "__main__":
    collect_kosis_metadata()
