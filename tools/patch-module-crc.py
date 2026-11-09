#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把原厂模块的符号版本 CRC 改写为自编内核的 CRC（研究用）。

背景：6.18 起使用 EXTENDED_MODVERSIONS，模块里的 `__version_ext_crcs`(u32) 与
`__version_ext_names` 一一对应；加载器只按扩展段校验。本脚本按名字把 CRC 改成
目标内核（vmlinux.symvers）的值，使模块通过 CRC 检查。

注意：改写会让模块签名失效（MODULE_SIG_FORCE=n 时仍可加载），并且如果内核与模块
之间存在真实的类型/布局差异，运行时仍可能出错——必须真机验证，不作为日用方案。

用法：
  patch-module-crc.py --symvers out618_cdev/vmlinux.symvers \
      --src <模块目录> --dst <输出目录>
"""
import argparse
import os
import re
import shutil
import struct
import sys


def load_symvers(path):
    d = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and f[0].startswith('0x'):
            d[f[1]] = int(f[0], 16)
    return d


def section(path, name):
    import subprocess
    h = subprocess.run(['readelf', '-S', '-W', path], capture_output=True, text=True).stdout
    m = re.search(r'\b' + re.escape(name) + r'\s+\w+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)', h)
    if not m:
        return None
    return int(m.group(2), 16), int(m.group(3), 16)


def patch_ko(path, symvers):
    blob = bytearray(open(path, 'rb').read())
    patched = 0
    crc_sec = section(path, '__version_ext_crcs')
    name_sec = section(path, '__version_ext_names')
    if crc_sec and name_sec:
        off_c, size_c = crc_sec
        off_n, size_n = name_sec
        names_blob = bytes(blob[off_n:off_n + size_n])
        pos = 0
        idx = 0
        while idx * 4 < size_c:
            end = names_blob.index(b'\0', pos)
            name = names_blob[pos:end].decode('ascii', 'replace')
            pos = end + 1
            if name in symvers:
                want = symvers[name]
                got = struct.unpack('<I', blob[off_c + idx * 4:off_c + idx * 4 + 4])[0]
                if got != want:
                    blob[off_c + idx * 4:off_c + idx * 4 + 4] = struct.pack('<I', want)
                    patched += 1
            idx += 1
        return bytes(blob), patched, True
    # 老格式：__versions，64 字节条目（u64 crc + char name[56]）
    sec = section(path, '__versions')
    if sec:
        off, size = sec
        for i in range(0, size - 63, 64):
            name = bytes(blob[off + i + 8:off + i + 64]).split(b'\0')[0].decode('ascii', 'replace')
            if name in symvers:
                want = symvers[name]
                got = struct.unpack('<Q', blob[off + i:off + i + 8])[0]
                if got != want:
                    blob[off + i:off + i + 8] = struct.pack('<Q', want)
                    patched += 1
        return bytes(blob), patched, True
    return bytes(blob), 0, False


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--symvers', required=True)
    ap.add_argument('--src', required=True)
    ap.add_argument('--dst', required=True)
    a = ap.parse_args(argv[1:])
    symvers = load_symvers(a.symvers)
    total = 0
    files = 0
    with_ext = 0
    for root, _d, fs in os.walk(a.src):
        for fn in fs:
            if not fn.endswith('.ko'):
                continue
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, a.src)
            dst = os.path.join(a.dst, rel)
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            data, n, ok = patch_ko(src, symvers)
            open(dst, 'wb').write(data)
            files += 1
            total += n
            with_ext += 1 if ok else 0
    print('模块 %d 个，改写 CRC %d 条，输出到 %s' % (files, total, a.dst))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
