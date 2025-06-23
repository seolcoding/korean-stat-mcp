import os
import time
import json
import re
import base64
from urllib.parse import urlparse

# Selenium 및 관련 라이브러리 임포트
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
except ImportError:
    print("[오류] 필수 라이브러리가 설치되지 않았습니다.")
    print(
        "터미널에서 'pip install selenium webdriver-manager beautifulsoup4' 명령어를 실행하여 설치해주세요."
    )
    exit()

# --- 기본 설정 ---
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

BASE_URL = "https://ko.wikipedia.org"
SAVE_DIRECTORY = "downloaded_logos"  # 이미지를 저장할 폴더 이름


def setup_driver():
    """Selenium WebDriver를 설정하고 반환합니다."""
    print("Selenium WebDriver 설정 중...")
    options = Options()
    options.add_argument("--headless")  # 헤드리스 모드 (UI 없이 백그라운드에서 실행)
    options.add_argument("--no-sandbox")  # Docker 또는 CI/CD 환경에서 필요할 수 있음
    options.add_argument("--disable-dev-shm-usage")  # 공유 메모리 문제 방지
    options.add_argument("--disable-gpu")  # GPU 가속 비활성화 (헤드리스 모드에서 권장)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    try:
        # webdriver-manager를 사용하여 자동으로 드라이버 설치 및 로드
        service = ChromeService(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)  # 페이지 로드 타임아웃 30초 설정
        print("WebDriver 설정 완료.")
        return driver
    except WebDriverException as e:
        print(f"[오류] WebDriver 설정에 실패했습니다: {e}")
        print("Chrome 브라우저가 설치되어 있는지 확인해주세요.")
        print(
            "리눅스 환경이라면 'sudo apt-get install -y google-chrome-stable' 등으로 설치할 수 있습니다."
        )
        return None


def get_downloaded_files(directory):
    """지정된 디렉토리에서 확장자를 제외한 파일 이름 목록을 set 형태로 반환합니다."""
    if not os.path.exists(directory):
        return set()
    # file_1, file_2 같은 경우를 위해 _숫자를 제거하고 비교
    return {re.sub(r"_\d+$", "", os.path.splitext(f)[0]) for f in os.listdir(directory)}


def download_image_with_js(driver, image_url):
    """
    JavaScript를 사용하여 이미지를 Base64로 인코딩하여 가져옵니다.
    별도의 HTTP 요청을 보내지 않아 429 오류를 피하는 데 도움이 됩니다.
    """
    js_script = """
    const url = arguments[0];
    const callback = arguments[1];
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.blob();
        })
        .then(blob => {
            const reader = new FileReader();
            reader.onloadend = () => {
                callback(reader.result);
            };
            reader.onerror = () => {
                callback({error: 'File could not be read'});
            };
            reader.readAsDataURL(blob);
        })
        .catch(error => {
            callback({error: error.message});
        });
    """
    try:
        return driver.execute_async_script(js_script, image_url)
    except Exception as e:
        print(f"    [오류] JavaScript 실행 중 오류 발생: {e}")
        return None


def download_logos_from_wiki(driver):
    """
    모든 로고가 다운로드될 때까지 위키피디아 페이지를 순회하며 다운로드합니다.
    """
    if not os.path.exists(SAVE_DIRECTORY):
        os.makedirs(SAVE_DIRECTORY)
        print(f"'{SAVE_DIRECTORY}' 폴더를 생성했습니다.")

    while True:
        downloaded_names = get_downloaded_files(SAVE_DIRECTORY)
        to_download_list = [
            item
            for item in initial_pairs
            if item.get("name")
            and item["name"].replace("/", "_").replace("\\", "_")
            not in downloaded_names
        ]

        if not to_download_list:
            print(
                "\n✨ 모든 파일을 성공적으로 다운로드했습니다! 프로그램을 종료합니다."
            )
            break

        print(
            f"\n--- 남은 파일: {len(to_download_list)}개. 다운로드 사이클을 시작합니다. ---"
        )

        for item in to_download_list:
            name = item.get("name")
            page_path = item.get("address")

            if not name or not page_path:
                continue

            page_url = f"{BASE_URL}{page_path}"
            wait_for_next_request = 1

            try:
                print(f"-> 작업 대상: '{name}' ({page_url})")
                driver.get(page_url)
                soup = BeautifulSoup(driver.page_source, "html.parser")

                tags_to_process = []

                # 우선순위 1: 지정된 CSS 선택자
                image_tag = soup.select_one(
                    "#mw-content-text > div.mw-content-ltr.mw-parser-output > table.infobox > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(1) > td > span > a > img"
                )
                if image_tag:
                    tags_to_process.append(image_tag)
                    print("    [정보] 1순위 CSS 선택자로 이미지 발견.")
                else:
                    # 우선순위 2: src에 'Flag'와 '.svg'가 모두 포함된 모든 이미지 검색
                    flag_svg_images = [img for img in soup.find_all("img")]
                    if flag_svg_images:
                        tags_to_process.extend(flag_svg_images)
                        print(
                            f"    [정보] 2순위 'Flag'와 '.svg' 포함 이미지 {len(flag_svg_images)}개 발견."
                        )
                    else:
                        # 우선순위 3: '휘장' 또는 '상징' 텍스트 기반 검색
                        symbol_th = soup.find("th", string=re.compile(r"휘장|상징"))
                        if symbol_th and symbol_th.find_next_sibling("td"):
                            symbol_image_tag = symbol_th.find_next_sibling(
                                "td"
                            ).select_one("a.image img")
                            if symbol_image_tag:
                                tags_to_process.append(symbol_image_tag)
                                print("    [정보] 3순위 '휘장/상징'으로 이미지 발견.")

                if not tags_to_process:
                    print(
                        f"    [경고] '{name}' 페이지에서 다운로드할 이미지를 찾지 못했습니다. 건너뜁니다."
                    )
                    time.sleep(wait_for_next_request)
                    continue

                # 찾은 모든 이미지 태그에 대해 다운로드 수행
                for idx, image_tag in enumerate(tags_to_process):
                    image_url = image_tag.get("src")
                    if not image_url:
                        continue

                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
                    elif image_url.startswith("/"):
                        image_url = BASE_URL + image_url

                    print(
                        f"    다운로드 시도 ({idx + 1}/{len(tags_to_process)}): {image_url}"
                    )

                    base64_data_url = download_image_with_js(driver, image_url)
                    if not base64_data_url or isinstance(base64_data_url, dict):
                        print(
                            f"      [실패] 이미지 데이터를 가져오지 못했습니다. ({base64_data_url.get('error', '') if isinstance(base64_data_url, dict) else ''})"
                        )
                        continue

                    try:
                        header, encoded = base64_data_url.split(",", 1)
                        file_extension = "." + header.split("/")[1].split(";")[
                            0
                        ].replace("+", "_")
                        image_data = base64.b64decode(encoded)
                    except (ValueError, IndexError):
                        print("      [오류] Base64 데이터 형식이 올바르지 않습니다.")
                        continue

                    safe_filename = name.replace("/", "_").replace("\\", "_")
                    # 이미지가 여러 개일 경우에만 파일명에 숫자 추가
                    filename_suffix = f"_{idx + 1}" if len(tags_to_process) > 1 else ""
                    save_filename = f"{safe_filename}{filename_suffix}{file_extension}"
                    file_path = os.path.join(SAVE_DIRECTORY, save_filename)

                    with open(file_path, "wb") as f:
                        f.write(image_data)
                    print(f"      [성공] '{save_filename}' 저장 완료!")

            except TimeoutException:
                print(
                    f"    [실패] '{name}' 페이지 로드 시간 초과. 다음 사이클에서 재시도합니다."
                )
            except WebDriverException as e:
                print(
                    f"    [실패] '{name}' 처리 중 WebDriver 오류 발생: {e}. 다음 사이클에서 재시도합니다."
                )
            except Exception as e:
                print(
                    f"    [실패] '{name}' 처리 중 알 수 없는 오류 발생: {e}. 다음 사이클에서 재시도합니다."
                )

            print(f"    ({wait_for_next_request}초 대기...)")
            time.sleep(wait_for_next_request)


if __name__ == "__main__":
    driver = setup_driver()
    if driver:
        try:
            download_logos_from_wiki(driver)
        finally:
            print("WebDriver를 종료합니다.")
            driver.quit()
