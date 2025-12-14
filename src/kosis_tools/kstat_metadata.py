"""
k-stat.go.kr 메타데이터 모듈.

이 모듈은 KOSIS의 statHtmlContent.do에서 k-stat.go.kr URL을 추출하고,
k-stat.go.kr에서 상세 통계 메타데이터를 수집합니다.

주요 기능:
    - statHtmlContent.do HTML에서 k-stat URL 추출
    - k-stat.go.kr에서 통계 메타데이터 파싱
    - 통계승인번호(statsConfmNo)로 메타데이터 조회

Example:
    기본 사용:
    >>> from kosis_tools.kstat_metadata import KstatMetadata
    >>> kstat = KstatMetadata()
    >>> url = kstat.get_kstat_url("101", "DT_1IN1503")
    >>> print(url)
    https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo=101001

    메타데이터 조회:
    >>> meta = kstat.fetch_metadata("101001")
    >>> print(meta["stats_name"])
    주민등록인구현황

    통합 조회:
    >>> meta = kstat.get_metadata_by_table("101", "DT_1IN1503")
    >>> print(meta["stats_name"])

Note:
    - 모든 테이블에 k-stat URL이 있는 것은 아닙니다
    - k-stat.go.kr은 외부 사이트이므로 타임아웃이 발생할 수 있습니다
    - requests + BeautifulSoup으로 파싱 (Playwright 사용 금지)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .base import KosisBaseClient
from .config import KosisConfig

logger = logging.getLogger(__name__)


class KstatMetadata(KosisBaseClient):
    """
    k-stat.go.kr 메타데이터 클라이언트.

    KOSIS 테이블과 연결된 k-stat.go.kr의 상세 메타데이터를 조회합니다.
    k-stat.go.kr은 통계설명자료서비스로, 통계의 정의, 작성기관,
    작성주기 등 상세 메타데이터를 제공합니다.

    이 클래스는 KosisBaseClient를 상속받아 rate limiting 등의
    공통 기능을 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃 등 설정.
        kstat_base_url: k-stat.go.kr 기본 URL

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> kstat = KstatMetadata()
        >>> # URL 추출
        >>> url = kstat.get_kstat_url("101", "DT_1IN1503")
        >>> # 메타데이터 조회
        >>> meta = kstat.fetch_metadata("101001")
        >>> print(meta["stats_name"])
        주민등록인구현황

    Note:
        - 일부 테이블은 k-stat 링크가 없습니다 (정상)
        - k-stat.go.kr 접속 실패 시 None 반환
    """

    KSTAT_BASE_URL = "https://www.k-stat.go.kr"
    STAT_HTML_URL = "https://kosis.kr/statHtml/statHtmlContent.do"

    # k-stat URL 추출 패턴
    KSTAT_URL_PATTERN = re.compile(
        r'https://www\.k-stat\.go\.kr/metasvc/msba100/statsdcdta\?statsConfmNo=([^&"\'\s>]+)'
    )

    def get_kstat_url(
        self,
        org_id: str,
        tbl_id: str,
    ) -> Optional[str]:
        """
        KOSIS 테이블의 k-stat URL을 추출합니다.

        statHtmlContent.do 페이지의 HTML에서 k-stat.go.kr URL을 찾습니다.
        이 URL은 통계승인번호(statsConfmNo)를 포함하고 있습니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

            tbl_id: 통계표 ID.
                    예: "DT_1IN1503", "DT_1B040A3"

        Returns:
            k-stat URL 문자열.
            예: "https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo=101001"

            k-stat URL이 없거나 조회 실패 시 None 반환.

        Example:
            >>> kstat = KstatMetadata()
            >>> url = kstat.get_kstat_url("101", "DT_1IN1503")
            >>> if url:
            ...     print(f"k-stat URL: {url}")
            ...     confm_no = url.split("=")[-1]
            ...     print(f"승인번호: {confm_no}")
            k-stat URL: https://www.k-stat.go.kr/...?statsConfmNo=101001
            승인번호: 101001

        Note:
            - 모든 테이블에 k-stat URL이 있는 것은 아닙니다
            - requests.get으로 HTML 파싱 (Playwright 사용 금지)
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return None

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return None

        # Rate limiting 적용
        self._apply_rate_limit()

        url = f"{self.STAT_HTML_URL}?orgId={org_id.strip()}&tblId={tbl_id.strip()}"
        logger.debug(f"statHtmlContent 요청: {url}")

        try:
            response = requests.get(url, timeout=self.config.timeout)
            response.raise_for_status()

            # k-stat URL 추출
            match = self.KSTAT_URL_PATTERN.search(response.text)
            if match:
                kstat_url = match.group(0)
                logger.info(f"k-stat URL 발견: {kstat_url}")
                return kstat_url

            logger.debug(f"k-stat URL 없음: org_id={org_id}, tbl_id={tbl_id}")
            return None

        except requests.RequestException as e:
            logger.error(f"statHtmlContent 요청 실패: {e}")
            return None

    def get_stats_confm_no(
        self,
        org_id: str,
        tbl_id: str,
    ) -> Optional[str]:
        """
        테이블의 통계승인번호를 추출합니다.

        k-stat URL에서 statsConfmNo 파라미터 값을 추출합니다.

        Args:
            org_id: 기관 ID.
            tbl_id: 통계표 ID.

        Returns:
            통계승인번호 문자열.
            예: "101001", "110026"

            추출 실패 시 None 반환.

        Example:
            >>> kstat = KstatMetadata()
            >>> confm_no = kstat.get_stats_confm_no("101", "DT_1IN1503")
            >>> if confm_no:
            ...     print(f"승인번호: {confm_no}")
            승인번호: 101001
        """
        kstat_url = self.get_kstat_url(org_id, tbl_id)
        if not kstat_url:
            return None

        # URL에서 statsConfmNo 추출
        match = re.search(r'statsConfmNo=([^&"\'\s>]+)', kstat_url)
        if match:
            return match.group(1)

        return None

    def fetch_metadata(
        self,
        stats_confm_no: str,
    ) -> Optional[Dict[str, Any]]:
        """
        k-stat.go.kr에서 통계 메타데이터를 조회합니다.

        통계승인번호로 k-stat.go.kr의 상세 메타데이터 페이지를 파싱하여
        통계명, 작성기관, 작성주기 등의 정보를 추출합니다.

        Args:
            stats_confm_no: 통계승인번호.
                            예: "101001", "110026"
                            get_stats_confm_no()로 얻거나 직접 지정.

        Returns:
            메타데이터 딕셔너리:
            {
                "stats_confm_no": "101001",     # 통계승인번호
                "stats_name": "주민등록인구현황", # 통계명
                "org_name": "행정안전부",        # 작성기관
                "period": "월",                 # 작성주기
                "purpose": "...",               # 작성목적
                "legal_basis": "...",           # 법적근거
                "survey_target": "...",         # 조사대상
                "survey_area": "...",           # 조사지역
                "survey_items": "...",          # 조사항목
                "pub_period": "...",            # 공표주기
                "pub_method": "...",            # 공표방법
                "raw_html": "..."               # 원본 HTML (디버깅용)
            }

            조회 실패 시 None 반환.

        Example:
            >>> kstat = KstatMetadata()
            >>> meta = kstat.fetch_metadata("101001")
            >>> if meta:
            ...     print(f"통계명: {meta['stats_name']}")
            ...     print(f"작성기관: {meta['org_name']}")
            ...     print(f"작성주기: {meta['period']}")
            통계명: 주민등록인구현황
            작성기관: 행정안전부
            작성주기: 월

        Note:
            - k-stat.go.kr HTML 구조에 의존하므로 사이트 변경 시 파싱 실패 가능
            - BeautifulSoup으로 파싱 (Playwright 사용 금지)
        """
        if not stats_confm_no or not stats_confm_no.strip():
            logger.warning("통계승인번호가 비어있습니다.")
            return None

        # Rate limiting 적용
        self._apply_rate_limit()

        url = f"{self.KSTAT_BASE_URL}/metasvc/msba100/statsdcdta?statsConfmNo={stats_confm_no.strip()}"
        logger.info(f"k-stat 메타데이터 조회: {url}")

        try:
            response = requests.get(url, timeout=self.config.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 메타데이터 추출
            metadata = {
                "stats_confm_no": stats_confm_no.strip(),
                "kstat_url": url,
            }

            # 테이블에서 항목 추출
            # k-stat 페이지는 <th>와 <td> 쌍으로 정보를 표시
            for row in soup.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    key = th.get_text(strip=True)
                    value = td.get_text(strip=True)

                    # 주요 필드 매핑
                    if "통계명" in key:
                        metadata["stats_name"] = value
                    elif "작성기관" in key:
                        metadata["org_name"] = value
                    elif "작성주기" in key:
                        metadata["period"] = value
                    elif "작성목적" in key:
                        metadata["purpose"] = value
                    elif "법적근거" in key:
                        metadata["legal_basis"] = value
                    elif "조사대상" in key:
                        metadata["survey_target"] = value
                    elif "조사지역" in key:
                        metadata["survey_area"] = value
                    elif "조사항목" in key:
                        metadata["survey_items"] = value
                    elif "공표주기" in key:
                        metadata["pub_period"] = value
                    elif "공표방법" in key:
                        metadata["pub_method"] = value
                    elif "승인번호" in key:
                        metadata["approval_no"] = value
                    elif "승인일자" in key:
                        metadata["approval_date"] = value

            # 최소한 통계명이라도 추출되었는지 확인
            if "stats_name" in metadata:
                logger.info(f"k-stat 메타데이터 추출 완료: {metadata.get('stats_name')}")
                return metadata

            # 페이지 구조가 다른 경우 대체 파싱 시도
            # 제목 추출 시도
            title = soup.find("h1") or soup.find("h2") or soup.find("h3")
            if title:
                metadata["stats_name"] = title.get_text(strip=True)
                logger.info(f"k-stat 제목 추출: {metadata['stats_name']}")
                return metadata

            logger.warning(f"k-stat 메타데이터 추출 실패: {stats_confm_no}")
            return None

        except requests.RequestException as e:
            logger.error(f"k-stat 요청 실패: {e}")
            return None

    def get_metadata_by_table(
        self,
        org_id: str,
        tbl_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        테이블 ID로 k-stat 메타데이터를 한 번에 조회합니다.

        get_kstat_url()과 fetch_metadata()를 순차적으로 호출하여
        테이블 ID만으로 k-stat 메타데이터를 조회합니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

            tbl_id: 통계표 ID.
                    예: "DT_1IN1503"

        Returns:
            메타데이터 딕셔너리. 구조는 fetch_metadata() 반환값과 동일.
            추가 필드:
            {
                ...
                "org_id": "101",            # 원본 기관 ID
                "tbl_id": "DT_1IN1503"      # 원본 테이블 ID
            }

            k-stat URL이 없거나 조회 실패 시 None 반환.

        Example:
            >>> kstat = KstatMetadata()
            >>> meta = kstat.get_metadata_by_table("101", "DT_1IN1503")
            >>> if meta:
            ...     print(f"통계명: {meta['stats_name']}")
            ...     print(f"승인번호: {meta['stats_confm_no']}")
            통계명: 주민등록인구현황
            승인번호: 101001

        Note:
            - 내부적으로 2개의 HTTP 요청 (statHtmlContent.do, k-stat.go.kr)
            - rate limiting 적용됨
        """
        # 승인번호 추출
        confm_no = self.get_stats_confm_no(org_id, tbl_id)
        if not confm_no:
            logger.debug(f"k-stat 링크 없음: org_id={org_id}, tbl_id={tbl_id}")
            return None

        # 메타데이터 조회
        metadata = self.fetch_metadata(confm_no)
        if metadata:
            metadata["org_id"] = org_id
            metadata["tbl_id"] = tbl_id

        return metadata

    def has_kstat_link(
        self,
        org_id: str,
        tbl_id: str,
    ) -> bool:
        """
        테이블에 k-stat 링크가 있는지 확인합니다.

        메타데이터 조회 전에 k-stat 링크 존재 여부를 빠르게 확인합니다.

        Args:
            org_id: 기관 ID.
            tbl_id: 통계표 ID.

        Returns:
            True: k-stat 링크가 있음
            False: k-stat 링크가 없거나 확인 실패

        Example:
            >>> kstat = KstatMetadata()
            >>> if kstat.has_kstat_link("101", "DT_1IN1503"):
            ...     meta = kstat.get_metadata_by_table("101", "DT_1IN1503")
            ...     print(meta["stats_name"])
            ... else:
            ...     print("k-stat 링크 없음")
        """
        return self.get_kstat_url(org_id, tbl_id) is not None
