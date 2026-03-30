---
description: 브라우저에서 실시간 LLM 모니터링 대시보드. GPU 메트릭, 엔진 상태, 성능 이력. 설정 불필요.
---

# asiai web

시각적 모니터링과 벤치마크를 위한 웹 대시보드를 시작합니다.

## 사용법

```bash
asiai web
asiai web --port 9000
asiai web --host 0.0.0.0
asiai web --no-open
```

## 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--port` | `8899` | 수신할 HTTP 포트 |
| `--host` | `127.0.0.1` | 바인딩할 호스트 |
| `--no-open` | | 브라우저를 자동으로 열지 않음 |
| `--db` | `~/.local/share/asiai/asiai.db` | SQLite 데이터베이스 경로 |

## 요구 사항

웹 대시보드에는 추가 의존성이 필요합니다:

```bash
pip install asiai[web]
# 또는 모두 설치:
pip install asiai[all]
```

## 페이지

### 대시보드 (`/`)

엔진 상태, 로드된 모델, 메모리 사용량, 최근 벤치마크 결과를 포함한 시스템 개요.

### 벤치마크 (`/bench`)

브라우저에서 직접 교차 엔진 벤치마크 실행:

- **Quick Bench** 버튼 — 1 프롬프트, 1회 실행, ~15초
- 고급 옵션: 엔진, 프롬프트, 실행 횟수, 컨텍스트 크기(4K/16K/32K/64K), 전력
- SSE를 통한 실시간 진행
- 승자 하이라이트 포함 결과 테이블
- 처리량과 TTFT 차트
- **공유 카드** — 벤치마크 후 자동 생성 (API 경유 PNG, SVG 폴백)
- **공유 섹션** — 링크 복사, PNG/SVG 다운로드, X/Reddit 공유, JSON 내보내기

### 이력 (`/history`)

벤치마크와 시스템 메트릭의 시계열 시각화:

- 시스템 차트: CPU 부하, 메모리 %, GPU 사용률 (renderer/tiler 분할)
- 엔진 활동: TCP 연결, 처리 중 요청, KV 캐시 사용률 %
- 벤치마크 차트: 엔진별 처리량(tok/s)과 TTFT
- 프로세스 메트릭: 벤치마크 실행 중 엔진 CPU %와 RSS 메모리
- 시간 범위 필터 (1h / 24h / 7d / 30d / 90d) 또는 커스텀 날짜 범위
- 컨텍스트 크기 표시 포함 데이터 테이블 (예: "code (64K ctx)")

### 모니터 (`/monitor`)

5초 갱신의 실시간 시스템 모니터링:

- CPU 부하 스파크라인
- 메모리 게이지
- 서멀 상태
- 로드된 모델 목록

### 닥터 (`/doctor`)

시스템, 엔진, 데이터베이스의 인터랙티브 상태 확인. `asiai doctor`와 동일한 검사를 시각적 인터페이스로.

## API 엔드포인트

웹 대시보드는 프로그래밍 접근을 위한 REST API 엔드포인트를 노출합니다.

### `GET /api/status`

경량 상태 확인. 10초 캐시, 500ms 이내 응답.

```json
{
  "status": "ok",
  "ts": 1709700000,
  "uptime": 86400,
  "engines": {"ollama": true, "lmstudio": false},
  "memory_pressure": "normal",
  "thermal_level": "nominal"
}
```

상태 값: `ok` (모든 엔진 접근 가능), `degraded` (일부 중단), `error` (전부 중단).

### `GET /api/snapshot`

전체 시스템 + 엔진 스냅샷. 5초 캐시. CPU 부하, 메모리, 서멀 상태, 로드된 모델 포함 엔진별 상태.

### `GET /api/benchmarks`

필터 포함 벤치마크 결과. tok/s, TTFT, 전력, context_size, engine_version을 포함한 실행별 데이터 반환.

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `hours` | `168` | 시간 범위 (0 = 전체) |
| `model` | | 모델 이름으로 필터 |
| `engine` | | 엔진 이름으로 필터 |
| `since` / `until` | | Unix 타임스탬프 범위 (hours 재정의) |

### `GET /api/engine-history`

엔진 상태 이력 (접근성, TCP 연결, KV 캐시, 예측 토큰).

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `hours` | `168` | 시간 범위 |
| `engine` | | 엔진 이름으로 필터 |

### `GET /api/benchmark-process`

벤치마크 실행 중 프로세스 수준 CPU 및 메모리 메트릭 (7일 보존).

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `hours` | `168` | 시간 범위 |
| `engine` | | 엔진 이름으로 필터 |

### `GET /api/metrics`

Prometheus 노출 형식. 시스템, 엔진, 모델, 벤치마크 메트릭을 커버하는 게이지.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'asiai'
    static_configs:
      - targets: ['localhost:8899']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

메트릭:

| 메트릭 | 유형 | 설명 |
|--------|------|------|
| `asiai_cpu_load_1m` | gauge | CPU 부하 평균 (1분) |
| `asiai_memory_used_bytes` | gauge | 사용 메모리 |
| `asiai_thermal_speed_limit_pct` | gauge | CPU 속도 제한 % |
| `asiai_engine_reachable{engine}` | gauge | 엔진 접근성 (0/1) |
| `asiai_engine_models_loaded{engine}` | gauge | 로드된 모델 수 |
| `asiai_engine_tcp_connections{engine}` | gauge | 확립된 TCP 연결 |
| `asiai_engine_requests_processing{engine}` | gauge | 처리 중 요청 |
| `asiai_engine_kv_cache_usage_ratio{engine}` | gauge | KV 캐시 사용 비율 (0-1) |
| `asiai_engine_tokens_predicted_total{engine}` | counter | 누적 예측 토큰 |
| `asiai_model_vram_bytes{engine,model}` | gauge | 모델별 VRAM |
| `asiai_bench_tok_per_sec{engine,model}` | gauge | 최근 벤치마크 tok/s |

## 참고 사항

- 대시보드는 기본적으로 `127.0.0.1`에 바인딩 (로컬호스트만)
- 네트워크에 노출하려면 `--host 0.0.0.0` 사용 (예: 원격 모니터링)
- 포트 `8899`는 추론 엔진 포트와의 충돌을 피하기 위해 선택됨
