# 보고서 에이전트 MCP 도구 11종 — 공개 사본(비공개 원본에서 주석을 걷었다 · 코드는 같다).
# GenOS(Flowise 기반) 에이전트 플랫폼의 「MCP 도구」 코드칸에 통째로 붙여 넣는다 —
# 전역 `mcp`(FastMCP)는 플랫폼이 넣어 준다. 설치·환경변수는 mcp/README.md.


_DRAFT_TTL = 24 * 3600
_DRAFT_MAX = 2 * 1024 * 1024
_REFS_PROMPT_MAX = 12000


def _draft_dir():
    import os
    d = os.environ.get("HWPX_DRAFT_DIR", "/tmp/hwpx-drafts")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_key(key):
    import re
    s = key if isinstance(key, str) else u""
    if u"{" in s or u"}" in s:
        return u""
    s = re.sub(u"[^A-Za-z0-9_-]", u"", s)[:64]
    return s if len(s) >= 8 else u""


def _sweep_drafts(d):
    import os, time
    now = time.time()
    try:
        for name in os.listdir(d):
            p = os.path.join(d, name)
            try:
                if now - os.path.getmtime(p) > _DRAFT_TTL:
                    os.unlink(p)
            except Exception:
                pass
    except Exception:
        pass


def _refs_path(k):
    import os
    return os.path.join(_draft_dir(), k + "_refs.md")


def _refmap_path(k):
    import os
    return os.path.join(_draft_dir(), k + "_refmap.json")


def _refmap_read(k):
    import json, os
    try:
        p = _refmap_path(k)
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _refmap_write(k, items):
    import json, os
    try:
        with open(_refmap_path(k), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        with open(os.path.join(_draft_dir(), k + "_paths.txt"),
                  "w", encoding="utf-8") as f:
            f.write(u" | ".join(x.get("path", u"") for x in items if x.get("path")))
        return True
    except Exception:
        return False


def _parse_refmap_lines(text):
    import re
    items, keep = [], []
    for ln in (text or u"").splitlines():
        m = re.match(u"^\\[자료 목록\\]\\s*(.+)$", ln.strip())
        if not m:
            keep.append(ln)
            continue
        parts = [p.strip() for p in m.group(1).split(u"|")]
        while len(parts) < 4:
            parts.append(u"")
        items.append({"no": parts[0], "name": parts[1],
                      "path": parts[2], "kind": (parts[3] or u"").lower()})
    return u"\n".join(keep).lstrip(), items


def _refs_blocks(text):
    import re
    out = []
    pat = re.compile(u"^\\[참고자료 (\\d+): (.*)\\]\\s*$", re.M)
    ms = list(pat.finditer(text or u""))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[m.end():end].strip()))
    return out


_원본_열기 = False


def _refs_digest(env, blocks, key=u"", refmap=None):
    lines = [env.strip()] if env and env.strip() else []
    refmap = refmap or []

    def _자료줄수(kind, body):
        if (kind or u"").lower() not in (u"csv", u"tsv"):
            return u""
        줄 = [x for x in (body or u"").splitlines() if x.strip()]
        n = max(0, len(줄) - 1)
        if not n:
            return u""
        잘림 = u"이상" if u"(이하 생략" in (body or u"") else u""
        return u" · **자료 %d줄%s**(머리글 제외)" % (n, 잘림)
    bmap = {no: (name, body) for no, name, body in (blocks or [])}
    if not blocks and not refmap:
        lines.append(u"[참고자료] (첨부 없음)")
        return u"\n\n".join(lines)
    head = []
    if key:
        head.append(u"[자료 열쇠] %s" % key)
    head.append(u"[참고자료]")
    seen = set()
    for it in refmap:
        no, name = it.get("no", u""), it.get("name", u"") or u"첨부"
        seen.add(no)
        if _원본_열기 and (it.get("kind") or u"") == u"hwpx":
            head.append(u"%s: %s (hwpx · 원본 직접 읽기)" % (no, name))
            continue
        nm, body = bmap.get(no, (name, u""))
        head.append(u"%s: %s (%s · 청크 %s자%s)"
                    % (no, nm or name, it.get("kind") or u"기타",
                       format(len(body), ","), _자료줄수(it.get("kind"), body)))
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), u"")
        if first:
            head.append(u"   머리글: %s" % first[:120])
    for no, name, body in (blocks or []):
        if no in seen:
            continue
        head.append(u"%s: %s (%s자)" % (no, name, format(len(body), ",")))
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), u"")
        if first:
            head.append(u"   머리글: %s" % first[:120])
    lines.append(u"\n".join(head))
    return u"\n\n".join(lines)


def _merge_refs(old_map, old_blocks, new_map, new_blocks):
    def _n(no):
        try:
            return int(no)
        except (TypeError, ValueError):
            return 0
    rows = {}
    for it in old_map or []:
        rows.setdefault(it.get("no", u""), [it.get("name", u""), None, None])[1] = it
    for no, name, body in old_blocks or []:
        rows.setdefault(no, [name, None, None])[2] = body
    by_name = {r[0]: no for no, r in rows.items() if r[0]}
    last = max([_n(no) for no in rows] or [0])
    new_rows = {}
    for it in new_map or []:
        new_rows.setdefault(it.get("no", u""), [it.get("name", u""), None, None])[1] = it
    for no, name, body in new_blocks or []:
        new_rows.setdefault(no, [name, None, None])[2] = body
    for no in sorted(new_rows, key=_n):
        name, it, body = new_rows[no]
        if name and name in by_name:
            got = by_name[name]
        else:
            last += 1
            got = str(last)
            if name:
                by_name[name] = got
        if it is not None:
            it = dict(it, no=got)
        rows[got] = [name, it, body]
    order = sorted(rows, key=_n)
    refmap = [rows[no][1] for no in order if rows[no][1] is not None]
    blocks = [(no, rows[no][0], rows[no][2]) for no in order if rows[no][2] is not None]
    return refmap, blocks


def _stash_refs(refs, key=u""):
    import os, re
    try:
        text = refs if isinstance(refs, str) else u""
        k = _safe_key(key)
        km = re.search(u"^\\[자료 열쇠\\]\\s*(\\S+)\\s*$", text, re.M)
        if km:
            text = (text[:km.start()] + text[km.end():]).lstrip()
            if not k:
                k = _safe_key(km.group(1))
        text, refmap = _parse_refmap_lines(text)
        pm = re.search(u"^\\[자료 경로\\]\\s*(.+?)\\s*$", text, re.M)
        legacy_paths = u""
        if pm:
            text = (text[:pm.start()] + text[pm.end():]).lstrip()
            legacy_paths = pm.group(1)
        if not k:
            if len(text) > _REFS_PROMPT_MAX:
                return (text[:_REFS_PROMPT_MAX]
                        + u"\n(이하 생략 — 저장소를 쓰지 못해 발췌본만 싣는다)")
            return text
        if legacy_paths and not refmap:
            try:
                with open(os.path.join(_draft_dir(), k + "_paths.txt"),
                          "w", encoding="utf-8") as f:
                    f.write(legacy_paths)
            except Exception:
                pass
        env = text.split(u"[참고자료")[0] if u"[참고자료" in text else text
        blocks = _refs_blocks(text)
        if not blocks and u"[참고자료" in text and u"(첨부 없음)" not in text:
            tail = text[text.index(u"[참고자료"):]
            m = re.match(u"\\[참고자료([^\\]]*)\\]", tail)
            name = (m.group(1).lstrip(u": ").strip() if m else u"") or u"첨부파일"
            body = (tail[m.end():] if m else tail).strip()
            if body:
                blocks = [(u"1", name, body)]
                text = u"%s\n\n[참고자료 1: %s]\n%s" % (env.strip(), name, body)
        p = _refs_path(k)
        if blocks or refmap:
            d = _draft_dir()
            _sweep_drafts(d)
            old_blocks = []
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    old_blocks = _refs_blocks(f.read())
            refmap, blocks = _merge_refs(_refmap_read(k), old_blocks, refmap, blocks)
            text = env.strip() + u"\n\n" + u"\n\n".join(
                u"[참고자료 %s: %s]\n%s" % b for b in blocks)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            if refmap:
                _refmap_write(k, refmap)
            return _refs_digest(env, blocks, k, refmap)
        old_map = _refmap_read(k)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                old = f.read()
            return _refs_digest(env, _refs_blocks(old), k, old_map)
        if old_map:
            return _refs_digest(env, [], k, old_map)
        return _refs_digest(env, [])
    except Exception as e:
        return u"%s\n\n(참고자료 저장 실패: %s: %s — 이번 턴은 전문을 그대로 씁니다)" % (
            refs if isinstance(refs, str) else u"", type(e).__name__, e)


@mcp.tool()
async def save_refs(refs: str = "", key: str = "") -> str:
    """하는 일:
        참고자료를 세션 저장소(/tmp)에 넣고 프롬프트에 실을 목차를 낸다.
        배선은 이 도구를 안 문다 — `build_state`(③)가 같은 일을 한다. 옛 배선 호환·진단용으로 남긴다.
    넘기는 입력:
        refs: ② Download refs 출력 전체 — [환경] + [자료 목록] + [참고자료 N: …] 블록들
        key: 대화 식별자. 워크플로우가 `{{$flow.chatId}}` 를 넘긴다
    돌려주는 반환:
        [환경] + 파일 목차 한 덩이. 자료 전문은 `load_refs` 로 꺼낸다.
    """
    return _stash_refs(refs, key)


_SEC_ROLE_TEXT = {
    u"추진배경": u"왜 하는지",
    u"현황":     u"지금 어떻고 무엇이 모자란지",
    u"주요내용": u"무엇을 하겠다는 것인지",
    u"추진방안": u"어떻게 하겠다는 것인지",
    u"향후계획": u"언제 무엇을 할지",
    u"본론":     u"",
}


def _sample_outline(pages):
    rows = _plan_rows(pages) if pages else None
    if not rows:
        return u""
    out = [u"[샘플 골격] — 장수에 맞춘 샘플. 단 이름과 역할."]
    for _i, _nm, _pt, _b, _d, _시 in rows:
        표 = u" · 표 하나" if _시 == u"표" else u""
        out.append(u"  %d단 %s — %s%s" % (_i, _nm, _SEC_ROLE_TEXT.get(_nm, u""), 표))
    return u"\n".join(out)


def _inventory_block(key):
    k = _safe_key(key)
    lines = [u"[목록]"]
    refs = _refmap_read(k) if k else []
    if refs:
        lines.append(u"- 첨부: " + u" · ".join(u"%s %s" % (r.get("no", u""), r.get("name", u"") or u"첨부")
                                              for r in refs))
    else:
        lines.append(u"- 첨부: 없음")
    vs = _versions_read(k) if k else []
    if vs:
        lines.append(u"- 버전: " + u" · ".join(
            u"%s v%s (%s장)" % (v.get("kind", u""), v.get("v", u""), v.get("pages", u"0.00")) for v in vs))
    else:
        lines.append(u"- 버전: 아직 없음")
    return u"\n".join(lines)


@mcp.tool()
async def build_state(refs: str = "", key: str = "", target_lines: str = "",
                      part: str = "", target_pages: str = "", title: str = "",
                      purpose: str = "") -> str:
    """하는 일:
        이번 턴에 읽을 재료를 한 덩어리로 낸다 — 워크플로의 `3_Load state` 가 부른다.
        `part` 가 낼 재료를 고른다(공개 워크플로는 "agent").
    넘기는 입력:
        refs: ② Download refs 출력 전체
        key: 대화 식별자. 워크플로우가 `{{$flow.chatId}}` 를 넘긴다
        part: 낼 조각
              "agent"   사실 + [목록] + [검토] + [샘플 골격] — 공개 워크플로가 쓰는 값
              "slim"·"outline"·"edit"·"all"   노드가 갈래로 나뉘던 옛 배선 호환
        target_pages: 목표 장수 1~5. [샘플 골격]을 그 장수에 맞춰 낸다.
                      비우면 저장된 값을 쓴다 — `3_Load state` 는 Agent 앞이라 넘길 값이 없다
        title: 이번 턴에 정한 제목. 비우면 저장된 값
        purpose: 이번 턴에 정한 목적. 비우면 저장된 값
                 값과 [검토]는 **파일에서** 읽는다(`<key>_state.json` · 저장 도구가 남긴다).
                 State 로 잇지 않는 까닭 — 플랫폼(Flowise)의 State 는 턴을 못 넘는다
        target_lines: 옛 판 호환. target_pages 가 있으면 무시된다
    돌려주는 반환:
        [자료 열쇠] · [환경] · [참고자료] · [outline] · [draft] · [제목] · [목적] · [목표 분량]
        그리고 part 에 따라 [목록] · [검토] · [샘플 골격]("agent" 면 셋 다).
        없는 것은 태그 자체가 안 붙는다 — [검토]가 없으면 그 줄이 없다.
    """
    import json
    try:
        digest = _stash_refs(refs, key)
    except Exception as e:
        digest = u"[참고자료] (목차 생성 실패: %s: %s)" % (type(e).__name__, e)
    try:
        meta = json.loads(_load_draft(key=key, part="meta"))
    except Exception as e:
        meta = {"exists": False, "note": u"%s: %s" % (type(e).__name__, e)}

    k = _safe_key(key)
    st = _state_read(k)
    _제목 = (title or u"").strip() or st[u"title"]
    _목적 = (purpose or u"").strip() or st[u"purpose"]
    _검토 = st[u"review"]
    _p = (part or u"all").strip().lower()
    _사실 = _p in (u"all", u"facts", u"slim", u"spec", u"outline", u"edit", u"agent")
    _슬림 = _p in (u"slim", u"agent")
    _w = _pages_pick(meta.get("spec"), _pages_arg(target_pages, target_lines), _state_pages(k))

    out = [digest] if _사실 else []
    if _사실 and key and u"[자료 열쇠]" not in digest:
        out.insert(0, u"[자료 열쇠] %s — `load_refs`·`load_draft` 에 글자 그대로 넣어라" % key)
    if _사실:
        osecs = meta.get("outline_sections") or []
        if meta.get("outline_exists") and osecs:
            _합 = sum((x.get("pages") or 0) for x in osecs if x.get("pages") is not None)
            def _orow(x):
                bits = []
                if x.get("pages") is not None:
                    bits.append(u"%.1f장" % x["pages"])
                if x.get("table"):
                    bits.append(u"표 하나")
                return u"%s %s%s%s" % (x.get("no", u""), x.get("name", u""),
                                       (u" — %s" % x["brief"]) if x.get("brief") else u"",
                                       (u" (%s)" % u" · ".join(bits)) if bits else u"")
            out.append(u"[outline] %d단%s\n" % (len(osecs), (u" · 합 %.1f장" % _합) if _합 else u"")
                       + u"\n".join(_orow(x) for x in osecs))
        else:
            out.append(u"[outline] 없음")
        if not meta.get("exists"):
            out.append(u"[draft] 없음 — 이번이 첫 작성이다")
        else:
            secs = meta.get("sections") or []
            if not secs:
                out.append(u"[draft] %s자 · 단으로 분해되지 않음(자유 형식)"
                           % format(meta.get("chars", 0), ","))
            else:
                head = u"[draft] %d단 · %s장" % (len(secs), _pg(meta.get("points", 0)))
                def _drow(x):
                    pa = x.get("pages_at") or {}
                    bits = [u"%s장" % _pg(x.get("pts", 0))]
                    if pa:
                        bits.append((u"%d쪽" % pa["start_page"]) if pa["start_page"] == pa["end_page"]
                                    else (u"%d~%d쪽" % (pa["start_page"], pa["end_page"])))
                    걸 = [t for t in (pa.get("tables") or []) if t["start_page"] != t["end_page"]]
                    if 걸:
                        bits.append(u"표가 %d쪽 끝에 걸릴 듯(%d줄)" % (걸[0]["start_page"], 걸[0]["over"]))
                    elif pa.get("tables"):
                        bits.append(u"표")
                    return u"%s %s%s (%s)" % (x.get("no", u""), x.get("name", u""),
                                              u" (작성 예정)" if x.get("todo") else u"", u" · ".join(bits))
                rows = [_drow(x) for x in secs]
                out.append(head + u"\n" + u"\n".join(rows))
        if _슬림:
            out.append(_inventory_block(key))
        out.append(u"\n".join([u"[제목] " + (_제목 or u"(아직 없음)"),
                               u"[목적] " + (_목적 or u"(아직 없음)"),
                               u"[목표 분량] " + ((u"%d장" % _w) if _w else u"(아직 없음)")]))
        if _검토.strip() and _p in (u"slim", u"edit", u"agent"):
            out.append(u"[검토]\n" + _검토.strip())
    if _p in (u"outline", u"agent"):
        try:
            s = _sample_outline(_w or (2 if _p == u"agent" else 0))
            if s:
                out.append(s)
        except Exception:
            pass
    return u"\n\n".join(out)


@mcp.tool()
async def load_refs(key: str = "", file: str = "", search: str = "",
                    offset: int = 0, max_chars: int = 8000) -> str:
    """하는 일:
        참고자료를 꺼내 읽는다 — 첨부마다 전처리기가 뽑은 본문(청크)을 읽는다.
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다
        file: 목차의 번호("1") 또는 파일명 일부. 비우면 첫 자료
        search: 찾을 낱말 — 긴 자료에서 필요한 대목만 고를 때
        offset: 이어 읽기 시작 위치. 반환 끝에 `(이하 생략 …)` 이 왔을 때만 올린다
        max_chars: 한 번에 받을 최대 글자 수(기본 8000 · 1000~12000)
    돌려주는 반환:
        자료 본문. 머리에 출처(`[청크 번호: 파일명]`)가 붙는다.
        없거나 만료면 `LOAD_FAIL: 원인`.
    """
    import os
    try:
        k = _safe_key(key)
        if not k:
            return u"LOAD_FAIL: 대화 식별자가 없다 — 대화에 실린 참고자료를 그대로 써라"
        try:
            cap = int(str(max_chars).strip() or 8000)
        except Exception:
            cap = 8000
        cap = max(1000, min(cap, 12000))
        try:
            off = max(0, int(str(offset).strip() or 0))
        except Exception:
            off = 0
        want = (u"%s" % (file or u"")).strip()
        kw = (u"%s" % (search or u"")).strip()

        def cut(s, src):
            piece = s[off:off + cap]
            if not piece:
                return u"LOAD_FAIL: offset 이 자료 끝을 넘었다(전체 %s자)" % format(len(s), ",")
            if len(s) > off + cap:
                piece += (u"\n(이하 생략 — 전체 %s자 중 %s자까지 읽었다. 더 필요하면 "
                          u"offset=%d 로 이어 읽어라)"
                          % (format(len(s), ","), format(off + len(piece), ","), off + cap))
            return src + u"\n" + piece

        refmap = _refmap_read(k)
        hit = None
        for it in refmap:
            if not want:
                hit = it
                break
            if want == it.get("no") or want.lower() in (it.get("name") or u"").lower():
                hit = it
                break
        if _원본_열기 and hit is not None and (hit.get("kind") or u"") == u"hwpx":
            path = hit.get("path") or u""
            if not (path and os.path.exists(path)):
                return (u"LOAD_FAIL: 원본이 사라졌다(보관 기간 초과로 보인다) — "
                        u"'%s' 파일을 다시 첨부하라" % (hit.get("name") or u"첨부"))
            try:
                from hwpx_reader.core import core_read_text, core_search
            except Exception as e:
                return (u"LOAD_FAIL: hwpx 파서를 못 불렀다(%s: %s) — 도구 자산의 "
                        u"hwpx-reader 패키지 선택을 확인하라" % (type(e).__name__, e))
            src = u"[원본 %s: %s · hwpx]" % (hit.get("no") or u"1",
                                             hit.get("name") or u"첨부")
            try:
                if kw:
                    hits = core_search(path, kw, context=True)
                    if not hits:
                        return (u"%s\n(검색 '%s' — 맞는 줄이 없다. 낱말을 바꿔 다시 "
                                u"찾거나 search 없이 통째로 읽어라)" % (src, kw[:30]))
                    rows = []
                    for h in hits[:60]:
                        rows.append(u"· %s" % h.get("line", u""))
                        nxt = (h.get("next") or u"").strip()
                        if nxt:
                            rows.append(u"    %s" % nxt)
                    body = u"\n".join(rows)
                    if len(hits) > 60:
                        body += u"\n(%d건 중 60건만 실었다 — 낱말을 좁혀라)" % len(hits)
                    return u"%s (검색 '%s' %d건)\n%s" % (src, kw[:30], len(hits), body)
                return cut(core_read_text(path), src)
            except Exception as e:
                return u"LOAD_FAIL: 원본을 읽지 못했다(%s: %s)" % (type(e).__name__, e)

        p = _refs_path(k)
        if not os.path.exists(p):
            if hit is not None:
                return (u"LOAD_FAIL: '%s' 의 청크가 저장돼 있지 않다 — 파일을 다시 첨부하라"
                        % (hit.get("name") or u"첨부"))
            return u"LOAD_FAIL: 저장된 참고자료가 없다(첨부가 없었거나 만료됨)"
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        blocks = _refs_blocks(text)
        chosen = None
        if want:
            chosen = next((b for b in blocks if want == b[0]), None) or next(
                (b for b in blocks if want.lower() in b[1].lower()), None)
            if chosen is None:
                return u"LOAD_FAIL: '%s' 에 해당하는 참고자료가 없다" % want[:40]
        elif len(blocks) == 1:
            chosen = blocks[0]
        if chosen is None:
            return cut(text, u"[청크 — 전체]")
        no, name, body = chosen
        src = u"[청크 %s: %s]" % (no, name)
        if kw:
            lines = [ln for ln in body.splitlines() if kw in ln]
            if not lines:
                return u"%s\n(검색 '%s' — 맞는 줄이 없다)" % (src, kw[:30])
            return u"%s (검색 '%s' %d건)\n%s" % (src, kw[:30], len(lines),
                                                u"\n".join(lines[:60]))
        return cut(body, src)
    except Exception as e:
        return u"LOAD_FAIL: %s: %s" % (type(e).__name__, e)


@mcp.tool()
async def probe_refs(key: str = "", path: str = "") -> str:
    """하는 일:
        진단 전용 — 첨부 **원본 파일**이 이 컨테이너에서 열리는지 판별한다.
        전처리기가 메타데이터(`file_path`)로 붙여 주는 `/nfs…` 경로가 여기서 열리면,
        `load_refs` 가 잘린 청크가 아니라 원본을 직접 읽을 수 있다.
        배선은 이 도구를 안 문다 — 도구 테스트칸에서 직접 부른다. 읽기만 한다.
    넘기는 입력:
        key: 대화 식별자. 주면 그 대화의 첨부 경로들(② 가 실어 보낸 것)을 검사한다.
             첨부를 올린 턴을 한 번 돌린 뒤에 부른다
        path: 특정 경로 하나만 볼 때. 비우면 후보 마운트 뿌리를 훑는다
    돌려주는 반환:
        사람이 읽는 판별 리포트. **첫 줄이 결론**이다.
    """
    import os, json
    MAXLIST = 15

    def look(p):
        d = {"path": p, "exists": os.path.exists(p)}
        if not d["exists"]:
            return d
        try:
            d["is_dir"] = os.path.isdir(p)
            if d["is_dir"]:
                names = sorted(os.listdir(p))
                d["entries"] = len(names)
                d["sample"] = names[:MAXLIST]
            else:
                d["size"] = os.path.getsize(p)
                d["readable"] = os.access(p, os.R_OK)
                if d["readable"]:
                    with open(p, "rb") as f:
                        head = f.read(16)
                    d["head_hex"] = head.hex()
                    d["looks_like"] = ("zip(hwpx/docx)" if head[:2] == b"PK" else
                                       "hwp(ole)" if head[:4] == b"\xd0\xcf\x11\xe0" else
                                       "pdf" if head[:4] == b"%PDF" else "unknown")
        except Exception as e:
            d["error"] = "%s: %s" % (type(e).__name__, e)
        return d

    try:
        out = {"cwd": os.getcwd(),
               "draft_dir": _draft_dir(),
               "hwpx_out_dir": os.environ.get("HWPX_OUT_DIR", "/tmp/hwpx-out")}
        targets = []
        if path and path.strip():
            targets = [path.strip()]
        elif key:
            k = _safe_key(key)
            if not k:
                return (u"PROBE_FAIL: 대화 식별자를 못 읽었다(중괄호가 남아 있으면 "
                        u"템플릿이 안 풀린 것). 경로를 직접 넣어 부르거나 path 인자를 써라")
            pf = os.path.join(_draft_dir(), k + "_paths.txt")
            if not os.path.exists(pf):
                return (u"PROBE_FAIL: 그 대화의 첨부 경로 기록이 없다 — 첨부를 올린 턴을 "
                        u"한 번 돌린 뒤에 다시 불러라(② 가 경로를 실어 보낸다)")
            with open(pf, "r", encoding="utf-8") as f:
                targets = [t.strip() for t in f.read().split(u"|") if t.strip()]
        else:
            try:
                d0 = _draft_dir()
                recent = sorted((os.path.join(d0, n) for n in os.listdir(d0)
                                 if n.endswith("_paths.txt")),
                                key=os.path.getmtime, reverse=True)[:3]
                out["auto_from"] = [os.path.basename(x) for x in recent]
                for pf in recent:
                    with open(pf, "r", encoding="utf-8") as f:
                        targets += [t.strip() for t in f.read().split(u"|") if t.strip()]
            except Exception as e:
                out["auto_error"] = "%s: %s" % (type(e).__name__, e)
        out["targets"] = [look(t) for t in targets]
        hit = [t for t in out["targets"] if t.get("exists") and not t.get("is_dir")]
        if hit:
            head = (u"PROBE_OK 원본 파일이 열린다 — %d개. load_refs 를 원본 읽기로 "
                    u"바꾸면 TopK·chunk 절단이 무의미해진다." % len(hit))
        elif targets:
            head = (u"PROBE_NO 첨부 경로가 이 컨테이너에서 안 보인다 — 전처리기 파드에만 "
                    u"있는 마운트다. 지금 구조(청크 저장)를 그대로 쓴다.")
        else:
            head = (u"PROBE_INFO 검사할 경로 기록이 없다 — 첨부를 올린 턴을 한 번 "
                    u"돌린 뒤 key 를 주고 다시 불러라.")
        return head + u"\n" + json.dumps(out, ensure_ascii=False, indent=1)
    except Exception as e:
        return u"PROBE_FAIL: %s: %s" % (type(e).__name__, e)


def _clean_md(s):
    import re
    s = s.replace(u"**", u"").replace(u"__", u"")
    s = s.replace(u"`", u"")
    s = re.sub(u"\\[([^\\]]+)\\]\\(([^)]*)\\)", u"\\1", s)
    return s.strip()


def _tabify(s):
    import re
    m = re.match(u"^(['’]?\\d{2}\\s*[.년]\\s*(?:\\d{1,2}\\.\\s*)*"
                 u"(?:\\d{1,2}\\s*(?:[~–-]\\s*\\d{1,2}\\s*)?월?|[상하]반기|\\d분기|말|초)?)\\s+(\\S.*)$", s)
    return (m.group(1).rstrip() + u"\t" + m.group(2)) if m else s


def _convert_rows(raw, table_offset=0):
    import re
    text = (raw or u"")
    if not isinstance(text, str):
        text = u"%s" % text
    text = text.replace(u"\\n", u"\n")

    rows, tables = [], []
    table_no = table_offset
    in_table = False
    cur = None
    head_no = 0
    img_no = 0
    SEP_CELL = re.compile(u"^:?-+:?$")

    for ln in text.splitlines():
        t = ln.rstrip()
        s = t.lstrip()

        if re.match(u"^-{3,}$", s) or re.match(u"^={3,}$", s):
            in_table, cur = False, None
            continue
        if not s:
            in_table, cur = False, None
            continue

        if s.startswith(u"|"):
            cells = [c.strip() for c in s.strip().strip(u"|").split(u"|")]
            if not in_table:
                in_table = True
                table_no += 1
                rows.append((u"[표%d]" % table_no, t))
                cur = {"headers": [_clean_md(c) for c in cells], "rows": []}
                tables.append(cur)
            else:
                if all(SEP_CELL.match(c or u"-") for c in cells):
                    continue
                if cur is not None:
                    cur["rows"].append([_clean_md(c) for c in cells])
            continue
        in_table, cur = False, None

        mimg = re.match(u"^[-*+\u25a1\u2610\u25e6]\\s*\\[(\uc774\ubbf8\uc9c0|\ud45c)(\\d+)\\]\\s*(.*)$", s)
        if mimg:
            if mimg.group(1) == u"이미지":
                img_no += 1
            rows.append((u"[%s%s]" % (mimg.group(1),
                                      img_no if mimg.group(1) == u"이미지"
                                      else mimg.group(2)), t))
            cap = _clean_md(mimg.group(3)).strip()
            if cap:
                rows.append((u"* " + cap, t))
            continue

        if re.match(u"^\\[(표|이미지)\\d+\\]$", s):
            if s.startswith(u"[이미지"):
                img_no += 1
                s = u"[이미지%d]" % img_no
            rows.append((s, t))
            continue

        mh = re.match(u"^#{1,6}\\s*(.+)$", s)
        if mh:
            h = _clean_md(mh.group(1))
            mn = re.match(u"^(\\d+)\\.\\s", h)
            if mn:
                head_no = int(mn.group(1))
            else:
                head_no += 1
                h = u"%d. %s" % (head_no, h)
            rows.append((h, t))
            continue

        mq = re.match(u"^>\\s*(.*)$", s)
        if mq:
            rows.append((u"* " + _clean_md(mq.group(1)), t))
            continue

        ml = re.match(u"^(\\s*)[-*+]\\s+(.*)$", t)
        if ml:
            indent = len(ml.group(1).replace(u"\t", u"  "))
            mark = u"- " if indent >= 4 else (u"◦ " if indent >= 2 else u"□ ")
            rows.append((mark + _tabify(_clean_md(ml.group(2))), t))
            continue

        head = s[:1]
        if head in u"□☐◦-*·※" and not (head in u"-*" and not s[1:2].isspace()):
            rows.append((head + u" " + _tabify(_clean_md(s[1:])), t))
        else:
            rows.append((_clean_md(s) if re.match(u"^\\d+\\.\\s", s)
                         else u"□ " + _clean_md(s), t))

    return rows, tables


def _convert_md(raw, table_offset=0):
    rows, tables = _convert_rows(raw, table_offset)
    return u"\n".join(c for c, _ in rows), tables


_PT_HEADING = 2
_PT_TABLE_PAD = 1
_PT_IMAGE = 8
_PT_PER_PAGE = 25
_PT_FIRST_PAGE = 26
_PT_DISP = 25.5
_TABLE_PT = 7


def _pg(pts):
    try:
        return u"%.2f" % (float(pts or 0) / _PT_DISP)
    except Exception:
        return u"0.00"


def _pages_arg(target_pages, target_lines=u""):
    import re as _re
    try:
        m = _re.search(u"\\d+", u"%s" % (target_pages if target_pages is not None else u""))
        n = int(m.group()) if m else 0
    except Exception:
        n = 0
    if 1 <= n <= 5:
        return n
    return _pages_from_lines(target_lines)
_PT_LINE_CHARS = 38
_PT_LINE_TAIL = 32

def _line_pts(n):
    if n <= _PT_LINE_CHARS:
        return 1
    return 1 + -(-(n - _PT_LINE_CHARS) // _PT_LINE_TAIL)


def _table_ratios(t):
    try:
        from hwpx_core import tablespec as TS
    except Exception:
        return None
    headers = list((t or {}).get("headers") or [])
    rows = [list(r or []) for r in ((t or {}).get("rows") or [])]
    N = max([len(headers)] + [len(r) for r in rows] + [0])
    if N <= 1:
        return None
    firsts = ([headers[0]] if headers else []) + [r[0] for r in rows if r]
    try:
        base = TS.col_widths(N, None, None, None, firsts)
    except Exception:
        return None
    need = [0] * N
    for r in [headers] + rows:
        for ci, c in enumerate(r[:N]):
            need[ci] = max(need[ci], TS.text_w(c) + TS.CELL_PAD)
    if all(need[i] <= base[i] for i in range(N)):
        return None
    w = [max(TS.MIN_COL_W, x) for x in need]
    slack = TS.TOTAL_W - sum(w)
    if slack < 0:
        return None
    return [x + slack // N for x in w]


def _table_fold(t, ratios=None):
    import math
    try:
        from hwpx_core import tablespec as TS
    except Exception:
        return [], 0
    headers = list((t or {}).get("headers") or [])
    rows = [list(r or []) for r in ((t or {}).get("rows") or [])]
    N = max([len(headers)] + [len(r) for r in rows] + [0])
    if N <= 0:
        return [], 0
    firsts = ([headers[0]] if headers else []) + [r[0] for r in rows if r]
    try:
        widths = TS.col_widths(N, ratios, None, None, firsts)
    except Exception:
        return [], 0
    room = [max(1, w - TS.CELL_PAD) for w in widths]
    folds, extra = [], 0
    for ri, r in enumerate([headers] + rows):
        tall = 1
        for ci, c in enumerate(r[:N]):
            need = TS.text_w(c)
            lines = 1 if need <= room[ci] else int(math.ceil(float(need) / room[ci]))
            if lines > 1:
                folds.append({"row": ri, "col": ci, "text": u"%s" % c,
                              "need": round(need / float(TS.CHAR_W_13PT), 1),
                              "room": round(room[ci] / float(TS.CHAR_W_13PT), 1), "lines": lines})
            tall = max(tall, lines)
        extra += tall - 1
    return folds, extra


def _points(conv_body, tables=None, intent=u""):
    import re
    rows = [len((t or {}).get("rows") or []) + 1 + _table_fold(t, _table_ratios(t))[1] for t in (tables or [])]
    total = 0
    det = {"heading": 0, "line": 0, "table": 0, "image": 0, "lines": 0, "intent": 0}
    itxt = (intent or u"").strip()
    if itxt:
        det["intent"] = _line_pts(len(itxt)) + 1
        total += det["intent"]
    ti = 0
    for ln in (conv_body or u"").splitlines():
        srt = ln.strip()
        if not srt:
            continue
        mk = re.match(u"^\\[(표|이미지)\\d+\\]$", srt)
        if mk:
            if mk.group(1) == u"표":
                n = (rows[ti] if ti < len(rows) else 4) + _PT_TABLE_PAD
                ti += 1
                det["table"] += n
            else:
                n = _PT_IMAGE
                det["image"] += n
        elif re.match(u"^\\d+\\.\\s", srt):
            n = _PT_HEADING
            det["heading"] += n
        else:
            n = _line_pts(len(srt))
            det["line"] += n
            det["lines"] += 1
        total += n
    rest = max(0, total - _PT_FIRST_PAGE)
    det["pages"] = 1 + (rest + _PT_PER_PAGE - 1) // _PT_PER_PAGE
    return total, det


_AIM_BOX = 35
_AIM_DOT = 70

_BAND_LINES = {u"□": 1, u"◦": 2}
_BAND_FILL = {u"□": 30.0 / _PT_LINE_CHARS, u"◦": 28.0 / _PT_LINE_TAIL}


def _band_full(band):
    k = _BAND_LINES.get(band, 1)
    return _PT_LINE_CHARS + (k - 1) * _PT_LINE_TAIL


def _band_floor(band):
    k, full = _BAND_LINES.get(band, 1), _band_full(band)
    for n in range(1, full + 1):
        if _line_pts(n) == k and _tail_fill(n) >= _BAND_FILL[band]:
            return n
    return full


def _tail_fill(n):
    k = _line_pts(n)
    if k <= 1:
        return n / float(_PT_LINE_CHARS)
    return (n - _PT_LINE_CHARS - (k - 2) * _PT_LINE_TAIL) / float(_PT_LINE_TAIL)


_BOX_NAME_MAX = 38
_SCHED_MIN = 3
_SCHED_MAX = 5


_END_MAX_SHARE = 0.20
_END_MIN_ITEMS = 12


def _delta(n, aim):
    d = n - aim
    if d > 0:
        return u"**%d자를 덜어 %d자로 만들어라**" % (d, aim)
    return u"**%d자를 보태 %d자로 만들어라**" % (-d, aim)


_SCHED_PAT = (u"^[(’'~∼\\s]*\\d{2}\\s*(?:"
              u"년(?=\\s*$|\\t|\\s{2}|\\s*(?:\\d{1,2}\\s*월|[상하]반기|[1-4]\\s*분기|초|말|이후|부터))"
              u"\\s*(?:\\d{1,2}\\s*월|[상하]반기|[1-4]\\s*분기|초|말|이후|부터)?"
              u"|[.]\\s*(?:\\d{1,2}\\s*[월.]|[상하]반기|[1-4]\\s*분기|초|말|하|상))"
              u"|^[(~∼\\s]*['’]\\d{2}[.]\\s+\\S")


def _is_sched(t):
    import re
    return bool(re.match(_SCHED_PAT, (t or u"").lstrip(u"-*□◦· \t")))


_SHAPE_DOT_MIN = 2
_SHAPE_FREE = (u"향후계획", u"추진일정", u"행정사항")

_SECS_BY_PAGES = {1: 3, 2: 4, 3: 5, 4: 5, 5: 5}
_SHAPE_VISUAL_PT = 7
_SHAPE_UNIT_PT = 5


def _plan_for(pages):
    try:
        n = int(pages)
    except Exception:
        return None
    if n < 1:
        return None
    secs = _SECS_BY_PAGES.get(n, 5)
    vis = min(n, 12)
    budget = _PT_FIRST_PAGE + (n - 1) * _PT_PER_PAGE
    text = max(0, budget - secs * _PT_HEADING)
    box = max(1, int(round(float(text) / _SHAPE_UNIT_PT)))
    return secs, vis, box, box * _SHAPE_DOT_MIN, budget


_SEC_ROLE = [
    (u"추진배경", 0.6, u""),
    (u"현황",     1.3, u"표"),
    (u"주요내용", 1.8, u"표"),
    (u"추진방안", 1.5, u"표"),
    (u"향후계획", 0.8, u""),
]
_VIS_ALWAYS = (u"주요내용",)


def _plan_rows(pages, secs_want=0):
    got = _plan_for(pages)
    if not got:
        return None
    secs, vis, box, dot, budget = got
    try:
        secs = int(secs_want) or secs
    except Exception:
        pass
    secs = max(2, min(12, secs))
    역할 = _SEC_ROLE[:secs] if secs <= len(_SEC_ROLE) else (
        _SEC_ROLE + [(u"본론", 1.2, u"")] * (secs - len(_SEC_ROLE)))
    역할 = [x for x in 역할 if x[0] != u"향후계획"][:secs - 1] + [_SEC_ROLE[-1]]
    w = sum(x[1] for x in 역할)
    rows, 남은시각물 = [], vis
    for i, (nm, 무게, 종류) in enumerate(역할, 1):
        pt = int(round(budget * 무게 / w))
        시 = 종류 if (종류 and nm != u"향후계획"
                    and (남은시각물 > 0 or nm in _VIS_ALWAYS)) else u""
        if 시:
            남은시각물 -= 1
        b = max(1, int(round((pt - _PT_HEADING - (_TABLE_PT if 시 == u"표" else 0))
                             / float(_SHAPE_UNIT_PT))))
        if nm == u"향후계획":
            rows.append((i, nm, pt, 0,
                         max(_SCHED_MIN, min(_SCHED_MAX, int(pages) if str(pages).isdigit() else 5)),
                         u"일정"))
            continue
        rows.append((i, nm, pt, b, b * _SHAPE_DOT_MIN, 시))
    return rows


def _pages_from_lines(target_lines):
    import re
    n = int(re.sub(r"[^0-9]", "", str(target_lines or "")) or 0)
    return max(1, min(5, int(round(n / 16.0)))) if n else 0


def _pages_pick(spec, target_lines, 저장값=0):
    try:
        n = int(target_lines or 0)
    except Exception:
        n = 0
    if not (1 <= n <= 5):
        n = _pages_from_lines(target_lines)
    if n:
        return n
    try:
        n = int(저장값 or 0)
    except Exception:
        n = 0
    if 1 <= n <= 5:
        return n
    try:
        return int((spec or {}).get("pages") or 0)
    except Exception:
        return 0


def _shape(text):
    import re
    box = dot = tab = img = sched = 0
    in_tab = False
    notes = []
    for ln in (text or u"").split(u"\n"):
        t = ln.strip()
        if not t:
            in_tab = False
            continue
        if t.startswith(u">") or (t[:1] in u"*\u203b" and t[1:2].isspace()):
            notes.append(t)
            in_tab = False
            continue
        if t.startswith(u"|"):
            if not in_tab:
                tab += 1
            in_tab = True
            continue
        in_tab = False
        if u"[이미지" in t or u"[그림" in t:
            img += 1
        elif ln[:1] in u" \t" and t.startswith(u"-"):
            dot += 1
        elif t.startswith(u"-"):
            box += 1
            if _is_sched(t):
                sched += 1
    seen = set(re.findall(u"[A-Z]{2,6}(?![a-zA-Z])", text or u""))
    for n in notes:
        seen -= set(re.findall(u"[A-Z]{2,6}(?![a-zA-Z])", n))
    return {"box": box, "dot": dot, "tab": tab, "img": img,
            "sched": sched, "note": len(notes), "abbr": sorted(seen)}


def _lint_measure(draft="", target_lines="", target_pages="", scope=""):
    import json, re
    try:
        raw = draft if isinstance(draft, str) else (u"" if draft is None else u"%s" % draft)
        try:
            raw = _cut_head(raw)
            if _split_draft(raw)[1]:
                raw, _ = _strip_non_body(raw)
            else:
                raw = u"\n".join(l for l in raw.replace(u"\r\n", u"\n").split(u"\n")
                                 if _is_body_line(l))
        except Exception:
            pass
        rows, _tables = _convert_rows(raw)


        try:
            from hwpx_core.endings import (ending_word as _ending_word,
                                           is_verb_ending as _verb_ending)
        except Exception:
            _ending_word = _verb_ending = None

        HANJA = re.compile(u"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
                           u"\U00020000-\U0002EE5F\U0002F800-\U0002FA1F]")
        POLITE = re.compile(u"(습니다|합니다|입니다|됩니다|하세요|해요|예요|에요|십시오)[.!?)”’\"']*\\s*$")
        DATE_LONG = re.compile(u"\\d{4}\\s*년\\s*\\d{1,2}\\s*월\\s*\\d{1,2}\\s*일")
        HEAD = re.compile(u"^\\d+\\.\\s")
        SCHED = re.compile(_SCHED_PAT)
        LISTED = re.compile(u"^[^:：]{1,12}[:：]\\s?")
        LISTED_MAX = 60
        MARKER_LINE = re.compile(u"^\\[(표|이미지)\\d+\\]$")
        MARKERS = u"□☐◦-*·※"

        v = []
        lenc = {"under": 0, "over": 0}

        def add(src, rule, sev, msg, **extra):
            d = {"rule": rule, "severity": sev, "message": msg,
                 "line": (src or u"")[:200]}
            d.update(extra)
            v.append(d)

        conv = [c.strip() for c, _ in rows]
        srcs = [s for _, s in rows]

        _secof, _cur_sec = [], u"머리"
        for _s in conv:
            if HEAD.match(_s or u""):
                _cur_sec = u"%s단" % _s.split(u".", 1)[0].strip()
            _secof.append(_cur_sec)


        nonempty = [s for s in conv if s]

        for i, s in enumerate(conv):
            if not s or MARKER_LINE.match(s):
                continue
            src = srcs[i]
            rest = s[1:].strip()
            free = bool(SCHED.match(rest) or u"\t" in s
                        or (LISTED.match(rest) and len(s) <= LISTED_MAX))
            band = u"□" if s[0] in u"□☐" else (u"◦" if s[0] == u"◦" else u"")
            if band and not free:
                want = _BAND_LINES[band]
                full = _band_full(band)
                got = _line_pts(len(s))
                if got > want:
                    lenc["over"] += 1
                    add(src, "length", "error",
                        u"%s 줄이 %d줄에 앉는다(%d줄 규격) — %d자. **한 줄 분량을 덜어라**"
                        % (band, got, want, len(s)),
                        n=len(s), band=band, lines=got, want=want, full=full,
                        over=True, sec=_secof[i], text=rest[:80])
                elif got < want or _tail_fill(len(s)) < _BAND_FILL[band]:
                    lenc["under"] += 1
                    add(src, "length", "error",
                        u"%s 줄이 덜 찼다 — %d줄에 %d자(%d줄 %d자면 꽉 찬다). "
                        u"수치·근거·조건을 보태고, 채울 사실이 없으면 지워라"
                        % (band, got, len(s), want, full),
                        n=len(s), band=band, lines=got, want=want, full=full,
                        over=False, sec=_secof[i], text=rest[:80])
        body_lines = len(nonempty)
        _body, _tbl = _convert_md(raw)
        pts, det = _points(_body, _tbl, u"")
        tgt_m = re.search(u"\\d+", u"%s" % (target_lines if target_lines is not None else u""))
        tgt = int(tgt_m.group()) if tgt_m else 0
        if 1 <= tgt <= 8:
            tgt *= 16
        _tp = _pages_arg(target_pages, u"")
        if _tp:
            tgt = _tp * 16
        pages_want = max(1, (tgt + 15) // 16) if tgt else 0
        _상자 = 0
        budget = (_PT_FIRST_PAGE + (pages_want - 1) * _PT_PER_PAGE) if pages_want else 0

        if tgt and nonempty:
            if pts > budget:
                add(u"", "total_length", "warning",
                    u"본문 %s장 — 목표 %d장보다 %s장 많다. "
                    u"조사·군더더기 어절부터 압축하고 그래도 넘치면 항목을 덜어라"
                    % (_pg(pts), pages_want, _pg(pts - budget)))
            elif pts <= budget - _PT_PER_PAGE:
                add(u"", "total_length", "warning",
                    u"본문 %s장 — 목표 %d장에 한 장 넘게 못 미친다. "
                    u"내용을 보태 채워라 — 없는 사실을 지어내지는 마라"
                    % (_pg(pts), pages_want))

        errs = [x for x in v if x["severity"] == "error"]
        warns = [x for x in v if x["severity"] != "error"]
        wrules = {}
        for x in warns:
            wrules[x["rule"]] = wrules.get(x["rule"], 0) + 1

        _넘침 = [x for x in errs if x.get("rule") == "length" and x.get("over")]
        _덜참 = [x for x in errs if x.get("rule") == "length" and x.get("band")
                and not x.get("over")]
        _넘침.sort(key=lambda y: -(y["lines"] - y["want"]))
        _덜참.sort(key=lambda y: y["n"] / float(y["full"]))
        _길이목록 = []
        for x in _넘침 + _덜참:
            _t = (x.get("text") or u"").strip()
            _길이목록.append(u"· %s %s %d/%d — %s"
                          % (x.get("sec") or u"?", x["band"], x["n"], x["full"],
                             _t if len(_t) <= 20 else _t[:20] + u"…"))
        _head = u""
        if _길이목록:
            _head = u"자수가 안 맞는 곳 %d — %s" % (
                len(_길이목록), u" · ".join(
                    u"%s %d~%d자 %d" % (b, _band_floor(b), _band_full(b),
                                       sum(1 for x in _넘침 + _덜참 if x["band"] == b))
                    for b in (u"□", u"◦")
                    if any(x["band"] == b for x in _넘침 + _덜참)))
        _미확인 = raw.count(u"(확인필요)")
        _extra, _pmap, _secpg = [], None, []
        try:
            _ds = _split_draft(raw)[1]
            if len(_ds) >= 2:
                _pmap = _page_map(_ds, start=_상자)
                _extra.append(u"쪽 자리 — " + _page_note(_ds, _pmap))
        except Exception:
            pass
        _접힘 = []
        for _ti, _t in enumerate(_tbl or []):
            for f in _table_fold(_t, _table_ratios(_t))[0]:
                _접힘.append(u"표%d %s %s열 「%s」 %s자 자리에 %s자"
                             % (_ti + 1, (u"머리글" if f["row"] == 0 else u"%d행" % f["row"]),
                                (_t.get("headers") or [u""] * (f["col"] + 1))[f["col"]] if f["col"] < len(_t.get("headers") or []) else f["col"] + 1,
                                f["text"][:20], f["room"], f["need"]))
        if _접힘:
            _extra.append(u"표 셀 접힘 %d — 접힌 행은 두 줄로 세었다 · " % len(_접힘) + u" · ".join(_접힘[:6]))
        _쪽 = det["pages"]
        if _pmap:
            _쪽 = max(_쪽, max(x["end_page"] for x in _pmap))
        det["pages"] = _쪽
        _분량 = (u"분량 %s장" % _pg(pts)) + ((u" / 목표 %d장" % pages_want) if pages_want else u"") \
               + (u" · %d쪽" % _쪽) + (u" · 표 %d개" % len(_tbl or []))
        if _미확인:
            _분량 += u" · (확인필요) %d개" % _미확인
        if scope:
            _단수 = len(_split_draft(raw)[1])
            _무엇 = ((u"%s %d단을" % (scope, _단수)) if _단수
                    else (u"%s(단 머리 없음)%s" % (scope, u"을" if scope.endswith(u"글") else u"를")))
            _첫줄 = u"[기계 검사] %s 조판하면 이렇게 앉는다." % _무엇
        else:
            _첫줄 = u"[기계 검사] 이 문서를 조판하면 이렇게 앉는다."
        note = (_첫줄 + u"\n"
                + _분량
                + u"".join(u"\n" + x for x in _extra)
                + ((u"\n" + _head) if _head else u"")
                + u"".join(u"\n" + x for x in _길이목록))
        payload = json.dumps({"pass": not errs, "error_count": len(errs),
                              "warning_count": len(warns),
                              "warning_rules": wrules,
                              "target_lines": tgt or None,
                              "body_lines": body_lines,
                              "length_under": lenc["under"],
                              "length_over": lenc["over"],
                              "points": pts,
                              "points_budget": budget or None,
                              "est_pages": det["pages"],
                              "page_map": _pmap, "section_pages": _secpg,
                              "unverified": _미확인,
                              "note": note},
                             ensure_ascii=False)
        return payload
    except Exception as e:
        return json.dumps(
            {"pass": True, "lint_unavailable": True, "note": u"",
             "error_count": 0, "warning_count": 0, "warning_rules": {},
             "error": "%s: %s" % (type(e).__name__, e)},
            ensure_ascii=False)


@mcp.tool()
async def view_layout(draft: str = "", key: str = "", target_pages: str = "") -> str:
    """하는 일:
        네가 쓴 글이 쪽에 어떻게 앉나 보여 준다 — 자수와 줄 수, 장수, 표가 쪽 금에 걸리는 곳.
        규칙(종결·한자 등)은 안 본다 — 그건 `check_rules`.
    넘기는 입력:
        draft: 네가 쓴 글 — 이 글을 잰다
        key: [자료 열쇠]를 글자 그대로 넣는다 — 저장본 전체를 잰다(draft 를 안 줄 때)
        target_pages: [목표 분량] — 비우면 목표 대비 없이 장수만 잰다(저장된 값으로 안 떨어진다)
    돌려주는 반환:
        첫 줄이 무엇을 쟀는지 말한다. 이어 분량·쪽 수·표 수, 그리고 쪽 자리 한 줄 —
        `1단 1쪽 · 2단 2쪽(표가 1쪽 끝에 안 들어 2쪽으로 통째로 밀림 — 1쪽 아래 9줄 빔)` 꼴. 표는 쪽 금에서
        쪼개지지 않고 통째로 밀린다 — 셈이 3줄 넘게 넘치면 밀린 것으로 쪽 수에 넣고, 그 안이면 「걸릴 듯」으로만 말한다
        (어림이라 한/글 실측과 한두 줄 어긋날 수 있다). 빈 줄만큼 앞 단을 줄이거나 표를 옮기면 든다.
        표 셀이 열 폭을 넘어 접히는 곳도 한 줄로 — `표1 6행 주제열 「…」 8.3자 자리에 12자`. 열 폭은 파일 도구가 내용에
        맞춰 넓히는 것과 같은 셈이라, 뜨는 접힘은 넓혀도 안 드는 칸이다. 접힌 행은 두 줄로 세어 쪽 수에 든다.
        자수가 안 맞는 줄마다 `· 2단 ◦ 44/70 — 앞머리` — 단 · 밴드 · 자수/꽉 찬 자수.
        자수는 줄 앞 기호 두 칸(`◦ `·`□ `)을 넣어 센다 — [줄 길이]의 30~38·66~70 도 같은 셈이다.
        안 재는 줄 둘 — 연도로 시작하는 일정 줄(`'26. 8월 …`) · 앞 12자 안에 콜론이 있고 60자 이하인 나열 줄
        (`1단계(북부) : 갑동, 을동 …`). 뜬 줄은 모두 [줄 길이] 밖이다.
    """
    import json
    글 = draft if isinstance(draft, str) else (u"" if draft is None else u"%s" % draft)
    범위 = u"받은 글"
    if not 글.strip():
        글 = _read_local_draft(key if isinstance(key, str) else (u"" if key is None else u"%s" % key)) or u""
        범위 = u"저장본 전체"
        if not 글.strip():
            return u"LINT_FAIL: 잴 글이 없다 — draft 가 비었고 key 의 저장본도 없다"
    try:
        j = json.loads(_lint_measure(draft=글, target_pages=target_pages, scope=범위))
    except Exception as e:
        return u"LINT_FAIL: 잴 수 없었다 — %s: %s" % (type(e).__name__, e)
    if j.get("lint_unavailable"):
        return u"LINT_FAIL: 잴 수 없었다 — %s" % (j.get("error") or u"원인 모름")
    return j.get("note") or u""


@mcp.tool()
async def check_rules(key: str = "", draft: str = "") -> str:
    """하는 일:
        저장본 전체를 [문장 규칙]으로 검토한다 — 서술형 종결 · 경어체 · 한자 · 줄 끝 마침표 · 긴 날짜 꼴
        (`2026년 4월 13일`·`2026-04-13` — `'26. 4. 13`·`'26. 8월` 은 통과) · 참고자료에 없는 수치에 (확인필요)가
        없는 곳. 연도로 시작하는 일정 줄은 안 본다. 조판(자수·쪽)은 안 본다 — 그건 `view_layout`.
        흐름과 정합성(단끼리 겹침 · 표와 본문의 수치)은 여기 안 나온다 — 네가 읽어서 짚는다.
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다 — 저장본 전체를 본다
        draft: 이 글을 본다 — 주면 저장본 대신
    돌려주는 반환:
        첫 줄이 무엇을 봤는지 말한다. 걸린 줄마다 `· 2단 ◦ 서술형 종결(있다) — 앞머리`.
        걸린 것이 없으면 「규칙으로 잡힌 것 없음」 한 줄.
    """
    import os, re
    글 = draft if isinstance(draft, str) else (u"" if draft is None else u"%s" % draft)
    범위 = u"받은 글"
    k = _safe_key(key if isinstance(key, str) else (u"" if key is None else u"%s" % key))
    if not 글.strip():
        글 = _read_local_draft(key) or u""
        범위 = u"저장본 전체"
        if not 글.strip():
            return u"REVIEW_FAIL: 볼 글이 없다 — draft 가 비었고 key 의 저장본도 없다"
    try:
        from hwpx_core.endings import ending_word as _ew, is_verb_ending as _ve
    except Exception:
        _ew = _ve = None
    HANJA2 = re.compile(u"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002EE5F\U0002F800-\U0002FA1F]")
    POLITE2 = re.compile(u"(습니다|합니다|입니다|됩니다|하세요|해요|예요|에요|십시오)[.!?)\u201d\u2019\"']*\\s*$")
    DATE2 = re.compile(u"\\d{4}\\s*년\\s*\\d{1,2}\\s*월(\\s*\\d{1,2}\\s*일)?|\\d{4}[-./]\\d{1,2}[-./]\\d{1,2}")
    NUM2 = re.compile(u"\\d[\\d,]*(?:\\.\\d+)?")
    본문, _말 = _cut_tail(_cut_head(글.replace(u"\r\n", u"\n")))
    _pre, secs = _split_draft(본문)
    if not secs:
        secs = [{"no": u"", "name": u"", "text": 본문}]
    refs = u""
    p = _refs_path(k) if k else u""
    if p and os.path.exists(p):
        try:
            refs = open(p, "r", encoding="utf-8").read().replace(u",", u"")
        except Exception:
            refs = u""
    out, n항목 = [], 0
    for sec in secs:
        단 = (u"%s단" % sec["no"]) if sec["no"] else u"머리"
        for ln in sec["text"].split(u"\n"):
            m = re.match(u"^(\\s*)[-*]\\s+(.*\\S)\\s*$", ln)
            if not m or ln.strip().startswith(u"|") or ln.strip().startswith(u">"):
                continue
            t = m.group(2).strip()
            if re.match(u"^\\[(표|이미지)\\d+\\]$", t) or _is_sched(t):
                continue
            급 = u"◦" if len(m.group(1)) >= 2 else u"□"
            t = re.sub(u"\\*\\*", u"", t).strip()
            t = re.sub(u"^\\([^)]*\\)\\s*", u"", t).strip()
            if not t:
                continue
            n항목 += 1
            앞 = t[:22] + (u"…" if len(t) > 22 else u"")
            def hit(rule):
                out.append(u"· %s %s %s — %s" % (단, 급, rule, 앞))
            if POLITE2.search(t):
                hit(u"경어체")
            elif _ve is not None and _ve(t):
                hit(u"서술형 종결(%s)" % (_ew(t) if _ew else u""))
            if re.search(u"[가-힣A-Za-z)]\\.$", t):
                hit(u"줄 끝 마침표")
            if HANJA2.search(t):
                hit(u"한자")
            if DATE2.search(t):
                hit(u"날짜 꼴 — '26. 4. 13 꼴로")
            if refs and u"(확인필요)" not in t:
                없음 = []
                for num in NUM2.findall(t):
                    d = num.replace(u",", u"")
                    if len(d.replace(u".", u"")) >= 2 and not re.match(u"^(19|20)\\d\\d$", d) and d not in refs:
                        없음.append(num)
                if 없음:
                    hit(u"자료에 없는 수치 %s — (확인필요) 없음" % u"·".join(없음[:3]))
    머리 = u"[규칙 검토] %s %d단 %d항목을 봤다 — 종결·경어체·한자·마침표·날짜 꼴%s" % (
        범위, len(secs), n항목, u"·자료에 없는 수치" if refs else u" (참고자료가 없어 수치는 못 봤다)")
    if not out:
        return 머리 + u"\n규칙으로 잡힌 것 없음"
    return 머리 + u"\n" + u"\n".join(out[:80]) + (u"\n(…%d건 더)" % (len(out) - 80) if len(out) > 80 else u"")


@mcp.tool()
async def save_outline(key: str = "", new_text: str = "", title: str = "", purpose: str = "",
                       target_pages: str = "") -> str:
    """하는 일:
        골격 원고를 저장하고 화면에 돌려준다. 본문 저장은 `save_draft`, 파일은 `generate_hwpx_report`.
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다
        new_text: 골격 원고(`## N. 단명` + [내용]·[분량]·[표] 줄)
        title: 보고서 제목 · purpose: 이 보고서가 받으려는 결정 한 줄 · target_pages: 목표 장수 1~5 —
               비우면 지난 값이 남는다
    돌려주는 반환:
        `[draft 저장본](url)` 한 줄 + 골격. 원고 끝 `---` 아래 글(사용자에게 하는 말)은 저장하지 않고 반환 끝에 붙인다.
    """
    return await _patch_draft(key=key, mode=u"OUTLINE", new_text=new_text, title=title,
                              purpose=purpose, target_pages=target_pages)


_TODO_MARK = u"(작성 예정)"


def _is_todo(text):
    return _TODO_MARK in (text or u"")


def _hide_todo_mark(md):
    import re
    out = []
    for ln in (md or u"").split(u"\n"):
        if _TODO_MARK in ln:
            ln = re.sub(u"\\*\\*\\s*\\(작성 예정\\)\\s*\\*\\*\\s*", u"", ln)
            ln = re.sub(u"\\s*\\(작성 예정\\)\\s*", u" ", ln).rstrip()
            if re.match(u"^\\s*[-*]\\s*$", ln):
                continue
        out.append(ln)
    return u"\n".join(out)


def _split_draft(md):
    import re
    text = (md or u"").replace(u"\r\n", u"\n")
    heads = list(re.finditer(u"^##\\s*(\\d+)\\s*[.．]?\\s*(\\S[^\\n]*)$", text, re.M))
    pre = text[:heads[0].start()].strip() if heads else text.strip()
    secs = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        secs.append({"no": m.group(1), "name": m.group(2).strip(),
                     "text": text[m.start():end].strip()})
    return pre, secs


_BODY_OK = None


def _is_body_line(ln):
    import re
    t = (ln or u"").strip()
    if not t:
        return True
    if re.match(u"^##(?!#)", t):
        return True
    if re.match(u"^\\s*[-*]\\s", ln or u""):
        return True
    if t.startswith(u"|"):
        return True
    if t.startswith(u">"):
        return True
    if re.match(u"^\\[(?:이미지|그림)\\s*\\d*\\]$", t):
        return True
    return False


def _strip_non_body(md):
    pre, secs = _split_draft(md or u"")
    _pd = []
    if pre:
        _pk = []
        for _l in pre.split(u"\n"):
            (_pk if _is_body_line(_l) else _pd).append(_l)
        pre = u"\n".join(_pk).strip()
    if not secs:
        keep, drop = [], []
        for ln in (md or u"").split(u"\n"):
            (keep if _is_body_line(ln) else drop).append(ln)
        return u"\n".join(keep).strip(), [d.strip() for d in drop if d.strip()]
    drop = []
    for s in secs:
        keep = []
        for ln in (s.get("text") or u"").split(u"\n"):
            if _is_body_line(ln):
                keep.append(ln)
            else:
                drop.append(ln.strip())
        s["text"] = u"\n".join(keep).strip()
    return _join_draft(pre, secs), [d for d in (drop + _pd) if d and d.strip()]


_NODE_HEADS = (u"쓰기노드", u"수정노드", u"검토노드")


def _cut_head(md):
    import re
    text = (md or u"").replace(u"\r\n", u"\n")
    lines = text.split(u"\n")
    heads = [i for i, l in enumerate(lines)
             if re.match(u"^##\\s*\\d+\\s*[.．]?\\s*\\S", l.strip())]
    if heads and heads[0] > 0:
        return u"\n".join(lines[heads[0]:]).lstrip()
    return text


def _cut_tail(md):
    import re
    text = (md or u"").replace(u"\r\n", u"\n")
    lines = text.split(u"\n")
    heads = [i for i, l in enumerate(lines)
             if re.match(u"^##\\s*\\d+\\s*[.．]?\\s*\\S", l.strip())]
    start = heads[-1] + 1 if heads else 0
    cut = None
    for i in range(len(lines) - 1, start - 1, -1):
        if re.match(u"^([-*_])\\1{2,}$", lines[i].strip()):
            cut = i
            break
    if cut is None:
        return text, u""
    if not any(l.strip() and _is_body_line(l) for l in lines[:cut]):
        return text, u""
    return u"\n".join(lines[:cut]).rstrip(), u"\n".join(lines[cut + 1:]).strip()


def _empty_sections(md):
    import re
    _, secs = _split_draft(md or u"")
    out = []
    for s in secs:
        body = [x for x in (s.get("text") or u"").split(u"\n")
                if re.match(u"^\\s*[-*]\\s", x) or x.strip().startswith(u"|")]
        if not body:
            out.append(u"%s단 %s" % (s.get("no"), s.get("name")))
    return out


def _non_body_line(md):
    import re
    pre, secs = _split_draft(md or u"")
    if not secs:
        secs = [{"text": pre}]
    for s in secs:
        for ln in (s.get("text") or u"").split(u"\n"):
            t = ln.strip()
            if not t or t.startswith(u"##"):
                continue
            if re.match(u"^\\s*[-*]\\s", ln):
                continue
            if t.startswith(u"|") or t.startswith(u">"):
                continue
            if re.match(u"^\\[(?:이미지|그림)\\s*\\d*\\]$", t):
                continue
            if re.match(u"^[-:\\s|]+$", t):
                continue
            return t
    return u""


_FOOT_PAT = u"^\\s*>\\s*(?:\\*\\*)?([^:：]{1,24})(?:\\*\\*)?\\s*[:：]"


def _table_total_gaps(md):
    import re
    숫자 = re.compile(u"^(?:\\*{0,2})\\s*([\\d,]+(?:\\.\\d+)?)\\s*([^\\d*]*?)\\s*(?:\\*{0,2})$")

    def 뜯기(c):
        m = 숫자.match((c or u"").strip())
        if not m:
            return None
        try:
            v = float(m.group(1).replace(u",", u""))
        except ValueError:
            return None
        단위 = m.group(2).strip()
        if u"%" in 단위 or 단위 in (u"년", u"년도"):
            return None
        return v, 단위

    def 소계행(c):
        t = (c or u"").replace(u"*", u"").replace(u" ", u"").strip()
        return t.startswith((u"합계", u"총계", u"소계")) or t in (u"계", u"합")

    말, 블록 = [], []
    단 = [u""]

    def 훑기():
        if len(블록) < 4:
            return
        칸 = [[c.strip() for c in ln.strip().strip(u"|").split(u"|")] for ln in 블록]
        자료 = [r for n, r in enumerate(칸)
               if n and not re.match(u"^[-:\\s]*$", u"".join(r))]
        if len(자료) < 3:
            return
        끝 = 자료[-1]
        if not 소계행(끝[0] if 끝 else u""):
            return
        위 = [r for r in 자료[:-1] if not 소계행(r[0] if r else u"")]
        머리행 = 칸[0] if 칸 else []
        for col in range(1, len(끝)):
            있 = 뜯기(끝[col])
            if not 있:
                continue
            ㅁ = (머리행[col] if col < len(머리행) else u"").replace(u"*", u"")
            if any(x in ㅁ for x in (u"연도", u"년도", u"기간", u"일자", u"연차",
                                     u"비율", u"율(", u"%")):
                continue
            값 = [뜯기(r[col]) for r in 위 if col < len(r) and r[col].strip()]
            값 = [v for v in 값 if v]
            if len(값) < 2 or any(v[1] != 있[1] for v in 값):
                continue
            if not 있[1] and all(v[0] == int(v[0]) and 1900 <= v[0] <= 2100 for v in 값):
                continue
            합 = sum(v[0] for v in 값)
            if abs(합 - 있[0]) > 1e-9:
                말.append(u"%s%s 계산 %g / 적힘 %g"
                          % (단[0] + u" " if 단[0] else u"", ㅁ or (u"열%d" % col), 합, 있[0]))

    for ln in (md or u"").split(u"\n"):
        t = ln.strip()
        if t.startswith(u"|"):
            블록.append(ln)
            continue
        훑기()
        del 블록[:]
        if t.startswith(u"## "):
            m = re.match(u"^##\\s*(\\d+)", t)
            단[0] = (u"%s단" % m.group(1)) if m else u""
    훑기()
    return 말


def _dedup_footnotes(md):
    import re
    본, 버림 = [], []
    seen = set()
    for ln in (md or u"").split(u"\n"):
        m = re.match(_FOOT_PAT, ln)
        if m:
            이름 = m.group(1).strip().strip(u"*").strip()
            key = 이름.lower()
            if key in seen:
                버림.append(이름)
                continue
            seen.add(key)
        본.append(ln)
    return u"\n".join(본), 버림


def _분량줄(row):
    _i, nm, pt, box, dot, 시 = row
    장 = u"약 %s장" % _pg(pt)
    if 시 == u"일정":
        return 장
    return 장 + (u" · 표 하나" if 시 == u"표" else u"")


def _normalize_outline(md, pages=0):
    import re
    if _TODO_MARK not in (md or u"") and u"[내용]" not in (md or u""):
        return md or u"", False
    pre, secs = _split_draft(md or u"")
    if len(secs) < 2:
        return md or u"", False
    몫이름, 몫순서, 쓴 = {}, [], set()
    try:
        for r in (_plan_rows(pages, len(secs)) or []):
            몫순서.append(_분량줄(r))
            몫이름.setdefault(r[1], len(몫순서) - 1)
    except Exception:
        몫이름, 몫순서 = {}, []

    def _몫(i, name):
        j = 몫이름.get((name or u"").strip())
        if j is None or j in 쓴:
            j = i if (i < len(몫순서) and i not in 쓴) else None
        if j is None:
            return u""
        쓴.add(j)
        return 몫순서[j]

    for _i, s in enumerate(secs):
        줄 = (s.get("text") or u"").split(u"\n")
        머리 = 줄[0] if 줄 and 줄[0].lstrip().startswith(u"#") else u""
        요지 = []
        첫줄 = u""
        표제 = u""
        분량값 = None
        for ln in 줄[1:] if 머리 else 줄:
            t = ln.strip()
            if not t or t.startswith(u"#"):
                continue
            벗 = re.sub(u"^[-*]\\s*", u"", t)
            벗 = re.sub(u"\\*\\*", u"", 벗).strip()
            m분 = re.match(u"^\\[분량\\]", 벗)
            if m분:
                _pv, _tv, _ttv = _parse_budget_line(u"- " + 벗)
                if _pv is not None:
                    분량값 = (_pv, _tv, _ttv)
                continue
            m표 = re.match(u"^\\[표\\]\\s*(.+)$", 벗)
            if m표:
                ㅈ = re.sub(u"\\s*[（(][^)）]*[)）]?\\s*$", u"", m표.group(1).strip())
                ㅈ = (ㅈ or m표.group(1)).strip().strip(u"()（） ")
                표제 = 표제 or ㅈ
                continue
            if _TODO_MARK in t or 벗.startswith(u"[내용]"):
                벗 = 벗.replace(_TODO_MARK, u"").strip(u" ·-—:")
                벗 = re.sub(u"^\\[내용\\]\\s*", u"", 벗).strip()
                if 벗:
                    요지.append(벗)
            elif not 첫줄 and not t.startswith((u"|", u">")):
                첫줄 = u"언제 무엇을 할지 일정 줄" if _is_sched(벗) else 벗
        본 = u" · ".join(요지) or 첫줄
        if len(본) > 120:
            잘 = 본[:120].rfind(u" · ")
            본 = 본[:잘] if 잘 > 40 else 본[:120].rstrip()
        본 = re.sub(u"^\\[내용\\]\\s*", u"", 본)
        새 = [머리 or (u"## %s. %s" % (s.get("no", u""), s.get("name", u""))),
             u"- **%s** [내용]%s" % (_TODO_MARK, (u" " + 본) if 본 else u"")]
        if 분량값:
            몫값 = (u"%.1f장" % 분량값[0]) + (u" · 표 하나" if (분량값[1] or 표제) else u"")
            표제 = 표제 or 분량값[2]
        else:
            몫값 = _몫(_i, s.get("name"))
            if 몫값 and 표제 and u"표 하나" not in 몫값:
                몫값 += u" · 표 하나"
        if 몫값:
            if 표제 and u"표 하나" in 몫값:
                ㅈ = 표제 if len(표제) <= 30 else (표제[:29] + u"…")
                몫값 = 몫값.replace(u"표 하나", u"표 하나(%s)" % ㅈ)
            새.append(u"- [분량] %s" % 몫값)
        s["text"] = u"\n".join(새)
    return _join_draft(pre, secs), True


def _bare_only_sections(md, 이름=u""):
    import re
    최상위 = re.compile(u"^[-*]\\s+(.*)$")
    pre, secs = _split_draft(md or u"")
    조각 = secs if secs else [{"name": 이름 or u"이 단", "text": md or u""}]
    나쁜 = []
    for s in 조각:
        줄 = (s.get("text") or u"").split(u"\n")
        맨, 굵, 일정, 표 = 0, 0, 0, 0
        for ln in 줄:
            if ln.lstrip().startswith(u"|"):
                표 += 1
                continue
            if _is_sched(ln.lstrip(u"-*□☐◦ \t")):
                일정 += 1
                continue
            m = 최상위.match(ln)
            if not m:
                continue
            if u"**" in ln:
                굵 += 1
            else:
                맨 += 1
        if 맨 and not 굵 and not 일정 and not 표:
            나쁜.append((u"%s %s" % (s.get("no", u""), s.get("name", u""))).strip()
                       or (이름 or u"이 단"))
    return 나쁜


def _drop_bare_items(md):
    import re
    최상위 = re.compile(u"^[-*]\\s+(.*)$")
    수평선 = re.compile(u"^([-*_])\\1{2,}$")
    pre, secs = _split_draft(md or u"")
    조각 = secs if secs else [{"text": md or u""}]
    버림 = []
    for s in 조각:
        줄 = (s.get("text") or u"").split(u"\n")
        제대로 = sum(1 for ln in 줄
                   if 최상위.match(ln)
                   and ((최상위.match(ln).group(1) or u"").startswith(u"**")
                        or _is_sched(최상위.match(ln).group(1))))
        if not 제대로:
            continue
        남 = []
        for ln in 줄:
            t = ln.strip()
            if 수평선.match(t):
                버림.append(t)
                continue
            m = 최상위.match(ln)
            if m and not (m.group(1) or u"").startswith(u"**") and not _is_sched(m.group(1)):
                버림.append(t)
                continue
            남.append(ln)
        s["text"] = u"\n".join(남).strip()
    if not secs:
        return (조각[0]["text"], 버림)
    return _join_draft(pre, secs), 버림


def _drop_empty_tables(md):
    import re
    줄 = (md or u"").split(u"\n")
    out, i, 버림 = [], 0, 0
    while i < len(줄):
        if not 줄[i].lstrip().startswith(u"|"):
            out.append(줄[i]); i += 1
            continue
        j = i
        while j < len(줄) and 줄[j].lstrip().startswith(u"|"):
            j += 1
        블록 = 줄[i:j]
        칸 = [[c.strip() for c in ln.strip().strip(u"|").split(u"|")] for ln in 블록]
        자료 = [c for c in 칸[1:] if not re.match(u"^[-:\\s]*$", u"".join(c))]
        찬칸 = [v for row in 자료 for v in row[1:]
                if v and v not in (u"-", u"–", u"—", u"·")]
        if not 자료 or not 찬칸:
            버림 += 1
            while out and not out[-1].strip():
                out.pop()
            out.append(u"")
        else:
            out += 블록
        i = j
    return u"\n".join(out), 버림


_TAIL_NAME_MAX = 12


def _fold_box_tail(md):
    import re
    pat = re.compile(u"^([-*]\\s+)\\*\\*([^*]+?)\\*\\*[ \t]*(\\S.*)$")
    out, 접음, 내림 = [], 0, 0
    for ln in (md or u"").split(u"\n"):
        m = pat.match(ln)
        if not m:
            out.append(ln)
            continue
        머리, 이름, 꼬리 = m.group(1), m.group(2).rstrip(), m.group(3).rstrip()
        if u"**" in 꼬리 or u"[이미지" in 꼬리 or u"[그림" in 꼬리:
            out.append(ln)
            continue
        if _TODO_MARK in 이름:
            out.append(ln)
            continue
        꼬리 = re.sub(u"^[\\s—–\\-:·]+", u"", 꼬리).strip()
        if not 꼬리:
            out.append(u"%s**%s**" % (머리, 이름))
            continue
        if re.match(u"^\\(\\s*[^()]{1,10}\\s*\\)$", 이름):
            out.append(u"%s**%s %s**" % (머리, 이름, 꼬리))
            접음 += 1
            continue
        if len(꼬리) <= _TAIL_NAME_MAX:
            out.append(u"%s**%s %s**" % (머리, 이름, 꼬리))
            접음 += 1
        else:
            out.append(u"%s**%s**" % (머리, 이름))
            out.append(u"  - %s" % 꼬리)
            내림 += 1
    return u"\n".join(out), 접음 + 내림


def _join_draft(pre, secs):
    parts = []
    if pre:
        parts.append(pre.strip())
    parts += [(s.get("text") or u"").strip() for s in secs]
    return u"\n\n".join(p for p in parts if p)


def _match_section(secs, want):
    import re
    w = (want or u"").strip()
    w = re.sub(u"^##\\s*", u"", w)
    if not w:
        return None
    m = re.match(u"^(\\d+)\\s*(?:[.．]|단)?", w)
    num = m.group(1) if m and m.group(1) else u""
    name = re.sub(u"^\\d+\\s*(?:[.．]|단)?\\s*", u"", w).strip()
    for s in secs:
        if num and s["no"] == num:
            return s
    for s in secs:
        if name and s["name"] == name:
            return s
    for s in secs:
        if name and (name in s["name"] or s["name"] in name):
            return s
    return None


def _sections_path(k, part=u""):
    import os
    return os.path.join(_draft_dir(), k + ("_outline_sections.json" if part == u"outline" else "_sections.json"))


def _sidecar_read(k, part=u""):
    import json, os
    try:
        p = _sections_path(k, part)
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _renumber(secs):
    import re
    for i, s in enumerate(secs, 1):
        줄 = (s.get("text") or u"").split(u"\n")
        if 줄 and 줄[0].lstrip().startswith(u"#"):
            m = re.match(u"^(#{1,6})", 줄[0].strip())
            우물 = m.group(1) if m else u"##"
            줄[0] = u"%s %d. %s" % (우물, i, (s.get("name") or u"").strip())
        s["text"] = u"\n".join(줄)
        s["no"] = u"%d" % i
    return secs


def _restructure(md, op, section, new_text):
    import re
    o = (op or u"").strip().lower()
    pre, secs = _split_draft(md or u"")
    if len(secs) < 1:
        return None, u"단으로 분해되지 않는 초안이라 구조를 못 고친다"
    nt = (new_text or u"").strip()

    if o == u"insert":
        if not nt:
            return None, u"insert 에는 new_text 에 **새 단 이름**이 있어야 한다"
        새 = {"no": u"0", "name": nt,
              "text": u"## 0. %s\n- **%s** [내용] (사용자와 정할 자리)" % (nt, _TODO_MARK)}
        if section.strip():
            hit = _match_section(secs, section)
            if hit is None:
                return None, u"'%s' 에 맞는 단이 없다" % section
            secs.insert(secs.index(hit), 새)
        else:
            secs.append(새)
        알림 = u"`%s` 단을 넣었다" % nt

    elif o == u"move":
        hit = _match_section(secs, section)
        if hit is None:
            return None, u"'%s' 에 맞는 단이 없다" % section
        try:
            자리 = int(re.sub(u"[^0-9]", u"", nt) or 0)
        except Exception:
            자리 = 0
        if not 1 <= 자리 <= len(secs):
            return None, u"갈 자리를 1~%d 로 줘라(받은 값 '%s')" % (len(secs), nt)
        이름 = hit.get("name")
        secs.remove(hit)
        secs.insert(자리 - 1, hit)
        알림 = u"`%s` 를 %d번으로 옮겼다" % (이름, 자리)

    elif o == u"rename":
        hit = _match_section(secs, section)
        if hit is None:
            return None, u"'%s' 에 맞는 단이 없다" % section
        if not nt:
            return None, u"rename 에는 new_text 에 **새 이름**이 있어야 한다"
        옛 = hit.get("name")
        hit["name"] = nt
        알림 = u"`%s` 를 `%s` 로 바꿨다" % (옛, nt)

    elif o == u"merge":
        고를 = [x.strip() for x in re.split(u"[,·\\s]+", section or u"") if x.strip()]
        맞 = [_match_section(secs, x) for x in 고를]
        if len(맞) < 2 or any(x is None for x in 맞):
            return None, u"merge 는 section 에 단 둘 이상을 줘라(예: '2,3')"
        머 = 맞[0]
        몸 = []
        for x in 맞[1:]:
            줄 = (x.get("text") or u"").split(u"\n")
            몸 += [l for l in (줄[1:] if 줄 and 줄[0].lstrip().startswith(u"#") else 줄)]
            secs.remove(x)
        머["text"] = (머.get("text") or u"").rstrip() + u"\n" + u"\n".join(몸).strip()
        if nt:
            머["name"] = nt
        알림 = u"%s 를 `%s` 로 합쳤다" % (u"·".join(x.get("name") or u"?" for x in 맞),
                                     머.get("name"))
    else:
        return None, u"모르는 op '%s' — insert·move·rename·merge 중 하나다" % op

    _renumber(secs)
    return _join_draft(pre, secs), 알림


def _strip_outline_marks(md):
    import re
    빈 = []
    줄 = []
    이름 = u""
    본있 = False
    for ln in (md or u"").split(u"\n"):
        t = ln.strip()
        m = re.match(u"^#{1,6}\\s*\\d*\\.?\\s*(.*)$", t)
        if m and t.startswith(u"#"):
            if 이름 and not 본있:
                빈.append(이름)
            이름, 본있 = m.group(1).strip(), False
            줄.append(ln)
            continue
        벗 = re.sub(u"\\*\\*", u"", re.sub(u"^[-*]\\s*", u"", t)).strip()
        벗 = re.sub(u"^\\(작성 예정\\)\\s*", u"", 벗).strip()
        if re.match(u"^\\[(내용|분량|표)\\]", 벗):
            continue
        if t:
            본있 = True
        줄.append(ln.replace(_TODO_MARK, u"").replace(u"**** ", u""))
    if 이름 and not 본있:
        빈.append(이름)
    끝 = u"\n".join(줄)
    끝 = re.sub(u"\n{3,}", u"\n\n", 끝)
    return 끝, 빈


def _outline_brief(text):
    import re
    for ln in (text or u"").split(u"\n"):
        t = ln.strip()
        if not t or t.startswith(u"#"):
            continue
        벗 = re.sub(u"^[-*]\\s*", u"", t)
        벗 = re.sub(u"\\*\\*", u"", 벗).strip()
        벗 = re.sub(u"^\\(작성 예정\\)\\s*", u"", 벗).strip()
        m = re.match(u"^\\[내용\\]\\s*(.*)$", 벗)
        if m:
            v = m.group(1).strip()
            return v[:120] if len(v) > 120 else v
    return u""


def _re_outline_tag(tag, text):
    import re
    pat = re.compile(u"^\\s*[-*]\\s*(?:\\*\\*)?(?:\\(작성 예정\\))?\\s*(?:\\*\\*)?\\s*"
                     u"\\[%s\\]" % re.escape(tag), re.M)
    return pat.findall(text or u"")


def _spec_of(pages):
    try:
        n = int(pages)
    except Exception:
        return None
    rows = _plan_rows(n) if n > 0 else None
    if not rows:
        return None
    return {"pages": n,
            "sections": [{"no": r[0], "name": r[1], "pt": r[2],
                          "box": r[3], "dot": r[4], "vis": r[5]} for r in rows]}


def _sidecar_write(k, draft, memo=None, spec=None, part=u""):
    import json, time
    try:
        old = None
        keep = u""
        if not memo or not spec:
            old = _sidecar_read(k, part) or {}
        if not memo:
            keep = old.get("memo", u"") or u""
        if not spec:
            spec = old.get("spec") or None
        pre, secs = _split_draft(draft)
        data = {"v": 1, "ts": int(time.time()),
                "memo": (memo or keep) or u"",
                "whole": len(secs) < 2,
                "sections": [{"no": s["no"], "name": s["name"],
                              "chars": len(s["text"]),
                              "todo": _is_todo(s["text"])} for s in secs],
                "spec": spec}
        with open(_sections_path(k, part), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    except Exception:
        return None


def _versions_path(k):
    import os
    return os.path.join(_draft_dir(), k + "_versions.json")


def _versions_read(k):
    import json, os
    try:
        p = _versions_path(k)
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _snapshot(d, k, draft, part=u"", kind=u"", spec=None):
    import json, os, time
    try:
        vs = _versions_read(k)
        n = len(vs) + 1
        fn = k + (("_outline_v%d.md" if part == u"outline" else "_v%d.md") % n)
        with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
            f.write(draft)
        try:
            _b, _t = _convert_md(draft)
            _pts, _ = _points(_b, _t, u"")
        except Exception:
            _pts = 0
        vs.append({"v": n, "ts": int(time.time()),
                   "kind": kind or (u"골격" if part == u"outline" else u"채움"),
                   "part": part or u"draft", "chars": len(draft), "pages": _pg(_pts)})
        with open(_versions_path(k), "w", encoding="utf-8") as f:
            json.dump(vs, f, ensure_ascii=False)
    except Exception:
        pass


def _store_draft(draft, key=u"", memo=u"", spec=None, part=u"", kind=u""):
    import os, time, tempfile
    try:
        if not (draft and draft.strip()):
            return u"SAVE_FAIL: draft 가 비어 있다"

        k = _safe_key(key)
        if k:
            try:
                d = _draft_dir()
                _sweep_drafts(d)
                _fn = k + ("_outline.md" if part == u"outline" else ".md")
                with open(os.path.join(d, _fn), "w", encoding="utf-8") as f:
                    f.write(draft)
                _snapshot(d, k, draft, part, kind, spec)
            except Exception:
                pass
            try:
                _sp2 = _spec_from_outline_text(draft, spec) if part == u"outline" else _spec_from_outline(key, spec)
                if _sp2:
                    spec = _sp2
            except Exception:
                pass
            _sidecar_write(k, draft, memo, spec, part)

        import requests
        host = os.getenv("LLMOPS_CDN_API_SERVICE_SERVICE_HOST", "llmops-cdn-api-service")
        port = os.getenv("LLMOPS_CDN_API_SERVICE_SERVICE_PORT", "8080")
        up = "http://%s:%s/minio/upload/temp" % (host, port)
        public_host = os.getenv("HWPX_PUBLIC_HOST", "")
        fn = "draft_%d.md" % int(time.time())
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as f:
            path = f.name
            f.write(draft)
        try:
            with open(path, "rb") as f:
                files = {"file": (fn, f, "text/markdown")}
                resp = requests.post(up, data={"hostname": public_host},
                                     files=files, timeout=30)
            if resp.status_code >= 400:
                return u"SAVE_FAIL: HTTP %s %s" % (resp.status_code,
                                                   (resp.text or "")[:300])
            try:
                return resp.json()["data"]["presigned_url"]
            except Exception as parse:
                return u"SAVE_FAIL: 응답 해석 실패(%s) body=%s" % (
                    type(parse).__name__, (resp.text or "")[:300])
        finally:
            os.unlink(path)
    except Exception as e:
        return u"SAVE_FAIL: %s: %s" % (type(e).__name__, e)

def _state_path(k):
    import os
    return os.path.join(_draft_dir(), k + "_state.json")


_STATE_KEYS = (u"title", u"purpose", u"target_pages", u"review")


def _state_read(k):
    import json, os
    out = {x: u"" for x in _STATE_KEYS}
    if not k:
        return out
    try:
        p = _state_path(k)
        if not os.path.exists(p):
            return out
        with open(p, "r", encoding="utf-8") as f:
            old = json.load(f) or {}
        for x in _STATE_KEYS:
            v = old.get(x)
            if isinstance(v, str) and v.strip():
                out[x] = v
    except Exception:
        pass
    return out


def _state_write(k, **값):
    import json
    st = _state_read(k)
    for x in _STATE_KEYS:
        v = 값.get(x)
        if isinstance(v, str) and v.strip():
            st[x] = v.strip() if x != u"review" else v.rstrip()
    if not k:
        return st
    try:
        with open(_state_path(k), "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        pass
    return st


def _state_pages(k):
    import re
    try:
        n = int(re.sub(r"[^0-9]", "", _state_read(k).get(u"target_pages") or u"") or 0)
    except Exception:
        return 0
    return n if 1 <= n <= 5 else 0


@mcp.tool()
async def save_state(key: str = "", title: str = "", purpose: str = "",
                     target_pages: str = "", review: str = "", text: str = "") -> str:
    """하는 일:
        이 대화의 값(제목·목적·분량)과 검토 목록을 저장하고, 받은 글을 그대로 돌려준다.
        원고는 안 건드린다 — 본문은 `save_draft`, 골격은 `save_outline`.
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다
        title: 보고서 제목. 비우면 지난 값이 남는다 — 아래 셋도 같다
        purpose: 이 보고서가 받으려는 결정 한 줄
        target_pages: 목표 장수 1~5
        review: 검토 턴에 쓴 지적 목록 — 다음 턴 [검토]로 온다
        text: 화면에 낼 글
    돌려주는 반환:
        `text` 그대로. 저장했다는 말을 덧붙이지 않는다.
    """
    try:
        _state_write(_safe_key(key), title=title, purpose=purpose,
                     target_pages=target_pages, review=review)
    except Exception:
        pass
    return text if isinstance(text, str) else (u"" if text is None else u"%s" % text)


def _read_local_draft(key, part=u""):
    import os
    k = _safe_key(key)
    if not k:
        return None
    try:
        p = os.path.join(_draft_dir(), k + ("_outline.md" if part == u"outline" else ".md"))
        if os.path.exists(p) and os.path.getsize(p) <= _DRAFT_MAX:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
            if txt.strip():
                return txt
    except Exception:
        pass
    return None


def _fetch_draft_url(url):
    import os
    try:
        from urllib.parse import urlsplit
        u = (url or "").strip()
        if not u or u.startswith(u"SAVE_FAIL"):
            return None, None
        public_host = os.getenv("HWPX_PUBLIC_HOST", "")
        host = os.getenv("LLMOPS_CDN_API_SERVICE_SERVICE_HOST", "llmops-cdn-api-service")
        parts = urlsplit(u)
        allow = urlsplit(public_host)
        ok_hosts = {h for h in (allow.hostname, host) if h}
        if parts.scheme not in ("http", "https"):
            return None, u"허용되지 않은 프로토콜(%s)" % (parts.scheme or "없음")
        if parts.hostname not in ok_hosts:
            return None, u"허용되지 않은 주소(%s)" % (parts.hostname or "없음")
        if allow.port and parts.hostname == allow.hostname and parts.port != allow.port:
            return None, u"허용되지 않은 포트(%s)" % (parts.port or "기본")
        import requests
        r = requests.get(u, timeout=30, allow_redirects=False, stream=True)
        r.raise_for_status()
        MAX = _DRAFT_MAX
        raw = r.raw.read(MAX + 1, decode_content=True) or b""
        if len(raw) > MAX:
            return None, u"초안이 너무 큽니다(%dMB 초과)" % (MAX // (1024 * 1024))
        return raw.decode("utf-8", "replace"), None
    except Exception as e:
        return None, u"%s: %s" % (type(e).__name__, e)


@mcp.tool()
async def load_draft(url: str = "", key: str = "", part: str = "") -> str:
    """하는 일:
        직전 초안을 회수한다 — 기본은 원문 통째.
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다
        part: 비우면 본문 통째 · "outline"=골격 · "meta"=섹션 목록 JSON ·
              "3"/"추진방안"=그 단 원문만
        url: key 로 사본을 못 찾을 때의 폴백 — 초안 저장본 주소
    돌려주는 반환:
        초안 원문. `part="meta"` 면 JSON 이다.
        직전 초안이 없으면 빈 글, 실패는 `LOAD_FAIL: 원인`.
    """
    return _load_draft(url, key, part)


def _sec_pts(text):
    try:
        _b, _t = _convert_md(text or u"")
        return _points(_b, _t, u"")[0]
    except Exception:
        return 0


def _parse_budget_line(text):
    import re
    pages, table, title = None, False, u""
    for ln in (text or u"").split(u"\n"):
        t = re.sub(u"^\\s*[-*]\\s*", u"", ln.strip()).replace(u"**", u"")
        m = re.match(u"^\\[분량\\]\\s*(?:약\\s*)?([0-9]+(?:\\.[0-9]+)?)\\s*장(.*)$", t)
        if m:
            try:
                pages = float(m.group(1))
            except Exception:
                pages = None
            rest = m.group(2) or u""
            if u"표" in rest:
                table = True
                mt = re.search(u"표\\s*하나\\s*[（(]([^)）]*)[)）]", rest)
                if mt:
                    title = title or mt.group(1).strip()
            continue
        m2 = re.match(u"^\\[표\\]\\s*(.+)$", t)
        if m2:
            table = True
            title = title or m2.group(1).strip()
    return pages, table, title


def _page_map(secs, start=0.0):
    cum, out = float(start or 0), []
    for s in secs:
        start = cum
        blocks, cur = [], []
        for ln in (s.get("text") or u"").split(u"\n"):
            if ln.lstrip().startswith(u"|"):
                cur.append(ln)
                continue
            if cur:
                blocks.append((True, u"\n".join(cur)))
                cur = []
            if ln.strip():
                blocks.append((False, ln))
        if cur:
            blocks.append((True, u"\n".join(cur)))
        tables = []
        for is_tab, b in blocks:
            p = float(_sec_pts(b))
            if is_tab:
                ts, te = cum, cum + p
                sp = int(ts / _PT_DISP) + 1
                ep = int(max(te - 1e-6, ts) / _PT_DISP) + 1
                pushed = 0
                moved = False
                if ep != sp and p <= _PT_DISP and (te - sp * _PT_DISP) >= 3:
                    pushed = int(round(sp * _PT_DISP - ts))
                    moved = True
                    cum = sp * _PT_DISP
                    ts, te = cum, cum + p
                    sp = int(ts / _PT_DISP) + 1
                    ep = int(max(te - 1e-6, ts) / _PT_DISP) + 1
                tables.append({"start_page": sp, "end_page": ep,
                               "over": int(round(te - sp * _PT_DISP)) if ep != sp else 0,
                               "pushed": pushed, "moved": moved})
            cum += p
        out.append({"start_page": int(start / _PT_DISP) + 1,
                    "end_page": int(max(cum - 1e-6, start) / _PT_DISP) + 1,
                    "start": round(start / _PT_DISP, 2), "end": round(cum / _PT_DISP, 2),
                    "tables": tables})
    return out


def _page_note(secs, pmap):
    bits = []
    for s, p in zip(secs, pmap):
        쪽 = (u"%d쪽" % p["start_page"]) if p["start_page"] == p["end_page"] \
            else (u"%d~%d쪽" % (p["start_page"], p["end_page"]))
        밀 = [t for t in p["tables"] if t.get("moved")]
        걸 = [t for t in p["tables"] if t["start_page"] != t["end_page"]]
        if 밀:
            tag = (u"(표가 %d쪽 끝에 안 들어 %d쪽으로 통째로 밀림 — %d쪽 아래 %d줄 빔)"
                   % (밀[0]["start_page"] - 1, 밀[0]["start_page"], 밀[0]["start_page"] - 1, 밀[0]["pushed"]))
        elif 걸:
            tag = (u"(표가 %d쪽 끝에 걸릴 듯, %d줄 — 넘치면 통째로 %d쪽으로 밀린다)"
                   % (걸[0]["start_page"], 걸[0]["over"], 걸[0]["start_page"] + 1))
        elif p["tables"]:
            tag = u"(표)"
        else:
            tag = u""
        bits.append(u"%s단 %s%s" % (s.get("no") or u"?", 쪽, tag))
    return u" · ".join(bits)


def _compare_outline(secs, ometa):
    rows, diff = [], []
    by_no = {str(x.get("no")): x for x in (ometa or [])}
    for s in secs:
        tx = s.get("text") or u""
        pg = _sec_pts(tx) / _PT_DISP
        has_tab = any(ln.lstrip().startswith(u"|") for ln in tx.split(u"\n"))
        o = by_no.get(str(s.get("no"))) or {}
        rows.append({"no": s.get("no"), "name": s.get("name"), "pages": round(pg, 2), "table": has_tab,
                     "outline_pages": o.get("pages"), "outline_table": bool(o.get("table"))})
        if not o:
            continue
        if o.get("pages") is not None and abs(pg - o["pages"]) > 0.25:
            diff.append(u"%s단 %.1f장(골격 %.1f장)" % (s.get("no"), pg, o["pages"]))
        if o.get("table") and not has_tab:
            diff.append(u"%s단 표 없음(골격 표 하나)" % s.get("no"))
    return rows, diff


def _spec_from_outline_text(md, base=None):
    try:
        _p, secs = _split_draft(md or u"")
    except Exception:
        return None
    rows = []
    합 = 0.0
    for s in secs:
        pg, tb, _tt = _parse_budget_line(s.get("text") or u"")
        if pg is None:
            continue
        합 += pg
        rows.append({"no": s.get("no"), "name": s.get("name"),
                     "pt": int(round(pg * _PT_DISP)), "vis": u"표" if tb else u""})
    if not rows:
        return None
    n = 0
    try:
        n = int((base or {}).get("pages") or 0)
    except Exception:
        n = 0
    return {"pages": n or int(round(합)) or None, "sections": rows}


def _spec_from_outline(key, base=None):
    try:
        o = _read_local_draft(key, u"outline")
    except Exception:
        o = u""
    return _spec_from_outline_text(o, base) if o else None


def _outline_meta(key):
    try:
        o = _read_local_draft(key, u"outline")
        if not o:
            return False, []
        _p, secs = _split_draft(o)
        out = []
        for s in secs:
            pg, tb, tt = _parse_budget_line(s["text"])
            out.append({"no": s["no"], "name": s["name"], "brief": _outline_brief(s["text"]),
                        "pages": pg, "table": tb, "table_title": tt})
        return True, out
    except Exception:
        return False, []


def _load_draft(url=u"", key=u"", part=u""):
    import json
    part = part if isinstance(part, str) else (u"" if part is None else u"%s" % part)
    want = (part or u"").strip().lower()
    if want == u"outline":
        o = _read_local_draft(key, u"outline")
        return o if o else u"LOAD_FAIL: 골격이 없다 — 먼저 OUTLINE 으로 골격을 그려라"
    md = _read_local_draft(key)
    err = None
    if md is None:
        md, err = _fetch_draft_url(url)

    if not want:
        if md is not None:
            return md
        return (u"LOAD_FAIL: %s" % err) if err else u""

    _o = _outline_meta(key)
    if md is None:
        if want == u"meta":
            return json.dumps({"exists": False, "sections": [], "memo": u"",
                               "chars": 0, "whole": False,
                               "outline_exists": _o[0], "outline_sections": _o[1],
                               "note": (u"회수 실패: %s" % err) if err
                                       else u"직전 초안 없음"},
                              ensure_ascii=False)
        return u"LOAD_FAIL: 직전 초안이 없다%s" % ((u" (%s)" % err) if err else u"")
    pre, secs = _split_draft(md)
    if want == u"meta":
        side = _sidecar_read(_safe_key(key)) or {}
        _pm = _page_map(secs)
        try:
            _pts, _det = _points(_convert_md(md)[0],
                                 _convert_md(md)[1], u"")
        except Exception:
            _pts, _det = 0, {"pages": 0}
        return json.dumps({"exists": True,
                           "sections": [{"no": s["no"], "name": s["name"],
                                         "chars": len(s["text"]),
                                         "todo": _is_todo(s["text"]),
                                         "brief": _outline_brief(s["text"]),
                                         "pts": _sec_pts(s["text"]),
                                         "pages_at": _pm[_i] if _i < len(_pm) else None,
                                         "shape": _shape(s["text"])}
                                        for _i, s in enumerate(secs)],
                           "memo": side.get("memo", u"") or u"",
                           "spec": side.get("spec") or None,
                           "chars": len(md),
                           "points": _pts, "pages": _det.get("pages", 0),
                           "outline_exists": _o[0], "outline_sections": _o[1],
                           "whole": len(secs) < 2}, ensure_ascii=False)
    hit = _match_section(secs, part)
    if hit is not None:
        return hit["text"]
    return (u"LOAD_FAIL: '%s' 에 맞는 단이 없다 — 있는 단: %s"
            % ((part or u"")[:40],
               u", ".join(u"%s %s" % (s["no"], s["name"]) for s in secs) or u"없음"))


_FIX_FIND = u"FIND:"
_FIX_REPL = u"REPL:"
_FIXES_STRICT = False


def _parse_fixes(raw):
    import json
    text = raw if isinstance(raw, str) else (u"" if raw is None else u"%s" % raw)
    text = text.replace(u"\\n", u"\n").strip()
    if not text:
        return []
    if text[:1] in u"[{":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = [data]
            out = []
            for x in data or []:
                f = (x.get("find") or x.get("from") or u"").strip()
                r = (x.get("replace") or x.get("to") or u"").strip()
                if f and r:
                    out.append((f, r))
            return out
        except Exception:
            pass
    pairs, pending = [], None
    for ln in text.splitlines():
        t = ln.strip()
        if t.upper().startswith(_FIX_FIND):
            pending = t[len(_FIX_FIND):].strip()
        elif t.upper().startswith(_FIX_REPL):
            r = t[len(_FIX_REPL):].strip()
            if pending and r:
                pairs.append((pending, r))
            pending = None
    return pairs


def _apply_fixes(md, pairs):
    lines = (md or u"").replace(u"\r\n", u"\n").split(u"\n")
    used, missed, hit = set(), [], 0
    for find, repl in pairs:
        f = find.strip()
        done = False
        for i, ln in enumerate(lines):
            if i in used or ln.strip() != f:
                continue
            indent = ln[:len(ln) - len(ln.lstrip())]
            lines[i] = indent + repl.strip()
            used.add(i)
            hit += 1
            done = True
            break
        if not done:
            missed.append(f[:60])
    return u"\n".join(lines), hit, missed


_SAVE_FAIL = u"저장하지 못했습니다"
_뺀까닭_메모 = u"굵은 항목도 일정 줄도 없어 개조식 본문으로 볼 수 없었습니다"
_뺀까닭_빈 = u"개조식 본문 줄이 하나도 없었습니다"


def _저장못함(까닭, 다음=u""):
    return u"%s — %s.%s" % (_SAVE_FAIL, 까닭, (u" %s." % 다음) if 다음 else u"")


def _은는(말):
    c = ord((말 or u" ")[-1])
    if not 0xAC00 <= c <= 0xD7A3:
        return u"은(는)"
    return u"은" if (c - 0xAC00) % 28 else u"는"


def _단들(이름들):
    import re
    out = []
    for x in 이름들:
        m = re.match(u"^\\s*(\\d+)", x or u"")
        out.append((u"%s단" % m.group(1)) if m else (x or u"이 단"))
    return u"·".join(out)


def _단_빼기(md, 이름들, section):
    import re
    if not (section or u"").strip():
        return md, None
    pre, secs = _split_draft(md or u"")
    번호 = set()
    for x in 이름들:
        m = re.match(u"^\\s*(\\d+)", x or u"")
        if not m:
            return md, None
        번호.add(m.group(1))
    남 = [s for s in secs if s["no"] not in 번호]
    뺀 = [s for s in secs if s["no"] in 번호]
    if len(secs) < 2 or not 남 or not 뺀:
        return md, None
    return _join_draft(pre, 남), [u"%s단 %s" % (s["no"], s["name"]) for s in 뺀]


@mcp.tool()
async def save_draft(key: str = "", section: str = "", new_text: str = "",
                      fixes: str = "", url: str = "",
                      target_lines: str = "", op: str = "",
                      target_pages: str = "", mode: str = "",
                      title: str = "", purpose: str = "", review: str = "") -> str:
    """하는 일:
        네가 쓴 단을 저장본에 갈아 끼워 저장하고 화면에 돌려준다. 부분 수정의 심장이다 — 온 단은 다 갈아 끼우고,
        안 온 단은 글자 그대로 보존한다. 고치는 건 네가 한다(고친 단을 써서 넘긴다) — 도구는 저장만 한다.
        골격 저장은 `save_outline`, 값·검토 목록은 `save_state`.
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다
        section: 갈아 끼울 단 번호. 여럿이면 쉼표("2,4"). 단명("추진방안")·헤더 원문("## 3. 추진방안")도 받는다
        new_text: 그 단(들)의 원고 — `## N. 단명` 헤더로 시작하는 마크다운. 단 하나를 줄 때 헤더 줄을 빼면 기존 헤더를 지켜 붙인다
                  저장본이 아직 없으면(골격 없이 첫 저장) 낸 단이 곧 문서가 된다
        title: 보고서 제목 · purpose: 이 보고서가 받으려는 결정 한 줄 · target_pages: 목표 장수 1~5 —
               비우면 지난 값이 남는다(이 대화의 값으로 함께 남는다)
    돌려주는 반환:
        `[draft 저장본](url)` 한 줄 + 빈 줄 + 낸 단(들). 원고 아닌 줄을 덜어 냈으면 기계 알림 한 줄이 뒤에 붙는다 —
        원고 아닌 줄 = 첫 `## N.` 앞의 글 · 굵은 말머리도 일정 줄도 아닌 최상위 `- ` 줄(작업 메모) · 같은 용어의 둘째 각주 ·
        값이 하나도 없는 표.
        원고 끝 `---` 한 줄 아래 글(사용자에게 하는 말)은 저장하지 않고 반환 끝에 `---` 아래 그대로 붙인다.
        여러 단 저장에서 일부 단만 튕기면 그 단만 빼고 저장하고 `(5단 향후계획은 저장하지 않았습니다 — …)` 한 줄,
        통째로 튕기면 `저장하지 못했습니다 — 까닭. 사용자가 할 수 있는 것.` 한 줄 — 사람에게 하는 말이다.
    """
    return await _patch_draft(key=key, section=section, new_text=new_text, fixes=fixes, url=url, target_lines=target_lines, op=op, target_pages=target_pages, mode=mode, title=title, purpose=purpose, review=review)


async def _patch_draft(key: str = "", section: str = "", new_text: str = "",
                      fixes: str = "", url: str = "",
                      target_lines: str = "", op: str = "",
                      target_pages: str = "", mode: str = "",
                      title: str = "", purpose: str = "", review: str = "") -> str:
    try:
        section = section if isinstance(section, str) else (
            u"" if section is None else u"%s" % section)
        new_text = new_text if isinstance(new_text, str) else (
            u"" if new_text is None else u"%s" % new_text)
        op = (op if isinstance(op, str) else u"").strip().lower()
        _mode = (mode if isinstance(mode, str) else u"").strip().upper()
        _pages = _pages_arg(target_pages, target_lines)
        _k = _safe_key(key)
        review = _cut_tail(review if isinstance(review, str) else u"")[0] if review else review
        _state_write(_k, title=title, purpose=purpose,
                     target_pages=(u"%d" % _pages) if _pages else u"", review=review)
        if _mode in (u"OUTLINE", u"WRITE"):
            section = u""
        elif _mode == u"EDIT" and not section.strip():
            return _저장못함(u"고칠 단이 정해지지 않았습니다", u"몇 단을 고칠지 말해 주면 그 단을 고칩니다")

        if op:
            옛 = _read_local_draft(key)
            if 옛 is None:
                옛, _e = _fetch_draft_url(url)
            if not (옛 or u"").strip():
                return _저장못함(u"아직 초안이 없습니다", u"본문을 써 달라고 하면 새로 씁니다")
            새글, 알림 = _restructure(옛, op, section, new_text)
            if 새글 is None:
                return _저장못함(알림)
            res = _store_draft(새글, key, u"",
                               _spec_of(_pages_pick(
                                   (_sidecar_read(_k) or {}).get("spec"),
                                   _pages, _state_pages(_k))), kind=u"구조 %s" % op)
            머 = (u"[draft 저장본](%s)" % res
                 if isinstance(res, str) and res.startswith(u"http")
                 else u"(draft 저장본 링크 없음 — 대화 열쇠로 회수됩니다)")
            return u"%s — %s\n\n%s" % (머, 알림, _hide_todo_mark(새글))

        if not (new_text and new_text.strip()):
            return _저장못함(u"받은 원고가 비어 있었습니다", u"다시 써 달라고 하면 새로 씁니다")

        nt = new_text.replace(u"\r\n", u"\n").replace(u"\\n", u"\n").strip()
        nt, 말 = _cut_tail(nt)
        말꼬리 = (u"\n\n---\n" + 말) if 말 else u""

        if _mode == u"REVIEW":
            return nt + 말꼬리

        _lines = [x.strip() for x in nt.split(u"\n") if x.strip()]
        _본문 = [x for x in _lines if not x.startswith(u"#")]
        if _본문 and not any(x.startswith((u"-", u"|", u"[", u">")) for x in _본문):
            return _저장못함(u"받은 글에 개조식 항목 줄이 하나도 없어 원고로 볼 수 없었습니다",
                            u"다시 써 달라고 하면 새로 씁니다")

        import re as _re2
        nt = _cut_head(nt)
        _줄 = nt.split(u"\n")
        _머리 = 0
        for _x in _줄:
            _t = _x.strip()
            if _t and _re2.match(u"^([-*_])\\1{2,}$", _t):
                _머리 += 1
                continue
            if _t and _re2.match(u"^\\[(?:이미지|그림)\\s*\\d*\\]$", _t):
                break
            if _t and _t.startswith((u"#", u"-", u"|", u">", u"*")):
                break
            _머리 += 1
        else:
            _머리 = 0
        if _머리:
            nt = u"\n".join(_줄[_머리:]).lstrip()


        nt, _버린 = _strip_non_body(nt)
        _골격 = False
        if not section.strip():
            _장 = _pages_pick((_sidecar_read(_k) or {}).get("spec"),
                              _pages, _state_pages(_k))
            nt, _골격 = _normalize_outline(nt, _장)
        if _mode == u"OUTLINE":
            _골격 = True
        _뺀단 = []
        _메모단 = [] if _골격 else _bare_only_sections(nt, section.strip())
        if _메모단:
            nt, _뺀 = _단_빼기(nt, _메모단, section)
            if _뺀 is None:
                return _저장못함(u"%s이 개조식 본문 꼴이 아닙니다(굵은 항목도 일정 줄도 없음)" % _단들(_메모단),
                                u"다시 써 달라고 하면 그 단을 새로 씁니다")
            _뺀단 += [(x, _뺀까닭_메모) for x in _뺀]
        if not _골격:
            nt, _맨줄 = _drop_bare_items(nt)
            _버린 += _맨줄
        _빈단 = _empty_sections(nt)
        if _빈단:
            nt, _뺀 = _단_빼기(nt, _빈단, section)
            if _뺀 is None:
                return _저장못함(u"%s에 개조식 본문 줄이 하나도 없었습니다" % _단들(_빈단),
                                u"다시 써 달라고 하면 그 단을 새로 씁니다")
            _뺀단 += [(x, _뺀까닭_빈) for x in _뺀]
        drop_note = (u"\n\n(원고가 아닌 줄 %d개를 덜어 냈습니다: %s)"
                     % (len(_버린), _버린[0][:40])) if _버린 else u""
        for _까닭 in (_뺀까닭_메모, _뺀까닭_빈):
            _이름 = [n for n, k in _뺀단 if k == _까닭]
            if _이름:
                drop_note += u"\n\n(%s%s 저장하지 않았습니다 — %s)" % (u"·".join(_이름), _은는(_이름[-1]), _까닭)

        pairs = _parse_fixes(fixes)
        fix_note = u""
        if pairs:
            nt, hit, missed = _apply_fixes(nt, pairs)
            if missed:
                if _FIXES_STRICT:
                    return _저장못함(u"교정 %d건 중 %d건은 원문에서 그 줄을 찾지 못했습니다(%s)"
                                    % (len(pairs), len(missed), u" / ".join(missed[:3])))
                fix_note = (u"\n\n(교정 %d건 중 %d건은 원문에서 그 줄을 못 찾아 적용하지 "
                            u"못했습니다: %s)"
                            % (len(pairs), len(missed), u" / ".join(missed[:3])))

        sec_want = section.strip()
        _첫저장 = False
        md = None
        if sec_want:
            md = _read_local_draft(key)
            if md is None:
                md, err = _fetch_draft_url(url)
            if md is None:
                _p0, chk0 = _split_draft(nt)
                if not chk0:
                    return _저장못함(u"고칠 초안이 없고 낸 글에 `## N. 단명` 헤더도 없습니다%s"
                                    % ((u"(%s)" % err) if err else u""),
                                    u"본문을 처음부터 써 달라고 하면 새로 씁니다")
                _첫저장 = True
                drop_note += u"\n\n(첫 저장 — 저장본이 없어 낸 단 %d개가 곧 문서입니다)" % len(chk0)
        if not sec_want or _첫저장:
            _p, chk = _split_draft(nt)
            if len(chk) < 2 and not _골격 and not _첫저장:
                return _저장못함(u"전체를 바꾸려면 단이 둘 이상 와야 하는데 %d개만 왔습니다" % len(chk),
                                u"고칠 단을 말해 주면 그 단만 고칩니다")
            merged, shown = nt, nt
        else:
            pre, secs = _split_draft(md)
            if len(secs) < 2:
                return _저장못함(u"지금 초안이 단으로 나뉘지 않습니다(단 %d개)" % len(secs),
                                u"본문을 처음부터 써 달라고 하면 새로 씁니다")
            hit = _match_section(secs, sec_want)
            if hit is None:
                return _저장못함(u"'%s'에 맞는 단이 없습니다 — 있는 단: %s"
                                % (sec_want[:40],
                                   u", ".join(u"%s %s" % (s["no"], s["name"]) for s in secs)))
            if not nt.startswith(u"##"):
                head_line = hit["text"].splitlines()[0] if hit["text"] else (
                    u"## %s. %s" % (hit["no"], hit["name"]))
                nt = head_line + u"\n" + nt
            _p2, chunks = _split_draft(nt)
            if len(chunks) > 1 or _뺀단:
                for c in chunks:
                    h2 = _match_section(secs, u"%s. %s" % (c["no"], c["name"]))
                    if h2 is not None:
                        h2["text"] = c["text"]
                    else:
                        secs.append(c)
            else:
                hit["text"] = nt
            merged, shown = _join_draft(pre, secs), nt

        merged, _각주버림 = _dedup_footnotes(merged)
        merged, _접음 = _fold_box_tail(merged)
        merged, _빈표 = _drop_empty_tables(merged)
        shown, _ = _fold_box_tail(shown)
        shown, _ = _drop_empty_tables(shown)
        if _각주버림:
            drop_note += (u"\n\n(같은 용어 각주 %d개를 덜어 냈습니다: %s)"
                          % (len(_각주버림), u" · ".join(_각주버림[:3])))
        if _빈표:
            drop_note += u"\n\n(값이 하나도 없는 표 %d개를 덜어 냈습니다)" % _빈표

        _part = u"outline" if _골격 else u""
        _kind = (u"골격" if _골격 else (u"단 %s" % sec_want if sec_want else u"채움"))
        if _뺀단:
            _kind += u"(뺌 %s)" % _단들([n for n, _ in _뺀단])
        res = _store_draft(merged, key, u"",
                           _spec_of(_pages_pick(
                               (_sidecar_read(_k) or {}).get("spec"),
                               _pages, _state_pages(_k))), part=_part, kind=_kind)
        if _골격 and _read_local_draft(key) is None:
            try:
                _store_draft(merged, key, u"", part=u"", kind=u"골격 씨앗")
            except Exception:
                pass
        if isinstance(res, str) and res.startswith(u"http"):
            head = u"[draft 저장본](%s)" % res
        else:
            head = u"(draft 저장본 링크 없음 — 대화 열쇠로 회수됩니다)"
        if _골격:
            drop_note = u""
        return head + u"\n\n" + _hide_todo_mark(shown) + fix_note + drop_note + 말꼬리
    except Exception as e:
        return _저장못함(u"저장하다 오류가 났습니다(%s: %s)" % (type(e).__name__, e))


def _pick_images(conv_body):
    import re
    MARK = re.compile(u"^\\[이미지(\\d+)\\]$")
    lines = (conv_body or u"").split(u"\n")
    images, out, skip = [], [], set()
    for i, ln in enumerate(lines):
        if i in skip:
            continue
        m = MARK.match(ln.strip())
        out.append(ln)
        if not m:
            continue
        cap = u""
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j].strip()
            if not nxt:
                continue
            if nxt.startswith(u"* "):
                cap = nxt[2:].strip()
                skip.add(j)
            break
        images.append({"count": 1, "captions": [cap] if cap else []})
    return images, u"\n".join(x for i, x in enumerate(lines) if i not in skip)


@mcp.tool()
async def generate_hwpx_report(title: str = "", key: str = "", url: str = "",
                               intent: str = "", body: str = "",
                               owner: str = "", date: str = "",
                               tables: list = None, images: list = None) -> str:
    """하는 일:
        저장본을 K-water 표준서식 HWPX(한글) 파일로 만들고 다운로드 링크를 낸다.
        본문은 저장소에서 직접 읽는다(`key`) — 네가 넘기지 않는다. 표는 원고의 마크다운 표에서 도구가 뽑고,
        열 폭은 칸 내용에 맞춰 넓힌다(표 폭 안에 드는 한).
    넘기는 입력:
        key: [자료 열쇠]를 글자 그대로 넣는다
        title: 보고서 제목. 이 대화의 값으로도 남는다
        intent: 취지 상자 — 제목 아래 두 줄 꽉(70~72자) 한자어 동사구. 비우면 상자를 걷어낸다(1장짜리 관례)
    돌려주는 반환:
        성공이면 완료 메시지 + hwpx 다운로드 링크(마크다운 링크 꼴).
        실패면 `[생성 실패] 사유` 한 줄 — 업로드 실패도 한 줄이다(재호출하라).
    """
    import os, json, traceback

    def norm_listarg(v):
        if isinstance(v, str) and v.strip():
            try:
                v = json.loads(v)
            except Exception:
                return None
        if isinstance(v, dict):
            v = [v]
        return v if isinstance(v, list) else None

    def upload_to_cdn(file_path: str) -> str:
        import requests
        host = os.getenv("LLMOPS_CDN_API_SERVICE_SERVICE_HOST", "llmops-cdn-api-service")
        port = os.getenv("LLMOPS_CDN_API_SERVICE_SERVICE_PORT", "8080")
        up = "http://%s:%s/minio/upload/temp" % (host, port)
        public_host = os.getenv("HWPX_PUBLIC_HOST", "")
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            resp = requests.post(up, data={"hostname": public_host},
                                 files=files, timeout=30)
        resp.raise_for_status()
        return resp.json()["data"]["presigned_url"]

    try:
        try:
            _state_write(_safe_key(key), title=title)
        except Exception:
            pass
        md = body if (isinstance(body, str) and body.strip()) else None
        src_note = u"인자"
        if md is None:
            md = _read_local_draft(key)
            src_note = u"저장소(열쇠)"
        if md is None:
            md, err = _fetch_draft_url(url)
            src_note = u"저장소(URL)"
            if md is None:
                return (u"[생성 실패] 만들 초안이 없다%s — 먼저 초안을 만들고 나서 "
                        u"파일 생성을 요청하라." % ((u" (%s)" % err) if err else u""))
        if not md.strip():
            return u"[생성 실패] 초안이 비어 있다 — 먼저 초안을 만들어라."

        md, _빈단 = _strip_outline_marks(md)
        conv, md_tables = _convert_md(md)
        auto_images, conv = _pick_images(conv)

        norm_tables = norm_listarg(tables)
        norm_images = norm_listarg(images)
        key_note = u""
        if tables and norm_tables is None:
            key_note += (u"\n\n(tables 인자를 해석하지 못해 초안에서 뽑은 표로 "
                         u"만들었습니다.)")
        if images and norm_images is None:
            key_note += (u"\n\n(images 인자를 해석하지 못해 초안에서 뽑은 자리로 "
                         u"만들었습니다.)")
        use_tables = norm_tables if norm_tables else (md_tables or None)
        for _t in (use_tables or []):
            if isinstance(_t, dict) and not _t.get("col_ratios") and not _t.get("grid"):
                _r = _table_ratios(_t)
                if _r:
                    _t["col_ratios"] = _r
        use_images = norm_images if norm_images else (auto_images or None)

        from hwpx_skeleton import renderer
        out_dir = os.environ.get("HWPX_OUT_DIR", "/tmp/hwpx-out")
        os.makedirs(out_dir, exist_ok=True)

        gen_fields = {"title": title} if title else {}
        if isinstance(owner, str) and owner.strip():
            gen_fields["owner"] = owner.strip()
        if isinstance(date, str) and date.strip():
            gen_fields["date"] = date.strip()

        res = renderer.render(
            template_key="plan",
            fields=gen_fields,
            output_dir=out_dir,
            body=conv or None,
            intent=(intent or None),
            tables=use_tables,
            images=use_images,
        )
        if res.get("status") != "success":
            return (u"[생성 실패] %s ※ 'plan' 양식을 못 찾은 것이면 서버의 "
                    u"hwpx-skeleton 버전이 0.3.0 인지 확인하라."
                    % res.get("message", u"렌더 실패"))

        br_chk = res.get("body_result") or {}
        if conv.strip() and not br_chk.get("filled"):
            return (u"[생성 실패] %s. 휠(hwpx-skeleton) 버전과 plan 양식을 확인하라."
                    % br_chk.get("reason", u"본문을 채우지 못함"))

        path = res["path"]
        fn = os.path.basename(path)
        size = os.path.getsize(path)

        br = res.get("body_result") or {}
        extra = []
        if br.get("tables_added"):
            extra.append(u"표 %d개" % br["tables_added"])
        if br.get("images_added"):
            extra.append(u"이미지자리 %d개" % br["images_added"])
        extra_s = (u" (" + u", ".join(extra) + u" 포함)") if extra else u""
        if _빈단:
            key_note += (u"\n\n⚠️아직 채우지 않은 단이 있습니다 — %s. "
                         u"본문이 빈 채로 나왔으니 채우고 다시 뽑으시겠습니까?"
                         % u" · ".join(_빈단[:6]))

        try:
            link = upload_to_cdn(path)
            return (u"'%s' 보고서를 생성했습니다%s (%s bytes · 원고 출처 %s).\n\n"
                    u"[📄 %s 다운로드](%s)%s"
                    % (title or res.get("template_label") or u"보고서", extra_s,
                       format(size, ","), src_note, fn, link, key_note))
        except Exception as up:
            detail = "%s: %s" % (type(up).__name__, up)
            resp = getattr(up, "response", None)
            if resp is not None:
                detail += " [status=%s]" % getattr(resp, "status_code", "?")
            return u"[생성 실패(업로드)] %s — 잠시 후 다시 호출하라." % detail[:300]
    except Exception as e:
        return json.dumps({"ok": False, "message": "%s: %s" % (type(e).__name__, e),
                           "trace": traceback.format_exc()[-1200:]}, ensure_ascii=False)
