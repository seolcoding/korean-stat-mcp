#!/bin/bash
# KOSIS API 전체 테스트 (에러만 기록)
#
# 실행 방법:
#   chmod +x scripts/run_full_test.sh
#   nohup ./scripts/run_full_test.sh > /dev/null 2>&1 &
#
# 진행 상황 확인:
#   tail -f test_errors.log
#
# 결과 확인:
#   cat test_errors_result.json | jq '.success, .failed'

cd /Users/sdh/Dev/01_active_projects/kosis-data-processor

echo "=== KOSIS API 전체 테스트 시작 ===" | tee -a test_errors.log
echo "시작: $(date)" | tee -a test_errors.log
echo "총 252,890개 테이블, 병렬 20개" | tee -a test_errors.log

uv run python scripts/test_errors_only.py \
    --parallel 20 \
    --save-interval 500 \
    --output test_errors_result.json

echo "종료: $(date)" | tee -a test_errors.log
