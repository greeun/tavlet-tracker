# board_* 도구 정본 계약 (이 스킬이 쓰는 16종)

`tavlet-tracker`의 Planner · Generator · Evaluator · 오케스트레이터가 **모두** 이 파일을 읽는다. 도구 계약의 유일한 정본이다 — 다른 파일에 복사하지 않는다.

모든 값은 tavlet 체크아웃의 실제 소스에서 확인된 것이다. 근거 경로는 tavlet 레포 루트 기준.

- 도구 등록: `src/lib/mcp/board-tools.ts` · 엔드포인트 `src/app/api/mcp/route.ts` — 원격 Streamable HTTP 한 경로뿐이다(로컬 stdio 서버는 tavlet `f91ce574` 에서 삭제됐다)
- 서버가 노출하는 도구 전체의 이름·설명·입력 스키마: `tests/01-unit/__snapshots__/mcp-tools-list.json`
- 검증 스키마: `src/lib/validation/posts.ts` · `post-tasks.ts` · `releases.ts` · `primitives.ts`
- 보드 목록 DTO: `src/lib/services/agent-boards.ts`

> 서버는 도구 **33종**을 노출한다(tavlet `f2ac4eac`, 2026-11-24). 이 스킬은 그중 아래 **16종**만 쓴다 — 개인 task·공유 작업·로드맵·서베이·글 수정/삭제·내 작업함 도구는 이 스킬의 라이프사이클 밖이므로 호출하지 않는다. 숫자가 다시 바뀌면 **스냅샷 파일을 따른다.**

---

## 0. 성공/실패 판정 — 가장 흔한 함정

서버는 **오류를 예외로 전파하지 않는다.** 도구 결과 안에 담아 되돌린다:

```ts
// board-tools.ts — REST 와 같은 오류 봉투(5xx 는 원인을 숨긴 "서버 오류")
{ content: [{ type: "text", text: '{"ok":false,"error":"…","code":"…"}' }], isError: true }
```

**따라서 도구가 텍스트를 되돌렸다는 사실만으로 성공으로 판단하면 안 된다.**

**판정 규칙:**
- 반환에 `isError: true` 가 있으면 → **실패** (가장 확실한 신호)
- 파싱한 JSON이 `{"ok": false, …}` 이면 → **실패**
- 그 외에는 JSON 문자열이며 성공

**실패 시:** 반환 원문을 **그대로** 표면화하고 후속 쓰기를 **취소**한다. 이미 실행된 쓰기와 취소된 쓰기를 분리해 보고한다.

**전역 실패 모드:**
| 증상 | 원인 |
|---|---|
| HTTP 401 `{"success":false,"error":{"code":40101,…}}` | Authorization 헤더가 없다 |
| HTTP 401 `AGENT_TOKEN_REQUIRED` | 인증은 됐지만 PAT 가 아니다(쿠키 세션) — MCP는 에이전트 토큰 전용 표면이다 |
| HTTP 401 `INVALID_API_TOKEN` | PAT 가 무효(폐기·오타) |
| `{"ok":false,…,"code":"TOKEN_SCOPE_DENIED"}` (403) | 대상이 토큰 스코프 밖. 조회 도구는 READ, 쓰기 도구는 WRITE grant 를 요구한다(`board_list_boards` 만 예외로 WRITE) |

---

## 1. 인증 · 환경변수

env 는 없다. PAT 를 `Authorization: Bearer` 헤더로 넘긴다. 대상 테넌트는 **토큰 스코프만이** 정하며, 서버가 기본 보드를 고르는 경로는 존재하지 않는다 — `board_create_post` 의 `boardId` 는 필수 인자다.

PAT 접두사: 신규 발급은 `tvl_`, 레거시 `hhb_`는 **검증 수용 전용**(신규 발급 없음). 두 접두사 모두 **스크럽 대상**이다.

---

## 2. 테넌시 · URL 규약

`board_list_boards` 반환 형태 (근거: `agent-boards.ts:7-17,45-54`):

```jsonc
{ "boards": [ {
    "boardId": "<boardId>",
    "projectId": "<DB id>",              // ← 릴리스 도구의 projectId 인자는 여기서 해소한다
    "kind": "FEATURE",                   // FEATURE | BUG | FEEDBACK — 공개 여부가 아니다
    "name": "<보드명>",
    "org":       { "slug": "<org-slug>",       "name": "..." },
    "workspace": { "slug": "<workspace-slug>", "name": "..." },
    "project":   { "slug": "<project-slug>",   "name": "..." },
    "url": "/o/{orgSlug}/{wsSlug}/{projSlug}/{boardId}"
} ] }
```

- 이 목록은 **현재 토큰의 WRITE grant가 커버하는 보드만** 담는다 (`agent-boards.ts:37-44`). **목록에 없는 boardId는 그 토큰으로 쓸 수 없다.** 테넌트 확인의 정본 수단이다.
- 보드 피드 URL: `/o/{orgSlug}/{wsSlug}/{projSlug}/{boardId}` — 마지막 세그먼트가 **boardId**
- post URL: `/o/{orgSlug}/{wsSlug}/{projSlug}/{boardId}/post/{postId}` — 마지막 세그먼트가 **postId**
- 커밋 트레일러: 이 스킬은 특정 트레일러 형식을 **요구하지 않는다.** 구 `[tv:<taskId>]` 규약은 tavlet 레포의 S0~S4 파이프라인과 공존하기 위한 것이었고, 그 파이프라인은 삭제됐다(tavlet `ff3fa1f`). 대상 레포에 자체 규약이 있으면 그것을 따른다.

### 대상 테넌트 — 하드코딩하지 않는다

이 스킬은 tavlet.io 의 **모든 org**에서 동작한다. 특정 org의 boardId·slug 를 이 파일에 적어 두지 않는다 — 그 값은 실행 환경마다 다르고, 적어 두면 다른 테넌트에서 조용히 틀린 보드를 가리키게 된다.

| 무엇 | 어디서 온다 |
|---|---|
| `baseUrl` · `org` · `workspace` · `project` · `boardId` · `boardVisibility` | 대상 레포의 `.tavlet.json` (스키마: `mcp-setup.md` §3) |
| 그 boardId 가 실재하는지 | 매 실행 `board_list_boards()` 반환과 대조 (게이트 **G3**) |
| 공개면 여부 | `.tavlet.json` 의 `boardVisibility` 선언 — 어떤 도구도 반환하지 않는다(아래 §가시성) |

`.tavlet.json` 이 없으면 사용자에게 묻고, `board_list_boards()` 로 실재를 확인한 뒤 생성을 제안한다. **추측한 boardId 로 쓰기를 진행하지 않는다.**

### §가시성 — 어떤 도구도 공개 여부를 반환하지 않는다

DB 상 보드는 `kind`(`BoardKind` = `FEATURE`·`BUG`·`FEEDBACK`)와 `visibility`(`Visibility` = `PUBLIC`·`PRIVATE`·`INTERNAL`, 기본 `PUBLIC`)를 **따로** 가진다 (근거: `prisma/schema.prisma:282-283`, `138-142`; `src/lib/validation/primitives.ts:23`). 그런데 `AgentBoardDTO`는 `kind`만 싣고 **`visibility`는 싣지 않는다** (`agent-boards.ts:7-17`).

**결론 — 반드시 지킬 것:**
- `board_list_boards`의 `kind` 값을 공개 여부 판정에 쓰지 않는다. `kind === "PUBLIC"` 은 **절대 참이 되지 않는 조건**이다.
- 공개 여부의 정본은 `.tavlet.json`의 **`boardVisibility`** (`PUBLIC` | `INTERNAL` | `PRIVATE`) 이며, 이는 운영자가 선언하는 값이다.
- 값이 없거나 모호하면 **`PUBLIC`으로 간주(안전 측 기본값)** 하고 사용자에게 확인한다. DB 기본값도 `PUBLIC`이다.

---

## 3. 도구 16종 계약표

**R = 읽기(9종, 게이트 없음) · W = 쓰기(7종, 미리보기 + 명시 승인 필수).** 스테이지 코드는 오케스트레이터 워크플로 단계다.

| # | 도구 | R/W | 스테이지 | 인자 계약 | 실패 모드 | 사후 read-back 수단 |
|---|---|---|---|---|---|---|
| 1 | `board_list_boards` | R | **SA 테넌트 해소** (G3) | 인자 없음 (`{}`) | 인증 실패는 §0 전역 실패 모드. **빈 목록 = 이 토큰이 쓸 수 있는 보드 없음 → 중단** | — |
| 2 | `board_list_posts` | R | **SB 중복 정찰** (G4, 필수 선행) | `{ boardId, status?, q?, limit?, offset? }` — `boardId` 필수. `status` 는 post status enum(§5). 반환 `{ posts, total, nextOffset }` — 최신순, `limit` 기본 50·최대 200 | `boardId` 누락·enum 밖 `status`·`limit` 201 이상 → 스키마 오류. **`nextOffset` 이 null 이 아니면 아직 안 본 글이 있다** — `offset` 으로 이어 읽거나 `q` 로 좁힌다. 결과 0건이 "중복 없음"의 근거가 되려면 **서로 다른 `q` 2회 이상** 필요 | — |
| 3 | `board_get_post` | R | **SB 중복 정찰 / SG 현황 조회** | `{ postId }` | 404(없음)·403(스코프 밖) → 원문 표면화 후 중단 | — |
| 4 | `board_get_taxonomy` | R | **SC 분류 어휘 확인** | `{ boardId }` | 반환의 **실제 id만** 사용. 존재하지 않는 카테고리 id를 `board_create_post`에 넘기면 서비스가 거절 | — |
| 5 | `board_list_statuses` | R | **SD 상태 어휘 확인** (`board_set_status` 선행) | `{ boardId }` | `board_set_status`의 `columnId` 후보는 **여기서만** 얻는다. 조회 없이 `columnId`를 지어내지 않는다 | — |
| 6 | `board_list_tasks` | R | **SF/SG task 현황** | `{ postId }` | post가 없거나 스코프 밖이면 원문 표면화 후 중단 | — |
| 7 | `board_list_release_candidates` | R | **SK 릴리스 초안 후보** | `{ projectId }` ← `board_list_boards`의 `projectId`. **project slug 금지** | 프로젝트 내 DONE·릴리스 미할당 post 목록 반환. slug를 넘기면 결과 없음/오류 | — |
| 8 | **`board_create_post`** | **W** | **SE post 등록** | `{ boardId, title, body, categoryIds?, tagNames? }`. **`boardId` 필수** — 서버가 기본 보드를 고르는 경로는 없다. **`categoryIds`는 id 배열, `tagNames`는 이름 배열 — 비대칭** | `boardId` 누락 → 스키마 오류. 길이 초과 → 검증 오류 | **가능** — `board_get_post({postId})` 로 `title`·`body`·`categoryIds`·`tags` 대조 |
| 9 | **`board_create_tasks`** | **W** | **SF task 분해** | `{ postId, items: [{ title, detail?, assigneeId?, dueAt? }] }` (일괄). `items` **1–50개**. 이 스킬은 `title`·`detail` 만 쓴다 | 빈 `items` 등록 금지(빈 등록은 절차상 중단). 51개 이상 → 검증 오류 | **가능** — `board_list_tasks({postId})` 로 등록된 항목 대조 |
| 10 | **`board_update_task_status`** | **W** | **SG 진행 갱신** | `{ postId, taskId, status }`, status ∈ **`TODO`·`DOING`·`DONE`·`DROPPED`** | **post 상태 enum과 다른 집합이다 — 혼동 금지.** `taskId` 가 `postId` 글의 작업이 아니면 404 `POST_TASK_NOT_FOUND`. 세션에서 다루지 않은 task는 전이하지 않는다 | **가능** — `board_list_tasks({postId})` 로 해당 task 의 status 대조 |
| 11 | **`board_add_comment`** | **W** | **SH 세션 다이제스트** | `{ postId, body, internal?, parentId? }` — body **1–5000자**. `internal: true` = 팀 전용 댓글, 생략 = **공개 댓글**. `parentId` = 답글(1단계) | `internal: true` 는 DEVELOPER↑만 — 아니면 403 `COMMENT_INTERNAL_STAFF_ONLY`. 병합된 글 → 400 `POST_MERGED`. **공개 범위 규칙은 §3-2.** 스크럽(G7)은 `internal` 과 무관하게 필수 | **가능** — `board_list_comments({postId})` 로 본문·`internal` 대조 |
| 12 | **`board_set_status`** | **W** | **SI 상태 전이** | `{ postId, status? , columnId? }`, status ∈ **`OPEN`·`UNDER_REVIEW`·`PLANNED`·`IN_PROGRESS`·`DONE`·`DECLINED`** | **둘 다 없음 → throw `status 또는 columnId 중 하나는 필수입니다.` 둘 다 지정 → throw `status·columnId 는 동시에 지정할 수 없습니다.`** (근거: `board-tools.ts` 의 `board_set_status` 핸들러) | **가능** — `board_get_post({postId})` 의 `status`(=`boardStatus.kind`) · `boardStatus.id`(=`columnId`) 대조 (근거: `posts.ts:335,349`) |
| 13 | **`board_create_suggestion`** | **W** | **SJ 분류·중복 제안** | `{ postId, categoryIds?, tagIds?, kindNote?, priority?, rationale }`. `rationale` **필수**. `priority` ∈ `HIGH`·`MEDIUM`·`LOW`. **`duplicates` 인자는 서버 스키마에 없다** — 넘겨도 서비스에 전달되지 않는다. 중복 후보는 `rationale` 본문에 postId 로 적는다 | **여기서는 `tagIds`(id) — `board_create_post`의 `tagNames`(이름)와 반대다.** `rationale` 누락 → 스키마 오류. **`categoryIds`·`tagIds` 중 최소 하나가 있어야 한다** — 둘 다 비우면 `rationale` 이 있어도 `{"ok":false,"error":"올바르지 않은 제안입니다.","code":"VALIDATION_FAILED"}` 로 거절된다(2026-09-04 실측). 분류할 대상이 없는 제안은 성립하지 않기 때문이다. 병합은 항상 사람 승인 | **가능** — `board_get_suggestion({postId})` 로 최신 제안 1건(상태·자동 적용 여부) 대조 |
| 14 | **`board_create_release_draft`** | **W** | **SK 릴리스 초안** | `{ projectId, version, name?, body, entries }` (서버는 `platforms?`·`milestoneIds?` 도 받지만 이 스킬은 쓰지 않는다). `entries` 항목 = `{ title, body, type, postIds }`, `postIds` **1개 이상**. `type` ∈ `NEW`·`IMPROVED`·`FIXED`·`BETA` | **version 중복 → 409.** 발행되지 않는 **초안**임을 미리보기에 명시 | **초안 자체 없음** — 반환 id·version 그대로 보고. 간접 확인 2종만: `board_get_post({postId}).affectedRelease` 대조 · `board_list_release_candidates` 에서 해당 post 소거 |
| 15 | `board_list_comments` | R | **SH 댓글 중복 확인 / read-back** | `{ postId }` — 반환 `{ comments }`, 작성순, 답글은 `replies` 로 1단계 중첩 | 내부 댓글은 DEVELOPER↑에게만 보인다. 숨김 글은 스태프가 아니면 404 | — |
| 16 | `board_get_suggestion` | R | **SJ read-back** | `{ postId }` — 반환 `{ suggestion }`, 없으면 `{"suggestion":null}` | 최신 1건만 준다. 승인·기각은 사람만 한다 | —

**쓰기 7종 = 8·9·10·11·12·13·14.** `board_create_suggestion`은 REST `POST /api/agent/posts/{postId}/suggestions`이며 보드에 상태를 남기므로 **게이트 대상이다.**
**읽기 9종 = 1–7·15·16.** Evaluator는 읽기 9종만 호출할 수 있다.

### §3-1 사후 read-back — 쓰기 7종 중 6종이 검증된다

실행(12단계) 후의 read-back은 **읽기 9종으로 할 수 있는 것까지만** 가능하다. 도구 목록에 없는 조회는 존재하지 않는다.

| 쓰기 도구 | read-back | 무엇을 대조하나 | 근거 |
|---|---|---|---|
| `board_create_post` | 가능 | `board_get_post` 의 `title`·`body`·`categoryIds`·`tags` | `services/posts.ts:334-341` |
| `board_create_tasks` | 가능 | `board_list_tasks` 의 항목 목록 | `board-tools.ts` `board_list_tasks` |
| `board_update_task_status` | 가능 | `board_list_tasks` 의 해당 task status | `board-tools.ts` `board_list_tasks` |
| `board_add_comment` | 가능 | `board_list_comments` 의 본문·`internal`. 단 DEVELOPER 미만 토큰으로 `internal: true` 를 달 수는 없으므로(403) 이 경로에서 보이지 않는 경우는 생기지 않는다 | `services/comments.ts` `listComments` |
| `board_set_status` | 가능 | `board_get_post` 의 `status`·`boardStatus.id` | `services/posts.ts:335,349` |
| `board_create_suggestion` | 가능 | `board_get_suggestion` 의 최신 제안(상태·`rationale`). `{"suggestion":null}` 이면 미등록 | `services/suggestions.ts` `getPostSuggestion` |
| `board_create_release_draft` | **초안 자체 없음** | 간접 2종만: 포함된 post 의 `affectedRelease`(version 대조) · `board_list_release_candidates` 에서 그 post 소거 | `services/posts.ts:346` · `services/releases.ts:399`(후보 조건 `affectedReleaseId: null`) · `releases.ts:462-463`(초안 생성이 `affectedReleaseId` 를 채운다) |

**보고 규약 (지키지 않으면 C2 위반):**
- read-back이 **없는 1종**(`board_create_release_draft`)은 **미리보기와 최종 보고 양쪽에** `반환 id만 · 재조회 수단 없음` 을 표기한다.
- `board_add_comment`는 `board_list_comments` 에서 **승인한 본문과 같은 댓글을 찾았을 때만** "등록 확인"으로 적는다. 개수 증가만으로 판정하지 않는다 — 제3자 댓글과 구별되지 않는다.
- 릴리스 초안의 간접 확인 2종을 수행했다면 **간접임을 명시**한다. 초안 본문·엔트리는 어느 쪽으로도 재조회되지 않는다.
- **검증하지 않은 것을 검증했다고 쓰지 않는다.** 이 스킬은 그 문장을 막으려고 존재한다.

### §3-2 댓글 공개 범위 — `internal` 기본값

| `.tavlet.json` 의 `boardVisibility` | `board_add_comment` 기본 인자 |
|---|---|
| `PUBLIC`, 또는 값 없음·모호(§가시성의 안전 측 기본값) | **`"internal": true`** |
| `INTERNAL` · `PRIVATE` | `internal` 생략(공개 댓글 — 그 보드를 볼 수 있는 구성원만 읽는다) |

- 공개 보드에서 사용자가 공개 댓글을 원하면 `internal` 을 빼되, 미리보기에 **"외부 독자가 읽는 공개 댓글"** 을 표기하고 G6 별도 확인을 받는다.
- 403 `COMMENT_INTERNAL_STAFF_ONLY` 가 나면 토큰 사용자가 DEVELOPER 미만이다. **공개 댓글로 조용히 바꿔 재시도하지 않는다** — 실패로 처리하고, 공개 댓글로 바꿀지 사용자에게 묻는다. 바꾸면 인자가 달라지므로 재-미리보기(G5)다.
- 팀 전용 댓글도 **스크럽(G7)은 그대로 한다.** org 구성원 전체가 읽고, 보드·댓글 설정은 나중에 바뀔 수 있다.

---

## 4. 필드 길이 상한

| 대상 | 상한 | 근거 |
|---|---|---|
| post `title` | 1–200자 | `posts.ts:7` |
| post `body` | 1–10000자 | `posts.ts:8` |
| post `tagNames` | 항목당 1–40자, **최대 10개** | `posts.ts:10` |
| task `title` | 1–200자 | `post-tasks.ts:8` |
| task `detail` | ≤2000자 | `post-tasks.ts:9` |
| task `items` 배열 | **1–50개** | `post-tasks.ts:12-13` |
| comment `body` | 1–**5000**자 | `posts.ts:44` |
| release `version` | 1–50자(trim, 공백만 금지) | `releases.ts:29-33` |
| release `name` | ≤100자 | `releases.ts:76` |
| release draft `body` | 1–10000자 | `releases.ts:77` |
| release `entries` 배열 | **1–50개** | `releases.ts:78` |
| release entry `title` | 1–200자 | `releases.ts:68` |
| release entry `body` | 1–**20000**자 | `releases.ts:69` |
| release entry `postIds` | **1–100개** | `releases.ts:71` |

> **기존 스킬 문서와의 불일치 — 코드를 따른다.** tavlet 레포의 `agent/skills/tavlet-board-result/SKILL.md:29`는 댓글 본문을 "≤10000자"로 기재하지만 실제 검증 스키마는 **5000자**다(`posts.ts:44`). `tavlet-tracker`는 **5000자**를 쓴다. 기존 스킬 문서의 숫자를 복사하지 않는다.

---

## 5. enum 정본

| 대상 | 허용 값 | 근거 |
|---|---|---|
| **task status** (`board_update_task_status`) | `TODO` · `DOING` · `DONE` · `DROPPED` | `board-tools.ts`, `post-tasks.ts:19` |
| **post status** (`board_set_status`) | `OPEN` · `UNDER_REVIEW` · `PLANNED` · `IN_PROGRESS` · `DONE` · `DECLINED` | `board-tools.ts`, `primitives.ts:24-31` |
| **suggestion priority** | `HIGH` · `MEDIUM` · `LOW` | `board-tools.ts` |
| **changelog entry type** | `NEW` · `IMPROVED` · `FIXED` · `BETA` | `board-tools.ts`, `releases.ts:4` |
| **board kind** (`board_list_boards.kind`) | `FEATURE` · `BUG` · `FEEDBACK` | `prisma/schema.prisma:138-142` |
| **board visibility** (도구 미노출) | `PUBLIC` · `PRIVATE` · `INTERNAL` | `primitives.ts:23`, `prisma/schema.prisma:132-136,283` |

**두 status 집합은 교집합이 `DONE` 하나뿐이다.** `IN_PROGRESS`를 task에 넘기거나 `DOING`을 post에 넘기면 스키마 오류다.

---

## 6. 비대칭·혼동 체크리스트 (인자 확정 전 매번 대조)

- [ ] `board_create_post` → **`tagNames`**(태그 **이름** 배열, 항목 40자·최대 10개) · `categoryIds`(**id** 배열)
- [ ] `board_create_suggestion` → **`tagIds`**(태그 **id** 배열) · `categoryIds`(id 배열) — `create_post`와 반대다
- [ ] `board_create_suggestion` → 두 배열이 **모두 비어 있지 않은지**. 대상 보드의 `board_get_taxonomy` 가 `{"categories":[],"tags":[]}` 라면 지정할 id 가 없으므로 **이 쓰기 자체를 계획에서 뺀다.** 어휘를 만드는 board 도구는 없어 사람이 콘솔에서 먼저 만들어야 한다
- [ ] `projectId`는 **DB id**다. `board_list_boards` 반환의 `projectId`를 쓴다. project **slug**(`default`)를 넣지 않는다
- [ ] `board_set_status`는 `status`와 `columnId` 중 **정확히 하나**. 둘 다 없거나 둘 다 있으면 throw
- [ ] `columnId` 값은 `board_list_statuses` 반환에서만 가져온다
- [ ] `categoryIds`·`tagIds` 값은 `board_get_taxonomy` 반환에서만 가져온다
- [ ] task status vs post status 집합 혼동 없음
- [ ] 대상 `boardId`가 `board_list_boards` 반환에 실재
- [ ] 모든 문자열이 §4 길이 상한 이내
- [ ] `board_add_comment` 의 `internal` 이 §3-2 기본값과 맞는다(공개·미상 보드면 `true`)
- [ ] `board_create_suggestion` 에 `duplicates` 를 넣지 않았다 — 서버에 없는 인자다
- [ ] `board_list_posts` 정찰에서 `nextOffset` 이 남았는데 "중복 없음"으로 판정하지 않았다

---

## 7. 워크플로 스테이지 요약

```
SA 테넌트 해소      board_list_boards
SB 중복 정찰        board_list_posts (q 2회 이상) → board_get_post
SC 분류 어휘        board_get_taxonomy
SD 상태 어휘        board_list_statuses
SE post 등록        board_create_post            [W]
SF task 분해        board_list_tasks → board_create_tasks   [W]
SG 진행 갱신        board_list_tasks → board_update_task_status  [W]
SH 세션 다이제스트  board_list_comments → board_add_comment  [W]  (공개·미상 보드면 internal)
SI 상태 전이        board_list_statuses → board_set_status  [W]
SJ 분류·중복 제안   board_get_taxonomy → board_create_suggestion  [W] → board_get_suggestion
SK 릴리스 초안      board_list_release_candidates → board_create_release_draft  [W]
```

**의존 순서:** SE → SF → SG → SH → SI. SJ는 대상 post가 존재한 뒤. SK는 관련 post가 `DONE`이 된 뒤.
