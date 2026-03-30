---
description: "asiai 설정 방법: Mac에서 LLM 벤치마크용 엔진 URL, 포트, 영구 설정을 관리합니다."
---

# asiai config

영구적인 엔진 설정을 관리합니다. `asiai detect`로 발견된 엔진은 다음 감지를 빠르게 하기 위해 `~/.config/asiai/engines.json`에 자동 저장됩니다.

## 사용법

```bash
asiai config show              # 알려진 엔진 표시
asiai config add <engine> <url> [--label NAME]  # 엔진 수동 추가
asiai config remove <url>      # 엔진 제거
asiai config reset             # 모든 설정 초기화
```

## 서브커맨드

### show

URL, 버전, 소스(auto/manual), 마지막 확인 타임스탬프와 함께 모든 알려진 엔진을 표시합니다.

```
$ asiai config show
Known engines (3):
  ollama v0.17.7 at http://localhost:11434  (auto)  last seen 2m ago
  lmstudio v0.4.6 at http://localhost:1234  (auto)  last seen 2m ago
  omlx v0.9.2 at http://localhost:8800 [mac-mini]  (manual)  last seen 5m ago
```

### add

비표준 포트의 엔진을 수동 등록합니다. 수동 엔진은 자동 정리되지 않습니다.

```bash
asiai config add omlx http://localhost:8800 --label mac-mini
asiai config add ollama http://192.168.0.16:11434 --label mini
```

### remove

URL로 엔진 항목을 제거합니다.

```bash
asiai config remove http://localhost:8800
```

### reset

전체 설정 파일을 삭제합니다. 다음 `asiai detect`에서 엔진을 처음부터 다시 감지합니다.

## 작동 방식

설정 파일은 감지 시 발견된 엔진을 저장합니다:

- **Auto 항목** (`source: auto`): `asiai detect`가 새 엔진을 찾으면 자동 생성. 7일 비활성 후 정리.
- **Manual 항목** (`source: manual`): `asiai config add`로 생성. 자동 정리 안 됨.

`asiai detect`의 3계층 감지 캐스케이드는 이 설정을 레이어 1(가장 빠름)로 사용하고, 이어서 포트 스캔(레이어 2)과 프로세스 감지(레이어 3)를 수행합니다. 자세한 내용은 [detect](detect.md)를 참고하세요.

## 설정 파일 위치

```
~/.config/asiai/engines.json
```
