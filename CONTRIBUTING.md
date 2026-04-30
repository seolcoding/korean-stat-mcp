# 기여 가이드 (CONTRIBUTING)

환영합니다! `korean-stat-mcp`에 관심을 가져주셔서 감사합니다. 작은 수정 한 줄도 큰 도움이 됩니다.

> English version: [CONTRIBUTING-EN.md](./CONTRIBUTING-EN.md)

---

## 기여 방법

### 이슈 (Issue)

- **버그 리포트**: 재현 단계, 기대 결과, 실제 결과, 환경(OS/Python/패키지 버전)을 명시해주세요.
- **기능 제안**: 해결하려는 문제(왜)와 제안하는 해결책(어떻게)을 분리해서 적어주세요.
- 중복을 피하기 위해 기존 이슈를 먼저 검색해 주세요.

### Pull Request

1. 이슈를 먼저 열어 방향을 합의한 뒤 PR을 진행해 주세요. (사소한 오타 수정은 예외)
2. `main` 브랜치에서 직접 작업하지 말고, `feat/`, `fix/`, `docs/` 등의 브랜치를 분리해주세요.
3. 작은 단위의 커밋을 권장합니다. 한 PR은 하나의 논리적 변경에 집중해주세요.
4. PR 본문에 관련 이슈 번호(`Closes #123`)를 적어주세요.

---

## 개발 환경 셋업

```bash
# 1. 저장소 클론
git clone https://github.com/seolcoding/korean-stat-mcp.git
cd korean-stat-mcp

# 2. 의존성 설치 (uv 사용)
uv sync

# 3. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 KOSIS_API_KEY 를 채워주세요.
# KOSIS API 키 발급: https://kosis.kr/openapi/index/index.jsp

# 4. 테스트 실행
uv run pytest -q
```

> Python 패키지 매니저는 [uv](https://github.com/astral-sh/uv)를 표준으로 사용합니다.

---

## 코드 스타일

```bash
# 린트
uv run ruff check .

# 포맷
uv run ruff format .

# 타입 체크
uv run mypy src/
```

- 한 줄 100자 이내, 함수는 가급적 50줄 이내를 지향합니다.
- 공개 함수에는 docstring(한국어 또는 영어)을 적어주세요.
- 외부에서 들어오는 모든 KOSIS API 응답값은 문자열 가능성을 고려해 안전하게 파싱해주세요. 특히 `DT` 필드는 `"-"`, `"*"` 같은 특수값이 올 수 있습니다.

---

## 커밋 메시지 컨벤션

[Conventional Commits](https://www.conventionalcommits.org/) 를 권장합니다.

| Prefix | 용도 |
|---|---|
| `feat:` | 새로운 기능 |
| `fix:` | 버그 수정 |
| `docs:` | 문서만 수정 |
| `refactor:` | 동작 변경 없이 코드 구조 개선 |
| `test:` | 테스트 추가/수정 |
| `chore:` | 빌드/툴/메타 변경 |

예시:

```
feat: add verify_statistics tool for citation re-fetch
fix: handle KOSIS DT="-" placeholder as null in parser
```

---

## PR 체크리스트

PR을 열기 전에 아래 항목을 확인해주세요.

- [ ] `uv run pytest -q` 가 통과한다
- [ ] `uv run ruff check .` 가 통과한다
- [ ] `uv run mypy src/` 가 통과한다
- [ ] 새 기능에는 테스트를 추가했다
- [ ] 사용자가 보는 동작이 바뀌었다면 관련 docs(`README.md`, `docs/USER_GUIDE.md` 등)를 업데이트했다
- [ ] `CHANGELOG.md` 의 `## [Unreleased]` 섹션에 한 줄 항목을 추가했다

---

## 행동 강령

이 프로젝트의 모든 참여자는 [행동 강령(CODE_OF_CONDUCT.md)](./CODE_OF_CONDUCT.md) 을 준수해야 합니다.

---

## 영어 버전

For the English version, see [CONTRIBUTING-EN.md](./CONTRIBUTING-EN.md).
