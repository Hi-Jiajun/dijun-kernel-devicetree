#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTF 结构/函数原型比较（dijun vendor vs 自编内核）。

vendor BTF 从 stock Image 里直接扫描得到（.BTF 段在镜像里，非 ELF 也无妨）；
自编内核 BTF 从 out2/vmlinux（ELF）的 .BTF 段读取。

用途：
  btf-diff.py --a <Image|vmlinux> --b <vmlinux> --struct task_struct --func wake_up_process

输出：结构体大小/成员数、成员的增删与偏移变化；函数原型的参数类型序列。
"""
import argparse
import re
import struct
import subprocess
import sys

BTF_MAGIC = 0xEB9F
KIND_NAMES = {
    0: 'UNKN', 1: 'INT', 2: 'PTR', 3: 'ARRAY', 4: 'STRUCT', 5: 'UNION', 6: 'ENUM',
    7: 'FWD', 8: 'TYPEDEF', 9: 'VOLATILE', 10: 'CONST', 11: 'RESTRICT', 12: 'FUNC',
    13: 'FUNC_PROTO', 14: 'VAR', 15: 'DATASEC', 16: 'FLOAT', 17: 'DECL_TAG',
    18: 'TYPE_TAG', 19: 'ENUM64',
}
EXTRA_SIZE = {1: 4, 3: 12, 4: None, 5: None, 6: None, 13: None, 14: 4, 15: None,
              16: 0, 17: 4, 19: None}


def find_btf_blob(blob):
    if blob[:4] == b'\x7fELF':
        h = subprocess.run(['readelf', '-S', '-W', '/dev/stdin'], input=blob,
                           capture_output=True).stdout.decode('utf-8', 'replace')
        m = re.search(r'\.BTF\s+PROGBITS\s+[0-9a-f]+\s+([0-9a-f]+)\s+([0-9a-f]+)', h)
        if not m:
            raise SystemExit('ELF 里找不到 .BTF 段')
        off, size = int(m.group(1), 16), int(m.group(2), 16)
        return blob[off:off + size]
    i = 0
    while True:
        i = blob.find(b'\x9f\xeb', i)
        if i < 0:
            raise SystemExit('扫描不到 BTF')
        if i + 24 <= len(blob):
            magic, ver, _flags, hdr_len, type_off, type_len, str_off, str_len = \
                struct.unpack('<HBBIIIII', blob[i:i + 24])
            if magic == BTF_MAGIC and ver == 1 and hdr_len == 24 and type_len and str_len:
                total = hdr_len + type_len + str_len
                if i + total <= len(blob) and blob[i + total - 1] == 0:
                    return blob[i:i + total]
        i += 2


class BTF:
    def __init__(self, blob):
        magic, _ver, _flags, hdr_len, type_off, type_len, str_off, str_len = \
            struct.unpack('<HBBIIIII', blob[:24])
        self.types_blob = blob[hdr_len + type_off:hdr_len + type_off + type_len]
        self.strs = blob[hdr_len + str_off:hdr_len + str_off + str_len]
        self.types = [None]  # type id 从 1 开始
        self._parse()

    def s(self, off):
        end = self.strs.find(b'\0', off)
        return self.strs[off:end].decode('utf-8', 'replace')

    def _parse(self):
        b, i = self.types_blob, 0
        while i + 12 <= len(b):
            name_off, info, size = struct.unpack('<III', b[i:i + 12])
            i += 12
            vlen, kind = info & 0xFFFF, (info >> 24) & 0x1F
            rec = {'name': self.s(name_off) if name_off < len(self.strs) else '',
                   'kind': kind, 'vlen': vlen, 'size': size, 'extra': b''}
            if kind in (4, 5):
                rec['members'] = []
                for _ in range(vlen):
                    mn, mt, moff = struct.unpack('<III', b[i:i + 12])
                    rec['members'].append({'name': self.s(mn), 'type': mt, 'bit_off': moff})
                    i += 12
            elif kind == 13:
                rec['params'] = []
                for _ in range(vlen):
                    pn, pt = struct.unpack('<II', b[i:i + 8])
                    rec['params'].append({'name': self.s(pn), 'type': pt})
                    i += 8
            elif kind == 3:
                rec['extra'] = b[i:i + 12]
                i += 12
            elif kind in (6, 15):
                rec['extra'] = b[i:i + vlen * 12]
                i += vlen * 12
            elif kind == 19:
                rec['extra'] = b[i:i + vlen * 12]
                i += vlen * 12
            else:
                n = EXTRA_SIZE.get(kind, 0) or 0
                rec['extra'] = b[i:i + n]
                i += n
            self.types.append(rec)

    def type_name(self, tid, depth=0):
        if tid == 0 or tid >= len(self.types) or depth > 8:
            return 'void' if tid == 0 else '?%d' % tid
        t = self.types[tid]
        k = t['kind']
        if k in (8, 9, 10, 11, 18):
            return (t['name'] + ' -> ' if k == 8 and t['name'] else '') + self.type_name(t['size'], depth + 1)
        if k == 2:  # PTR
            return self.type_name(t['size'], depth + 1) + ' *'
        if k == 3:
            et, _idx, ne = struct.unpack('<III', t['extra'])
            return '%s[%d]' % (self.type_name(et, depth + 1), ne)
        if k in (4, 5):
            return ('struct ' if k == 4 else 'union ') + (t['name'] or '?')
        if k == 6:
            return 'enum ' + (t['name'] or '?')
        if k == 1:
            return t['name'] or 'int'
        if k == 12:
            return 'func ' + (t['name'] or '?')
        if k == 13:
            return 'proto'
        return KIND_NAMES.get(k, '?%d' % k).lower() + ' ' + (t['name'] or '')

    def find(self, kind, name):
        for tid, t in enumerate(self.types):
            if t and t['kind'] == kind and t['name'] == name:
                return tid
        return None


def dump_struct(btf, name):
    tid = btf.find(4, name)
    if tid is None:
        return None
    t = btf.types[tid]
    return {'size': t['size'] // 8, 'members': [
        (m['name'], btf.type_name(m['type']), m['bit_off'] // 8) for m in t['members']]}


def dump_func(btf, name):
    tid = btf.find(12, name)
    if tid is None:
        return None
    proto = btf.types[tid]['size']
    if proto == 0 or btf.types[proto]['kind'] != 13:
        return None
    p = btf.types[proto]
    return [btf.type_name(x['type']) for x in p['params']]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True, help='vendor 侧（Image 或 vmlinux）')
    ap.add_argument('--b', required=True, help='自编内核 vmlinux')
    ap.add_argument('--struct', action='append', default=[])
    ap.add_argument('--func', action='append', default=[])
    a = ap.parse_args(argv[1:])
    ba = BTF(find_btf_blob(open(a.a, 'rb').read()))
    bb = BTF(find_btf_blob(open(a.b, 'rb').read()))
    print('vendor BTF 类型 %d，自编 BTF 类型 %d\n' % (len(ba.types) - 1, len(bb.types) - 1))
    for name in a.struct:
        x, y = dump_struct(ba, name), dump_struct(bb, name)
        print('== struct %s' % name)
        if x is None or y is None:
            print('   一侧缺失：vendor=%s 自编=%s' % (x is not None, y is not None))
            continue
        print('   size: vendor=%d 自编=%d；成员数 %d vs %d' % (x['size'], y['size'], len(x['members']), len(y['members'])))
        mx = {m[0]: (m[1], m[2]) for m in x['members'] if m[0]}
        my = {m[0]: (m[1], m[2]) for m in y['members'] if m[0]}
        only_v = [k for k in mx if k not in my]
        only_o = [k for k in my if k not in mx]
        diffs = [(k, mx[k], my[k]) for k in mx if k in my and mx[k] != my[k]]
        if only_v: print('   仅 vendor: %s' % ', '.join(only_v[:12]))
        if only_o: print('   仅自编: %s' % ', '.join(only_o[:12]))
        for k, va, vb in diffs[:12]:
            print('   ~ %-24s vendor(%s@%s) 自编(%s@%s)' % (k, va[0], va[1], vb[0], vb[1]))
        if len(diffs) > 12: print('   ... 另有 %d 处成员差异' % (len(diffs) - 12))
    for name in a.func:
        x, y = dump_func(ba, name), dump_func(bb, name)
        print('== func %s' % name)
        if x is None or y is None:
            print('   一侧缺失：vendor=%s 自编=%s' % (x is not None, y is not None))
            continue
        print('   vendor: (%s)' % ', '.join(x))
        print('   自编  : (%s)' % ', '.join(y))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
