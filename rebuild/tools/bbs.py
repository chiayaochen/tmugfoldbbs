"""Byte-preserving MIME/text decoding and conservative FireBird BBS metadata."""
import datetime as dt
import codecs
import email
import email.header
import email.policy
import email.utils
import hashlib
import pathlib
import re
import unicodedata

CSI = re.compile(r'(?:\x1b\[|\^\[\[|\^\[)([0-?]*)([ -/]*)([@-~])')
OSC = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')
BYTE_CONTROL = re.compile(rb'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\^\[\[?[0-?]*[ -/]*[@-~]')

def decode_ansi(data, declared=None):
    clean = BYTE_CONTROL.sub(b'', data)
    _, info = decode_bytes(clean, declared)
    codec = info['encoding']
    if codec in ('utf-8-sig', 'utf-16'):
        text, info = decode_bytes(data, declared)
        return text, info, [{'type': 'text', 'text': text}]
    decoder = codecs.getincrementaldecoder(codec)(errors='backslashreplace')
    tokens, pending, halves = [], [], []
    def emit_text(text):
        if text:
            if tokens and tokens[-1]['type'] == 'text':
                tokens[-1]['text'] += text
            else:
                tokens.append({'type': 'text', 'text': text})
    def feed(chunk, final=False):
        nonlocal halves
        pos = 0
        while halves and pos < len(chunk):
            char = decoder.decode(chunk[pos:pos + 1], final=False)
            pos += 1
            if char:
                if len(char) == 1 and column_width(char) == 2:
                    tokens.append({'type': 'half', 'text': char, 'sequences': halves})
                else:
                    # A dangling Big5 lead byte followed by a control/newline is
                    # corruption, not a real two-color glyph. Keep its reversible
                    # escape and feed the newline through the normal renderer.
                    emit_text(char)
                    tokens.extend({'type':'ansi','text':code} for code in halves)
                    info['warnings'].append('invalid_half_character_bytes_preserved')
                halves = []
        emit_text(decoder.decode(chunk[pos:], final=final))
    pos = 0
    for match in BYTE_CONTROL.finditer(data):
        feed(data[pos:match.start()])
        code = match.group().decode('ascii')
        if decoder.getstate()[0]:
            halves.append(code)
        else:
            tokens.append({'type': 'ansi', 'text': code})
        pos = match.end()
    feed(data[pos:], final=True)
    if halves:
        for code in halves:
            tokens.append({'type': 'ansi', 'text': code})
        info['warnings'].append('dangling_half_character_control')
    info['half_color_characters'] = sum(t['type'] == 'half' for t in tokens)
    body = ''.join(t['text'] + (''.join(t['sequences']) if t['type'] == 'half' else '') for t in tokens)
    return body, info, tokens

def decode_bytes(data, declared=None):
    warnings = []
    if data.startswith(b'\xef\xbb\xbf'):
        return data.decode('utf-8-sig'), {'encoding': 'utf-8-sig', 'declared': declared, 'confidence': 'BOM', 'warnings': []}
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16'), {'encoding': 'utf-16', 'declared': declared, 'confidence': 'BOM', 'warnings': []}
    if all(b < 128 for b in data):
        return data.decode('ascii'), {'encoding': 'ascii', 'declared': declared, 'confidence': 'ASCII bytes (compatible with UTF-8/Big5)', 'warnings': []}
    if declared:
        try:
            text = data.decode(declared)
            return text, {'encoding': declared, 'declared': declared, 'confidence': 'declared codec, strict decoding', 'warnings': []}
        except (LookupError, UnicodeError):
            warnings.append('declared_encoding_failed')
    try:
        text = data.decode('utf-8')
        return text, {'encoding': 'utf-8', 'declared': declared, 'confidence': 'strict UTF-8', 'warnings': warnings}
    except UnicodeError:
        pass
    candidates = {}
    for codec in ('cp950', 'big5', 'big5hkscs'):
        try:
            candidates[codec] = data.decode(codec)
        except UnicodeError:
            pass
    if candidates:
        chosen = next(c for c in ('cp950', 'big5', 'big5hkscs') if c in candidates)
        agreement = len(set(candidates.values())) == 1
        warnings.append('encoding_inferred_no_declared_charset')
        if not agreement:
            warnings.append('legacy_codec_candidates_differ')
        return candidates[chosen], {'encoding': chosen, 'declared': declared, 'confidence': 'strict legacy codecs agree' if agreement else 'Taiwan CP950 context; differing alternatives retained in report', 'candidates': list(candidates), 'warnings': warnings}
    # Do not invent missing glyphs: reversible byte escapes plus original TXT.
    text = data.decode('cp950', errors='backslashreplace')
    return text, {'encoding': 'cp950', 'declared': declared, 'confidence': 'damaged legacy bytes, escaped', 'warnings': warnings + ['undecodable_bytes_preserved_as_hex'], 'escaped_bytes': re.findall(r'\\x[0-9a-f]{2}', text)}

def header(value):
    if value is None:
        return ''
    parts = []
    for text, charset in email.header.decode_header(value):
        if isinstance(text, bytes):
            parts.append(decode_bytes(text, None if charset == 'unknown-8bit' else charset)[0])
        elif any(0xdc80 <= ord(c) <= 0xdcff for c in text):
            parts.append(decode_bytes(text.encode('utf-8', 'surrogateescape'))[0])
        else:
            parts.append(text)
    return ''.join(parts)

def strip_ansi(text):
    return CSI.sub('', OSC.sub('', text))

def normalize_newlines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')

def column_width(char):
    if unicodedata.combining(char) or unicodedata.category(char) in ('Mn', 'Me', 'Cf'):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ('W', 'F', 'A') else 1

def read_source(path):
    raw = pathlib.Path(path).read_bytes()
    if pathlib.Path(path).suffix.lower() == '.eml':
        msg = email.message_from_bytes(raw, policy=email.policy.compat32)
        parts = []
        for part in msg.walk():
            if not part.is_multipart() and part.get_content_type() in ('text/plain', 'text/html'):
                body = part.get_payload(decode=True)
                if body is not None:
                    text, info, tokens = decode_ansi(body, part.get_content_charset())
                    parts.append({'mime_type': part.get_content_type(), 'bytes': body, 'text': text, 'decode': info, 'tokens': tokens})
        if not parts:
            raise ValueError('no readable text MIME part; original source retained')
        preferred = next((p for p in parts if p['mime_type'] == 'text/plain'), parts[0])
        headers = {k.lower(): header(msg.get(k)) for k in ('Subject', 'Date', 'From', 'To', 'Message-ID', 'Reply-To', 'References', 'In-Reply-To')}
    else:
        text, info, tokens = decode_ansi(raw)
        preferred = {'mime_type': 'text/plain', 'bytes': raw, 'text': text, 'decode': info, 'tokens': tokens}
        parts, headers = [preferred], {}
    return {'raw': raw, 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'body': preferred['text'], 'body_bytes': preferred['bytes'], 'tokens': preferred['tokens'], 'decode': preferred['decode'], 'parts': parts, 'headers': headers, 'newlines': {'CRLF': preferred['bytes'].count(b'\r\n'), 'LF': preferred['bytes'].count(b'\n') - preferred['bytes'].count(b'\r\n'), 'CR': preferred['bytes'].count(b'\r') - preferred['bytes'].count(b'\r\n')}}

def parse_metadata(body, headers):
    plain = normalize_newlines(strip_ansi(body))
    lines = plain.split('\n')
    author = re.search(r'^[ \t]*發信人\s*[:：]\s*([^\s(,，]+)(?:\s*\((.*?)\))?\s*[,，]\s*(?:信區|看板|板名)\s*[:：]\s*([A-Za-z0-9_.-]+)', plain, re.M)
    author_tw = re.search(r'^[ \t]*作者\s*[:：]\s*(\S+)(?:\s*\((.*?)\))?\s*(?:看板|板名)\s*[:：]\s*(\S+)', plain, re.M)
    title = re.search(r'^[ \t]*(?:標\s*題|標題)\s*[:：]\s*(.*)$', plain, re.M)
    station = re.search(r'^[ \t]*發信站\s*[:：]\s*(.*?)\s*[（(](.*?)[）)]\s*[,，]?\s*(.*)$', plain, re.M)
    time_line = re.search(r'^時間\s*[:：]\s*(.*)$', plain, re.M)
    a = author or author_tw
    date_raw = station.group(2).strip() if station else time_line.group(1).strip() if time_line else ''
    date_iso = ''
    if date_raw:
        try:
            date_iso = dt.datetime.strptime(date_raw, '%a %b %d %H:%M:%S %Y').replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).isoformat()
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(date_raw)
                date_iso = parsed.isoformat()
            except (ValueError, TypeError):
                pass
    bbs_date_parsed = bool(date_iso)
    if not date_iso and headers.get('date'):
        try:
            date_iso = email.utils.parsedate_to_datetime(headers['date']).isoformat()
        except (ValueError, TypeError):
            pass
    title_text = title.group(1).strip() if title else headers.get('subject', '').strip() or '無標題'
    result = {'parser': 'firebird-senduser' if author else 'ptt-author' if author_tw else 'unrecognized-preserved', 'author': a.group(1) if a else headers.get('from', ''), 'nickname': a.group(2) or '' if a else '', 'board': a.group(3) if a else '', 'title': title_text, 'bbs_date_raw': date_raw, 'date_iso': date_iso, 'date_source': 'bbs-header' if bbs_date_parsed else 'mail-Date-fallback' if date_iso else 'unknown', 'mail_date': headers.get('date', ''), 'station': station.group(1) if station else '', 'forwarding': station.group(3) if station else '', 'article_number': None, 'signature_marker_lines': [i for i, line in enumerate(lines) if line in ('--', '-- ')], 'reply_lines': sum(bool(re.match(r'^(?:[>:]|※ 引述|\s*【 在)', line)) for line in lines), 'push_lines': sum(bool(re.match(r'^(?:推|噓|→|\S+\s*:)', line)) for line in lines), 'source_ip': re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', plain), 'warnings': []}
    if not a:
        result['warnings'].append('metadata_author_board_unrecognized')
    if not title:
        result['warnings'].append('bbs_title_unrecognized_mail_subject_fallback')
    if not date_raw:
        result['warnings'].append('bbs_date_unrecognized_mail_date_fallback')
    elif not date_iso or result['date_source'] != 'bbs-header':
        result['warnings'].append('bbs_date_parse_failed')
    return result
