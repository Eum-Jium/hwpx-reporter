# -*- coding: utf-8 -*-
"""ReportPolicy — 7B 방어로직을 한데 묶은 미들웨어 파사드.

엔진(hwpx-skeleton)과 오케스트레이터(app) 사이에 끼워, render 인자를 검사·복구하고
응답을 정화한다. 엔진·전송(LLM)은 주입으로 받아 이 패키지는 순수하게 유지된다.

주입 콜백:
  llm_chat(messages, options) -> str            # 분량 재작성용 LLM 호출
  guide_text(template_key) -> str | None        # 유형별 지침 md
  render_fn(args) -> dict                        # 렌더(구제 시 재호출; 게이트 포함 경로)
"""
from __future__ import annotations
import json
from typing import Awaitable, Callable, Optional, Tuple

from .config import PolicyConfig, WEAK_7B
from . import language, body as body_mod, length

# 거부 메시지 (원본 문구 그대로 — 모델이 이 지시를 보고 재시도)
_MSG_EMPTY_BODY = ("body 인자가 비어 있다. 사용자가 '빈 양식'을 명시적으로 "
                   "요청하지 않았다면 반드시 본문을 작성해 body 에 담아 다시 "
                   "호출하라. get_writing_guide 를 아직 안 읽었다면 먼저 읽어라.")
_MSG_GUIDE_PREFIX = ("아래 세부지침에 맞게 body 를 다시 작성해 "
                     "render_from_skeleton 을 즉시 재호출하라. 포기하지 마라.\n\n")

# 사용자 메시지에 첨부하는 언어 지시 (구방식 — 하위호환용으로 유지)
USER_GUARD = ("\n\n(지시: 반드시 순수 한국어로만. 한자·중국어 금지. "
              "보고서 요청이면 body 에 본문을 반드시 작성해 포함할 것.)")

# 시스템 프롬프트에 1회 주입하는 언어 지시 — 사용자 메시지마다 붙이면
# 정당한 한자 언급 요청과 자기모순이 나고 이력이 오염되므로 이쪽을 권장.
SYSTEM_GUARD = ("\n\n[언어 규칙] 반드시 순수 한국어(한글)로만 답하고 "
                "한자·중국어를 쓰지 마라. 보고서 요청이면 렌더 도구의 body "
                "인자에 본문 전체를 반드시 작성해 포함하라.")


class ReportPolicy:
    def __init__(self, config: PolicyConfig = WEAK_7B, *,
                 llm_chat: Callable[[list, dict], Awaitable[str]],
                 guide_text: Callable[[str], Optional[str]],
                 guided_types,
                 template_specs):
        self.config = config
        self.llm_chat = llm_chat
        self.guide_text = guide_text
        self.guided_types = guided_types
        self.template_specs = template_specs

    # ── 언어 가드 ──────────────────────────────────────────
    def user_guard(self) -> str:
        """구방식: 사용자 메시지마다 첨부. system_guard 사용 시 쓰지 말 것."""
        return USER_GUARD if self.config.language_guard else ""

    def system_guard(self) -> str:
        """시스템 프롬프트에 1회 덧붙이는 언어 지시(권장)."""
        return SYSTEM_GUARD if self.config.language_guard else ""

    # ── render 인자 검사·복구 ──────────────────────────────
    async def prepare_render_args(self, args: dict, *, guides_read: set,
                                  last_guide_key: Optional[str],
                                  conversation: list) -> Tuple[Optional[dict], str, dict]:
        """render 전 게이트. 반환 (reject|None, effective_body, notes).
        reject 가 있으면 호출부는 그대로 반환(렌더 금지). 없으면 effective_body 로 렌더.
        args 는 제자리 수정되어 template_key/body 가 정규화된다."""
        cfg = self.config
        args = args or {}                       # None/누락 방어
        key = (args.get("template_key") or "").strip()
        # template_key 폴백 (누락/오타 시 직전 지침 유형)
        if (cfg.template_key_fallback and key not in self.template_specs
                and last_guide_key):
            key = last_guide_key
        args["template_key"] = key

        # body 는 문자열만 유효 — 7B 가 리스트/None 으로 흘려도 크래시 없이 빈 본문 취급
        raw_body = args.get("body")
        body = raw_body if isinstance(raw_body, str) else ""
        # '답변에서 이미 복구한 본문'(rescue 등) 표시 → 지침 미독 게이트 우회
        recovered_body = bool(args.pop("_recovered_body", False))
        notes: dict = {}

        # body 누락 방어 (enforce_nonempty_body 로 토글 — STRONG/OFF 는 빈 양식 렌더 허용)
        if (cfg.enforce_nonempty_body and not body.strip()
                and key in self.guided_types
                and not body_mod.user_wants_blank(conversation)):
            salvaged = (body_mod.extract_body_from_conversation(conversation)
                        if cfg.recover_body else "")
            if salvaged:
                body = salvaged
                args["body"] = salvaged
                recovered_body = True
            else:
                return self._reject(_MSG_EMPTY_BODY), body, notes

        # 지침 미독 게이트 (복구된 본문은 이미 지침 반영본으로 간주 → 통과)
        if (cfg.enforce_guide_read and body.strip() and key in self.guided_types
                and key not in guides_read and not recovered_body):
            guide = self.guide_text(key)
            guides_read.add(key)  # 지침 전달됨(또는 없음 확인) → 다음 호출은 통과
            if guide:  # 지침 파일이 없으면 강제할 내용이 없다 → 게이트 생략
                return self._reject(_MSG_GUIDE_PREFIX + guide), body, notes

        # 한자 게이트
        if cfg.reject_hanja:
            bad = language.find_hanja(args)
            if bad:
                return self._reject("한자/중국어가 포함되어 거부됨: " + ", ".join(bad)
                                    + " — 모든 값을 순수 한국어(한글)로 바꿔 다시 호출하라."), body, notes

        # 분량 자동 보정
        if cfg.autofix_length and body.strip():
            issues = length.check_line_lengths(body)
            if issues:
                body, n_fixed = await length.autofix_lengths(
                    body, self.llm_chat, cfg.max_line_fixes,
                    getattr(cfg, "max_autofix_llm_calls", 18))
                if n_fixed:
                    notes["length_autofix"] = n_fixed

        if recovered_body:
            notes["body_recovered_from_reply"] = True
        return None, body, notes

    # ── 응답 정화 ──────────────────────────────────────────
    def sanitize_reply(self, reply: str, events: list) -> str:
        if not self.config.sanitize_reply:
            return reply
        return language.sanitize_reply(reply, events)

    # ── 종료 시 구제 렌더 ──────────────────────────────────
    async def rescue_render(self, last_render_args: dict, *, conversation: list,
                            last_guide_key: Optional[str],
                            render_fn: Callable[[dict], Awaitable[dict]]) -> Optional[dict]:
        """모델이 render 를 성공 못 시키고 본문을 답변에만 써둔 채 끝낸 경우,
        답변에서 본문을 뽑아 render_fn 으로 직접 렌더. 성공 시 event dict, 아니면 None."""
        if not self.config.rescue_render:
            return None
        b = body_mod.extract_body_from_conversation(conversation)
        if not b:
            return None
        key = (last_render_args.get("template_key") or last_guide_key or "")
        if key not in self.template_specs:
            return None
        args = {
            "template_key": key,
            "fields": last_render_args.get("fields") or {},
            "body": b,
            "intent": last_render_args.get("intent"),
            "_recovered_body": True,   # 이미 답변에서 복구한 본문 → 지침 게이트 통과
        }
        result_obj = await render_fn(args)
        if not (result_obj and result_obj.get("status") == "success"):
            return None
        return {"name": "render_from_skeleton", "arguments": args,
                "result": json.dumps(result_obj, ensure_ascii=False)[:2000],
                "error": False, "result_obj": result_obj}

    @staticmethod
    def _reject(message: str) -> dict:
        return {"status": "error", "message": message}
