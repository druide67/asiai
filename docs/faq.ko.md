---
title: "자주 묻는 질문"
description: "asiai에 대한 자주 묻는 질문: 지원 엔진, Apple Silicon 요구 사항, Mac에서의 LLM 벤치마크, RAM 요구 사항 등."
type: faq
faq:
  - q: "asiai란 무엇입니까?"
    a: "asiai는 Apple Silicon Mac에서 LLM 추론 엔진을 벤치마크하고 모니터링하는 오픈소스 CLI 도구입니다. 7개 엔진(Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)을 지원하며 tok/s, TTFT, 전력 소비, VRAM 사용량을 측정합니다."
  - q: "Apple Silicon에서 가장 빠른 LLM 엔진은?"
    a: "M4 Pro 64GB에서 Qwen3-Coder-30B를 사용한 벤치마크에서 LM Studio(MLX 백엔드)가 102 tok/s를 달성하여 Ollama의 70 tok/s 대비 46% 빠릅니다. 다만 Ollama가 첫 번째 토큰까지의 지연 시간은 더 낮습니다."
  - q: "asiai는 Intel Mac에서 작동합니까?"
    a: "아닙니다. asiai는 Apple Silicon(M1, M2, M3, M4)이 필요합니다. Apple Silicon 칩에서만 사용 가능한 GPU 메트릭, IOReport 전력 모니터링, 하드웨어 감지용 macOS 전용 API를 사용합니다."
  - q: "로컬에서 LLM을 실행하려면 RAM이 얼마나 필요합니까?"
    a: "Q4 양자화된 7B 모델: 최소 8 GB. 13B: 16 GB. 30B: 32-64 GB. Qwen3.5-35B-A3B 같은 MoE 모델은 활성 파라미터가 약 7 GB에 불과하여 16 GB Mac에 이상적입니다."
  - q: "Mac에는 Ollama와 LM Studio 중 어느 것이 좋습니까?"
    a: "용도에 따라 다릅니다. LM Studio(MLX)는 처리량과 전력 효율이 우수합니다. Ollama(llama.cpp)는 첫 번째 토큰 지연이 낮고 대규모 컨텍스트 윈도우(32K 이상)를 더 잘 처리합니다. 자세한 비교는 asiai.dev/ollama-vs-lmstudio를 참고하세요."
  - q: "asiai에 sudo 또는 root 권한이 필요합니까?"
    a: "아닙니다. GPU 관측성(ioreg)과 전력 모니터링(IOReport)을 포함한 모든 기능이 sudo 없이 작동합니다. powermetrics와의 교차 검증용 선택적 --power 플래그만 sudo를 사용합니다."
  - q: "asiai는 어떻게 설치합니까?"
    a: "pip (pip install asiai) 또는 Homebrew (brew tap druide67/tap && brew install asiai)로 설치할 수 있습니다. Python 3.11 이상이 필요합니다."
  - q: "AI 에이전트가 asiai를 사용할 수 있습니까?"
    a: "예. asiai에는 11개 도구와 3개 리소스를 갖춘 MCP 서버가 포함되어 있습니다. pip install asiai[mcp]로 설치하고 MCP 클라이언트(Claude Code, Cursor 등)에서 asiai mcp로 설정하세요."
  - q: "전력 측정은 얼마나 정확합니까?"
    a: "IOReport 전력 읽기는 sudo powermetrics 대비 1.5% 미만의 차이로, LM Studio(MLX)와 Ollama(llama.cpp) 모두에서 20개 샘플로 검증되었습니다."
  - q: "여러 모델을 동시에 벤치마크할 수 있습니까?"
    a: "예. asiai bench --compare를 사용하여 교차 모델 벤치마크를 실행할 수 있습니다. model@engine 구문으로 정밀 제어가 가능하며, 최대 8개 비교 슬롯을 지원합니다."
  - q: "벤치마크 결과를 공유하려면?"
    a: "asiai bench --share를 실행하여 결과를 익명으로 커뮤니티 리더보드에 제출할 수 있습니다. --card를 추가하면 공유 가능한 1200x630 벤치마크 카드 이미지를 생성합니다."
  - q: "asiai는 어떤 메트릭을 측정합니까?"
    a: "7개 핵심 메트릭: tok/s(생성 속도), TTFT(첫 번째 토큰까지의 시간), power(GPU+CPU 와트), tok/s/W(에너지 효율), VRAM 사용량, 실행 간 안정성, 서멀 쓰로틀링 상태."
---

# 자주 묻는 질문

## 일반

**asiai란 무엇입니까?**

asiai는 Apple Silicon Mac에서 LLM 추론 엔진을 벤치마크하고 모니터링하는 오픈소스 CLI 도구입니다. 7개 엔진(Ollama, LM Studio, mlx-lm, llama.cpp, oMLX, vllm-mlx, Exo)을 지원하며 tok/s, TTFT, 전력 소비, VRAM 사용량을 의존성 없이 측정합니다.

**asiai는 Intel Mac이나 Linux에서 작동합니까?**

아닙니다. asiai는 Apple Silicon(M1, M2, M3, M4)이 필요합니다. Apple Silicon에서만 사용 가능한 macOS 전용 API(`sysctl`, `vm_stat`, `ioreg`, `IOReport`, `launchd`)를 사용합니다.

**asiai에 sudo 또는 root 권한이 필요합니까?**

아닙니다. GPU 관측성(`ioreg`)과 전력 모니터링(`IOReport`)을 포함한 모든 기능이 sudo 없이 작동합니다. `powermetrics`와의 교차 검증용 선택적 `--power` 플래그만 sudo를 사용합니다.

## 엔진 및 성능

**Apple Silicon에서 가장 빠른 LLM 엔진은?**

M4 Pro 64GB에서 Qwen3-Coder-30B(Q4_K_M)를 사용한 벤치마크에서 LM Studio(MLX 백엔드)가 **102 tok/s**를 달성하여 Ollama의 **70 tok/s** 대비 46% 빠릅니다. LM Studio는 전력 효율도 82% 우수합니다(8.23 vs 4.53 tok/s/W). [상세 비교](ollama-vs-lmstudio.md)를 참고하세요.

**Mac에는 Ollama와 LM Studio 중 어느 것이 좋습니까?**

용도에 따라 다릅니다:

- **LM Studio(MLX)**: 처리량에 최적 (코드 생성, 긴 응답). 더 빠르고 효율적이며 VRAM 사용량이 적음.
- **Ollama(llama.cpp)**: 지연 시간에 최적 (챗봇, 인터랙티브 사용). TTFT가 빠름. 대규모 컨텍스트 윈도우(32K 토큰 이상)에 우수.

**로컬에서 LLM을 실행하려면 RAM이 얼마나 필요합니까?**

| 모델 크기 | 양자화 | 필요 RAM |
|----------|--------|---------|
| 7B | Q4_K_M | 최소 8 GB |
| 13B | Q4_K_M | 최소 16 GB |
| 30B | Q4_K_M | 32-64 GB |
| 35B MoE (3B 활성) | Q4_K_M | 16 GB (활성 파라미터만 로드) |

## 벤치마크

**첫 벤치마크는 어떻게 실행합니까?**

3개 명령어:

```bash
pip install asiai     # 설치
asiai detect          # 엔진 감지
asiai bench           # 벤치마크 실행
```

**벤치마크는 얼마나 걸립니까?**

빠른 벤치마크(`asiai bench --quick`)는 약 2분입니다. 여러 프롬프트와 3회 실행을 포함한 전체 교차 엔진 비교는 10-15분 소요됩니다.

**전력 측정은 얼마나 정확합니까?**

IOReport 전력 읽기는 `sudo powermetrics` 대비 1.5% 미만의 차이로, LM Studio(MLX)와 Ollama(llama.cpp) 모두에서 20개 샘플로 검증되었습니다.

**다른 Mac 사용자와 결과를 비교할 수 있습니까?**

예. `asiai bench --share`를 실행하여 결과를 익명으로 [커뮤니티 리더보드](leaderboard.md)에 제출할 수 있습니다. `asiai compare`로 자신의 Mac 성능을 비교할 수 있습니다.

## AI 에이전트 통합

**AI 에이전트가 asiai를 사용할 수 있습니까?**

예. asiai에는 11개 도구와 3개 리소스를 갖춘 MCP 서버가 포함되어 있습니다. `pip install "asiai[mcp]"`로 설치하고 MCP 클라이언트(Claude Code, Cursor, Windsurf)에서 `asiai mcp`로 설정하세요. [에이전트 통합 가이드](agent.md)를 참고하세요.

**어떤 MCP 도구를 사용할 수 있습니까?**

11개 도구: `check_inference_health`, `get_inference_snapshot`, `list_models`, `detect_engines`, `run_benchmark`, `get_recommendations`, `diagnose`, `get_metrics_history`, `get_benchmark_history`, `refresh_engines`, `compare_engines`.

3개 리소스: `asiai://status`, `asiai://models`, `asiai://system`.
