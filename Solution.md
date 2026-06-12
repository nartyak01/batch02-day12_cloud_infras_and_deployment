# Solution — Day 12 Cloud Infrastructure & Deployment (Part 1–5)

> **AICB-P1 · VinUniversity 2026**  
> Đáp án các bài codelab từ Section 01 đến Section 05

---

## Part 1: Localhost vs Production

### Exercise 1.1 — Phát hiện anti-patterns trong `develop/app.py`

Ít nhất **7 vấn đề** trong file basic:

| # | Vấn đề | Chi tiết |
|---|--------|----------|
| 1 | **API key hardcode** | `OPENAI_API_KEY = "sk-hardcoded-fake-key..."` — nếu push lên GitHub public, key bị lộ ngay |
| 2 | **Database credentials hardcode** | `DATABASE_URL = "postgresql://admin:password123@..."` — secret trong source code |
| 3 | **Không có config management** | `DEBUG = True`, `MAX_TOKENS = 500` cố định trong code, không đọc từ env |
| 4 | **Logging không an toàn** | Dùng `print()` và log ra API key: `print(f"Using key: {OPENAI_API_KEY}")` |
| 5 | **Không có health check** | Platform cloud không biết container còn sống hay đã crash → không restart được |
| 6 | **Host/Port cố định** | `host="localhost"`, `port=8000` — không chạy được trong container (cần `0.0.0.0` và `PORT` env) |
| 7 | **Debug reload trong production** | `reload=True` — chỉ dùng khi dev, không phù hợp production |
| 8 | **Không graceful shutdown** | Không xử lý SIGTERM — request đang xử lý có thể bị cắt đột ngột |

### Exercise 1.3 — So sánh Basic vs Advanced

| Feature | Basic (`develop/`) | Advanced (`production/`) | Tại sao quan trọng? |
|---------|-------------------|--------------------------|---------------------|
| **Config** | Hardcode trong code | `config.py` đọc từ env vars (`Settings` dataclass) | Thay đổi config không cần sửa code; dev/staging/prod dùng cùng codebase |
| **Secrets** | `OPENAI_API_KEY = "sk-..."` | `os.getenv("OPENAI_API_KEY")` | Tránh lộ secret khi commit; rotate key dễ dàng |
| **Port/Host** | `localhost:8000` cố định | `HOST=0.0.0.0`, `PORT` từ env | Railway/Render inject `PORT`; container cần bind `0.0.0.0` |
| **Health check** | Không có | `GET /health` (liveness) + `GET /ready` (readiness) | Platform biết khi nào restart; load balancer biết khi nào route traffic |
| **Logging** | `print()` debug | Structured JSON logging | Dễ parse trong Datadog/Loki; không log secrets |
| **Shutdown** | Tắt đột ngột | `lifespan` + SIGTERM handler | Hoàn thành request in-flight trước khi container bị kill |
| **CORS** | Không có | `CORSMiddleware` với `ALLOWED_ORIGINS` | Kiểm soát domain nào được gọi API |
| **Validation** | Không validate input | `HTTPException(422)` khi thiếu `question` | Tránh lỗi runtime; API contract rõ ràng |

### Câu hỏi thảo luận — Part 1

**1. Push code có API key hardcode lên GitHub public?**  
→ Key bị lộ vĩnh viễn (Git history không xóa được). Bot quét GitHub liên tục và dùng key trong vài phút. Phải revoke key ngay, rotate secret mới, và dùng env vars / Secret Manager.

**2. Tại sao stateless quan trọng khi scale?**  
→ Khi có nhiều instances, request của cùng user có thể đến instance khác nhau. Nếu state lưu trong memory, instance B không thấy data của instance A → bug. Stateless = state lưu ngoài (Redis/DB), mọi instance đọc được.

**3. "Dev/prod parity" trong 12-factor?**  
→ Dev và production nên giống nhau về stack (cùng DB engine, cùng OS/container, cùng cách config). Không nên "chỉ chạy được trên laptop". Docker + env vars giúp đạt parity.

### Checkpoint 1

- [x] Hiểu tại sao hardcode secrets nguy hiểm
- [x] Biết cách dùng environment variables (`config.py`, `.env.example`)
- [x] Hiểu vai trò health check (`/health` liveness, `/ready` readiness)
- [x] Biết graceful shutdown qua `lifespan` và SIGTERM

---

## Part 2: Docker Containerization

### Exercise 2.1 — Đọc `develop/Dockerfile`

| Câu hỏi | Đáp án |
|---------|--------|
| **Base image?** | `python:3.11` (~1 GB, full Python distribution) |
| **Working directory?** | `/app` |
| **Tại sao COPY requirements.txt trước?** | Docker layer caching — nếu chỉ code thay đổi mà dependencies không đổi, Docker reuse layer `pip install`, build nhanh hơn |
| **CMD vs ENTRYPOINT?** | `CMD` = command mặc định, có thể override khi `docker run`. `ENTRYPOINT` = executable cố định, args từ `docker run` append vào. Thường dùng `ENTRYPOINT` cho binary, `CMD` cho default args |

### Exercise 2.3 — Multi-stage build (`production/Dockerfile`)

| Stage | Mục đích |
|-------|----------|
| **Stage 1: `builder`** | Cài gcc, libpq-dev, `pip install --user` dependencies vào `/root/.local` |
| **Stage 2: `runtime`** | Copy chỉ site-packages + source code; chạy với non-root user `appuser` |

**Tại sao image nhỏ hơn?**  
Runtime image bắt đầu từ `python:3.11-slim` (~150 MB) thay vì `python:3.11` (~1 GB). Không chứa gcc, build tools, pip cache. Chỉ copy artifacts cần chạy.

**Kết quả ước tính:** develop ~800 MB, production ~160–200 MB.

### Exercise 2.4 — Docker Compose stack (`production/docker-compose.yml`)

**Architecture:**

```
Client (curl/browser)
        │
        ▼
   ┌─────────┐
   │  Nginx  │  :80 — reverse proxy + load balancer
   └────┬────┘
        │
   ┌────┴────┬──────────┐
   ▼         ▼          ▼
 Agent    Redis      Qdrant
(FastAPI) (cache)  (vector DB)
```

**Services:**
- `agent` — FastAPI app, healthcheck, depends on redis + qdrant
- `redis` — session cache, rate limiting, persistent volume
- `qdrant` — vector database cho RAG
- `nginx` — expose port 80, proxy tới agent

**Communication:** Tất cả trong network `internal`. Agent gọi `redis://redis:6379`, `http://qdrant:6333` qua Docker DNS.

### Câu hỏi thảo luận — Part 2

**1. Tại sao COPY requirements trước COPY code?**  
→ Tận dụng Docker layer cache. Dependencies ít thay đổi hơn code → layer `pip install` được cache, rebuild nhanh.

**2. `.dockerignore` nên chứa gì?**  
→ `venv/`, `.env`, `__pycache__/`, `.git/`, `*.pyc`, `node_modules/`. Tránh copy secrets vào image; giảm build context size.

**3. Mount volume khi agent cần đọc file?**  
```bash
docker run -v /host/data:/app/data agent-production
# hoặc trong docker-compose:
volumes:
  - ./data:/app/data
```

### Checkpoint 2

- [x] Hiểu cấu trúc Dockerfile (FROM, WORKDIR, COPY, RUN, CMD, EXPOSE, HEALTHCHECK)
- [x] Biết lợi ích multi-stage builds (nhỏ hơn, an toàn hơn, non-root user)
- [x] Hiểu Docker Compose orchestration (multi-service, networks, volumes, healthcheck)
- [x] Biết debug: `docker logs`, `docker exec -it`, `docker compose ps`

---

## Part 3: Cloud Deployment

### Exercise 3.1 — Railway

**Các bước deploy:**
```bash
npm i -g @railway/cli
railway login
cd 03-cloud-deployment/railway
railway init
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
railway up
railway domain
```

**Điểm quan trọng trong `railway.toml`:**
- `startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"` — Railway inject `$PORT`
- `healthcheckPath = "/health"` — auto-restart nếu unhealthy
- `restartPolicyType = "ON_FAILURE"`

**Test sau deploy:**
```bash
curl https://<your-domain>/health
curl -X POST https://<your-domain>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "hello"}'
```

### Exercise 3.2 — So sánh `railway.toml` vs `render.yaml`

| Khía cạnh | Railway (`railway.toml`) | Render (`render.yaml`) |
|-----------|--------------------------|-------------------------|
| **Format** | TOML, gọn | YAML Blueprint, khai báo nhiều services |
| **Builder** | Nixpacks (auto-detect) hoặc Dockerfile | `runtime: python`, `buildCommand` explicit |
| **Services** | 1 service/app | Có thể khai báo web + redis trong 1 file |
| **Secrets** | `railway variables set` | `sync: false` hoặc `generateValue: true` |
| **Region** | Auto | Chọn explicit (`singapore`) |
| **Auto deploy** | Git push trigger | `autoDeploy: true` |
| **Health check** | `healthcheckPath` | `healthCheckPath` |

**Khác biệt chính:** Render dùng Infrastructure as Code đầy đủ hơn (multi-service blueprint). Railway đơn giản hơn cho MVP/prototype.

### Exercise 3.3 — GCP Cloud Run (`cloudbuild.yaml`)

**CI/CD pipeline 4 bước:**
1. **test** — `pytest tests/`
2. **build** — Docker image tag `$COMMIT_SHA` + `latest`
3. **push** — Push lên `gcr.io/$PROJECT_ID/ai-agent`
4. **deploy** — `gcloud run deploy` với `min-instances=1`, `max-instances=10`, secrets từ Secret Manager

### Câu hỏi thảo luận — Part 3

**1. Serverless (Lambda) không phải lúc nào tốt cho AI agent?**  
→ Cold start chậm (load model mất vài giây); timeout giới hạn; không phù hợp long-running/streaming; state management phức tạp.

**2. Cold start là gì?**  
→ Thời gian khởi động instance mới khi không có instance warm. User phải chờ → UX kém. Giảm bằng `min-instances=1`.

**3. Khi nào upgrade Railway → Cloud Run?**  
→ Cần auto-scaling theo traffic, SLA cao, multi-region, tích hợp GCP (BigQuery, Vertex AI), CI/CD production-grade, budget lớn hơn.

### Checkpoint 3

- [x] Hiểu deploy flow Railway/Render
- [x] Biết set env vars trên cloud (không commit secrets)
- [x] Hiểu health check path cho platform
- [x] Biết xem logs: `railway logs`, Render Dashboard → Logs

---

## Part 4: API Security

### Exercise 4.1 — API Key authentication (`develop/app.py`)

| Câu hỏi | Đáp án |
|---------|--------|
| **API key check ở đâu?** | Dependency `verify_api_key()` inject vào `/ask` qua `Depends()`. Đọc header `X-API-Key` |
| **Sai key thì sao?** | Thiếu key → `401 Unauthorized`. Sai key → `403 Forbidden` |
| **Rotate key?** | Đổi `AGENT_API_KEY` env var trên server, restart app. Client cập nhật header. Không cần sửa code |

### Exercise 4.2 — JWT flow (`production/auth.py`)

```
1. POST /auth/token  {username, password}
   → authenticate_user() check DEMO_USERS
   → create_token() → JWT signed với SECRET_KEY, expiry 60 phút

2. POST /ask  Header: Authorization: Bearer <token>
   → verify_token() decode JWT, extract sub + role
   → process request

3. Token expired → 401 "Token expired. Please login again."
```

**Demo credentials:**
- `student / demo123` — role `user`, 10 req/min
- `teacher / teach456` — role `admin`, 100 req/min

### Exercise 4.3 — Rate limiting (`rate_limiter.py`)

| Câu hỏi | Đáp án |
|---------|--------|
| **Algorithm?** | **Sliding Window** — deque lưu timestamps, loại bỏ timestamps cũ hơn 60s |
| **Limit?** | User: **10 requests / 60 giây**. Admin: **100 requests / 60 giây** |
| **Bypass cho admin?** | Dùng `rate_limiter_admin` thay vì `rate_limiter_user` khi `role == "admin"` |
| **Vượt limit?** | `429 Too Many Requests` + headers `X-RateLimit-*`, `Retry-After` |

### Exercise 4.4 — Cost guard (`cost_guard.py`)

**Logic hiện tại (in-memory demo):**
- Mỗi user: **$1/ngày** budget
- Global: **$10/ngày** tổng
- Vượt budget → `402 Payment Required`
- Global vượt → `503 Service Unavailable`
- Cảnh báo khi dùng ≥ 80% budget

**Redis implementation (theo CODE_LAB):**

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False

    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)
    return True
```

**Luồng bảo vệ đầy đủ:**
```
Request → Auth (401) → Rate Limit (429) → Validation (422) → Cost Check (402) → Agent (200)
```

### Câu hỏi thảo luận — Part 4

**1. API Key vs JWT vs OAuth2?**
- **API Key** — đơn giản, B2B, internal API, MVP
- **JWT** — stateless, user sessions, mobile/SPA apps
- **OAuth2** — third-party login (Google, GitHub), enterprise SSO

**2. Rate limit bao nhiêu cho AI agent?**  
→ MVP: 10–20 req/min/user. Production: tùy cost model. Admin/internal: cao hơn. Luôn có burst allowance và clear error message.

**3. API key bị lộ?**  
→ Revoke ngay, rotate key mới, check logs abuse, thêm IP whitelist nếu cần, alert khi usage spike bất thường.

### Checkpoint 4

- [x] Implement API key auth (`verify_api_key` dependency)
- [x] Hiểu JWT flow (login → token → Bearer header)
- [x] Implement rate limiting (sliding window, 10 req/min)
- [x] Hiểu cost guard (daily/monthly budget, 402 response)

---

## Part 5: Scaling & Reliability

### Exercise 5.1 — Health checks (`develop/app.py`)

**`/health` (Liveness):**
```python
@app.get("/health")
def health():
    return {
        "status": "ok",  # hoặc "degraded"
        "uptime_seconds": ...,
        "checks": {"memory": {...}}
    }
```
→ Trả 200 nếu process còn sống. Platform restart nếu fail.

**`/ready` (Readiness):**
```python
@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(503, "Agent not ready")
    return {"ready": True}
```
→ Trả 503 khi đang startup/shutdown. Load balancer không route traffic vào.

### Exercise 5.2 — Graceful shutdown

**Implementation trong `develop/app.py`:**
1. `lifespan` context manager — set `_is_ready = False` khi shutdown
2. Middleware đếm `_in_flight_requests`
3. Shutdown loop chờ in-flight requests hoàn thành (max 30s)
4. `signal.signal(SIGTERM, handle_sigterm)` — log signal, uvicorn xử lý graceful stop
5. `timeout_graceful_shutdown=30` trong uvicorn

### Exercise 5.3 — Stateless design (`production/app.py`)

**Anti-pattern (state trong memory):**
```python
conversation_history = {}  # Mỗi instance có dict riêng
```

**Correct (state trong Redis):**
```python
def save_session(session_id, data):
    _redis.setex(f"session:{session_id}", ttl, json.dumps(data))

def load_session(session_id):
    return json.loads(_redis.get(f"session:{session_id}") or "{}")
```

**Tại sao?** Scale 3 instances → request 1 đến Agent A, request 2 đến Agent B. Redis là shared storage, mọi instance đọc cùng session.

### Exercise 5.4 — Load balancing

**Stack (`production/docker-compose.yml`):**
```
Client → Nginx :8080 → agent:8000 (3 replicas) → Redis
```

**Nginx config:** `upstream agent_cluster { server agent:8000; }` — Docker DNS round-robin các replicas.

**Test:**
```bash
docker compose -f 05-scaling-reliability/production/docker-compose.yml up --scale agent=3
python 05-scaling-reliability/production/test_stateless.py
```

Quan sát `served_by` trong response — requests phân tán qua nhiều instance, session vẫn liên tục nhờ Redis.

### Exercise 5.5 — Test stateless

`test_stateless.py` thực hiện:
1. Tạo session mới qua `POST /chat`
2. Gửi 5 requests với cùng `session_id`
3. Ghi nhận `served_by` — nhiều instance khác nhau
4. Verify `GET /chat/{session_id}/history` — toàn bộ conversation còn nguyên

### Checkpoint 5

- [x] Implement `/health` và `/ready`
- [x] Implement graceful shutdown (lifespan + in-flight tracking + SIGTERM)
- [x] Refactor stateless (Redis session storage)
- [x] Hiểu load balancing với Nginx upstream
- [x] Test stateless design với `test_stateless.py`

---

## Tổng kết

| Part | Chủ đề | Kết quả đạt được |
|------|--------|------------------|
| 01 | Localhost vs Production | 12-factor config, health check, graceful shutdown |
| 02 | Docker | Dockerfile, multi-stage, docker-compose stack |
| 03 | Cloud Deployment | Railway, Render, Cloud Run CI/CD |
| 04 | API Security | API Key, JWT, rate limit, cost guard |
| 05 | Scaling | Stateless Redis, Nginx LB, health/readiness probes |

**Lệnh test nhanh (từ project root):**

```bash
# Part 1
cd 01-localhost-vs-production/production && cp .env.example .env && python app.py

# Part 2
docker build -f 02-docker/develop/Dockerfile -t agent-develop .
docker compose -f 02-docker/production/docker-compose.yml up

# Part 4
cd 04-api-gateway/production && python app.py

# Part 5
docker compose -f 05-scaling-reliability/production/docker-compose.yml up --scale agent=3
python 05-scaling-reliability/production/test_stateless.py
```

---

## Part 6: Final Project (Dự án hoàn chỉnh)

Dự án trong thư mục [06-lab-complete](file:///d:/AI20K/day12/batch02-day12_cloud_infras_and_deployment/06-lab-complete) đã được tích hợp đầy đủ pipeline Legal RAG thực tế từ các buổi trước và áp dụng toàn bộ các tiêu chuẩn production-ready.

### Cấu trúc dự án
```text
06-lab-complete/
├── app/
│   ├── __init__.py
│   ├── main.py            # API Gateway và routing
│   ├── config.py          # Quản lý cấu hình từ environment variables
│   └── rag/               # Pipeline Legal RAG (Day 08)
│       ├── shared.py
│       └── task10_generation.py
├── Dockerfile             # Multi-stage, optimized, non-root user
├── docker-compose.yml     # Orchestration stack
├── .dockerignore          # Giảm kích thước build context
├── .env.example           # Mẫu cấu hình môi trường
├── requirements.txt       # Danh sách dependencies
├── railway.toml           # Cấu hình deploy Railway
└── render.yaml            # Cấu hình deploy Render
```

### Các tính năng đã hoàn thiện trong Production Agent:

1. **Config Management (12-Factor App):**
   - Mọi cấu hình (`HOST`, `PORT`, `ENVIRONMENT`, API Keys, `REDIS_URL`, etc.) được đọc trực tiếp từ environment variables thông qua class `Settings` tại [config.py](file:///d:/AI20K/day12/batch02-day12_cloud_infras_and_deployment/06-lab-complete/app/config.py).
2. **API Authentication:**
   - Bảo mật endpoint `/ask` bằng API Key thông qua header `X-API-Key`.
3. **Rate Limiting:**
   - Giới hạn tần suất request (mặc định 20 req/min per user) bằng thuật toán Sliding Window lưu trong memory của agent. Trả về `429 Too Many Requests` khi vượt hạn mức.
4. **Cost Guard:**
   - Ước tính token sử dụng và kiểm soát chi phí hàng ngày dựa trên `DAILY_BUDGET_USD`. Trả về `503 Service Unavailable` khi vượt budget.
5. **Health & Readiness Checks:**
   - Endpoint `/health` (Liveness probe) kiểm tra tình trạng sống/chết của app.
   - Endpoint `/ready` (Readiness probe) kiểm tra trạng thái sẵn sàng xử lý request.
6. **Graceful Shutdown:**
   - Lắng nghe tín hiệu `SIGTERM` từ Docker/Cloud Orchestrator để dừng nhận request mới và hoàn thành các request in-flight trước khi tắt hẳn (grace period 30s).
7. **Docker Optimization:**
   - Dùng **Multi-stage build** trong [Dockerfile](file:///d:/AI20K/day12/batch02-day12_cloud_infras_and_deployment/06-lab-complete/Dockerfile) để loại bỏ compiler tools khỏi runtime image, sử dụng base image `python:3.11-slim` để tối ưu dung lượng (< 500 MB).
   - Chạy ứng dụng dưới quyền user non-root `agent` để bảo mật.
   - Khai báo chỉ thị `HEALTHCHECK` trực tiếp trong Dockerfile.
8. **Structured Logging:**
   - Toàn bộ log của ứng dụng được format dưới dạng JSON (chứa `ts`, `lvl`, `msg`, `event`, etc.) giúp dễ dàng tích hợp với các hệ thống phân tích logs như Datadog, Loki hay CloudWatch.

### Kết quả kiểm tra độ sẵn sàng (Production Readiness Check):
Khi chạy script kiểm tra tự động:
```bash
$env:PYTHONIOENCODING="utf-8"
python check_production_ready.py
```
Kết quả đạt tối đa **20/20** tiêu chí (100%):
```text

📁 Required Files
  ✅ Dockerfile exists
  ✅ docker-compose.yml exists
  ✅ .dockerignore exists
  ✅ .env.example exists
  ✅ requirements.txt exists
  ✅ railway.toml or render.yaml exists

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets in code

🌐 API Endpoints (code check)
  ✅ /health endpoint defined
  ✅ /ready endpoint defined
  ✅ Authentication implemented
  ✅ Rate limiting implemented
  ✅ Graceful shutdown (SIGTERM)
  ✅ Structured logging (JSON)

🐳 Docker
  ✅ Multi-stage build
  ✅ Non-root user
  ✅ HEALTHCHECK instruction
  ✅ Slim base image
  ✅ .dockerignore covers .env
  ✅ .dockerignore covers __pycache__

```
