#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""ABI 回归门：核验原厂模块集或外部编译模块与目标内核的兼容性。

核心判据：
  1. 内核导出符号校验：模块 `__version_ext_*` / `__versions` 中由内核提供的符号，CRC 必须逐条匹配；
  2. 模块间导出校验：模块相互依赖时，提供方 `.ko` 导出的 CRC 必须与使用方期望 CRC 一致；
  3. 强未定义符号校验：所有未定义符号必须由内核导出、模块间导出或显式白名单/豁免项覆盖；
  4. 可选校验：`vermagic` 逐字核对（防 `-dirty`/`+` 后缀引发 ENOEXEC）以及受保护符号清单核对。

用法：
  # 检查完整设备模块集（支持按分区标签防同名覆盖 + 同源替换）
  abi-gate.py --our-symvers Module.symvers \
      --moddir vendor_boot=<dir1> --moddir vendor_dlkm=<dir2> --moddir system_dlkm=<dir3> \
      --replace system_dlkm:rust_binder.ko=<built/rust_binder.ko> \
      --allow-dead-module xr_pmonitor.ko --out report.md

  # 兼容旧参数：校验外部自编模块（支持附加厂商模块导出表与 vermagic 校验）
  abi-gate.py --our-symvers vmlinux.symvers --extra-symvers vendor-modules.symvers \
      --modules <extmod_dir> --expect-vermagic "6.18.32-4k SMP preempt mod_unload modversions aarch64"
"""
import argparse
import json
import os
import sys

from _elfmod import KoElf


def load_symvers(path, treat_all_as_kernel=False):
    """读取 Module.symvers -> (kernel_dict, mod_dict)。

    标准 4 列格式中仅第 3 列等于 'vmlinux' 的行计入内核导出，其余计入模块导出；
    对 2 列纯符号文件或显式指定 --treat-all-as-kernel 时，全部计入内核导出。
    """
    kern = {}
    mods = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            cols = line.rstrip('\n').split('\t')
            if len(cols) < 2 or not cols[0].startswith('0x'):
                continue
            crc = int(cols[0], 16)
            sym = cols[1]
            owner = cols[2].strip() if len(cols) >= 3 else 'vmlinux'
            if treat_all_as_kernel or owner == 'vmlinux':
                kern[sym] = crc
            else:
                mods[sym] = (crc, owner)
    return kern, mods


def collect_modules(mod_specs, replace_specs):
    """扫描目录并应用 --replace 替换。使用 `<label>:<relpath>` 唯一标识，避免同名覆盖。"""
    replacements = {}
    for item in replace_specs:
        if '=' not in item:
            raise SystemExit('--replace 参数格式必须为 [<label>:]<filename>=<path>: %s' % item)
        k, v = item.split('=', 1)
        if not os.path.isfile(v):
            raise SystemExit('--replace 目标文件不存在: %s' % v)
        replacements[k] = v

    used_replacements = set()
    mods = []
    for idx, spec in enumerate(mod_specs):
        if '=' in spec:
            label, root = spec.split('=', 1)
        else:
            root = spec
            label = 'dir%d' % idx
        found = 0
        for r, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if not fn.endswith('.ko'):
                    continue
                orig_path = os.path.join(r, fn)
                rel = os.path.relpath(orig_path, root).replace(os.sep, '/')
                mod_id = '%s:%s' % (label, rel)
                scoped_key = '%s:%s' % (label, fn)
                actual_path = orig_path
                if mod_id in replacements:
                    actual_path = replacements[mod_id]
                    used_replacements.add(mod_id)
                elif scoped_key in replacements:
                    actual_path = replacements[scoped_key]
                    used_replacements.add(scoped_key)
                elif fn in replacements:
                    actual_path = replacements[fn]
                    used_replacements.add(fn)
                mods.append((label, rel, fn, mod_id, actual_path, KoElf(actual_path)))
                found += 1
        if not found:
            raise SystemExit('模块目录里没有找到 .ko: %s' % root)

    unused = set(replacements) - used_replacements
    if unused:
        raise SystemExit('--replace 未命中任何目录内模块: %s' % sorted(unused))
    return mods


def main(argv):
    ap = argparse.ArgumentParser(description='dijun 内核与模块 ABI 回归门')
    ap.add_argument('--stock-symvers', help='（可选）原厂导出符号表，供诊断对比')
    ap.add_argument('--our-symvers', required=True, help='目标内核 Module.symvers')
    ap.add_argument('--extra-symvers', action='append', default=[], help='附加模块导出表 (KBUILD_EXTRA_SYMBOLS)')
    ap.add_argument('--treat-all-as-kernel', action='store_true', help='将 --our-symvers 所有条目都视为内核导出')
    ap.add_argument('--modules', action='append', default=[], help='模块目录（向后兼容）')
    ap.add_argument('--moddir', action='append', default=[], help='带分区标签的模块目录 <label>=<dir>')
    ap.add_argument('--replace', action='append', default=[], help='内存中替换模块 [<label>:]<name.ko>=<path>')
    ap.add_argument('--allow-unresolved-prefix', action='append', default=[], help='允许未解析的符号前缀（告警不失败）')
    ap.add_argument('--allow-dead-module', action='append', default=[], help='豁免已知死模块（如 xr_pmonitor.ko）')
    ap.add_argument('--expect-vermagic', help='强制校验每个模块的 vermagic 逐字匹配此字符串')
    ap.add_argument('--protected-list', help='受保护内核符号列表，对未签名模块命中项发出告警/校验')
    ap.add_argument('--fail-on-protected', action='store_true', help='未签名模块引用受保护符号时判定失败')
    ap.add_argument('--json', help='输出机器可读 JSON 报告路径')
    ap.add_argument('--out', help='输出 Markdown 报告路径')
    a = ap.parse_args(argv[1:])

    mod_specs = list(a.moddir) + list(a.modules)
    if not mod_specs:
        raise SystemExit('必须指定至少一个 --moddir 或 --modules')

    kern_symvers, extra_mod_symvers = load_symvers(a.our_symvers, treat_all_as_kernel=a.treat_all_as_kernel)
    for ep in a.extra_symvers:
        ek, em = load_symvers(ep, treat_all_as_kernel=False)
        for sym, crc in ek.items():
            extra_mod_symvers.setdefault(sym, (crc, os.path.basename(ep)))
        for sym, val in em.items():
            extra_mod_symvers.setdefault(sym, val)

    mods = collect_modules(mod_specs, a.replace)

    # 收集目录内模块间导出（先注册目录内模块，再补充 extra_mod_symvers）
    provider = {}
    dup_conflicts = []
    for label, rel, _fn, mod_id, _path, elf in mods:
        declared = elf.exports()
        crcs = elf.export_crcs()
        if declared - set(crcs):
            print('WARN %s: %d 个 __ksymtab 符号缺 __crc_ 条目' % (mod_id, len(declared - set(crcs))),
                  file=sys.stderr)
        for sym, crc in crcs.items():
            if sym in provider:
                if provider[sym][0] != crc:
                    dup_conflicts.append((sym, provider[sym], (crc, mod_id, label)))
                continue
            provider[sym] = (crc, mod_id, label)

    for sym, (crc, owner) in extra_mod_symvers.items():
        if sym not in provider:
            provider[sym] = (crc, owner, 'extra-symvers')

    protected_syms = set()
    if a.protected_list:
        with open(a.protected_list, encoding='utf-8', errors='replace') as f:
            protected_syms = {l.strip() for l in f if l.strip() and not l.strip().startswith('#')}

    dead_set = set(a.allow_dead_module)
    provided_all = set(kern_symvers) | set(provider)

    kern_mismatch = []
    mod_mismatch = []
    missing_imports = {}
    exempted_dead = {}
    vermagic_mismatch = []
    protected_hits = {}
    ver_total = 0

    for _label, _rel, fn, mod_id, _path, elf in mods:
        is_dead = (fn in dead_set) or (mod_id in dead_set)
        vers = elf.versions()
        for sym, expect in vers.items():
            ver_total += 1
            if sym in kern_symvers:
                if kern_symvers[sym] != expect:
                    kern_mismatch.append((mod_id, sym, expect, kern_symvers[sym]))
            elif sym in provider:
                pcrc, powner, plabel = provider[sym]
                if pcrc != expect:
                    mod_mismatch.append((mod_id, sym, expect, pcrc, powner, plabel))

        lack = sorted(s for s in elf.imports() if s not in provided_all and s != 'module_layout')
        hard = [s for s in lack if not any(s.startswith(pre) for pre in a.allow_unresolved_prefix)]
        if hard:
            if is_dead:
                exempted_dead[mod_id] = hard
            else:
                missing_imports[mod_id] = hard

        if a.expect_vermagic:
            got_vm = elf.modinfo_first('vermagic')
            if got_vm != a.expect_vermagic:
                vermagic_mismatch.append((mod_id, got_vm, a.expect_vermagic))

        if protected_syms:
            has_sig = b'~Module signature appended~' in elf.blob
            if not has_sig:
                hits = sorted(s for s in elf.imports() if s in protected_syms)
                if hits:
                    protected_hits[mod_id] = hits

    passed = (
        not kern_mismatch
        and not mod_mismatch
        and not missing_imports
        and not vermagic_mismatch
        and not dup_conflicts
        and (not a.fail_on_protected or not protected_hits)
    )

    report = {
        'passed': passed,
        'modules': len(mods),
        'kernel_exports': len(kern_symvers),
        'module_exports': len(provider),
        'version_entries': ver_total,
        'provider_conflicts': dup_conflicts,
        'kernel_crc_mismatch': [
            {'module': m, 'symbol': s, 'expect': '0x%08x' % e, 'actual': '0x%08x' % g}
            for m, s, e, g in kern_mismatch
        ],
        'module_crc_mismatch': [
            {'module': m, 'symbol': s, 'expect': '0x%08x' % e, 'actual': '0x%08x' % pc, 'provider': pb}
            for m, s, e, pc, pb, _pl in mod_mismatch
        ],
        'unresolved': missing_imports,
        'exempted_dead_modules': exempted_dead,
        'vermagic_mismatch': [
            {'module': m, 'actual': g, 'expect': e} for m, g, e in vermagic_mismatch
        ],
        'unsigned_protected_hits': protected_hits,
    }

    md = ['# ABI 回归门\n']
    md.append('- 模块样本 %d 个；内核导出 %d；模块间/附加导出 %d；版本表条目 %d' % (
        len(mods), len(kern_symvers), len(provider), ver_total))
    md.append('- 内核符号 CRC 不符：**%d** 条' % len(kern_mismatch))
    for m, s, e, g in kern_mismatch[:15]:
        md.append('  - %s:%s 期望 `0x%08x` 实际 `0x%08x`' % (m, s, e, g))
    md.append('- 模块间符号 CRC 不符：**%d** 条' % len(mod_mismatch))
    for m, s, e, pc, pb, _pl in mod_mismatch[:15]:
        md.append('  - %s:%s 期望 `0x%08x` 提供方 %s `0x%08x`' % (m, s, e, pb, pc))
    md.append('- 无法解析导入的模块：**%d**' % len(missing_imports))
    for m, lack in list(missing_imports.items())[:15]:
        md.append('  - %s 缺 %d：%s' % (m, len(lack), ', '.join(lack[:6])))
    if exempted_dead:
        md.append('- 已豁免死模块：**%d**（%s）' % (len(exempted_dead), ', '.join(sorted(exempted_dead))))
    if a.expect_vermagic:
        md.append('- vermagic 不符：**%d**' % len(vermagic_mismatch))
        for m, g, e in vermagic_mismatch[:10]:
            md.append('  - %s 实际 `%s` ≠ 期望 `%s`' % (m, g, e))
    if protected_hits:
        md.append('- 未签名命中受保护导出：**%d**（原厂开启 `MODULE_SIG_PROTECT` 时会 `-EACCES`）' % len(protected_hits))
        for m, hits in list(protected_hits.items())[:10]:
            md.append('  - %s 命中 %d：%s' % (m, len(hits), ', '.join(hits[:6])))
    md.append('\n**判定：%s**' % ('PASS' if passed else 'FAIL'))
    text = '\n'.join(md) + '\n'
    print(text)

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
