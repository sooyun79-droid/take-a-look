# LLM 설정

## 실제 LLM을 켜려면

실제 OpenAI Responses 어댑터를 구현했습니다. 구조화된 JSON 응답을 요구하고 로컬에서 다시 검증합니다. 기본은 `mock`입니다. **이번 SearchLens benchmark는 API 키가 없어 실제 LLM을 사용하지 않았습니다.**

환경 설정:

| 이름 | 의미 |
|---|---|
| `TAKEALOOK_LLM_PROVIDER` | `mock` 또는 `openai` |
| `OPENAI_API_KEY` | 프로세스 환경에서만 읽는 API 키 |
| `TAKEALOOK_OPENAI_MODEL` | 계정에서 사용할 수 있는 모델 ID; 자동 기본 모델 선택 없음 |
| `TAKEALOOK_INVESTIGATOR_PROVIDER` / `TAKEALOOK_CHALLENGER_PROVIDER` | 역할별 공급자 선택 |
| `TAKEALOOK_INVESTIGATOR_MODEL` / `TAKEALOOK_CHALLENGER_MODEL` | 역할별 모델 선택 |

키는 채팅·코드·설정 파일·명령행에 적지 마세요. PowerShell에서는 프로세스 환경에 입력을 숨겨 넣을 수 있습니다.

```powershell
$temporaryKey = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $temporaryKey).Password
Remove-Variable temporaryKey
$env:TAKEALOOK_LLM_PROVIDER = 'openai'
$env:TAKEALOOK_OPENAI_MODEL = '<계정에서 사용할 모델 ID>'
python -B -m take_a_look web --open
```

OpenAI를 켜면 **선별·마스킹한 소스 코드가 OpenAI API로 전송**됩니다. 해당 코드에 전송 권한이 있을 때만 켜세요. `.env` 등 비밀 파일은 제외하지만 알려지지 않은 비밀 표현까지 완벽하게 감지하는 DLP는 아닙니다.

- API 키 또는 모델 설정이 없으면 mock으로 전환하고 원인을 기록합니다.
- 오류·거절·잘못된 schema·호출 예산 초과도 mock으로 전환합니다. 실제 완료 호출 수, fallback 수, context 잘림 여부를 보고서에 표시합니다.
- Investigator/Challenger는 별도 요청이며 대화 이력·Investigator의 confidence/이유를 Challenger에게 전달하지 않습니다.
- Challenger의 guard, caller, schema, test, fallback, dead-code, non-code, runtime 점검을 구조화합니다.
- API endpoint는 OpenAI로 고정하며 redirect/proxy를 사용하지 않습니다. 자동 retry 없음, 요청 timeout 30초, 역할별 최대 25회입니다.
- 저장 옵션은 `store: false`, 원시 오류 응답/Authorization/key는 로그에 남기지 않습니다.
- 저장소의 ‘Ignore previous instructions’ 같은 문장은 명시적인 untrusted data입니다. 모델에는 명령 실행 도구가 없고, 출력 schema의 임의 명령 필드는 거부합니다.
- confidence, 동의, 다수결 또는 Challenger의 권고만으로 확정·반증하지 않습니다.

공급자 교체 지점은 `Provider.complete(RoleRequest)`입니다. `FunctionAdapter`로 다른 공급자를 추가할 수 있습니다. 이번 내장 네트워크 어댑터는 OpenAI 하나이며 Claude 내장 연결은 아직 없습니다. [OpenAI 공식 구조화 출력 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 기준으로 요청 형식을 구현했습니다.

