"""
KOSIS에서 k-stat.go.kr 메타데이터 URL 추출 (requests only - NO Playwright)

Flow:
1. KOSIS statHtmlContent.do 직접 요청
2. HTML에서 k-stat.go.kr URL 추출
3. k-stat.go.kr 메타데이터 페이지 요청
"""

import re
import json
import time
import requests
from typing import Dict, Optional, List
from pathlib import Path


class KstatMetadataScraper:
    """k-stat.go.kr 메타데이터 스크래핑 (requests only)"""

    KSTAT_BASE_URL = "https://www.k-stat.go.kr/metasvc/msba100/statsdcdta"
    KOSIS_CONTENT_URL = "https://kosis.kr/statHtml/statHtmlContent.do"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

    def extract_kstat_url(self, org_id: str, tbl_id: str) -> Optional[str]:
        """
        KOSIS statHtmlContent.do에서 k-stat.go.kr URL 추출

        Returns:
            k-stat.go.kr URL 또는 None
        """
        url = f"{self.KOSIS_CONTENT_URL}?orgId={org_id}&tblId={tbl_id}"

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            # k-stat URL 패턴 검색 (statsConfmNo 포함된 것만)
            pattern = r'https://www\.k-stat\.go\.kr/metasvc/msba100/statsdcdta\?statsConfmNo=[^&"\'>\s]+'
            matches = re.findall(pattern, resp.text)

            if matches:
                # HTML entity decode (&amp; -> &)
                kstat_url = matches[0].replace("&amp;", "&")
                return kstat_url

            return None
        except Exception as e:
            print(f"  요청 오류: {e}")
            return None

    def extract_stats_confm_no(self, kstat_url: str) -> Optional[str]:
        """URL에서 statsConfmNo 추출"""
        match = re.search(r"statsConfmNo=([^&]+)", kstat_url)
        return match.group(1) if match else None

    def get_metadata_for_table(self, org_id: str, tbl_id: str) -> Dict:
        """
        테이블에 대한 k-stat.go.kr 메타데이터 URL 반환

        Returns:
            {"org_id", "tbl_id", "stats_confm_no", "kstat_url"} 또는 빈 dict
        """
        kstat_url = self.extract_kstat_url(org_id, tbl_id)

        if not kstat_url:
            return {}

        stats_confm_no = self.extract_stats_confm_no(kstat_url)

        return {
            "org_id": org_id,
            "tbl_id": tbl_id,
            "stats_confm_no": stats_confm_no,
            "kstat_url": kstat_url,
        }

    def get_metadata_for_tables(self, tables: List[Dict], delay: float = 0.3) -> List[Dict]:
        """
        여러 테이블에 대한 k-stat.go.kr 메타데이터 URL 일괄 조회

        Args:
            tables: [{"org_id": "...", "tbl_id": "...", "name": "..."}, ...]
            delay: 요청 간 대기 시간 (초)

        Returns:
            성공한 테이블 정보 리스트
        """
        results = []

        for table in tables:
            org_id = table.get("org_id")
            tbl_id = table.get("tbl_id")
            name = table.get("name", "")

            print(f"\n[{name}] {org_id}/{tbl_id}")

            result = self.get_metadata_for_table(org_id, tbl_id)

            if result:
                result["name"] = name
                print(f"  statsConfmNo: {result['stats_confm_no']}")
                print(f"  k-stat URL: {result['kstat_url']}")
                results.append(result)
            else:
                print("  k-stat URL 없음")

            time.sleep(delay)

        return results


def main():
    """테스트 실행"""
    scraper = KstatMetadataScraper()

    # 테스트 테이블 목록
    test_tables = [
        {"org_id": "101", "tbl_id": "DT_1YL20631", "name": "고령인구비율"},
        {"org_id": "101", "tbl_id": "DT_1IN1503", "name": "주민등록인구"},
        {"org_id": "101", "tbl_id": "DT_1B040A3", "name": "총인구(인구총조사)"},
        {"org_id": "101", "tbl_id": "DT_1DA7002S", "name": "성별 인구수"},
    ]

    print("=" * 70)
    print("k-stat.go.kr 메타데이터 URL 추출 (requests only)")
    print("=" * 70)

    results = scraper.get_metadata_for_tables(test_tables)

    # 결과 저장
    output_path = Path(__file__).parent.parent.parent / "kosis_data" / "kstat_urls.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_path}")
    print(f"총 {len(results)}/{len(test_tables)} 테이블 처리 완료")


if __name__ == "__main__":
    main()
