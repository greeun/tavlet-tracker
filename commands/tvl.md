---
description: tavlet 보드에 이번 세션 작업 등록·추적 (증거 심사 + 승인 게이트)
argument-hint: 이 작업 보드에 기록해줘 | <postId 또는 post URL> | <등록할 내용>
---

`tavlet-tracker` 스킬을 실행해 이번 세션의 작업을 tavlet 피드백 보드에 등록·추적하라.

요청: $ARGUMENTS

지침:

1. **스킬 실행.** `tavlet-tracker` 스킬의 절차를 따른다. 위 요청을 진입 입력으로 삼는다.

2. **인자 해석 — 맥락 지시일 때.** 인자가 비었거나 "이 작업", "방금 그거", "지금 한 거" 류를 가리키면, **직전 대화 맥락에서 실제로 수행·관측된 사실만** 수집한다:
   - 변경한 파일 경로(가능하면 `파일:라인`)
   - `git log --oneline -n <N>` / `git show --stat <hash>` 로 **확인한** 커밋 해시
   - 실제 실행한 명령과 그 출력
   - 에러 원문
   추정, 실행하지 않은 테스트의 통과 주장, 열어본 적 없는 파일 인용은 **금지**한다. 확인하지 못한 것은 삭제하지 말고 "미검증"으로 분류해 남긴다.

3. **인자 해석 — post URL일 때.** 인자가 post URL이면 **마지막 path 세그먼트가 postId**다: `/o/{org}/{ws}/{proj}/{boardId}/post/{postId}`. 보드 피드 URL(`/o/{org}/{ws}/{proj}/{boardId}`)은 마지막 세그먼트가 boardId이므로 혼동하지 않는다.

4. **tavlet 레포 판정 — 폐기.** 레포 내부 파이프라인(`/tav` → S0~S4)은 tavlet 커밋 `ff3fa1f` 에서 삭제됐고 tavlet `CLAUDE.md` 는 보드 등록을 이 스킬로 대체한다고 기록한다. tavlet 레포에서 실행하더라도 **핸드오프를 제안하지 않는다.**

5. **절차 준수.** 스킬 절차대로 **읽기 정찰 → 초안 → 심사 → 정확한 인자 미리보기 → 명시 승인 → 실행 → 사후 read-back** 을 지킨다. read-back은 **쓰기 7종 중 5종에만 가능**하다 — `board_create_suggestion` · `board_create_release_draft` 는 재조회 도구가 없으므로 **"반환 id만 · 재조회 수단 없음"** 으로 미리보기와 최종 보고에 표기한다(`references/board-tool-contract.md` §3-1). **승인 전에는 어떤 쓰기 도구(`board_create_post` · `board_create_tasks` · `board_update_task_status` · `board_add_comment` · `board_set_status` · `board_create_suggestion` · `board_create_release_draft`)도 호출하지 않는다.**
