#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""纯 Python 从 .ko 模块目录提取导出符号与 CRC，生成标准 Module.symvers。

用法：
  export-mod-symvers.py --modules <dir> [--modules <dir2>] --out vendor-modules.symvers
  export-mod-symvers.py --moddir vendor_boot=<dir1> --moddir vendor_dlkm=<dir2> --out out.symvers
"""
import argparse
import os
import sys

from _elfmod import KoElf


def iter_kos(specs):
    for spec in specs:
        if '=' in spec:
            label, root = spec.split('=', 1)
        else:
            root = spec
            label = os.path.basename(os.path.abspath(root))
        found = []
        for r, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if fn.endswith('.ko'):
                    full = os.path.join(r, fn)
                    rel = os.path.relpath(full, root).replace(os.sep, '/')
                    found.append((label, rel, full))
        if not found:
            raise SystemExit('模块目录里没有找到 .ko: %s' % root)
        for item in sorted(found):
            yield item


def main(argv):
    ap = argparse.ArgumentParser(description='从 .ko 模块提取导出符号 CRC 生成 Module.symvers')
    ap.add_argument('--modules', action='append', default=[], help='模块目录（可多次指定）')
    ap.add_argument('--moddir', action='append', default=[], help='带标签模块目录 <label>=<dir>')
    ap.add_argument('--keep-ext', action='store_true', help='第 3 列保留 .ko 扩展名（默认按标准 modpost 格式去掉 .ko）')
    ap.add_argument('--out', required=True, help='输出 symvers 文件路径')
    a = ap.parse_args(argv[1:])

    specs = list(a.moddir) + list(a.modules)
    if not specs:
        raise SystemExit('必须至少提供一个 --modules 或 --moddir')

    entries = {}  # sym -> (crc, mod_col, exp_type, ns, source_id)
    conflicts = []
    mod_count = 0

    for label, rel, full in iter_kos(specs):
        mod_count += 1
        elf = KoElf(full)
        exp = elf.export_details()
        declared = elf.exports()
        if declared - set(exp):
            print('WARN %s:%s 有 %d 个 __ksymtab 符号缺 __crc_ 条目' % (label, rel, len(declared - set(exp))),
                  file=sys.stderr)
        mod_name = rel if a.keep_ext else os.path.splitext(rel)[0]
        mod_col = '%s/%s' % (label, mod_name)
        for sym, (crc, exp_type, ns) in exp.items():
            if sym in entries:
                prev_crc, _prev_mod, _prev_type, _prev_ns, prev_src = entries[sym]
                if prev_crc != crc:
                    conflicts.append((sym, prev_crc, prev_src, crc, '%s:%s' % (label, rel)))
                continue
            entries[sym] = (crc, mod_col, exp_type, ns, '%s:%s' % (label, rel))

    if conflicts:
        for sym, c1, s1, c2, s2 in conflicts[:20]:
            print('ERROR CRC 冲突: %s 在 %s (0x%08x) 与 %s (0x%08x) 不一致' % (sym, s1, c1, s2, c2),
                  file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        for sym in sorted(entries):
            crc, mod_col, exp_type, ns, _src = entries[sym]
            f.write('0x%08x\t%s\t%s\t%s\t%s\n' % (crc, sym, mod_col, exp_type, ns))

    print('导出完成: 扫描 %d 个模块，提取 %d 条符号 -> %s' % (mod_count, len(entries), a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
