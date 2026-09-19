# Contributing

작은 재현 코드, 입력과 기대값, 실제 증거를 함께 제출해 주세요. 비공개 저장소 원본·자격 증명·개인 경로는 제거하세요. 정상 코드를 CONFIRMED로 판단한 사례를 특히 중요하게 다룹니다.

Install only this project's parser with npm ci --ignore-scripts --no-audit --no-fund. Run Python unittest, npm test, npm run typecheck, npm run check:syntax and python -B tools/check.py as shown in README. Never execute arbitrary target scripts on the host.

New rules need a failing fixture, a guarded counterexample, unsupported cases and evidence-gate tests. LLM replay tests must not be reported as live LLM evaluations. A high confidence score is not proof. Changes are contributed under this project's MIT license.
