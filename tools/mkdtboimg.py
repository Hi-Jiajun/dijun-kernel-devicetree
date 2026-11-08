#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 Android dtbo.img（dt_table_header + dt_table_entry + 各 entry 的 DTBO）。

行为对齐 AOSP mkdtimg 的产物布局（已用设备 dtbo_a 实测验证）：
  - 头部 32 字节大端：magic/total_size/header_size/entry_size/entry_count/
    entries_offset/page_size/version
  - 每个 entry 32 字节：dt_size/dt_offset/id/rev/custom0..3
  - 各 DTBO 紧接在条目表后连续排布（本机 stock 镜像即如此，不做按页填充）
  - id/rev 默认从 DTBO 根节点的 board_id/board_rev 读取，custom0 默认 0xabc

用法：
  mkdtboimg.py --out build/dtbo.img --entry a.dtbo --entry b.dtbo
  mkdtboimg.py --out build/x.img --entry a.dtbo:id=0x090f0000,rev=0
  mkdtboimg.py --info stock/device-dtbo_a.img     # 打印容器信息
"""
import argparse
import struct
import sys

MAGIC = 0xD7B7AB1E
HEADER_SIZE = 32
ENTRY_SIZE = 32
PAGE_SIZE = 2048
VERSION = 0
CUSTOM0 = 0xABC


def read_root_props(blob):
    """只读 FDT 结构块里根节点的属性，取 board_id / board_rev。"""
    magic, _, off_struct, off_strings, _, _, _, _, size_strings, _ = struct.unpack('>10I', blob[:40])
    if magic != 0xD00DFEED:
        raise ValueError('不是 FDT')
    strings = blob[off_strings:off_strings + size_strings]
    i = off_struct
    props = {}
    depth = 0
    while True:
        tok = struct.unpack('>I', blob[i:i + 4])[0]
        i += 4
        if tok == 1:  # BEGIN_NODE
            end = blob.index(b'\0', i)
            name = blob[i:end]
            i = (end + 4) & ~3
            depth += 1
            if depth > 1:
                # 只关心根节点属性；用占位 token 跳过子树
                break
        elif tok == 3:  # PROP
            ln, nameoff = struct.unpack('>II', blob[i:i + 8])
            i += 8
            val = blob[i:i + ln]
            i = (i + ln + 3) & ~3
            nm = strings[nameoff:strings.index(b'\0', nameoff)].decode()
            props[nm] = val
        elif tok == 9:
            break
        else:
            break
    return props


def make_entry(path, override):
    blob = open(path, 'rb').read()
    props = read_root_props(blob)
    def u32(name, default):
        raw = props.get(name)
        return struct.unpack('>I', raw)[0] if raw and len(raw) == 4 else default
    eid = override.get('id', u32('board_id', 0))
    rev = override.get('rev', u32('board_rev', 0))
    custom0 = override.get('custom0', CUSTOM0)
    return blob, eid, rev, custom0


def pack(paths, out):
    entries = []
    for p in paths:
        override = {}
        if ':' in p:
            p, spec = p.split(':', 1)
            for kv in spec.split(','):
                k, v = kv.split('=')
                override[k] = int(v, 0)
        entries.append(make_entry(p, override))
    count = len(entries)
    data_off = HEADER_SIZE + count * ENTRY_SIZE
    body = bytearray()
    table = bytearray()
    for blob, eid, rev, custom0 in entries:
        table += struct.pack('>8I', len(blob), data_off + len(body), eid, rev, custom0, 0, 0, 0)
        body += blob
    total = data_off + len(body)
    header = struct.pack('>8I', MAGIC, total, HEADER_SIZE, ENTRY_SIZE, count,
                         HEADER_SIZE, PAGE_SIZE, VERSION)
    with open(out, 'wb') as f:
        f.write(header + table + body)
    return total, count, entries


def info(path):
    d = open(path, 'rb').read()
    magic, total, hsz, esz, cnt, off, page, ver = struct.unpack('>8I', d[:32])
    print('magic=%#x total=%d header=%d entry=%d count=%d entries_off=%d page=%d version=%d file=%d'
          % (magic, total, hsz, esz, cnt, off, page, ver, len(d)))
    for i in range(cnt):
        sz, o, idx, rev, c0, c1, c2, c3 = struct.unpack('>8I', d[off + i * esz: off + (i + 1) * esz])
        print('  [%d] size=%d off=%d id=%#010x rev=%d custom=%#x/%#x/%#x/%#x'
              % (i, sz, o, idx, rev, c0, c1, c2, c3))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--entry', action='append', default=[])
    ap.add_argument('--info')
    a = ap.parse_args(argv[1:])
    if a.info:
        info(a.info)
        return 0
    if not a.out or not a.entry:
        ap.print_help()
        return 2
    total, count, entries = pack(a.entry, a.out)
    print('写出 %s: entries=%d total=%d' % (a.out, count, total))
    for blob, eid, rev, c0 in entries:
        print('  id=%#010x rev=%d size=%d' % (eid, rev, len(blob)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
