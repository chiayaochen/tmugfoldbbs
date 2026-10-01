import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from bbs import decode_ansi, decode_bytes, parse_metadata, read_source, column_width
from ansi import render
from build import run

class PreservationTests(unittest.TestCase):
    def test_big5_ansi_between_bytes(self):
        raw='中'.encode('cp950')
        body,info,tokens=decode_ansi(raw[:1]+b'\x1b[31m'+raw[1:]+b'\r\n'+ '文'.encode('cp950'))
        self.assertEqual(body,'中\x1b[31m\r\n文')
        self.assertEqual(info['half_color_characters'],1)
        result=render(tokens)
        self.assertIn('half-left',result['raw']);self.assertIn('half-right',result['raw'])
        self.assertIn('color:#b94c4c',result['raw'])
        self.assertNotIn('�',result['raw'])

    def test_sgr_cross_line_and_reset(self):
        _,_,tokens=decode_ansi(b'\x1b[1;33;44;4;5;7mA\r\nB\x1b[0mC')
        html=render(tokens)['reading']
        self.assertIn('font-weight:700',html)
        self.assertIn('text-decoration:underline',html)
        self.assertIn('ansi-blink',html)
        self.assertIn('style="">C',html)
        self.assertEqual(html.count('color:#668bc9'),2)

    def test_html_is_inert_and_cursor_never_deletes(self):
        _,_,tokens=decode_ansi(b'<script>alert("x")</script>&\x1b[M keep')
        result=render(tokens)
        self.assertIn('&lt;script&gt;',result['reading'])
        self.assertNotIn('<script>',result['reading'])
        self.assertIn('keep',result['reading'])
        self.assertEqual(result['controls'][0]['sequence'],'\\x1b[M')

    def test_hkscs_and_invalid_bytes(self):
        # Representative non-CP950 HKSCS character; strict preference is tested.
        char='𨋢';body,info=decode_bytes(char.encode('big5hkscs'))
        self.assertEqual(body,char);self.assertEqual(info['encoding'],'big5hkscs')
        body,info=decode_bytes(b'\xff')
        self.assertEqual(body,'\\xff');self.assertIn('escaped_bytes',info)

    def test_width_and_metadata(self):
        self.assertEqual([column_width(c) for c in 'A中　─'],[1,2,2,2])
        raw='發信人: test (暱稱), 信區: basic_serve\r\n標  題: 測試\r\n發信站: 杏林綠意 (Sat Feb 14 13:24:50 1998), 轉信\r\n--\r\n'
        meta=parse_metadata(raw,{'date':'Wed, 26 Apr 2017 23:40:41 +0800'})
        self.assertEqual(meta['date_source'],'bbs-header')
        self.assertTrue(meta['date_iso'].startswith('1998-02-14'))
        self.assertEqual(meta['author'],'test');self.assertEqual(meta['signature_marker_lines'],[3])

    def test_batch_failure_retains_original_and_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder);source=p/'input';source.mkdir()
            (source/'bad.eml').write_bytes(b'Content-Type: application/octet-stream\r\n\r\nopaque')
            (source/'good.txt').write_bytes('完整原文'.encode('cp950'))
            before={f.name:f.read_bytes() for f in source.iterdir()}
            with self.assertRaises(SystemExit):run(source,p/'site',p/'reports')
            self.assertEqual(len(list((p/'site/metadata').glob('*.json'))),2)
            self.assertEqual(before,{f.name:f.read_bytes() for f in source.iterdir()})
            self.assertIn('fallback',(p/'reports/conversion.log').read_text())

    def test_rebuild_refuses_to_erase_a_git_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder);source=p/'input';source.mkdir()
            (source/'one.txt').write_text('保留')
            target=p/'checkout';target.mkdir();(target/'.git').mkdir()
            (target/'.bbs-generated').write_text('previous published marker')
            with self.assertRaises(ValueError):run(source,target,p/'reports')
            self.assertTrue((target/'.git').is_dir())

if __name__=='__main__':unittest.main()
