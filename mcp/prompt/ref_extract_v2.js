var NL = String.fromCharCode(10);

var chatKey = '';
try {
  chatKey = ($flow && ($flow.chatId || $flow.sessionId)) || '';
} catch (e) {
  chatKey = '';
}
if (typeof chatKey !== 'string') chatKey = String(chatKey);

var kst = new Date(Date.now() + 9 * 3600 * 1000);
var today = kst.toISOString().slice(0, 10);
var yoil = ['일', '월', '화', '수', '목', '금', '토'][kst.getUTCDay()];
var who = $vars.genosUserInfo;
if (who === 'DEFAULT' || who === undefined || who === null) who = '';
if (typeof who === 'string' && who.charAt(0) === '{') {
  try { who = JSON.parse(who); } catch (e) { /* 못 읽으면 문자열 그대로 */ }
}
if (who && typeof who === 'object') who = who.name || who.user_id || '';
who = String(who).trim().slice(0, 60);
var env = '[환경]' + NL + '오늘: ' + today + ' (' + yoil + ')';
if (who) env += NL + '요청자: ' + who;

var raw = $vars.genosUploaded || '';
if (typeof raw !== 'string') raw = JSON.stringify(raw);
if (raw === 'DEFAULT') raw = '';

var MAX_FILES = 8;
var TOTAL_BUDGET = 100000;

function attr(s, name) {
  var m = String(s || '').match(new RegExp(name + '="([^"]*)"'));
  return m ? m[1] : '';
}

function kindOf(path, name) {
  var s = String(path || name || '');
  var i = s.lastIndexOf('.');
  if (i < 0 || i === s.length - 1) return 'unknown';
  return s.slice(i + 1).toLowerCase();
}

var docs = [];
var re = new RegExp('<doc([^>]*)>([\\s\\S]*?)</doc>', 'g');
var mm;
while ((mm = re.exec(raw)) !== null) {
  var name = attr(mm[1], 'file_name');
  var path = attr(mm[1], 'file_path');
  var text = (mm[2] || '').split('[DA]').join(' ').trim();
  if (!name && !path && !text) continue;
  docs.push({ name: name, path: path, text: text,
              kind: kindOf(path, name) });
}
var total = docs.length;
if (docs.length > MAX_FILES) docs = docs.slice(0, MAX_FILES);

var chunked = 0;
for (var i = 0; i < docs.length; i++) {
  if (docs[i].text) chunked++;
}
var perFile = chunked > 0 ? Math.max(3000, Math.floor(TOTAL_BUDGET / chunked))
                          : TOTAL_BUDGET;

var maplines = [];
var blocks = [];
for (var j = 0; j < docs.length; j++) {
  var d = docs[j];
  var no = j + 1;
  var nm = d.name || ('첨부 ' + no);
  maplines.push('[자료 목록] ' + no + '|' + nm + '|' + d.path + '|' + d.kind);
  if (!d.text) continue;
  var body = d.text.slice(0, perFile);
  if (d.text.length > perFile) body += NL + '(이하 생략 — 발췌본)';
  blocks.push('[참고자료 ' + no + ': ' + nm + ']' + NL + body);
}

var ref;
if (maplines.length) {
  ref = blocks.length ? blocks.join(NL + NL)
                      : '[참고자료] (첨부는 왔으나 전처리기 본문이 비었다 — 다시 첨부)';
  if (total > docs.length) {
    ref += NL + NL + '[참고자료] 첨부 ' + total + '개 중 ' + docs.length
         + '개만 전달됨 — 나머지는 이번 턴에 반영되지 않는다.';
  }
} else {
  var m2 = raw.match(new RegExp('file_name="([^"]*)"'));
  var label = m2 ? m2[1] : '첨부파일';
  var txt = raw.replace(new RegExp('</?doc[^>]*>', 'g'), ' ')
               .split('[DA]').join(' ').trim();
  ref = txt ? ('[참고자료: ' + label + ']' + NL + txt.slice(0, 12000))
            : '[참고자료] (첨부 없음)';
}

var head = chatKey ? ('[자료 열쇠] ' + chatKey + NL) : '';
if (maplines.length) head += maplines.join(NL) + NL;
return head + env + NL + NL + ref;
