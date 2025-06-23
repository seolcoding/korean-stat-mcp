import os
import requests
from bs4 import BeautifulSoup
import time
import json
import re

# JSON 파일에서 다운로드할 목록을 불러옵니다.
# 스크립트와 같은 위치에 data 폴더를 만들고 그 안에 name_address_pair.json 파일을 넣어주세요.
try:
    with open("data/name_address_pair.json", encoding="utf-8") as f:
        initial_pairs = json.load(f)
except FileNotFoundError:
    print("[오류] 'data/name_address_pair.json' 파일을 찾을 수 없습니다.")
    print(
        "스크립트와 동일한 경로에 'data' 폴더를 생성하고, 그 안에 json 파일을 넣어주세요."
    )
    exit()

# 기본 설정
BASE_URL = "https://ko.wikipedia.org"
SAVE_DIRECTORY = "downloaded_logos"  # 이미지를 저장할 폴더 이름

# 403 접근 거부 오류를 피하기 위한 브라우저 헤더 정보
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def get_downloaded_files(directory):
    """지정된 디렉토리에서 확장자를 제외한 파일 이름 목록을 set 형태로 반환합니다."""
    if not os.path.exists(directory):
        return set()
    # os.path.splitext()는 ('파일명', '.확장자') 튜플을 반환하므로, 첫 번째 요소[0]를 사용합니다.
    return {os.path.splitext(f)[0] for f in os.listdir(directory)}


def download_logos_from_wiki():
    """
    모든 로고가 다운로드될 때까지 위키피디아 페이지를 순회하며 다운로드합니다.
    """
    # 저장 폴더가 없으면 생성
    if not os.path.exists(SAVE_DIRECTORY):
        os.makedirs(SAVE_DIRECTORY)
        print(f"'{SAVE_DIRECTORY}' 폴더를 생성했습니다.")

    # =================================================================
    # === 모든 파일을 받을 때까지 무한 반복하는 로직 ===
    # =================================================================
    while True:
        # 1. 이미 다운로드된 파일 목록을 확인 (확장자 제외)
        downloaded_names = get_downloaded_files(SAVE_DIRECTORY)

        # 2. 이번 주기에 다운로드해야 할 작업 목록 생성
        to_download_list = [
            item
            for item in initial_pairs
            if item.get("name")
            and item["name"].replace("/", "_").replace("\\", "_")
            not in downloaded_names
        ]

        # 3. 다운로드할 파일이 없으면 성공 메시지를 출력하고 루프 종료
        if not to_download_list:
            print(
                "\n✨ 모든 파일을 성공적으로 다운로드했습니다! 프로그램을 종료합니다."
            )
            break

        print(
            f"\n--- 남은 파일: {len(to_download_list)}개. 다운로드 사이클을 시작합니다. ---"
        )

        # 4. 다운로드해야 할 목록을 순회하며 작업 수행
        for item in to_download_list:
            name = item.get("name")
            page_path = item.get("address")

            # 유효하지 않은 항목은 건너뛰기
            if not name or not page_path:
                continue

            page_url = f"{BASE_URL}{page_path}"
            wait_for_next_request = 1  # 기본 대기 시간 1초

            try:
                print(f"-> 작업 대상: '{name}'")

                # 페이지 접속
                response = requests.get(page_url, headers=HEADERS, timeout=15)
                response.raise_for_status()

                # HTML 파싱 및 이미지 태그 검색
                soup = BeautifulSoup(response.text, "html.parser")
                image_tag = None
                user_selector = "#mw-content-text > div.mw-content-ltr.mw-parser-output > table.infobox > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(1) > td > span > a > img"
                image_tag = soup.select_one(user_selector)
                if not image_tag:
                    symbol_th = soup.find("th", string=re.compile(r"휘장|상징"))
                    if symbol_th and symbol_th.find_next_sibling("td"):
                        image_tag = symbol_th.find_next_sibling("td").select_one(
                            "a.image img"
                        )

                if not image_tag:
                    print(
                        f"   [경고] '{name}' 페이지에서 이미지 태그를 찾을 수 없습니다. 이번 사이클에서는 건너뜁니다."
                    )
                    time.sleep(wait_for_next_request)
                    continue

                # 이미지 URL 추출 및 다운로드
                image_url = image_tag.get("src")
                if image_url.startswith("//"):
                    image_url = "https:" + image_url

                image_response = requests.get(
                    image_url, headers=HEADERS, stream=True, timeout=15
                )
                image_response.raise_for_status()

                # 파일명 및 저장
                file_extension = (
                    os.path.splitext(image_url.split("/")[-1])[1].split("?")[0]
                    or ".png"
                )
                safe_filename = name.replace("/", "_").replace("\\", "_")
                save_filename = f"{safe_filename}{file_extension}"
                file_path = os.path.join(SAVE_DIRECTORY, save_filename)

                with open(file_path, "wb") as f:
                    for chunk in image_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"   [성공] '{save_filename}' 저장 완료!")

            except requests.exceptions.HTTPError as e:
                # 429 오류를 명시적으로 확인하고 처리
                if e.response.status_code == 429:
                    print(
                        "   [경고] 429 오류 (요청 과다). 다음 요청까지 대기 시간을 늘립니다."
                    )
                    wait_for_next_request = (
                        30  # 429 오류 발생 시 다음 요청까지 30초 대기
                    )
                else:
                    print(
                        f"   [실패] '{name}' 처리 중 HTTP 오류 발생: {e}. 다음 사이클에서 재시도합니다."
                    )
            except requests.exceptions.RequestException as e:
                # 네트워크 관련 오류 발생 시 실패 메시지만 출력하고 넘어감
                print(
                    f"   [실패] '{name}' 처리 중 네트워크 오류 발생: {e}. 다음 사이클에서 재시도합니다."
                )
            except Exception as e:
                # 기타 모든 오류 발생 시
                print(
                    f"   [실패] '{name}' 처리 중 알 수 없는 오류 발생: {e}. 다음 사이클에서 재시도합니다."
                )

            # 각 요청마다 대기 (기본 1초, 429 발생 시 30초)
            print(f"   ({wait_for_next_request}초 대기...)")
            time.sleep(wait_for_next_request)


if __name__ == "__main__":
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print(
            "스크립트를 실행하려면 'requests'와 'beautifulsoup4' 라이브러리가 필요합니다."
        )
        print(
            "터미널에서 'pip install requests beautifulsoup4' 명령어를 실행하여 설치해주세요."
        )
        exit()

    download_logos_from_wiki()
