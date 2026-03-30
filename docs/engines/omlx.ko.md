---
description: "Apple Silicon에서의 oMLX 벤치마크: SSD KV 캐싱, 연속 배치 처리, 포트 8000, 성능 비교."
---

# oMLX

oMLX는 네이티브 macOS 추론 서버로, 페이지드 SSD KV 캐싱을 사용하여 메모리만으로는 처리할 수 없는 대형 컨텍스트 윈도우를 처리하고, 포트 8000에서 연속 배치 처리로 동시 요청을 처리합니다. Apple Silicon에서 OpenAI 및 Anthropic 호환 API를 모두 지원합니다.

[oMLX](https://omlx.ai/)는 페이지드 SSD KV 캐싱과 연속 배치 처리를 갖춘 네이티브 macOS LLM 추론 서버입니다. 메뉴바에서 관리하며 Apple Silicon용 MLX로 구축되었습니다.

## 설정

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

또는 [GitHub releases](https://github.com/jundot/omlx/releases)에서 `.dmg`를 다운로드하세요.

## 세부 정보

| 속성 | 값 |
|------|-----|
| 기본 포트 | 8000 |
| API 유형 | OpenAI 호환 + Anthropic 호환 |
| VRAM 보고 | 아니요 |
| 모델 형식 | MLX (safetensors) |
| 감지 방법 | `/admin/info` JSON 엔드포인트 또는 `/admin` HTML 페이지 |
| 요구사항 | macOS 15+, Apple Silicon (M1+), 최소 16 GB RAM |

## 참고

- oMLX는 vllm-mlx와 포트 8000을 공유합니다. asiai는 `/admin/info` 프로빙을 사용하여 구별합니다.
- SSD KV 캐싱으로 메모리 압력을 줄이면서 더 큰 컨텍스트 윈도우를 지원합니다.
- 연속 배치 처리로 동시 요청 시 처리량이 향상됩니다.
- 텍스트 LLM, 비전-언어 모델, OCR 모델, 임베딩, 리랭커를 지원합니다.
- `/admin`의 관리 대시보드에서 실시간 서버 메트릭을 확인할 수 있습니다.
- `.dmg`로 설치 시 앱 내 자동 업데이트를 지원합니다.

## 참고 항목

`asiai bench --engines omlx`로 엔진 비교 --- [방법 알아보기](../benchmark-llm-mac.md)
