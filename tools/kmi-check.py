#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GKI/KMI 对齐判定：自编内核能否加载原厂闭源模块。

四项判定：
  1) KMI 符号覆盖：android/abi_gki_aarch64(+xiaomi_xring) 里每个符号，自编内核是否导出；
  2) CRC 一致性：原厂 Module.symvers 的 0x… 值与自编内核 __crc_<sym> 是否相同（MODVERSIONS）；
  3) 模块需求覆盖：原厂 .ko 的未定义符号，自编内核是否全部提供（否则模块加载失败）；
  4) KCFI 类型 id：两边 __kcfi_typeid_<sym> 值是否相同（CFI_CLANG）。

用法：
  kmi-check.py --stock-symvers <原厂 Module.symvers> --vmlinux <自编 vmlinux> \
               --kmi <abi_gki_aarch64> --kmi <abi_gki_aarch64_xiaomi_xring> \
               --modules <原厂 vendor_dlkm 目录> --out report.md
"""
import argparse
import json
import os
import re
import subprocess
import sys

CRC_RE = re.compile(r'__crc_(\w+)')


def read_stock_symvers(path):
    """原厂 Module.symvers -> {symbol: crc}。"""
    out = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and f[0].startswith('0x'):
            out[f[1]] = f[0]
    return out


def nm_symbols(vmlinux):
    """从 vmlinux 提取 __crc_* 与 __kcfi_typeid_* 值。"""
    crc, kcfi = {}, {}
    p = subprocess.run(['nm', '--defined-only', vmlinux], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit('nm 失败: %s' % p.stderr[:200])
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        addr, _typ, name = parts[0], parts[1], parts[2]
        if name.startswith('__crc_'):
            crc[name[len('__crc_'):]] = '0x' + addr.lstrip('0').lower().rjust(8, '0')
        elif name.startswith('__kcfi_typeid_'):
            kcfi[name[len('__kcfi_typeid_'):]] = addr
    # 地址位数归一化
    crc = {k: '0x%08x' % int(v, 16) for k, v in crc.items()}
    return crc, kcfi


def read_kmi(paths):
    syms = set()
    for path in paths:
        for line in open(path, encoding='utf-8', errors='replace'):
            s = line.strip()
            if not s or s.startswith('#') or s.startswith('['):
                continue
            syms.add(s.split()[0])
    return syms


def module_needs(modules_dir):
    """原厂 .ko -> {ko: set(undefined symbols)}。"""
    needs = {}
    for root, _dirs, files in os.walk(modules_dir):
        for fn in files:
            if not fn.endswith('.ko'):
                continue
            path = os.path.join(root, fn)
            p = subprocess.run(['nm', '-u', path], capture_output=True, text=True)
            if p.returncode != 0:
                continue
            syms = set()
            for line in p.stdout.splitlines():
                parts = line.split()
                if parts:
                    syms.add(parts[-1])
            needs[os.path.relpath(path, modules_dir)] = syms
    return needs


def module_exports(modules_dir):
    """原厂模块之间互相提供的导出符号（__ksymtab_<sym>）。"""
    out = set()
    for root, _dirs, files in os.walk(modules_dir):
        for fn in files:
            if not fn.endswith('.ko'):
                continue
            p = subprocess.run(['nm', '--defined-only', os.path.join(root, fn)],
                               capture_output=True, text=True)
            for line in p.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2].startswith('__ksymtab_'):
                    out.add(parts[2][len('__ksymtab_'):])
    return out


def module_kcfi(modules_dir):
    out = {}
    for root, _dirs, files in os.walk(modules_dir):
        for fn in files:
            if not fn.endswith('.ko'):
                continue
            path = os.path.join(root, fn)
            p = subprocess.run(['nm', path], capture_output=True, text=True)
            for line in p.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2].startswith('__kcfi_typeid_'):
                    out[parts[2][len('__kcfi_typeid_'):]] = parts[0]
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock-symvers', required=True)
    ap.add_argument('--vmlinux', required=True)
    ap.add_argument('--our-symvers', help='自编内核的 vmlinux.symvers（CRC 的可靠来源）')
    ap.add_argument('--kmi', action='append', default=[])
    ap.add_argument('--modules', default=None)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv[1:])

    stock = read_stock_symvers(a.stock_symvers)
    _nm_crc, our_kcfi = nm_symbols(a.vmlinux)
    our_crc = read_stock_symvers(a.our_symvers) if a.our_symvers else _nm_crc
    kmi = read_kmi(a.kmi) if a.kmi else set()

    kmi_cover = {s: (s in our_crc) for s in kmi}
    kmi_missing = sorted(s for s, ok in kmi_cover.items() if not ok)

    common = sorted(set(stock) & set(our_crc))
    crc_same = [s for s in common if stock[s].lower() == our_crc[s].lower()]
    crc_diff = sorted(s for s in common if stock[s].lower() != our_crc[s].lower())
    stock_only = sorted(set(stock) - set(our_crc))

    kmi_crc_diff = [s for s in crc_diff if s in kmi]
    kmi_crc_same = [s for s in crc_same if s in kmi]

    md = []
    md.append('# GKI/KMI 对齐判定\n')
    md.append('原厂导出符号 %d，自编内核导出 %d，交集 %d。\n' % (len(stock), len(our_crc), len(common)))
    md.append('## 1. KMI 契约')
    if kmi:
        md.append('- KMI 符号表合计 %d 个；自编内核导出 %d 个（缺 %d）'
                  % (len(kmi), len(kmi) - len(kmi_missing), len(kmi_missing)))
        if kmi_missing:
            md.append('- 缺失示例：%s' % ', '.join(kmi_missing[:15]))
        md.append('- KMI 符号中 CRC 相同 %d，不同 %d' % (len(kmi_crc_same), len(kmi_crc_diff)))
        if kmi_crc_diff:
            md.append('- CRC 不同的 KMI 符号示例：%s' % ', '.join(kmi_crc_diff[:15]))
    else:
        md.append('- 未提供 KMI 列表，跳过')
    md.append('\n## 2. CRC（MODVERSIONS）')
    md.append('- 交集 %d 个：相同 %d（%.1f%%），不同 %d' %
              (len(common), len(crc_same), 100.0 * len(crc_same) / max(1, len(common)), len(crc_diff)))
    md.append('- 原厂有、自编没有的导出符号 %d 个' % len(stock_only))
    if crc_diff:
        md.append('- CRC 不同示例：%s' % ', '.join(crc_diff[:15]))

    result = {
        'stock_symbols': len(stock),
        'our_symbols': len(our_crc),
        'common': len(common),
        'crc_same': len(crc_same),
        'crc_diff': len(crc_diff),
        'stock_only': len(stock_only),
        'kmi_total': len(kmi),
        'kmi_missing': kmi_missing,
        'kmi_crc_diff': kmi_crc_diff,
        'kcfi_checked': 0,
        'kcfi_mismatch': [],
        'module_needs_missing': {},
    }

    if a.modules:
        md.append('\n## 3. 原厂模块的符号需求')
        needs = module_needs(a.modules)
        mexp = module_exports(a.modules)
        md.append('- 原厂模块互相导出的符号 %d 个' % len(mexp))
        missing = {}
        for ko, syms in needs.items():
            allow = mexp | set(our_crc) | {'module_layout'}
            lack = sorted(s for s in syms if s not in allow)
            if lack:
                missing[ko] = lack
        md.append('- 检查 .ko %d 个；有缺符号的 %d 个' % (len(needs), len(missing)))
        if missing:
            worst = sorted(missing.items(), key=lambda kv: -len(kv[1]))[:10]
            for ko, lack in worst:
                md.append('  - %s: 缺 %d，例 %s' % (ko, len(lack), ', '.join(lack[:6])))
        result['module_needs_missing'] = {k: v[:20] for k, v in list(missing.items())[:50]}

        md.append('\n## 4. KCFI 类型 id')
        mk = module_kcfi(a.modules)
        common_k = sorted(set(mk) & set(our_kcfi))
        mism = [s for s in common_k if int(mk[s], 16) != int(our_kcfi[s], 16)]
        result['kcfi_checked'] = len(common_k)
        result['kcfi_mismatch'] = mism[:50]
        md.append('- 模块与内核共有的 __kcfi_typeid_ 符号 %d 个；值不同 %d 个' % (len(common_k), len(mism)))
        if mism:
            md.append('  - 不同示例：%s' % ', '.join(mism[:10]))

    text = '\n'.join(md) + '\n'
    print(text)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text)
        json.dump(result, open(a.out + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('写出 %s / %s.json' % (a.out, a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
