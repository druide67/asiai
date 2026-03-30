---
description: "Mac에서 asiai를 백그라운드 데몬으로 실행: 부팅 시 자동 시작 모니터링, 웹 대시보드, Prometheus 메트릭."
---

# asiai daemon

macOS launchd LaunchAgent을 통한 백그라운드 서비스를 관리합니다.

## 서비스

| 서비스 | 설명 | 모델 |
|--------|------|------|
| `monitor` | 정기적으로 시스템 + 추론 메트릭 수집 | 주기적 (`StartInterval`) |
| `web` | 웹 대시보드를 영구 서비스로 실행 | 상주 (`KeepAlive`) |

## 사용법

```bash
# 모니터링 데몬 (기본)
asiai daemon start                     # 모니터링 시작 (60초마다)
asiai daemon start --interval 30       # 커스텀 간격
asiai daemon start --alert-webhook URL # 웹훅 알림 활성화

# 웹 대시보드 서비스
asiai daemon start web                 # 127.0.0.1:8899에서 웹 시작
asiai daemon start web --port 9000     # 커스텀 포트
asiai daemon start web --host 0.0.0.0  # 네트워크에 공개 (인증 없음!)

# 상태 (모든 서비스 표시)
asiai daemon status

# 중지
asiai daemon stop                      # monitor 중지
asiai daemon stop web                  # web 중지
asiai daemon stop --all                # 모든 서비스 중지

# 로그
asiai daemon logs                      # monitor 로그
asiai daemon logs web                  # web 로그
asiai daemon logs web -n 100           # 마지막 100줄
```

## 작동 방식

각 서비스는 `~/Library/LaunchAgents/`에 별도의 launchd LaunchAgent plist를 설치합니다:

- **Monitor**: 설정된 간격(기본: 60초)으로 `asiai monitor --quiet`를 실행. 데이터는 SQLite에 저장. `--alert-webhook`가 제공되면 상태 전환(메모리 프레셔, 서멀, 엔진 다운) 시 알림을 POST.
- **Web**: `asiai web --no-open`을 영구 프로세스로 실행. 크래시 시 자동 재시작 (`KeepAlive: true`, `ThrottleInterval: 10s`).

두 서비스 모두 로그인 시 자동 시작 (`RunAtLoad: true`).

## 보안

- 서비스는 **사용자 수준**에서 실행 (root 불필요)
- 웹 대시보드는 기본적으로 `127.0.0.1`에 바인딩 (로컬호스트만)
- `--host 0.0.0.0` 사용 시 경고 표시 — 인증이 설정되지 않음
- 로그는 `~/.local/share/asiai/`에 저장
