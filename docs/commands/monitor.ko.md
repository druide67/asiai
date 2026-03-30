---
description: Apple Silicon의 GPU 사용률, 서멀 상태, 메모리 프레셔를 지속적으로 모니터링합니다. sudo 불필요.
---

# asiai monitor

시스템과 추론 메트릭 스냅샷. SQLite에 저장됩니다.

## 사용법

```bash
asiai monitor [options]
```

## 옵션

| 옵션 | 설명 |
|------|------|
| `-w, --watch SEC` | SEC초마다 갱신 |
| `-q, --quiet` | 출력 없이 수집 및 저장 (데몬용) |
| `-H, --history PERIOD` | 이력 표시 (예: `24h`, `1h`) |
| `-a, --analyze HOURS` | 트렌드를 포함한 종합 분석 |
| `-c, --compare TS TS` | 두 타임스탬프 비교 |
| `--alert-webhook URL` | 상태 전환 시 웹훅 URL로 알림 POST |

## 출력

```
System
  Uptime:    3d 12h
  CPU Load:  2.45 / 3.12 / 2.89  (1m / 5m / 15m)
  Memory:    45.2 GB / 64.0 GB  71%
  Pressure:  normal
  Thermal:   nominal  (100%)

GPU
  Utilization: 45%  (renderer 44%, tiler 45%)
  Memory:      24.2 GB in use / 48.0 GB allocated

Power
  GPU: 12.6W  CPU: 4.4W  ANE: 0.0W  DRAM: 5.2W
  Total: 22.2W  (IOReport, no sudo)

Inference  ollama 0.17.4
  Models loaded: 1  VRAM total: 26.0 GB

  Model                                        VRAM   Format  Quant
  ──────────────────────────────────────── ────────── ──────── ──────
  qwen3.5:35b-a3b                            26.0 GB     gguf Q4_K_M
```

전력 모니터링은 Apple의 IOReport Energy Model을 사용하여 GPU, CPU, ANE, DRAM 전력 소비를 읽습니다 — sudo 불필요. 검증 세부 사항은 [방법론](../methodology.md#전력-측정)을 참고하세요.

## 알림 웹훅

`--alert-webhook URL`이 제공되면, asiai는 **상태 전환**이 감지될 때마다 웹훅 URL로 JSON 알림을 POST합니다:

| 알림 유형 | 트리거 | 심각도 |
|----------|--------|--------|
| `mem_pressure_warn` | 메모리 프레셔: normal → warn | warning |
| `mem_pressure_critical` | 메모리 프레셔: normal/warn → critical | critical |
| `thermal_degraded` | 서멀 레벨: nominal → fair/serious/critical | warning/critical |
| `engine_down` | 엔진이 접근 가능했으나 접근 불가로 변경 | critical |

알림은 스팸 방지를 위해 유형별로 **5분 쿨다운**이 있습니다. 각 알림은 이력용으로 SQLite에 저장됩니다.

### 웹훅 페이로드

```json
{
    "alert": "mem_pressure_warn",
    "severity": "warning",
    "ts": 1741350000,
    "host": "macmini.local",
    "message": "Memory pressure changed: normal → warn",
    "details": {
        "mem_pressure": "warn",
        "mem_used": 54000000000,
        "mem_total": 68719476736
    },
    "source": "asiai/0.7.0"
}
```

### 데몬과 함께 사용

```bash
asiai daemon start monitor --alert-webhook https://hooks.slack.com/services/...
```

## 데이터 저장

모든 스냅샷은 SQLite(`~/.local/share/asiai/metrics.db`)에 저장되며, 90일 자동 보존 기간이 있습니다.
