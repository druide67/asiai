---
description: "asiai 터미널 UI: 터미널에서 인터랙티브 대시보드로 LLM 추론 엔진을 실시간 모니터링합니다."
---

# asiai tui

자동 갱신이 있는 인터랙티브 터미널 대시보드.

## 사용법

```bash
asiai tui
```

## 요구 사항

`tui` 엑스트라가 필요합니다:

```bash
pip install asiai[tui]
```

터미널 UI를 위해 [Textual](https://textual.textualize.io/)이 설치됩니다.

## 기능

- 실시간 시스템 메트릭 (CPU, 메모리, 서멀)
- 엔진 상태 및 로드된 모델
- 설정 가능한 간격의 자동 갱신
