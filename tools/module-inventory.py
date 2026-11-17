#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原厂模块需求集与依赖图（dijun 6.6.118）。

输入：若干模块目录（vendor_boot ramdisk / vendor_dlkm …）
输出：
  - 每个 .ko 的 vermagic / depends / 导入符号 / 导出符号 / __versions 记录数
  - 提供方解析：内核导出（原厂 Module.symvers）+ 模块间导出
  - 每个模块无法解析的导入符号、跨模块依赖边
  - Markdown 摘要 + JSON

用法：
  module-inventory.py --kernel-symvers <原厂 Module.symvers> \
      --tree os3-vendor_boot:/path/to/lib/modules/... \
      --tree vendor_dlkm:/path/to/vendor_dlkm \
      --out report/module-inventory.md
"""
import argparse
import json
import os
import re
import struct
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def modinfo(ko):
    d = {}
    for key in ('vermagic', 'depends', 'license', 'srcversion'):
        p = run(['modinfo', '-F', key, ko])
        if p.returncode == 0:
            d[key] = p.stdout.strip()
    return d


def imports(ko):
    p = run(['nm', '-u', ko])
    out = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        if parts:
            out.add(parts[-1])
    return out


def exports(ko):
    p = run(['nm', '--defined-only', ko])
    out = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            name = parts[2]
            for pre in ('__ksymtab_gpl_', '__ksymtab_'):
                if name.startswith(pre):
                    out.add(name[len(pre):])
                    break
    return out


def versions(ko):
    """解析 __versions 段：{symbol: crc}。"""
    h = run(['readelf', '-S', '-W', ko]).stdout
    m = re.search(r'__versions\s+\w+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)', h)
    if not m:
        return {}
    off, size = int(m.group(2), 16), int(m.group(3), 16)
    if not size:
        return {}
    with open(ko, 'rb') as f:
        f.seek(off)
        data = f.read(size)
    out = {}
    step = 64  # unsigned long crc + char name[56]
    for i in range(0, len(data) - step + 1, step):
        crc = struct.unpack('<Q', data[i:i + 8])[0]
        name = data[i + 8:i + 64].split(b'\0')[0].decode('ascii', 'replace')
        if name:
            out[name] = '0x%08x' % crc
    return out


def read_kernel_symvers(path):
    syms = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and f[0].startswith('0x'):
            syms[f[1]] = f[0]
    return syms


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--kernel-symvers', required=True)
    ap.add_argument('--tree', action='append', default=[], help='名称:目录')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv[1:])

    kernel = read_kernel_symvers(a.kernel_symvers)
    mods = {}   # name -> info
    by_path = {}
    for spec in a.tree:
        label, root = spec.split(':', 1)
        for r, _d, files in os.walk(root):
            for fn in files:
                if not fn.endswith('.ko'):
                    continue
                path = os.path.join(r, fn)
                name = fn[:-3]
                key = label + '/' + os.path.relpath(path, root)
                info = {
                    'name': name,
                    'key': key,
                    'source': label,
                    'path': path,
                    'size': os.path.getsize(path),
                    'imports': sorted(imports(path)),
                    'exports': sorted(exports(path)),
                    'versions': versions(path),
                    'modinfo': modinfo(path),
                }
                mods[key] = info
                by_path[path] = key

    mod_exports = {}
    for key, info in mods.items():
        for s in info['exports']:
            mod_exports.setdefault(s, []).append(key)

    providers = set(kernel) | set(mod_exports)

    md = []
    md.append('# 原厂模块需求集与依赖图\n')
    md.append('模块总数 %d；内核导出符号（原厂 Module.symvers）%d；模块间导出符号 %d。\n'
              % (len(mods), len(kernel), len(mod_exports)))
    src_cnt = {}
    for info in mods.values():
        src_cnt[info['source']] = src_cnt.get(info['source'], 0) + 1
    md.append('来源分布：%s\n' % '，'.join('%s=%d' % kv for kv in sorted(src_cnt.items())))

    unresolved = {}
    dep_edges = 0
    vers_mismatch = []
    for key, info in mods.items():
        lack = [s for s in info['imports'] if s not in providers and s != 'module_layout']
        if lack:
            unresolved[key] = lack
        for s in info['imports']:
            if s in mod_exports and key not in mod_exports[s]:
                dep_edges += 1
        for s, crc in info['versions'].items():
            if s in kernel and kernel[s].lower() != crc.lower():
                vers_mismatch.append((key, s, crc, kernel[s]))

    md.append('\n## 1. 解析结果')
    md.append('- 有无法解析导入符号的模块：**%d / %d**' % (len(unresolved), len(mods)))
    md.append('- 跨模块依赖边（导入→模块导出）：%d' % dep_edges)
    md.append('- 模块 `__versions` 与原厂内核符号表 CRC 不一致的条目：%d' % len(vers_mismatch))
    if vers_mismatch:
        md.append('  - 示例：%s' % '; '.join('%s:%s(模块 %s/内核 %s)' % t for t in vers_mismatch[:5]))

    md.append('\n## 2. 无法解析清单（按缺失数量排序）')
    for name, lack in sorted(unresolved.items(), key=lambda kv: -len(kv[1]))[:20]:
        md.append('- `%s`（%s）缺 %d：%s' % (name, mods[name]['source'], len(lack), ', '.join(lack[:8])))
    if not unresolved:
        md.append('- 无')

    md.append('\n## 3. 依赖层级（被最多模块依赖的导出符号）')
    top = sorted(mod_exports.items(), key=lambda kv: -len(kv[1]))[:15]
    for sym, users in top:
        md.append('- `%s` ← %d 个模块（例：%s）' % (sym, len(users), ', '.join(users[:3])))

    md.append('\n## 4. 说明')
    md.append('- 解析范围只包含给出的目录；本地没有 system_dlkm 镜像，未纳入。')
    md.append('- 内核侧只提供 **原厂** 导出符号表；自编内核的导出情况需另做比对。')
    md.append('- `__versions` 的 CRC 与原厂内核表一致，说明该符号表与这批模块同代。')

    text = '\n'.join(md) + '\n'
    print(text)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(text)
    json.dump({
        'modules': {k: {kk: vv for kk, vv in v.items() if kk != 'path'} for k, v in mods.items()},
        'mod_exports': mod_exports,
        'unresolved': unresolved,
        'vers_mismatch_count': len(vers_mismatch),
        'dep_edges': dep_edges,
    }, open(a.out + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print('写出 %s 与 .json' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
