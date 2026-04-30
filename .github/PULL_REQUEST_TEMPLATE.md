# Pull Request

## 변경 요약 / Summary

<!-- 이 PR이 무엇을 바꾸고 왜 필요한지 간단히 설명해 주세요. -->
<!-- Briefly describe what this PR changes and why. -->

## 관련 이슈 / Related issue

<!-- 예: Closes #123, Refs #456 -->

## 변경 종류 / Type of change

- [ ] bugfix
- [ ] feature
- [ ] docs
- [ ] refactor
- [ ] test
- [ ] chore

## 테스트 / Testing

<!-- 어떤 테스트를 추가했고, 어떤 명령으로 실행/통과시켰는지 적어주세요. -->
<!-- Describe tests added and commands used to verify them. -->

## 체크리스트 / Checklist

- [ ] CHANGELOG.md `[Unreleased]` 섹션에 항목 추가 / Added entry to `[Unreleased]` in CHANGELOG.md
- [ ] CONTRIBUTING 가이드를 따랐음 / Followed the CONTRIBUTING guide
- [ ] `uv run pytest -q tests/unit -m "not network"` 통과 / unit tests pass
- [ ] `uv run ruff check src/kosis_tools src/mcp_server` 통과 / scoped ruff check passes
- [ ] `uv run ruff format --check src/kosis_tools src/mcp_server` 통과 / scoped format check passes
- [ ] `uv run python scripts/validation/check_release_readiness.py --quiet` 통과 / release-readiness check passes
- [ ] 새 기능에 docstring + 예시 추가 / Added docstrings and examples for new features
- [ ] 사유 정보(API 키, 개인 도메인 등) 노출 없음 / No sensitive info (API keys, private domains, etc.) leaked
