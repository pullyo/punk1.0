<<<<<<< HEAD
# Token Saver

Codex가 긴 빌드·테스트 로그 전체를 문맥에 넣기 전에 필요한 부분만 읽도록 돕는 로컬 플러그인입니다. Python 3.10 이상과 표준 라이브러리만 사용하며 API 호출은 없습니다.

## 구성

- `token-saver/`: 배포 가능한 플러그인 원본. 짧은 스킬 지침과 로그 발췌 CLI 포함.
- `tests/`: 원문 보존, 출력 제한, 오류 우선순위, 한글·UTF-16 및 CLI 검증.
- `BENCHMARK.json`: 재현 가능한 합성 로그의 문자 수 비교.

## 사용

설치 후 새 Codex 작업에서 다음과 같이 요청합니다.

> $token-saver 토큰 사용을 줄이면서 테스트 실패 원인을 찾아줘.

CLI는 설치 전에도 사용할 수 있습니다. `python`은 실행 가능한 Python 3.10+ 경로로 바꿀 수 있습니다. 이 PC의 번들 런타임은 `C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`입니다.

```powershell
python .\token-saver\scripts\token_saver.py compact .\build.log --max-chars 6000
python .\token-saver\scripts\token_saver.py compact .\build.log --focus 'TS2345'
python .\token-saver\scripts\token_saver.py read .\build.log --start 120 --end 160
```

긴 명령 출력은 먼저 새 파일에 보관합니다. PowerShell 예시:

```powershell
$logPath = Join-Path $PWD ('build-' + [guid]::NewGuid().ToString('N') + '.log')
npm test *> $logPath
$testExit = $LASTEXITCODE
python .\token-saver\scripts\token_saver.py compact $logPath
Write-Output "Original test exit code: $testExit"
```

CLI 종료 코드 0은 발췌 성공, 2는 입력/옵션 오류입니다. 테스트 성공 여부는 원래 명령의 종료 코드로 판단해야 합니다. UTF-8과 BOM이 있는 UTF-16을 지원하며 다른 인코딩은 `--encoding cp949`처럼 지정합니다. 입력은 최대 32 MiB, 출력은 기본 6,000자입니다. 출력 한도는 문자 수이며 토큰 수가 아닙니다.

## 설치

현재 폴더는 개발 원본입니다. 개발 완료만으로 현재 Codex 작업에 자동 활성화되지는 않습니다. `dist/token-saver-0.1.0.zip`은 공유용이며, 직접 실행 검증과 실제 앱 설치 검증은 구분합니다.

Codex의 `plugin-creator` 스킬을 사용해 이 원본을 개인 플러그인 위치 `~/plugins/token-saver`에 복사하고 기본 개인 마켓플레이스 `~/.agents/plugins/marketplace.json`에 등록한 다음 설치할 수 있습니다. 기존 동명 플러그인이 있으면 덮어쓰기 전에 확인해야 합니다. 등록된 마켓플레이스 이름이 `personal`인 경우 설치 명령은 다음과 같습니다.

```text
codex plugin add token-saver@personal
```

설치 후 새 작업을 열어 `$token-saver`를 호출합니다.

## 절감 범위와 한계

이 플러그인은 스킬이 선택되고 로그를 발췌해서 읽을 때 입력 분량을 줄입니다. 모든 도구 출력을 자동 가로채거나, 이미 전달된 문맥을 삭제하거나, 계정 한도를 변경하지 않습니다. 모델의 내부 추론 토큰이나 청구량을 측정하지 않습니다.

오류 단어 검색과 우선순위는 휴리스틱입니다. 중복 제거·긴 줄 축약·줄 생략으로 정보가 빠질 수 있어 원문 경로, SHA-256, 줄 번호와 생략 수를 표시합니다. 중요한 판단 전에 필요한 범위를 다시 읽으세요. 작은 로그는 메타데이터 때문에 더 커질 수 있으므로 그대로 읽는 편이 낫습니다. 스킬 로딩, 명령문, 후속 조회 비용을 포함한 실제 세션 절감률은 별도 실측이 필요합니다.

파일을 수정하거나 전송하지 않으며 비밀값을 자동 마스킹하지 않습니다. 로그 자체에 포함된 값은 발췌에도 나타날 수 있습니다.

스킬의 본문과 보조 자료를 필요할 때 읽는 구조는 [OpenAI 공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills)를 참고했습니다.

## 검증 재현

```powershell
python -m unittest discover -s tests -v
python tests/benchmark.py
python scripts/package_plugin.py
```
=======
# Puncture-
A plugin that reduces Codex token consumption
>>>>>>> origin/main
