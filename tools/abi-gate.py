#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ABI 回归门：原厂模块能否加载到自编内核上。

判据（按优先级）：
  1. 每个模块的 `__versions` 条目若指向内核导出符号，其期望 CRC 必须与自编内核导出一致；
  2. 每个模块的未定义符号必须由内核导出或模块间导出提供；
  3. 输出不匹配条数与示例，退出码 0 表示全部通过。

用法：
  abi-gate.py --stock-symvers <原厂 Module.symvers> --our-symvers <自编 vmlinux.symvers> \
      --modules <vendor_boot 模块目录> --modules <vendor_dlkm 模块目录> [--out report.md]
"""
import argparse
import os
import re
import struct
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def load_symvers(path):
    d = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and f[0].startswith('0x'):
            d[f[1]] = f[0].lower()
    return d


def _section(ko, name):
    h = run(['readelf', '-S', '-W', ko]).stdout
    m = re.search(r'\b' + re.escape(name) + r'\s+\w+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)', h)
    if not m:
        return None
    return int(m.group(2), 16), int(m.group(3), 16)


def module_versions(ko):
    """读取模块期望的符号 CRC。

    6.18 起 EXTENDED_MODVERSIONS 用 `__version_ext_crcs`(u32) + `__version_ext_names`，
    加载器优先只看这一组；老格式 `__versions` 仅在扩展段缺失时使用。
    """
    ext_crc = _section(ko, '__version_ext_crcs')
    ext_name = _section(ko, '__version_ext_names')
    blob = open(ko, 'rb').read()
    out = {}
    if ext_crc and ext_name:
        off_c, size_c = ext_crc
        off_n, size_n = ext_name
        crcs = struct.unpack('<%dI' % (size_c // 4), blob[off_c:off_c + size_c])
        names_blob = blob[off_n:off_n + size_n]
        pos = 0
        for c in crcs:
            end = names_blob.index(b'\0', pos)
            name = names_blob[pos:end].decode('ascii', 'replace')
            pos = end + 1
            out[name] = '0x%08x' % c
        return out
    sec = _section(ko, '__versions')
    if not sec:
        return {}
    off, size = sec
    data = blob[off:off + size]
    for i in range(0, len(data) - 63, 64):
        crc = struct.unpack('<Q', data[i:i + 8])[0]
        name = data[i + 8:i + 64].split(b'\0')[0].decode('ascii', 'replace')
        if name:
            out[name] = '0x%08x' % crc
    return out


def module_imports(ko):
    """只统计强未定义符号；weakref（nm 类型 w/v）是可选依赖，缺失不影响加载。"""
    p = run(['nm', ko])
    out = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == 'U':
            out.add(parts[2])
        elif len(parts) == 2 and parts[0] == 'U':
            out.add(parts[1])
    return out


def module_exports(ko):
    p = run(['nm', '--defined-only', ko])
    out = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        for pre in ('__ksymtab_gpl_', '__ksymtab_'):
            if parts[2].startswith(pre):
                out.add(parts[2][len(pre):])
                break
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock-symvers', help='原厂导出符号表；省略时以自编内核为准判断哪些符号由内核提供')
    ap.add_argument('--our-symvers', required=True)
    ap.add_argument('--modules', action='append', default=[])
    ap.add_argument('--out')
    ap.add_argument('--allow-unresolved-prefix', action='append', default=[],
                    help='已知本地缺件导致的未解析符号前缀（记为警告，不判失败）')
    a = ap.parse_args(argv[1:])

    ours = load_symvers(a.our_symvers)
    stock = load_symvers(a.stock_symvers) if a.stock_symvers else ours

    kos = []
    for root in a.modules:
        for r, _d, files in os.walk(root):
            for fn in files:
                if fn.endswith('.ko'):
                    kos.append(os.path.join(r, fn))
    if not kos:
        raise SystemExit('没有找到 .ko')

    mod_exports = set()
    for ko in kos:
        mod_exports |= module_exports(ko)
    provided = set(ours) | mod_exports

    version_mismatch = []
    missing_imports = {}
    for ko in kos:
        rel = os.path.basename(ko)
        for sym, expect in module_versions(ko).items():
            if sym in ours:  # 该符号由内核提供，模块会校验 CRC
                if ours[sym].lower() != expect.lower():
                    version_mismatch.append((rel, sym, expect, ours.get(sym)))
        lack = sorted(s for s in module_imports(ko) if s not in provided and s != 'module_layout')
        if lack:
            hard = [s for s in lack if not any(s.startswith(pre) for pre in a.allow_unresolved_prefix)]
            if hard:
                missing_imports[rel] = hard

    md = []
    md.append('# ABI 回归门\n')
    md.append('- 模块 %d 个；内核导出 %d；模块间导出 %d' % (len(kos), len(ours), len(mod_exports)))
    md.append('- 内核符号 CRC 不符：**%d** 条' % len(version_mismatch))
    for r, s, e, g in version_mismatch[:10]:
        md.append('  - %s:%s 期望 %s 实际 %s' % (r, s, e, g))
    md.append('- 无法解析导入的模块：**%d**' % len(missing_imports))
    for r, lack in list(missing_imports.items())[:10]:
        md.append('  - %s 缺 %d：%s' % (r, len(lack), ', '.join(lack[:6])))
    passed = not version_mismatch and not missing_imports
    md.append('\n**判定：%s**' % ('PASS' if passed else 'FAIL'))
    text = '\n'.join(md) + '\n'
    print(text)
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, 'w', encoding='utf-8').write(text)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
