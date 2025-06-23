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
    print("터미널에서 'pip install selenium webdriver-manager beautifulsoup4' 명령어를 실행하여 설치해주세요.")
    exit()

# --- 기본 설정 ---
# JSON 파일에서 다운로드할 목록을 불러옵니다.
# 스크립트와 같은 위치에 data 폴더를 만들고 그 안에 name_address_pair.json 파일을 넣어주세요.
try:
    with open("data/name_address_pair.json", encoding="utf-8") as f:
        initial_pairs = json.load(f)
except FileNotFoundError:
    print("[오류] 'data/name_address_pair.json' 파일을 찾을 수 없습니다.")
    print("스크립트와 동일한 경로에 'data' 폴더를 생성하고, 그 안에 json 파일을 넣어주세요.")
    exit()

BASE_URL = "https://ko.wikipedia.org"
SAVE_DIRECTORY = "downloaded_logos"  # 이미지를 저장할 폴더 이름

def setup_driver():
    """Selenium WebDriver를 설정하고 반환합니다."""
    print("Selenium WebDriver 설정 중...")
    options = Options()
    options.add_argument("--headless")  # 헤드리스 모드 (UI 없이 백그라운드에서 실행)
    options.add_argument("--no-sandbox") # Docker 또는 CI/CD 환경에서 필요할 수 있음
    options.add_argument("--disable-dev-shm-usage") # 공유 메모리 문제 방지
    options.add_argument("--disable-gpu") # GPU 가속 비활성화 (헤드리스 모드에서 권장)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        # webdriver-manager를 사용하여 자동으로 드라이버 설치 및 로드
        service = ChromeService(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30) # 페이지 로드 타임아웃 30초 설정
        print("WebDriver 설정 완료.")
        return driver
    except WebDriverException as e:
        print(f"[오류] WebDriver 설정에 실패했습니다: {e}")
        print("Chrome 브라우저가 설치되어 있는지 확인해주세요.")
        print("리눅스 환경이라면 'sudo apt-get install -y google-chrome-stable' 등으로 설치할 수 있습니다.")
        return None


def get_downloaded_files(directory):
    """지정된 디렉토리에서 확장자를 제외한 파일 이름 목록을 set 형태로 반환합니다."""
    if not os.path.exists(directory):
        return set()
    return {os.path.splitext(f)[0] for f in os.listdir(directory)}


def download_image_with_js(driver, image_url):
    """
    JavaScript를 사용하여 이미지를 Base64로 인코딩하여 가져옵니다.
    별도의 HTTP 요청을 보내지 않아 429 오류를 피하는 데 도움이 됩니다.
    """
    # 비동기 JavaScript 실행을 위한 스크립트
    # fetch API로 이미지를 가져와 blob으로 변환하고, FileReader로 Base64 데이터 URL을 생성합니다.
    js_script = """
    const url = arguments[0];
    const callback = arguments[1];
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
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
        # 비동기 스크립트를 실행하고 결과가 올 때까지 기다립니다.
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
            item for item in initial_pairs
            if item.get("name") and item["name"].replace("/", "_").replace("\\", "_") not in downloaded_names
        ]

        if not to_download_list:
            print("\n✨ 모든 파일을 성공적으로 다운로드했습니다! 프로그램을 종료합니다.")
            break

        print(f"\n--- 남은 파일: {len(to_download_list)}개. 다운로드 사이클을 시작합니다. ---")

        for item in to_download_list:
            name = item.get("name")
            page_path = item.get("address")

            if not name or not page_path:
                continue

            page_url = f"{BASE_URL}{page_path}"
            wait_for_next_request = 1  # 기본 대기 시간 1초

            try:
                print(f"-> 작업 대상: '{name}' ({page_url})")

                # 페이지 접속 (Selenium 사용)
                driver.get(page_url)

                # HTML 파싱 및 이미지 태그 검색
                soup = BeautifulSoup(driver.page_source, "html.parser")
                image_tag = None

                # 우선순위 1: 지정된 CSS 선택자
                user_selector = "#mw-content-text > div.mw-content-ltr.mw-parser-output > table.infobox > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(1) > td > span > a > img"
                image_tag = soup.select_one(user_selector)
                
                # 우선순위 2: '휘장' 또는 '상징' 텍스트 기반 검색
                if not image_tag:
                    symbol_th = soup.find("th", string=re.compile(r"휘장|상징"))
                    if symbol_th and symbol_th.find_next_sibling("td"):
                        image_tag = symbol_th.find_next_sibling("td").select_one("a.image img")

                if not image_tag:
                    print(f"    [경고] '{name}' 페이지에서 이미지 태그를 찾을 수 없습니다. 이번 사이클에서는 건너뜁니다.")
                    time.sleep(wait_for_next_request)
                    continue

                # 이미지 URL 추출
                image_url = image_tag.get("src")
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                elif image_url.startswith("/"):
                    image_url = BASE_URL + image_url
                
                print(f"    이미지 URL 발견: {image_url}")

                # JavaScript를 이용해 이미지 데이터 다운로드
                base64_data_url = download_image_with_js(driver, image_url)
                if not base64_data_url or isinstance(base64_data_url, dict):
                    print(f"    [실패] '{name}'의 이미지 데이터를 가져오지 못했습니다. 다음 사이클에서 재시도합니다.")
                    continue

                # 파일명 및 저장 경로 설정
                # data:image/png;base64,..... 형태에서 확장자 추출
                try:
                    header, encoded = base64_data_url.split(",", 1)
                    file_extension = "." + header.split("/")[1].split(";")[0]
                    image_data = base64.b64decode(encoded)
                except (ValueError, IndexError):
                     print(f"    [오류] Base64 데이터 형식이 올바르지 않습니다. 건너뜁니다.")
                     continue

                safe_filename = name.replace("/", "_").replace("\\", "_")
                save_filename = f"{safe_filename}{file_extension}"
                file_path = os.path.join(SAVE_DIRECTORY, save_filename)

                # 파일로 저장
                with open(file_path, "wb") as f:
                    f.write(image_data)

                print(f"    [성공] '{save_filename}' 저장 완료!")

            except TimeoutException:
                print(f"    [실패] '{name}' 페이지 로드 시간 초과. 다음 사이클에서 재시도합니다.")
            except WebDriverException as e:
                print(f"    [실패] '{name}' 처리 중 WebDriver 오류 발생: {e}. 다음 사이클에서 재시도합니다.")
            except Exception as e:
                print(f"    [실패] '{name}' 처리 중 알 수 없는 오류 발생: {e}. 다음 사이클에서 재시도합니다.")

            # 각 요청마다 대기
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
