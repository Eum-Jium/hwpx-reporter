"""재는 기계 — 빌드 산물(공개 사본: 주석·설명을 걷었다). 쓰는 쪽은 `scripts/layout.py`."""

_DRAFT_MAX = 2 * 1024 * 1024

def _draft_dir():
    import os
    d = os.environ.get('HWPX_DRAFT_DIR', '/tmp/hwpx-drafts')
    os.makedirs(d, exist_ok=True)
    return d

def _safe_key(key):
    import re
    s = key if isinstance(key, str) else u''
    if u'{' in s or u'}' in s:
        return u''
    s = re.sub(u'[^A-Za-z0-9_-]', u'', s)[:64]
    return s if len(s) >= 8 else u''

def _refs_path(k):
    import os
    return os.path.join(_draft_dir(), k + '_refs.md')
_SEC_ROLE_TEXT = {u'추진배경': u'왜 하는지', u'현황': u'지금 어떻고 무엇이 모자란지', u'주요내용': u'무엇을 하겠다는 것인지', u'추진방안': u'어떻게 하겠다는 것인지', u'향후계획': u'언제 무엇을 할지', u'본론': u''}

def _sample_outline(pages):
    rows = _plan_rows(pages) if pages else None
    if not rows:
        return u''
    out = [u'[샘플 골격] — 장수에 맞춘 샘플. 단 이름과 역할.']
    for (_i, _nm, _pt, _b, _d, _시) in rows:
        표 = u' · 표 하나' if _시 == u'표' else u''
        out.append(u'  %d단 %s — %s%s' % (_i, _nm, _SEC_ROLE_TEXT.get(_nm, u''), 표))
    return u'\n'.join(out)

def _clean_md(s):
    import re
    s = s.replace(u'**', u'').replace(u'__', u'')
    s = s.replace(u'`', u'')
    s = re.sub(u'\\[([^\\]]+)\\]\\(([^)]*)\\)', u'\\1', s)
    return s.strip()

def _tabify(s):
    import re
    m = re.match(u"^(['’]?\\d{2}\\s*[.년]\\s*(?:\\d{1,2}\\.\\s*)*(?:\\d{1,2}\\s*(?:[~–-]\\s*\\d{1,2}\\s*)?월?|[상하]반기|\\d분기|말|초)?)\\s+(\\S.*)$", s)
    return m.group(1).rstrip() + u'\t' + m.group(2) if m else s

def _convert_rows(raw, table_offset=0):
    import re
    text = raw or u''
    if not isinstance(text, str):
        text = u'%s' % text
    text = text.replace(u'\\n', u'\n')
    (rows, tables) = ([], [])
    table_no = table_offset
    in_table = False
    cur = None
    head_no = 0
    img_no = 0
    SEP_CELL = re.compile(u'^:?-+:?$')
    for ln in text.splitlines():
        t = ln.rstrip()
        s = t.lstrip()
        if re.match(u'^-{3,}$', s) or re.match(u'^={3,}$', s):
            (in_table, cur) = (False, None)
            continue
        if not s:
            (in_table, cur) = (False, None)
            continue
        if s.startswith(u'|'):
            cells = [c.strip() for c in s.strip().strip(u'|').split(u'|')]
            if not in_table:
                in_table = True
                table_no += 1
                rows.append((u'[표%d]' % table_no, t))
                cur = {'headers': [_clean_md(c) for c in cells], 'rows': []}
                tables.append(cur)
            else:
                if all((SEP_CELL.match(c or u'-') for c in cells)):
                    continue
                if cur is not None:
                    cur['rows'].append([_clean_md(c) for c in cells])
            continue
        (in_table, cur) = (False, None)
        mimg = re.match(u'^[-*+□☐◦]\\s*\\[(이미지|표)(\\d+)\\]\\s*(.*)$', s)
        if mimg:
            if mimg.group(1) == u'이미지':
                img_no += 1
            rows.append((u'[%s%s]' % (mimg.group(1), img_no if mimg.group(1) == u'이미지' else mimg.group(2)), t))
            cap = _clean_md(mimg.group(3)).strip()
            if cap:
                rows.append((u'* ' + cap, t))
            continue
        if re.match(u'^\\[(표|이미지)\\d+\\]$', s):
            if s.startswith(u'[이미지'):
                img_no += 1
                s = u'[이미지%d]' % img_no
            rows.append((s, t))
            continue
        mh = re.match(u'^#{1,6}\\s*(.+)$', s)
        if mh:
            h = _clean_md(mh.group(1))
            mn = re.match(u'^(\\d+)\\.\\s', h)
            if mn:
                head_no = int(mn.group(1))
            else:
                head_no += 1
                h = u'%d. %s' % (head_no, h)
            rows.append((h, t))
            continue
        mq = re.match(u'^>\\s*(.*)$', s)
        if mq:
            rows.append((u'* ' + _clean_md(mq.group(1)), t))
            continue
        ml = re.match(u'^(\\s*)[-*+]\\s+(.*)$', t)
        if ml:
            indent = len(ml.group(1).replace(u'\t', u'  '))
            mark = u'- ' if indent >= 4 else u'◦ ' if indent >= 2 else u'□ '
            rows.append((mark + _tabify(_clean_md(ml.group(2))), t))
            continue
        head = s[:1]
        if head in u'□☐◦-*·※' and (not (head in u'-*' and (not s[1:2].isspace()))):
            rows.append((head + u' ' + _tabify(_clean_md(s[1:])), t))
        else:
            rows.append((_clean_md(s) if re.match(u'^\\d+\\.\\s', s) else u'□ ' + _clean_md(s), t))
    return (rows, tables)

def _convert_md(raw, table_offset=0):
    (rows, tables) = _convert_rows(raw, table_offset)
    return (u'\n'.join((c for (c, _) in rows)), tables)
_PT_HEADING = 2
_PT_TABLE_PAD = 1
_PT_IMAGE = 8
_PT_PER_PAGE = 25
_PT_FIRST_PAGE = 26
_PT_DISP = 25.5
_TABLE_PT = 7

def _pg(pts):
    try:
        return u'%.2f' % (float(pts or 0) / _PT_DISP)
    except Exception:
        return u'0.00'

def _pages_arg(target_pages, target_lines=u''):
    import re as _re
    try:
        m = _re.search(u'\\d+', u'%s' % (target_pages if target_pages is not None else u''))
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
    headers = list((t or {}).get('headers') or [])
    rows = [list(r or []) for r in (t or {}).get('rows') or []]
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
        for (ci, c) in enumerate(r[:N]):
            need[ci] = max(need[ci], TS.text_w(c) + TS.CELL_PAD)
    if all((need[i] <= base[i] for i in range(N))):
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
        return ([], 0)
    headers = list((t or {}).get('headers') or [])
    rows = [list(r or []) for r in (t or {}).get('rows') or []]
    N = max([len(headers)] + [len(r) for r in rows] + [0])
    if N <= 0:
        return ([], 0)
    firsts = ([headers[0]] if headers else []) + [r[0] for r in rows if r]
    try:
        widths = TS.col_widths(N, ratios, None, None, firsts)
    except Exception:
        return ([], 0)
    room = [max(1, w - TS.CELL_PAD) for w in widths]
    (folds, extra) = ([], 0)
    for (ri, r) in enumerate([headers] + rows):
        tall = 1
        for (ci, c) in enumerate(r[:N]):
            need = TS.text_w(c)
            lines = 1 if need <= room[ci] else int(math.ceil(float(need) / room[ci]))
            if lines > 1:
                folds.append({'row': ri, 'col': ci, 'text': u'%s' % c, 'need': round(need / float(TS.CHAR_W_13PT), 1), 'room': round(room[ci] / float(TS.CHAR_W_13PT), 1), 'lines': lines})
            tall = max(tall, lines)
        extra += tall - 1
    return (folds, extra)

def _points(conv_body, tables=None, intent=u''):
    import re
    rows = [len((t or {}).get('rows') or []) + 1 + _table_fold(t, _table_ratios(t))[1] for t in tables or []]
    total = 0
    det = {'heading': 0, 'line': 0, 'table': 0, 'image': 0, 'lines': 0, 'intent': 0}
    itxt = (intent or u'').strip()
    if itxt:
        det['intent'] = _line_pts(len(itxt)) + 1
        total += det['intent']
    ti = 0
    for ln in (conv_body or u'').splitlines():
        srt = ln.strip()
        if not srt:
            continue
        mk = re.match(u'^\\[(표|이미지)\\d+\\]$', srt)
        if mk:
            if mk.group(1) == u'표':
                n = (rows[ti] if ti < len(rows) else 4) + _PT_TABLE_PAD
                ti += 1
                det['table'] += n
            else:
                n = _PT_IMAGE
                det['image'] += n
        elif re.match(u'^\\d+\\.\\s', srt):
            n = _PT_HEADING
            det['heading'] += n
        else:
            n = _line_pts(len(srt))
            det['line'] += n
            det['lines'] += 1
        total += n
    rest = max(0, total - _PT_FIRST_PAGE)
    det['pages'] = 1 + (rest + _PT_PER_PAGE - 1) // _PT_PER_PAGE
    return (total, det)
_BAND_LINES = {u'□': 1, u'◦': 2}
_BAND_FILL = {u'□': 30.0 / _PT_LINE_CHARS, u'◦': 28.0 / _PT_LINE_TAIL}

def _band_full(band):
    k = _BAND_LINES.get(band, 1)
    return _PT_LINE_CHARS + (k - 1) * _PT_LINE_TAIL

def _band_floor(band):
    (k, full) = (_BAND_LINES.get(band, 1), _band_full(band))
    for n in range(1, full + 1):
        if _line_pts(n) == k and _tail_fill(n) >= _BAND_FILL[band]:
            return n
    return full

def _tail_fill(n):
    k = _line_pts(n)
    if k <= 1:
        return n / float(_PT_LINE_CHARS)
    return (n - _PT_LINE_CHARS - (k - 2) * _PT_LINE_TAIL) / float(_PT_LINE_TAIL)
_SCHED_MIN = 3
_SCHED_MAX = 5
_SCHED_PAT = u"^[(’'~∼\\s]*\\d{2}\\s*(?:년(?=\\s*$|\\t|\\s{2}|\\s*(?:\\d{1,2}\\s*월|[상하]반기|[1-4]\\s*분기|초|말|이후|부터))\\s*(?:\\d{1,2}\\s*월|[상하]반기|[1-4]\\s*분기|초|말|이후|부터)?|[.]\\s*(?:\\d{1,2}\\s*[월.]|[상하]반기|[1-4]\\s*분기|초|말|하|상))|^[(~∼\\s]*['’]\\d{2}[.]\\s+\\S"

def _is_sched(t):
    import re
    return bool(re.match(_SCHED_PAT, (t or u'').lstrip(u'-*□◦· \t')))
_SHAPE_DOT_MIN = 2
_SECS_BY_PAGES = {1: 3, 2: 4, 3: 5, 4: 5, 5: 5}
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
    return (secs, vis, box, box * _SHAPE_DOT_MIN, budget)
_SEC_ROLE = [(u'추진배경', 0.6, u''), (u'현황', 1.3, u'표'), (u'주요내용', 1.8, u'표'), (u'추진방안', 1.5, u'표'), (u'향후계획', 0.8, u'')]
_VIS_ALWAYS = (u'주요내용',)

def _plan_rows(pages, secs_want=0):
    got = _plan_for(pages)
    if not got:
        return None
    (secs, vis, box, dot, budget) = got
    try:
        secs = int(secs_want) or secs
    except Exception:
        pass
    secs = max(2, min(12, secs))
    역할 = _SEC_ROLE[:secs] if secs <= len(_SEC_ROLE) else _SEC_ROLE + [(u'본론', 1.2, u'')] * (secs - len(_SEC_ROLE))
    역할 = [x for x in 역할 if x[0] != u'향후계획'][:secs - 1] + [_SEC_ROLE[-1]]
    w = sum((x[1] for x in 역할))
    (rows, 남은시각물) = ([], vis)
    for (i, (nm, 무게, 종류)) in enumerate(역할, 1):
        pt = int(round(budget * 무게 / w))
        시 = 종류 if 종류 and nm != u'향후계획' and (남은시각물 > 0 or nm in _VIS_ALWAYS) else u''
        if 시:
            남은시각물 -= 1
        b = max(1, int(round((pt - _PT_HEADING - (_TABLE_PT if 시 == u'표' else 0)) / float(_SHAPE_UNIT_PT))))
        if nm == u'향후계획':
            rows.append((i, nm, pt, 0, max(_SCHED_MIN, min(_SCHED_MAX, int(pages) if str(pages).isdigit() else 5)), u'일정'))
            continue
        rows.append((i, nm, pt, b, b * _SHAPE_DOT_MIN, 시))
    return rows

def _pages_from_lines(target_lines):
    import re
    n = int(re.sub('[^0-9]', '', str(target_lines or '')) or 0)
    return max(1, min(5, int(round(n / 16.0)))) if n else 0

def _lint_measure(draft='', target_lines='', target_pages='', scope=''):
    import json, re
    try:
        raw = draft if isinstance(draft, str) else u'' if draft is None else u'%s' % draft
        try:
            raw = _cut_head(raw)
            if _split_draft(raw)[1]:
                (raw, _) = _strip_non_body(raw)
            else:
                raw = u'\n'.join((l for l in raw.replace(u'\r\n', u'\n').split(u'\n') if _is_body_line(l)))
        except Exception:
            pass
        (rows, _tables) = _convert_rows(raw)
        try:
            from hwpx_core.endings import ending_word as _ending_word, is_verb_ending as _verb_ending
        except Exception:
            _ending_word = _verb_ending = None
        HANJA = re.compile(u'[㐀-䶿一-\u9fff豈-\ufaff𠀀-\U0002ee5f丽-\U0002fa1f]')
        POLITE = re.compile(u'(습니다|합니다|입니다|됩니다|하세요|해요|예요|에요|십시오)[.!?)”’"\']*\\s*$')
        DATE_LONG = re.compile(u'\\d{4}\\s*년\\s*\\d{1,2}\\s*월\\s*\\d{1,2}\\s*일')
        HEAD = re.compile(u'^\\d+\\.\\s')
        SCHED = re.compile(_SCHED_PAT)
        LISTED = re.compile(u'^[^:：]{1,12}[:：]\\s?')
        LISTED_MAX = 60
        MARKER_LINE = re.compile(u'^\\[(표|이미지)\\d+\\]$')
        MARKERS = u'□☐◦-*·※'
        v = []
        lenc = {'under': 0, 'over': 0}

        def add(src, rule, sev, msg, **extra):
            d = {'rule': rule, 'severity': sev, 'message': msg, 'line': (src or u'')[:200]}
            d.update(extra)
            v.append(d)
        conv = [c.strip() for (c, _) in rows]
        srcs = [s for (_, s) in rows]
        (_secof, _cur_sec) = ([], u'머리')
        for _s in conv:
            if HEAD.match(_s or u''):
                _cur_sec = u'%s단' % _s.split(u'.', 1)[0].strip()
            _secof.append(_cur_sec)
        nonempty = [s for s in conv if s]
        for (i, s) in enumerate(conv):
            if not s or MARKER_LINE.match(s):
                continue
            src = srcs[i]
            rest = s[1:].strip()
            free = bool(SCHED.match(rest) or u'\t' in s or (LISTED.match(rest) and len(s) <= LISTED_MAX))
            band = u'□' if s[0] in u'□☐' else u'◦' if s[0] == u'◦' else u''
            if band and (not free):
                want = _BAND_LINES[band]
                full = _band_full(band)
                got = _line_pts(len(s))
                if got > want:
                    lenc['over'] += 1
                    add(src, 'length', 'error', u'%s 줄이 %d줄에 앉는다(%d줄 규격) — %d자. **한 줄 분량을 덜어라**' % (band, got, want, len(s)), n=len(s), band=band, lines=got, want=want, full=full, over=True, sec=_secof[i], text=rest[:80])
                elif got < want or _tail_fill(len(s)) < _BAND_FILL[band]:
                    lenc['under'] += 1
                    add(src, 'length', 'error', u'%s 줄이 덜 찼다 — %d줄에 %d자(%d줄 %d자면 꽉 찬다). 수치·근거·조건을 보태고, 채울 사실이 없으면 지워라' % (band, got, len(s), want, full), n=len(s), band=band, lines=got, want=want, full=full, over=False, sec=_secof[i], text=rest[:80])
        body_lines = len(nonempty)
        (_body, _tbl) = _convert_md(raw)
        (pts, det) = _points(_body, _tbl, u'')
        tgt_m = re.search(u'\\d+', u'%s' % (target_lines if target_lines is not None else u''))
        tgt = int(tgt_m.group()) if tgt_m else 0
        if 1 <= tgt <= 8:
            tgt *= 16
        _tp = _pages_arg(target_pages, u'')
        if _tp:
            tgt = _tp * 16
        pages_want = max(1, (tgt + 15) // 16) if tgt else 0
        _상자 = 0
        budget = _PT_FIRST_PAGE + (pages_want - 1) * _PT_PER_PAGE if pages_want else 0
        if tgt and nonempty:
            if pts > budget:
                add(u'', 'total_length', 'warning', u'본문 %s장 — 목표 %d장보다 %s장 많다. 조사·군더더기 어절부터 압축하고 그래도 넘치면 항목을 덜어라' % (_pg(pts), pages_want, _pg(pts - budget)))
            elif pts <= budget - _PT_PER_PAGE:
                add(u'', 'total_length', 'warning', u'본문 %s장 — 목표 %d장에 한 장 넘게 못 미친다. 내용을 보태 채워라 — 없는 사실을 지어내지는 마라' % (_pg(pts), pages_want))
        errs = [x for x in v if x['severity'] == 'error']
        warns = [x for x in v if x['severity'] != 'error']
        wrules = {}
        for x in warns:
            wrules[x['rule']] = wrules.get(x['rule'], 0) + 1
        _넘침 = [x for x in errs if x.get('rule') == 'length' and x.get('over')]
        _덜참 = [x for x in errs if x.get('rule') == 'length' and x.get('band') and (not x.get('over'))]
        _넘침.sort(key=lambda y: -(y['lines'] - y['want']))
        _덜참.sort(key=lambda y: y['n'] / float(y['full']))
        _길이목록 = []
        for x in _넘침 + _덜참:
            _t = (x.get('text') or u'').strip()
            _길이목록.append(u'· %s %s %d/%d — %s' % (x.get('sec') or u'?', x['band'], x['n'], x['full'], _t if len(_t) <= 20 else _t[:20] + u'…'))
        _head = u''
        if _길이목록:
            _head = u'자수가 안 맞는 곳 %d — %s' % (len(_길이목록), u' · '.join((u'%s %d~%d자 %d' % (b, _band_floor(b), _band_full(b), sum((1 for x in _넘침 + _덜참 if x['band'] == b))) for b in (u'□', u'◦') if any((x['band'] == b for x in _넘침 + _덜참)))))
        _미확인 = raw.count(u'(확인필요)')
        (_extra, _pmap, _secpg) = ([], None, [])
        try:
            _ds = _split_draft(raw)[1]
            if len(_ds) >= 2:
                _pmap = _page_map(_ds, start=_상자)
                _extra.append(u'쪽 자리 — ' + _page_note(_ds, _pmap))
        except Exception:
            pass
        _접힘 = []
        for (_ti, _t) in enumerate(_tbl or []):
            for f in _table_fold(_t, _table_ratios(_t))[0]:
                _접힘.append(u'표%d %s %s열 「%s」 %s자 자리에 %s자' % (_ti + 1, u'머리글' if f['row'] == 0 else u'%d행' % f['row'], (_t.get('headers') or [u''] * (f['col'] + 1))[f['col']] if f['col'] < len(_t.get('headers') or []) else f['col'] + 1, f['text'][:20], f['room'], f['need']))
        if _접힘:
            _extra.append(u'표 셀 접힘 %d — 접힌 행은 두 줄로 세었다 · ' % len(_접힘) + u' · '.join(_접힘[:6]))
        _쪽 = det['pages']
        if _pmap:
            _쪽 = max(_쪽, max((x['end_page'] for x in _pmap)))
        det['pages'] = _쪽
        _분량 = u'분량 %s장' % _pg(pts) + (u' / 목표 %d장' % pages_want if pages_want else u'') + u' · %d쪽' % _쪽 + u' · 표 %d개' % len(_tbl or [])
        if _미확인:
            _분량 += u' · (확인필요) %d개' % _미확인
        if scope:
            _단수 = len(_split_draft(raw)[1])
            _무엇 = u'%s %d단을' % (scope, _단수) if _단수 else u'%s(단 머리 없음)%s' % (scope, u'을' if scope.endswith(u'글') else u'를')
            _첫줄 = u'[기계 검사] %s 조판하면 이렇게 앉는다.' % _무엇
        else:
            _첫줄 = u'[기계 검사] 이 문서를 조판하면 이렇게 앉는다.'
        note = _첫줄 + u'\n' + _분량 + u''.join((u'\n' + x for x in _extra)) + (u'\n' + _head if _head else u'') + u''.join((u'\n' + x for x in _길이목록))
        payload = json.dumps({'pass': not errs, 'error_count': len(errs), 'warning_count': len(warns), 'warning_rules': wrules, 'target_lines': tgt or None, 'body_lines': body_lines, 'length_under': lenc['under'], 'length_over': lenc['over'], 'points': pts, 'points_budget': budget or None, 'est_pages': det['pages'], 'page_map': _pmap, 'section_pages': _secpg, 'unverified': _미확인, 'note': note}, ensure_ascii=False)
        return payload
    except Exception as e:
        return json.dumps({'pass': True, 'lint_unavailable': True, 'note': u'', 'error_count': 0, 'warning_count': 0, 'warning_rules': {}, 'error': '%s: %s' % (type(e).__name__, e)}, ensure_ascii=False)

async def check_rules(key: str='', draft: str='') -> str:
    import os, re
    글 = draft if isinstance(draft, str) else u'' if draft is None else u'%s' % draft
    범위 = u'받은 글'
    k = _safe_key(key if isinstance(key, str) else u'' if key is None else u'%s' % key)
    if not 글.strip():
        글 = _read_local_draft(key) or u''
        범위 = u'저장본 전체'
        if not 글.strip():
            return u'REVIEW_FAIL: 볼 글이 없다 — draft 가 비었고 key 의 저장본도 없다'
    try:
        from hwpx_core.endings import ending_word as _ew, is_verb_ending as _ve
    except Exception:
        _ew = _ve = None
    HANJA2 = re.compile(u'[㐀-䶿一-\u9fff豈-\ufaff𠀀-\U0002ee5f丽-\U0002fa1f]')
    POLITE2 = re.compile(u'(습니다|합니다|입니다|됩니다|하세요|해요|예요|에요|십시오)[.!?)”’"\']*\\s*$')
    DATE2 = re.compile(u'\\d{4}\\s*년\\s*\\d{1,2}\\s*월(\\s*\\d{1,2}\\s*일)?|\\d{4}[-./]\\d{1,2}[-./]\\d{1,2}')
    NUM2 = re.compile(u'\\d[\\d,]*(?:\\.\\d+)?')
    (본문, _말) = _cut_tail(_cut_head(글.replace(u'\r\n', u'\n')))
    (_pre, secs) = _split_draft(본문)
    if not secs:
        secs = [{'no': u'', 'name': u'', 'text': 본문}]
    refs = u''
    p = _refs_path(k) if k else u''
    if p and os.path.exists(p):
        try:
            refs = open(p, 'r', encoding='utf-8').read().replace(u',', u'')
        except Exception:
            refs = u''
    (out, n항목) = ([], 0)
    for sec in secs:
        단 = u'%s단' % sec['no'] if sec['no'] else u'머리'
        for ln in sec['text'].split(u'\n'):
            m = re.match(u'^(\\s*)[-*]\\s+(.*\\S)\\s*$', ln)
            if not m or ln.strip().startswith(u'|') or ln.strip().startswith(u'>'):
                continue
            t = m.group(2).strip()
            if re.match(u'^\\[(표|이미지)\\d+\\]$', t) or _is_sched(t):
                continue
            급 = u'◦' if len(m.group(1)) >= 2 else u'□'
            t = re.sub(u'\\*\\*', u'', t).strip()
            t = re.sub(u'^\\([^)]*\\)\\s*', u'', t).strip()
            if not t:
                continue
            n항목 += 1
            앞 = t[:22] + (u'…' if len(t) > 22 else u'')

            def hit(rule):
                out.append(u'· %s %s %s — %s' % (단, 급, rule, 앞))
            if POLITE2.search(t):
                hit(u'경어체')
            elif _ve is not None and _ve(t):
                hit(u'서술형 종결(%s)' % (_ew(t) if _ew else u''))
            if re.search(u'[가-힣A-Za-z)]\\.$', t):
                hit(u'줄 끝 마침표')
            if HANJA2.search(t):
                hit(u'한자')
            if DATE2.search(t):
                hit(u"날짜 꼴 — '26. 4. 13 꼴로")
            if refs and u'(확인필요)' not in t:
                없음 = []
                for num in NUM2.findall(t):
                    d = num.replace(u',', u'')
                    if len(d.replace(u'.', u'')) >= 2 and (not re.match(u'^(19|20)\\d\\d$', d)) and (d not in refs):
                        없음.append(num)
                if 없음:
                    hit(u'자료에 없는 수치 %s — (확인필요) 없음' % u'·'.join(없음[:3]))
    머리 = u'[규칙 검토] %s %d단 %d항목을 봤다 — 종결·경어체·한자·마침표·날짜 꼴%s' % (범위, len(secs), n항목, u'·자료에 없는 수치' if refs else u' (참고자료가 없어 수치는 못 봤다)')
    if not out:
        return 머리 + u'\n규칙으로 잡힌 것 없음'
    return 머리 + u'\n' + u'\n'.join(out[:80]) + (u'\n(…%d건 더)' % (len(out) - 80) if len(out) > 80 else u'')

def _split_draft(md):
    import re
    text = (md or u'').replace(u'\r\n', u'\n')
    heads = list(re.finditer(u'^##\\s*(\\d+)\\s*[.．]?\\s*(\\S[^\\n]*)$', text, re.M))
    pre = text[:heads[0].start()].strip() if heads else text.strip()
    secs = []
    for (i, m) in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        secs.append({'no': m.group(1), 'name': m.group(2).strip(), 'text': text[m.start():end].strip()})
    return (pre, secs)

def _is_body_line(ln):
    import re
    t = (ln or u'').strip()
    if not t:
        return True
    if re.match(u'^##(?!#)', t):
        return True
    if re.match(u'^\\s*[-*]\\s', ln or u''):
        return True
    if t.startswith(u'|'):
        return True
    if t.startswith(u'>'):
        return True
    if re.match(u'^\\[(?:이미지|그림)\\s*\\d*\\]$', t):
        return True
    return False

def _strip_non_body(md):
    (pre, secs) = _split_draft(md or u'')
    _pd = []
    if pre:
        _pk = []
        for _l in pre.split(u'\n'):
            (_pk if _is_body_line(_l) else _pd).append(_l)
        pre = u'\n'.join(_pk).strip()
    if not secs:
        (keep, drop) = ([], [])
        for ln in (md or u'').split(u'\n'):
            (keep if _is_body_line(ln) else drop).append(ln)
        return (u'\n'.join(keep).strip(), [d.strip() for d in drop if d.strip()])
    drop = []
    for s in secs:
        keep = []
        for ln in (s.get('text') or u'').split(u'\n'):
            if _is_body_line(ln):
                keep.append(ln)
            else:
                drop.append(ln.strip())
        s['text'] = u'\n'.join(keep).strip()
    return (_join_draft(pre, secs), [d for d in drop + _pd if d and d.strip()])

def _cut_head(md):
    import re
    text = (md or u'').replace(u'\r\n', u'\n')
    lines = text.split(u'\n')
    heads = [i for (i, l) in enumerate(lines) if re.match(u'^##\\s*\\d+\\s*[.．]?\\s*\\S', l.strip())]
    if heads and heads[0] > 0:
        return u'\n'.join(lines[heads[0]:]).lstrip()
    return text

def _cut_tail(md):
    import re
    text = (md or u'').replace(u'\r\n', u'\n')
    lines = text.split(u'\n')
    heads = [i for (i, l) in enumerate(lines) if re.match(u'^##\\s*\\d+\\s*[.．]?\\s*\\S', l.strip())]
    start = heads[-1] + 1 if heads else 0
    cut = None
    for i in range(len(lines) - 1, start - 1, -1):
        if re.match(u'^([-*_])\\1{2,}$', lines[i].strip()):
            cut = i
            break
    if cut is None:
        return (text, u'')
    if not any((l.strip() and _is_body_line(l) for l in lines[:cut])):
        return (text, u'')
    return (u'\n'.join(lines[:cut]).rstrip(), u'\n'.join(lines[cut + 1:]).strip())

def _join_draft(pre, secs):
    parts = []
    if pre:
        parts.append(pre.strip())
    parts += [(s.get('text') or u'').strip() for s in secs]
    return u'\n\n'.join((p for p in parts if p))

def _read_local_draft(key, part=u''):
    import os
    k = _safe_key(key)
    if not k:
        return None
    try:
        p = os.path.join(_draft_dir(), k + ('_outline.md' if part == u'outline' else '.md'))
        if os.path.exists(p) and os.path.getsize(p) <= _DRAFT_MAX:
            with open(p, 'r', encoding='utf-8') as f:
                txt = f.read()
            if txt.strip():
                return txt
    except Exception:
        pass
    return None

def _sec_pts(text):
    try:
        (_b, _t) = _convert_md(text or u'')
        return _points(_b, _t, u'')[0]
    except Exception:
        return 0

def _page_map(secs, start=0.0):
    (cum, out) = (float(start or 0), [])
    for s in secs:
        start = cum
        (blocks, cur) = ([], [])
        for ln in (s.get('text') or u'').split(u'\n'):
            if ln.lstrip().startswith(u'|'):
                cur.append(ln)
                continue
            if cur:
                blocks.append((True, u'\n'.join(cur)))
                cur = []
            if ln.strip():
                blocks.append((False, ln))
        if cur:
            blocks.append((True, u'\n'.join(cur)))
        tables = []
        for (is_tab, b) in blocks:
            p = float(_sec_pts(b))
            if is_tab:
                (ts, te) = (cum, cum + p)
                sp = int(ts / _PT_DISP) + 1
                ep = int(max(te - 1e-06, ts) / _PT_DISP) + 1
                pushed = 0
                moved = False
                if ep != sp and p <= _PT_DISP and (te - sp * _PT_DISP >= 3):
                    pushed = int(round(sp * _PT_DISP - ts))
                    moved = True
                    cum = sp * _PT_DISP
                    (ts, te) = (cum, cum + p)
                    sp = int(ts / _PT_DISP) + 1
                    ep = int(max(te - 1e-06, ts) / _PT_DISP) + 1
                tables.append({'start_page': sp, 'end_page': ep, 'over': int(round(te - sp * _PT_DISP)) if ep != sp else 0, 'pushed': pushed, 'moved': moved})
            cum += p
        out.append({'start_page': int(start / _PT_DISP) + 1, 'end_page': int(max(cum - 1e-06, start) / _PT_DISP) + 1, 'start': round(start / _PT_DISP, 2), 'end': round(cum / _PT_DISP, 2), 'tables': tables})
    return out

def _page_note(secs, pmap):
    bits = []
    for (s, p) in zip(secs, pmap):
        쪽 = u'%d쪽' % p['start_page'] if p['start_page'] == p['end_page'] else u'%d~%d쪽' % (p['start_page'], p['end_page'])
        밀 = [t for t in p['tables'] if t.get('moved')]
        걸 = [t for t in p['tables'] if t['start_page'] != t['end_page']]
        if 밀:
            tag = u'(표가 %d쪽 끝에 안 들어 %d쪽으로 통째로 밀림 — %d쪽 아래 %d줄 빔)' % (밀[0]['start_page'] - 1, 밀[0]['start_page'], 밀[0]['start_page'] - 1, 밀[0]['pushed'])
        elif 걸:
            tag = u'(표가 %d쪽 끝에 걸릴 듯, %d줄 — 넘치면 통째로 %d쪽으로 밀린다)' % (걸[0]['start_page'], 걸[0]['over'], 걸[0]['start_page'] + 1)
        elif p['tables']:
            tag = u'(표)'
        else:
            tag = u''
        bits.append(u'%s단 %s%s' % (s.get('no') or u'?', 쪽, tag))
    return u' · '.join(bits)
