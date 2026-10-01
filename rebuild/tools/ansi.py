"""Safe ANSI renderer. Decode controls BEFORE legacy multibyte characters.

Conservative archival stream, not a destructive 24-line terminal replay: cursor
commands are recorded, represented by optional annotations, and never erase text.
"""
import copy
import html
import re
from bbs import CSI, OSC, column_width, normalize_newlines

PALETTE = ['#121212','#b94c4c','#58a66a','#b8a35c','#668bc9','#aa72b0','#62a8ad','#cccccc',
           '#747474','#ff7676','#8bce8b','#e7d784','#94b5f7','#dca1e4','#97dce0','#eeeeee']

class Style:
    def __init__(self):
        self.reset()

    def reset(self):
        self.fg = self.bg = None
        self.bold = self.underline = self.blink = self.reverse = False

    def sgr(self, params, errors):
        # FireBird signatures sometimes contain private =m/=S/=M sequences.
        if any(c not in '0123456789;' for c in params):
            errors.append({'code': params + 'm', 'reason': 'private_sgr_preserved_no_known_semantics'})
            return
        values = [int(p) if p else 0 for p in params.split(';')]
        i = 0
        while i < len(values):
            n = values[i]
            if n == 0: self.reset()
            elif n == 1: self.bold = True
            elif n == 4: self.underline = True
            elif n == 5: self.blink = True
            elif n == 7: self.reverse = True
            elif n == 22: self.bold = False
            elif n == 24: self.underline = False
            elif n == 25: self.blink = False
            elif n == 27: self.reverse = False
            elif 30 <= n <= 37: self.fg = PALETTE[n - 30]
            elif 40 <= n <= 47: self.bg = PALETTE[n - 40]
            elif 90 <= n <= 97: self.fg = PALETTE[n - 90 + 8]
            elif 100 <= n <= 107: self.bg = PALETTE[n - 100 + 8]
            elif n == 39: self.fg = None
            elif n == 49: self.bg = None
            elif n in (38, 48) and i + 2 < len(values) and values[i + 1] == 5:
                k = min(255, values[i + 2]); i += 2
                if k < 16: color = PALETTE[k]
                elif k >= 232: color = '#{0:02x}{0:02x}{0:02x}'.format(8 + (k - 232)*10)
                else:
                    v = k - 16; levels = [0,95,135,175,215,255]
                    color = '#%02x%02x%02x' % (levels[v//36], levels[v//6%6], levels[v%6])
                if n == 38: self.fg = color
                else: self.bg = color
            elif n in (38,48) and i + 4 < len(values) and values[i+1] == 2:
                color = '#%02x%02x%02x' % tuple(min(255,max(0,x)) for x in values[i+2:i+5]); i += 4
                if n == 38: self.fg = color
                else: self.bg = color
            else: errors.append({'code': str(n)+'m', 'reason': 'unsupported_sgr'})
            i += 1

    def css(self):
        fg, bg = self.fg, self.bg
        if self.bold and fg in PALETTE[:8]: fg = PALETTE[PALETTE.index(fg)+8]
        if self.reverse: fg, bg = bg or '#121212', fg or '#ddd'
        return ';'.join(([f'color:{fg}'] if fg else []) + ([f'background-color:{bg}'] if bg else []) +
                        (['font-weight:700'] if self.bold else []) + (['text-decoration:underline'] if self.underline else []))

def parse(tokens):
    style = Style(); rows = [[]]; errors = []; controls = []
    def control(code):
        match = CSI.fullmatch(code)
        if match and match.group(3) == 'm': style.sgr(match.group(1), errors)
        else:
            controls.append({'line': len(rows), 'sequence': code.encode('unicode_escape').decode('ascii')})
            # Preserve a zero-column marker in BOTH views; users can inspect its
            # meaning without applying uncertain destructive cursor behavior.
            rows[-1].append({'marker': code.encode('unicode_escape').decode('ascii')})
            errors.append({'code': code.encode('unicode_escape').decode('ascii'), 'reason': 'cursor_or_unknown_control_retained_as_annotation'})
    for token in tokens:
        if token['type'] == 'ansi': control(token['text']); continue
        if token['type'] == 'half':
            left = style.css()
            for seq in token['sequences']: control(seq)
            rows[-1].append({'text': token['text'], 'css': left, 'right_css': style.css(), 'blink': style.blink})
            continue
        # Unicode BOM inputs may still contain ANSI inside text tokens.
        pieces = re.split(r'(\x1b\[[0-?]*[ -/]*[@-~]|\^\[\[?[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\))', token['text'])
        for piece in pieces:
            if CSI.fullmatch(piece) or OSC.fullmatch(piece): control(piece); continue
            lines = normalize_newlines(piece).split('\n')
            for i, line in enumerate(lines):
                if i: rows.append([])
                if line: rows[-1].append({'text': line, 'css': style.css(), 'blink': style.blink})
    return rows, errors, controls

def fixed_text(text, column):
    result = []; ascii_run = ''; wide_spaces = ''
    def flush():
        nonlocal ascii_run
        result.append(html.escape(ascii_run)); ascii_run = ''
    def flush_spaces():
        nonlocal wide_spaces
        if wide_spaces:
            # Fullwidth spaces have no ink to position. One exact-width box
            # preserves every space but avoids tens of thousands of DOM nodes
            # in large ANSI posters.
            result.append('<span class="wide-spaces" style="width:calc(var(--cell)*'+str(2*len(wide_spaces))+')">'+wide_spaces+'</span>')
            wide_spaces = ''
    for char in text:
        if char == '\u3000':
            flush(); wide_spaces += char; column += 2; continue
        flush_spaces()
        if char == '\t':
            count = 8 - column % 8; ascii_run += ' ' * count; column += count
        elif char == '\b':
            flush(); result.append('<span class="control-note" title="原始退格字元">⌫</span>')
        elif ord(char) < 32:
            flush(); result.append('<span class="control-note">'+html.escape(repr(char)[1:-1])+'</span>')
        elif ord(char) < 127:
            ascii_run += char; column += 1
        else:
            flush(); w = column_width(char)
            if w == 0:
                result.append(html.escape(char))
            else:
                if '\u2500' <= char <= '\u25ff':
                    result.append(f'<span class="c{w} shape"><span>'+html.escape(char)+'</span></span>')
                else: result.append(f'<span class="c{w}">'+html.escape(char)+'</span>')
                column += w
    flush_spaces(); flush()
    return ''.join(result), column

def render_row(row, fixed):
    parts = []; column = 0
    for cell in row:
        if 'marker' in cell:
            parts.append('<span class="control-note" title="原始終端控制碼：'+html.escape(cell['marker'],quote=True)+'">⌘</span>'); continue
        text = cell['text']; css = cell['css']
        blink = ' ansi-blink' if cell.get('blink') else ''
        if 'right_css' in cell and len(text) == 1 and column_width(text) == 2:
            # Each Big5 byte had its own ANSI state. Draw two clipped halves of
            # the SAME decoded character, not two broken replacement glyphs.
            escaped = html.escape(text)
            shape = '\u2500' <= text <= '\u25ff'
            glyph = '<span>'+escaped+'</span>' if shape else escaped
            parts.append('<span class="half c2'+(' half-shape' if shape else '')+'" role="img" aria-label="'+escaped+'">'+
                         '<span class="half-left" aria-hidden="true" style="'+css+'">'+glyph+'</span>'+
                         '<span class="half-right" aria-hidden="true" style="'+cell['right_css']+'">'+glyph+'</span></span>')
            column += 2
        else:
            if fixed: escaped, column = fixed_text(text, column)
            else: escaped = html.escape(text).replace('\t','        ')
            parts.append('<span class="ansi'+blink+'" style="'+css+'">'+escaped+'</span>')
    return ''.join(parts)

def render(tokens):
    rows, errors, controls = parse(tokens)
    plain = [''.join(c.get('text','') for c in row) for row in rows]
    art = set()
    for i, line in enumerate(plain):
        boxes = sum('\u2500' <= c <= '\u259f' for c in line)
        punct = sum(c in '/\\_|^*+=~' for c in line)
        multi_columns = bool(re.search(r'\S {4,}\S', line))
        short_letters = len(re.sub(r'[\s\W_]','',line)) < max(5,len(line)//3)
        if boxes >= 2 or (punct >= 8 and short_letters) or (multi_columns and punct >= 4):
            art.update(range(max(0,i-1),min(len(rows),i+2)))
    reading = []; i = 0
    while i < len(rows):
        is_art = i in art; end = i+1
        while end < len(rows) and (end in art) == is_art: end += 1
        content = '\n'.join(render_row(row,is_art) for row in rows[i:end])
        if is_art: reading.append('<div class="art-scroll" tabindex="0" aria-label="原始圖形區塊，可左右捲動"><pre class="terminal art">'+content+'</pre></div>')
        else: reading.append('<div class="prose">'+content+'</div>')
        i = end
    raw = '\n'.join(render_row(row,True) for row in rows)
    return {'reading': ''.join(reading), 'raw': '<div class="art-scroll raw-scroll" tabindex="0" aria-label="原始 BBS 固定欄寬，可左右捲動"><pre class="terminal">'+raw+'</pre></div>', 'errors': errors, 'controls': controls, 'art_lines':len(art)}
