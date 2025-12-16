"""
아티팩트 호스팅 모듈.

서버에서 생성된 아티팩트(차트, 리포트 등)를 호스팅하고 URL을 제공합니다.
클라이언트는 이 URL을 참조하여 리포트를 조합합니다.

Directory Structure:
    /tmp/kosis_artifacts/
        charts/      - 차트 (HTML, PNG, SVG)
        reports/     - 클라이언트가 퍼블리시한 리포트
        data/        - 원본 데이터 (CSV, JSON)

Example:
    >>> from kosis_tools.artifact_host import ArtifactHost
    >>> host = ArtifactHost(base_url="http://localhost:8000")
    >>> url = host.save_chart(chart_html, "population_trend")
    >>> print(url)
    "http://localhost:8000/artifacts/charts/abc123.html"
"""

from __future__ import annotations

import json
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class ArtifactHost:
    """
    아티팩트 호스팅 관리자.

    Attributes:
        base_url: 외부 접근 URL (예: http://localhost:8000)
        artifacts_dir: 아티팩트 저장 디렉토리
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        artifacts_dir: str = "/tmp/kosis_artifacts",
    ):
        self.base_url = base_url.rstrip("/")
        self.artifacts_dir = Path(artifacts_dir)

        # 디렉토리 생성
        (self.artifacts_dir / "charts").mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "data").mkdir(parents=True, exist_ok=True)

    def _generate_id(self, prefix: str = "") -> str:
        """고유 ID 생성."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"{prefix}{timestamp}_{short_uuid}" if prefix else f"{timestamp}_{short_uuid}"

    def save_chart(
        self,
        content: str,
        name: Optional[str] = None,
        format: str = "html",
    ) -> Dict[str, str]:
        """
        차트를 저장하고 URL을 반환합니다.

        Args:
            content: 차트 내용 (HTML, SVG 등)
            name: 파일명 (없으면 자동 생성)
            format: 파일 형식 (html, svg, png)

        Returns:
            {"artifact_id": "...", "url": "...", "path": "..."}
        """
        artifact_id = self._generate_id("chart_")
        filename = f"{name or artifact_id}.{format}"
        filepath = self.artifacts_dir / "charts" / filename

        # 바이너리 vs 텍스트
        if format == "png":
            filepath.write_bytes(content if isinstance(content, bytes) else content.encode())
        else:
            filepath.write_text(content, encoding="utf-8")

        url = f"{self.base_url}/artifacts/charts/{filename}"

        logger.info(f"Chart saved: {filepath} -> {url}")

        return {
            "artifact_id": artifact_id,
            "url": url,
            "local_path": str(filepath),
            "type": "chart",
            "format": format,
        }

    def save_data(
        self,
        data: Union[list, dict],
        name: Optional[str] = None,
        format: str = "json",
    ) -> Dict[str, str]:
        """
        데이터를 저장하고 URL을 반환합니다.

        Args:
            data: 저장할 데이터
            name: 파일명 (없으면 자동 생성)
            format: 파일 형식 (json, csv)

        Returns:
            {"artifact_id": "...", "url": "...", "path": "...", "record_count": ...}
        """
        artifact_id = self._generate_id("data_")
        filename = f"{name or artifact_id}.{format}"
        filepath = self.artifacts_dir / "data" / filename

        if format == "csv":
            import pandas as pd
            df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
            df.to_csv(filepath, index=False, encoding="utf-8-sig")
            record_count = len(df)
        else:
            filepath.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            record_count = len(data) if isinstance(data, list) else 1

        url = f"{self.base_url}/artifacts/data/{filename}"

        logger.info(f"Data saved: {filepath} -> {url}")

        return {
            "artifact_id": artifact_id,
            "url": url,
            "local_path": str(filepath),
            "type": "data",
            "format": format,
            "record_count": record_count,
        }

    def publish_report(
        self,
        html_content: str,
        title: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        클라이언트가 만든 리포트를 퍼블리시합니다.

        Args:
            html_content: HTML 리포트 내용
            title: 리포트 제목 (파일명에 사용)

        Returns:
            {"report_id": "...", "url": "...", "path": "..."}
        """
        report_id = self._generate_id("report_")

        # 파일명에서 특수문자 제거
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in (title or ""))
        filename = f"{safe_title}_{report_id}.html" if safe_title else f"{report_id}.html"
        filepath = self.artifacts_dir / "reports" / filename

        filepath.write_text(html_content, encoding="utf-8")

        url = f"{self.base_url}/artifacts/reports/{filename}"

        logger.info(f"Report published: {filepath} -> {url}")

        return {
            "report_id": report_id,
            "url": url,
            "local_path": str(filepath),
            "type": "report",
            "title": title,
        }

    def list_artifacts(
        self,
        artifact_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        저장된 아티팩트 목록을 반환합니다.

        Args:
            artifact_type: 타입 필터 (charts, reports, data)
            limit: 최대 개수

        Returns:
            {"charts": [...], "reports": [...], "data": [...]}
        """
        result = {}

        types_to_list = [artifact_type] if artifact_type else ["charts", "reports", "data"]

        for atype in types_to_list:
            type_dir = self.artifacts_dir / atype
            if type_dir.exists():
                files = sorted(type_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
                result[atype] = [
                    {
                        "filename": f.name,
                        "url": f"{self.base_url}/artifacts/{atype}/{f.name}",
                        "size_kb": f.stat().st_size / 1024,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    }
                    for f in files[:limit]
                ]

        return result

    def get_artifact_path(self, artifact_type: str, filename: str) -> Optional[Path]:
        """아티팩트 파일 경로 반환 (static serving용)."""
        filepath = self.artifacts_dir / artifact_type / filename
        return filepath if filepath.exists() else None


# 싱글톤 인스턴스
_host: Optional[ArtifactHost] = None


def get_artifact_host() -> ArtifactHost:
    """ArtifactHost 싱글톤 인스턴스 반환 (환경변수 사용)."""
    import os
    global _host
    if _host is None:
        base_url = os.environ.get("KOSIS_BASE_URL", "http://localhost:8000")
        artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
        _host = ArtifactHost(base_url=base_url, artifacts_dir=artifacts_dir)
    return _host


def save_chart(content: str, name: Optional[str] = None, format: str = "html") -> Dict[str, str]:
    """차트 저장 편의 함수."""
    return get_artifact_host().save_chart(content, name, format)


def save_data(data: Union[list, dict], name: Optional[str] = None, format: str = "json") -> Dict[str, str]:
    """데이터 저장 편의 함수."""
    return get_artifact_host().save_data(data, name, format)


def publish_report(html_content: str, title: Optional[str] = None) -> Dict[str, str]:
    """리포트 퍼블리시 편의 함수."""
    return get_artifact_host().publish_report(html_content, title)


def save_report(html_content: str, name: Optional[str] = None) -> Dict[str, str]:
    """
    리포트 저장 편의 함수 (execute_code 내에서 사용).

    publish_report의 별칭으로, 코드에서 더 직관적인 이름.
    """
    return get_artifact_host().publish_report(html_content, title=name)
