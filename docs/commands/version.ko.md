---
description: "asiai 버전, Python 환경, 에이전트 등록 상태를 하나의 명령으로 확인합니다."
---

# asiai version

버전과 시스템 정보를 표시합니다.

## 사용법

```bash
asiai version
asiai --version
```

## 출력

`version` 서브커맨드는 확장된 시스템 컨텍스트를 표시합니다:

```
asiai 1.0.1
  Apple M4 Pro, 64 GB RAM
  Engines: ollama, lmstudio
  Daemon: monitor, web
```

`--version` 플래그는 버전 문자열만 표시합니다:

```
asiai 1.0.1
```

## 용도

- 이슈와 버그 리포트에서의 빠른 시스템 확인
- 에이전트 컨텍스트 수집 (칩, RAM, 사용 가능한 엔진)
- 스크립팅용: `VERSION=$(asiai version | head -1)`
