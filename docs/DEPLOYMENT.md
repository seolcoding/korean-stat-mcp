# KOSIS MCP Server - 배포 가이드

> **상태**: ✅ 프로덕션 운영 중 (Cloudflare Tunnel)
> **배포일**: 2025-12-20
> **서버**: 사용자 자체 호스팅 (예: Ubuntu 24.04+, Docker 환경)
> **접속 URL**: ${KOSIS_MCP_URL}  # 사용자 자체 호스팅 인스턴스 주소
> **참조 문서**: FastMCP 공식문서, pgvector GitHub, Cloudflare R2 Docs

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│  연구실 리눅스 서버                                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Docker: kosis-mcp                                            │  │
│  │  └── FastMCP (uvicorn, stateless_http=True)                   │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │  Docker: postgres (pgvector/pgvector:pg16)                    │  │
│  │  └── PostgreSQL 16 + pgvector extension                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼ Upload (boto3 S3 API)                │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Cloudflare R2                                                 │  │
│  │  └── /charts/, /reports/, /data/ (Egress 무료)                │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. FastMCP HTTP 배포

### 2.1 프로덕션 ASGI 앱 생성

**출처**: [FastMCP 공식문서 - HTTP Deployment](https://github.com/jlowin/fastmcp/blob/main/docs/deployment/http.mdx)

```python
# src/mcp_server/app.py
from fastmcp import FastMCP

def create_app():
    """프로덕션용 ASGI 앱 팩토리."""
    # stateless_http=True: 수평 확장 시 필수
    # 각 요청이 독립적으로 처리되어 로드밸런서 뒤에서 안전
    mcp = FastMCP("kosis-stats", stateless_http=True)

    # 도구 등록은 기존 server.py에서 import
    # ...

    return mcp.http_app()

app = create_app()  # uvicorn이 사용
```

### 2.2 실행 방법

```bash
# 개발 (단일 워커)
uvicorn src.mcp_server.app:app --host 0.0.0.0 --port 8000

# 프로덕션 (멀티 워커)
FASTMCP_STATELESS_HTTP=true uvicorn src.mcp_server.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4
```

### 2.3 기존 FastAPI와 통합 (선택사항)

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

api = FastAPI(title="KOSIS API")

# 기존 REST 엔드포인트
@api.get("/health")
def health():
    return {"status": "ok"}

# MCP 서버 마운트
from .mcp_app import create_mcp_app
api.mount("/mcp", create_mcp_app())

# 아티팩트 정적 파일 (로컬 폴백용)
api.mount("/artifacts", StaticFiles(directory="/app/artifacts"), name="artifacts")
```

### 2.4 CORS 설정

**출처**: FastMCP 2.3.2+ 미들웨어 지원

```python
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = mcp.http_app(middleware=middleware)
```

---

## 3. Cloudflare R2 연동

### 3.1 boto3 설정

**출처**: [Cloudflare R2 Docs - S3 API Compatibility](https://developers.cloudflare.com/r2/api/s3/)

```python
# src/kosis_tools/r2_storage.py
import boto3
from botocore.config import Config

def create_r2_client():
    """R2 S3 호환 클라이언트 생성."""
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        # 필수: R2는 region 지정 필요
        region_name=os.environ.get("R2_REGION", "auto"),  # wnam, enam, weur, eeur, apac, auto
        config=Config(
            signature_version="s3v4",
            # boto3 1.36.0+ 체크섬 호환성 이슈 해결
            # 출처: Cloudflare R2 Docs
            request_checksum_calculation="WHEN_REQUIRED",
            response_checksum_validation="WHEN_REQUIRED",
        ),
    )
```

### 3.2 업로드 유틸리티

```python
class R2Storage:
    def __init__(self):
        self.client = create_r2_client()
        self.bucket = os.environ["R2_BUCKET_NAME"]
        self.public_url = os.environ["R2_PUBLIC_URL"]

    def upload_file(self, local_path: str, key: str) -> str:
        """파일 업로드 후 퍼블릭 URL 반환."""
        content_type = self._get_content_type(key)
        self.client.upload_file(
            local_path,
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"{self.public_url}/{key}"

    def upload_bytes(self, data: bytes, key: str) -> str:
        """바이트 데이터 업로드."""
        content_type = self._get_content_type(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return f"{self.public_url}/{key}"

    @staticmethod
    def _get_content_type(key: str) -> str:
        if key.endswith(".html"):
            return "text/html; charset=utf-8"
        elif key.endswith(".json"):
            return "application/json"
        elif key.endswith(".png"):
            return "image/png"
        elif key.endswith(".svg"):
            return "image/svg+xml"
        return "application/octet-stream"
```

### 3.3 환경 변수

```bash
# .env
R2_ACCOUNT_ID=your_account_id          # Cloudflare 대시보드에서 확인
R2_ACCESS_KEY_ID=your_access_key       # R2 > Manage R2 API Tokens
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=kosis-assets
R2_PUBLIC_URL=https://pub-xxx.r2.dev   # 퍼블릭 버킷 URL 또는 커스텀 도메인
R2_REGION=auto                          # wnam, enam, weur, eeur, apac, auto
```

---

## 4. Docker 설정

### 4.1 Dockerfile

```dockerfile
FROM python:3.12-slim

# 빌드 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# uv 설치
RUN pip install --no-cache-dir uv

# 의존성 먼저 설치 (캐시 활용)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 소스 복사
COPY src/ src/
COPY data/ data/

# 환경변수
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# 아티팩트 디렉토리
RUN mkdir -p /app/artifacts/charts /app/artifacts/reports /app/artifacts/data

EXPOSE 8000

# 프로덕션 실행
CMD ["uv", "run", "uvicorn", "mcp_server.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]
```

### 4.2 docker-compose.yml

```yaml
version: "3.8"

services:
  kosis-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      # FastMCP
      - FASTMCP_STATELESS_HTTP=true
      # KOSIS
      - KOSIS_API_KEY=${KOSIS_API_KEY}
      # PostgreSQL
      - DATABASE_URL=postgresql+asyncpg://kosis:${POSTGRES_PASSWORD}@postgres:5432/kosis
      # R2
      - R2_ACCOUNT_ID=${R2_ACCOUNT_ID}
      - R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
      - R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
      - R2_BUCKET_NAME=${R2_BUCKET_NAME}
      - R2_PUBLIC_URL=${R2_PUBLIC_URL}
      - R2_REGION=${R2_REGION:-auto}
      # OpenAI (임베딩용)
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./artifacts:/app/artifacts
      - ./kosis_data:/app/kosis_data:ro
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_USER=kosis
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=kosis
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kosis"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 4.3 초기화 SQL

```sql
-- migrations/init.sql
-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 테이블 카탈로그
CREATE TABLE IF NOT EXISTS kosis_tables (
    id SERIAL PRIMARY KEY,
    tbl_id VARCHAR(50) UNIQUE NOT NULL,
    tbl_nm TEXT NOT NULL,
    org_id VARCHAR(10),
    org_nm VARCHAR(100),
    stat_nm TEXT,
    description TEXT,
    contents TEXT,
    keywords TEXT[],
    start_prd VARCHAR(10),
    end_prd VARCHAR(10),
    prd_se VARCHAR(5),
    embedding vector(1536),  -- text-embedding-3-small 기본 차원
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스는 데이터 로드 후 생성 (HYBRID_SEARCH.md 참조)
```

---

## 5. 배포 체크리스트

### 5.1 사전 준비

- [ ] Cloudflare 계정 생성 및 R2 버킷 생성
- [ ] R2 API 토큰 발급 (Object Read & Write 권한)
- [ ] R2 퍼블릭 접근 설정 (또는 커스텀 도메인)
- [ ] OpenAI API 키 발급
- [ ] KOSIS API 키 확인

### 5.2 배포 순서

```bash
# 1. 저장소 클론 및 환경 설정
git clone <repo>
cd kosis-mcp
cp .env.example .env
# .env 파일 편집

# 2. 이미지 빌드 및 실행
docker compose up -d --build

# 3. 로그 확인
docker compose logs -f kosis-mcp

# 4. 헬스체크
curl http://localhost:8000/health
```

### 5.3 업데이트

```bash
git pull
docker compose up -d --build
```

---

## 6. 외부 접근 (✅ 완료)

### Cloudflare Tunnel 설정 (현재 운영 중)

**현재 배포 상태:**
```bash
# Cloudflare Tunnel URL (임시)
${KOSIS_MCP_URL}

# 테스트
curl ${KOSIS_MCP_URL}/health
```

**설정 방법:**
```bash
# Cloudflare Tunnel 설치 (원격 서버에서)
# docker-compose.remote.yml 사용

# 터널 시작 (포함됨)
docker compose -f docker-compose.remote.yml up -d
```

**Claude Desktop 연결:**
```json
{
  "mcpServers": {
    "kosis": {
      "url": "${KOSIS_MCP_URL}",
      "transport": "streamable-http"
    }
  }
}
```

### 향후 개선 (Phase 5)

| 작업 | 상태 | 비고 |
|------|------|------|
| **영구 터널 설정** | 📋 예정 | 현재는 임시 URL (재시작 시 변경됨) |
| **커스텀 도메인** | 📋 예정 | `kosis-mcp.yourdomain.com` |
| **인증 추가** | 📋 예정 | API Key 또는 OAuth |

### 옵션 비교

| 방법 | 장점 | 단점 | 상태 |
|------|------|------|------|
| **Cloudflare Tunnel** | 무료, 포트 개방 불필요 | 임시 URL (영구 설정 필요) | ✅ **현재 사용 중** |
| **Tailscale** | 포트 개방 불필요, 무료 | 클라이언트 설치 필요 | - |
| **포트포워딩 + DDNS** | 표준 | 보안 설정 필요 | - |

---

## 7. 참조 문서

### 공식 문서
- [FastMCP - HTTP Deployment](https://gofastmcp.com/deployment/http)
- [FastMCP - Running Servers](https://gofastmcp.com/deployment/running-server)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Cloudflare R2 - S3 API](https://developers.cloudflare.com/r2/api/s3/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)

### 관련 프로젝트 문서
- [HYBRID_SEARCH.md](./HYBRID_SEARCH.md) - 하이브리드 검색 설계
- [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 전체 아키텍처
