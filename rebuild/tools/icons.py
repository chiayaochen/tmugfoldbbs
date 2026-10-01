"""Dependency-free PNG terminal icon; all marks stay inside maskable safe area."""
import struct
import zlib

def make_icons(folder):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    for size in (192,512):
        rows=[]
        for y in range(size):
            row=bytearray([0])
            for x in range(size):
                a=x/size;b=y/size
                mark=(.28<a<.48 and (abs(b-(a+.04))<.028 or abs(b-(-a+.96))<.028)) or (.55<a<.76 and .64<b<.69)
                row.extend((141,211,174) if mark else (18,22,21))
            rows.append(row)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')
        (folder/f'icon-{size}.png').write_bytes(png)
