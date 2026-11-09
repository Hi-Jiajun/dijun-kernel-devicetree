#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""从 Android dtbo.img 容器中按条目导出各 overlay。

用法：
  dtbo-extract.py --info dtbo.img
  dtbo-extract.py --img dtbo.img --out <目录>

头部/条目为 big-endian；条目紧接头部连续排布（与 AOSP mkdtimg 产物一致）。
"""
import argparse
import os
import struct
import sys

MAGIC = 0xD7B7AB1E


def parse(blob):
    if len(blob) < 32:
        raise SystemExit('文件太短，不是 dtbo 容器')
    magic, total, hsz, esz, cnt, off, page, ver = struct.unpack('>8I', blob[:32])
    if magic != MAGIC:
        raise SystemExit('magic 不符: %#x' % magic)
    entries = []
    for i in range(cnt):
        start = off + i * esz
        chunk = blob[start:start + esz]
        if len(chunk) < 16:
            raise SystemExit('条目表不完整（第 %d 条）' % i)
        size, doff, eid, rev = struct.unpack('>4I', chunk[:16])
        entries.append({'index': i, 'size': size, 'offset': doff, 'id': eid, 'rev': rev,
                        'blob': blob[doff:doff + size]})
    return {'total': total, 'page': page, 'version': ver, 'entries': entries}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--img')
    ap.add_argument('--out')
    ap.add_argument('--info', action='store_true')
    a = ap.parse_args(argv[1:])
    if not a.img:
        ap.print_help()
        return 2
    blob = open(a.img, 'rb').read()
    info = parse(blob)
    print('total=%d page=%d version=%d entries=%d' %
          (info['total'], info['page'], info['version'], len(info['entries'])))
    for e in info['entries']:
        print('  [%d] size=%d off=%d id=%#010x rev=%d' %
              (e['index'], e['size'], e['offset'], e['id'], e['rev']))
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for e in info['entries']:
            name = 'entry%02d_id%08x_rev%d.dtbo' % (e['index'], e['id'], e['rev'])
            with open(os.path.join(a.out, name), 'wb') as f:
                f.write(e['blob'])
            print('  写出', name)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
