#!/usr/bin/env python3
"""
KOSIS API 에러만 기록하는 테스트.

성공은 카운트만, 실패한 테이블만 상세 기록.
실시간으로 결과 파일 업데이트.

Usage:
    nohup uv run python scripts/test_errors_only.py &
    tail -f test_errors.log
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import argparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from kosis_tools.data import StatisticsData
from kosis_tools.table_meta import TableMetadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("test_errors.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ErrorRecord:
    """실패한 테이블 정보."""
    tbl_id: str
    tbl_nm: str
    org_id: str
    prd_se: str
    error_type: str
    error_msg: str
    obj_vars_count: int


class ErrorOnlyTester:
    """에러만 기록하는 테스터."""

    def __init__(self, metadata_path: str, output_path: str = "test_errors_result.json"):
        self.metadata_path = Path(metadata_path)
        self.output_path = Path(output_path)
        self.tables: List[Dict] = []
        self.client = StatisticsData()
        self.meta_client = TableMetadata(self.client.config)

        # 결과 저장 (메모리에 유지, 주기적으로 파일에 저장)
        self.results = {
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": None,
            "total": 0,
            "tested": 0,
            "success": 0,
            "failed": 0,
            "meta_fail": 0,
            "by_period": defaultdict(lambda: {"success": 0, "failed": 0}),
            "by_error_type": defaultdict(int),
            "errors": []  # 실패한 테이블만 기록
        }
        self.lock = asyncio.Lock()

    def load_metadata(self, limit: int = None, offset: int = 0) -> None:
        """메타데이터 로드."""
        logger.info(f"메타데이터 로드: {self.metadata_path}")
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "tables" in data:
            all_tables = data["tables"]
        elif isinstance(data, list):
            all_tables = data
        else:
            raise ValueError(f"알 수 없는 메타데이터 형식")

        # offset과 limit 적용
        if offset > 0:
            all_tables = all_tables[offset:]
        if limit:
            all_tables = all_tables[:limit]

        self.tables = all_tables
        self.results["total"] = len(self.tables)
        logger.info(f"테이블 {len(self.tables)}개 로드 (offset={offset})")

    async def test_single_table(self, table: Dict) -> bool:
        """단일 테이블 테스트. 성공=True, 실패=False."""
        tbl_id = table["tbl_id"]
        org_id = table["org_id"]
        tbl_nm = table.get("tbl_nm", "N/A")

        try:
            # 메타데이터 조회
            prd_info = await asyncio.to_thread(
                self.meta_client.get_prd_info, org_id, tbl_id
            )

            prd_se = "Y"
            obj_vars_count = 0

            if prd_info:
                info = prd_info[0]
                prd_se = info.get("PRD_SE", "Y")
                obj_vars = await asyncio.to_thread(
                    self.meta_client.get_obj_vars, org_id, tbl_id
                )
                obj_vars_count = len(obj_vars) if obj_vars else 0
            else:
                # 메타 실패
                async with self.lock:
                    self.results["meta_fail"] += 1
                    self.results["by_error_type"]["meta_fail"] += 1
                    self.results["errors"].append(asdict(ErrorRecord(
                        tbl_id=tbl_id, tbl_nm=tbl_nm, org_id=org_id,
                        prd_se="", error_type="meta_fail",
                        error_msg="메타데이터 조회 실패", obj_vars_count=0
                    )))
                return False

            # 데이터 조회
            data = await asyncio.to_thread(
                self.client.get_data_with_smart_retry, org_id, tbl_id
            )

            if data:
                async with self.lock:
                    self.results["success"] += 1
                    self.results["by_period"][prd_se]["success"] += 1
                return True
            else:
                async with self.lock:
                    self.results["failed"] += 1
                    self.results["by_period"][prd_se]["failed"] += 1
                    self.results["by_error_type"]["all_strategies_failed"] += 1
                    self.results["errors"].append(asdict(ErrorRecord(
                        tbl_id=tbl_id, tbl_nm=tbl_nm, org_id=org_id,
                        prd_se=prd_se, error_type="all_strategies_failed",
                        error_msg="모든 전략 실패", obj_vars_count=obj_vars_count
                    )))
                return False

        except Exception as e:
            async with self.lock:
                self.results["failed"] += 1
                self.results["by_error_type"]["exception"] += 1
                self.results["errors"].append(asdict(ErrorRecord(
                    tbl_id=tbl_id, tbl_nm=tbl_nm, org_id=org_id,
                    prd_se="", error_type="exception",
                    error_msg=str(e)[:200], obj_vars_count=0
                )))
            return False

    async def save_results(self):
        """결과 파일 저장."""
        async with self.lock:
            # defaultdict를 일반 dict로 변환
            output = {
                **self.results,
                "by_period": dict(self.results["by_period"]),
                "by_error_type": dict(self.results["by_error_type"]),
            }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    async def run_tests(self, max_concurrent: int = 20, save_interval: int = 100) -> None:
        """병렬 테스트 실행."""
        logger.info(f"테스트 시작 (동시 실행: {max_concurrent}, 저장 간격: {save_interval})")

        semaphore = asyncio.Semaphore(max_concurrent)
        tested = 0
        total = len(self.tables)

        async def test_with_limit(table):
            nonlocal tested
            async with semaphore:
                result = await self.test_single_table(table)
                async with self.lock:
                    self.results["tested"] += 1
                    tested = self.results["tested"]
                return result

        tasks = [test_with_limit(table) for table in self.tables]

        # 진행 상황 추적
        completed = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            completed += 1

            # 주기적 저장 및 로그
            if completed % save_interval == 0 or completed == total:
                await self.save_results()
                async with self.lock:
                    success_rate = self.results["success"] / completed * 100 if completed > 0 else 0
                    logger.info(
                        f"진행: {completed}/{total} ({completed/total*100:.1f}%) | "
                        f"성공: {self.results['success']} ({success_rate:.1f}%) | "
                        f"실패: {self.results['failed']} | 에러목록: {len(self.results['errors'])}개"
                    )

        # 최종 저장
        self.results["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        await self.save_results()

    def print_summary(self):
        """결과 요약 출력."""
        print("\n" + "=" * 70)
        print("KOSIS API 전체 테스트 결과")
        print("=" * 70)
        print(f"총 테이블: {self.results['total']:,}개")
        print(f"테스트 완료: {self.results['tested']:,}개")
        print(f"")
        print(f"성공: {self.results['success']:,}개 ({self.results['success']/self.results['tested']*100:.1f}%)")
        print(f"실패: {self.results['failed']:,}개")
        print(f"메타 실패: {self.results['meta_fail']:,}개")
        print(f"")
        print(f"에러 기록: {len(self.results['errors'])}개")
        print(f"결과 파일: {self.output_path}")
        print("=" * 70 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="KOSIS API 에러만 기록 테스트")
    parser.add_argument("--limit", type=int, help="테스트할 테이블 수 제한")
    parser.add_argument("--offset", type=int, default=0, help="시작 위치")
    parser.add_argument("--parallel", type=int, default=20, help="동시 실행 수")
    parser.add_argument("--output", default="test_errors_result.json", help="결과 파일")
    parser.add_argument("--save-interval", type=int, default=500, help="저장 간격")

    args = parser.parse_args()

    metadata_path = project_root / "data" / "metadata_api" / "tables.json"

    if not metadata_path.exists():
        logger.error(f"메타데이터 파일 없음: {metadata_path}")
        sys.exit(1)

    tester = ErrorOnlyTester(str(metadata_path), args.output)
    tester.load_metadata(limit=args.limit, offset=args.offset)

    await tester.run_tests(
        max_concurrent=args.parallel,
        save_interval=args.save_interval
    )

    tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
