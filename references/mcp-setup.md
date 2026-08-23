# MCP 배선 · `.tavlet.json` · 배포

게이트 **G1(MCP 연결)** 이 막혔을 때, 그리고 이 스킬을 처음 설치할 때 읽는다.

tavlet은 4계층 테넌시(Organization → Workspace → Project → Board)를 가진 멀티테넌트 SaaS다. **org마다 PAT가 다르다.** 이 문서의 절차는 그 사실을 전제로 한다.

---

## 0. 불변 규칙 3개

1. **MCP 등록은 프로젝트(= org/보드) 단위로 분리한다.** org마다 PAT가 다르므로 user 스코프 단일 등록은 금지다 — 한 토큰으로 모든 org를 쓰려는 순간, 그 토큰이 커버하지 않는 보드에는 실패하고 커버하는 보드에는 **의도하지 않은 테넌트로 쓸 위험**이 생긴다.
2. **토큰 값을 git 추적 파일에 절대 쓰지 않는다.** 파일에 쓰기 전 `git check-ignore -v <파일>` 로 무시 대상임을 **확인하고**, 확인되지 않으면 쓰지 않는다.
3. **원격 엔드포인트를 쓴다.** 정규 경로는 `https://tavlet.io/api/mcp`(Streamable HTTP)다. 로컬에 설치하거나 클론할 것이 없다. 로컬 stdio 서버(`agent/mcp/board/server.ts`)는 tavlet 저장소 접근 권한이 있는 개발자의 개발용 경로이며, 이 스킬의 전제가 아니다.

---

## 1. 사전 준비

| 항목 | 확인 방법 |
|---|---|
| tavlet.io 계정 | https://tavlet.io 가입. 대상 org의 멤버여야 한다 |
| PAT 발급 | tavlet 콘솔 → API 토큰. 신규 접두사는 `tvl_`. 대상 보드에 **WRITE grant**가 포함되어야 한다 |
| 대상 boardId | 보드 피드 URL `/o/{org}/{ws}/{proj}/{boardId}` 의 **마지막 세그먼트** |

Node·클론·빌드는 필요 없다 — 서버는 tavlet.io 가 운영한다.

PAT 접두사 `tvl_`(신규) · `hhb_`(레거시, 검증 수용 전용). **두 접두사 모두 스크럽 대상 문자열이다** — 초안 본문·로그·설정 예시 어디에도 실제 값을 남기지 않는다.

---

## 2. 등록 방식

### A안 — `claude mcp add` (권장)

```bash
claude mcp add tavlet \
  --transport http \
  --scope local \
  --header "Authorization: Bearer $TAVLET_BOARD_TOKEN_TAVLET_IO" \
  https://tavlet.io/api/mcp
```

- `--scope local`(이 프로젝트에서 나만) 또는 `--scope project`(레포에 `.mcp.json` 생성 — 이 경우 B안의 gitignore·환경변수 규칙이 선행 조건이 된다).
- 토큰은 셸 환경변수로 넘긴다. 값을 명령줄에 직접 쓰면 **셸 히스토리에 남는다.**
- **org마다 변수명을 분리한다** — `TAVLET_BOARD_TOKEN_TAVLET_IO`, `TAVLET_BOARD_TOKEN_<다른ORG>`. 같은 변수명을 재사용하면 어느 org의 토큰이 실려 있는지 알 수 없게 되고, 그것이 테넌트 오등록의 출발점이다.
- 플래그 이름이 다르면 `claude mcp add --help` 로 현재 버전의 문법을 확인한다. **문법이 맞다고 단정하지 말고 §4 스모크 테스트로 판정한다.**
- 등록 확인: `claude mcp list`

### B안 — 프로젝트 `.mcp.json` (팀 공유)

```json
{
  "mcpServers": {
    "tavlet": {
      "type": "http",
      "url": "https://tavlet.io/api/mcp",
      "headers": {
        "Authorization": "Bearer ${TAVLET_BOARD_TOKEN_TAVLET_IO}"
      }
    }
  }
}
```

- **토큰 값을 파일에 지정하지 않는다.** 환경변수 참조만 둔다 — 그래야 이 파일을 git으로 공유할 수 있다.
- 환경변수 치환이 동작하지 않으면(= 스모크 테스트가 401) A안으로 전환한다.
- 값을 직접 지정해야 한다면 **먼저** gitignore 등재를 확인한다:
  ```bash
  printf '\n.mcp.json\n' >> .gitignore
  git check-ignore -v .mcp.json   # 매칭 줄이 나와야 토큰을 쓴다
  ```

### C안 — 로컬 stdio (tavlet 개발자 전용)

tavlet 저장소를 체크아웃해 개발 중이고 `http://localhost:18000` 을 대상으로 삼을 때만 쓴다. 절차는 tavlet 레포 `docs/api-reference.md` §7.2. 이 경우 `BOARD_DEFAULT_BOARD_ID` env 로 기본 보드를 두는 경로가 남아 있는데, **이 스킬은 그 경로를 쓰지 않는다** — 게이트 **G3**(테넌트 확정)은 매 실행마다 `board_list_boards()` 반환에 대상 boardId 가 실재함을 확인하도록 요구하고, 승인 미리보기의 `board_create_post` JSON에는 **언제나 명시 `boardId` 가 실린다**. 원격판(A·B안)에는 그 fallback 자체가 없고 `boardId` 가 필수 인자다.

### 어느 안을 고를까

| 상황 | 안 |
|---|---|
| 대부분 | **A** |
| 팀과 공유하는 레포이고 각자 자기 토큰을 쓴다 | **B** |
| tavlet 자체를 개발 중이고 로컬 서버를 본다 | **C** |
| org가 여러 개다 | 프로젝트마다 위 중 하나를 **따로** — 하나의 등록을 여러 org에 재사용하지 않는다 |

---

## 3. `.tavlet.json` — 이 스킬이 규약 소유자다

tavlet `CLAUDE.md:16-17`은 "등록 대상 보드는 `.tavlet.json`(gitignore, 기본 = 내부 작업 보드)이 정한다"고 문서화하지만 **코드 구현체가 없다.** `tavlet-tracker`가 스키마를 정의하고 소비한다.

```jsonc
{
  "baseUrl": "https://tavlet.io",        // 필수. localhost 가 아니면 G6 프로덕션 경고 발동
  "org": "tavlet-io",                    // 필수. URL 조립 + 테넌트 식별 (org SLUG)
  "workspace": "default",                // 필수. URL 조립 (workspace SLUG)
  "project": "default",                  // 필수. project SLUG — projectId 가 아니다
  "projectId": "<board_list_boards.projectId>", // 선택. 릴리스 도구용 DB id.
                                         //   없으면 실행 시 board_list_boards 로 해소하고 기록을 제안
  "boardId": "xnUwXGnBK4E2",             // 필수. 기본 등록 대상
  "boardVisibility": "INTERNAL",         // 필수. PUBLIC | INTERNAL | PRIVATE — G6 공개면 경고 판단의 정본
  "boardKind": "<board_list_boards().kind 를 그대로 옮겨 적는다>",
                                         // 선택. FEATURE | BUG | FEEDBACK 중 하나.
                                         //   ↑ 예시값을 복사하지 말 것. 보드의 실제 kind 는 DB에만 있고
                                         //   소스로 확인할 수 없다. board_list_boards() 반환값을 채운다.
                                         //   용도는 그 반환값과의 대조뿐이며, 공개 여부 판정에는 쓰지 않는다.
  "publicBoardId": "M6Nz6bWCr2Ow",       // 선택. 공개면에 올릴 때만 명시 지정
  "mcpServerName": "board"               // 선택. 기본 "board"
}
```

**토큰은 이 파일에 담지 않는다. 어떤 필드로도 담지 않는다.**

### `boardVisibility` 가 필수인 이유

어떤 `board_*` 도구도 보드의 공개 여부를 반환하지 않는다. `board_list_boards`가 주는 `kind`는 `FEATURE`·`BUG`·`FEEDBACK`(보드 종류)이며 공개 여부가 아니다. DB에는 `Board.visibility`(`PUBLIC`·`PRIVATE`·`INTERNAL`, 기본 `PUBLIC`)가 따로 있지만 에이전트 API DTO에 실리지 않는다. 자세한 근거는 `board-tool-contract.md` §가시성.

→ 따라서 **공개 여부는 운영자가 이 파일에 선언한다.** 값이 없으면 **`PUBLIC`으로 간주(안전 측 기본값)** 하고 사용자에게 확인한다.

### gitignore

tavlet 레포에서는 이미 gitignore 되어 있다(`tavlet/.gitignore:74`). **다른 레포에서는 생성 전에 등재를 먼저 처리한다:**

```bash
printf '\n.tavlet.json\n' >> .gitignore
git check-ignore -v .tavlet.json   # 매칭 줄이 나와야 생성한다
```

파일이 없으면: 사용자에게 대상 보드를 묻고 → `board_list_boards()` 로 실재 확인 → 위 스키마대로 **생성을 제안**한다(gitignore 확인 후). 사용자가 거절하면 이번 세션 한정으로 값을 들고 진행한다.

---

## 4. 스모크 테스트 — 수용 기준

등록 후 **세션을 재시작**하고 `board_list_boards()` 를 한 번 호출한다. 아래 3개가 전부 참이어야 통과다.

- (a) `board_list_boards` 도구가 세션에 **존재**한다
- (b) 반환이 `Error:` 또는 `[board]` 로 **시작하지 않는다** (그리고 `isError` 가 없다)
- (c) 반환 목록에 **대상 boardId가 실재**한다

세 조건을 모두 만족하면 G1 통과다. 하나라도 어긋나면 §5로 간다.

---

## 5. 진단 분기

| 증상 | 원인 | 조치 |
|---|---|---|
| `board_*` 도구가 세션에 아예 없다 | 등록이 안 됐거나 세션 재시작 전 | `claude mcp list` 로 등록 확인 → 세션 재시작. `.mcp.json` JSON 문법 오류도 흔한 원인이다 |
| 연결 자체가 401 | Authorization 헤더가 전달되지 않았거나 토큰이 무효 | B안의 `${VAR}` 치환이 동작하지 않는 경우가 대부분 — A안으로 전환. 401 `AGENT_TOKEN_REQUIRED` 는 헤더가 아예 없다는 뜻이다 |
| 도구 결과가 `INVALID_API_TOKEN` | PAT 가 무효(폐기·오타) | 콘솔에서 재발급 |
| 도구 결과가 403 `TOKEN_SCOPE_DENIED` | 그 대상이 토큰 스코프 밖 | 스코프에 대상 보드 grant 추가. 조회 도구는 READ, 쓰기 도구는 WRITE 를 요구한다 |
| 목록이 **빈 배열** | 이 토큰이 쓸 수 있는 보드가 하나도 없다 | 토큰 스코프에 WRITE grant를 추가한다. **쓰기 경로로 진행하지 않는다** |
| 목록에 대상 boardId가 **없다** | 그 토큰은 이 보드에 쓸 권한이 없다 (다른 org PAT일 가능성) | 목록에 있는 보드 중에서 고르거나, 올바른 org PAT로 **MCP를 재등록**한다. **여기서 멈춘다** — 이 상태로 진행하면 테넌트 오등록이다 |
| 연결은 되는데 대상이 localhost | C안(로컬 stdio)으로 등록돼 있다 | 의도한 것이면 그대로. 프로덕션이 목적이면 A안으로 재등록한다 |
| `GET`/`DELETE` 가 405 | 원격 엔드포인트는 stateless — 세션 기반 표면을 지원하지 않는다 | 정상 동작이다. 도구 호출은 전부 `POST` 로 이뤄진다 |

**어떤 경우에도 REST를 직접 호출하거나 우회 스크립트를 만들지 않는다.** 그것은 승인 게이트를 우회하는 두 번째 쓰기 경로다.

---

## 6. 스킬 배포 (심링크)

정본은 https://github.com/greeun/tavlet-tracker 다. `~/.claude/` 에는 **복사본이 아니라 심링크**를 둔다 — 복사본은 정본과 조용히 갈라진다.

```bash
git clone https://github.com/greeun/tavlet-tracker.git
cd tavlet-tracker

ln -s "$(pwd)" ~/.claude/skills/tavlet-tracker
ln -s "$(pwd)/commands/tvl.md" ~/.claude/commands/tvl.md
```

확인:

```bash
ls -l ~/.claude/skills/tavlet-tracker ~/.claude/commands/tvl.md
```

두 심링크가 클론 경로를 가리키면 배포 완료다. 이후 `/tvl` 슬래시 커맨드와 스킬 자동 활성화가 모두 동작한다. 갱신은 `git pull` 이면 된다 — 심링크라 별도 재배포가 없다.
