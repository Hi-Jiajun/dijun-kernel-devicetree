#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""纯 Python ELF64 原厂模块清单、ABI 核验与拓扑依赖闭包工具。

不依赖外部 readelf / modinfo / nm，直接复用 `_elfmod.KoElf`（兼容 Linux 6.6
`__versions` 与 6.18+ `__version_ext_crcs`/`__version_ext_names`），提供两种模式：

1. 全量模块清点与内核符号核验（兼容原 CLI）：
   module-inventory.py --kernel-symvers symvers/6.18.32-os4.0.4.0/vmlinux-pure.symvers \\
       --tree vendor_boot:/path/to/vb-ramdisk \\
       --tree vendor_dlkm:/path/to/vendor_dlkm \\
       --out report/module-inventory.md

2. 子系统依赖拓扑闭包（depends ∪ 模块间导出符号 ∪ softdep pre:）与 `.modinfo` 参数表导出：
   module-inventory.py \\
       --tree vendor_boot:/path/to/vb-ramdisk \\
       --tree vendor_dlkm:/path/to/vendor_dlkm \\
       --closure xring_drm --closure synaptics_tcm2 \\
       --closure-out closure.md --closure-json closure.json
"""
import argparse
import heapq
import json
import os
import re
import sys

from _elfmod import KoElf

TREE_PRIORITY_ORDER = ('vendor_boot', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm')


def norm_name(raw):
    """按内核规范归一化模块名：取 basename、去 .ko 后缀、将 '-' 转为 '_'。"""
    base = os.path.basename(raw.strip())
    if base.endswith('.ko'):
        base = base[:-3]
    return base.replace('-', '_')


def parse_softdeps(values):
    """解析 `.modinfo` softdep 条目为 (pre_list, post_list)。"""
    pre, post = [], []
    for item in values:
        tokens = item.split()
        cur = None
        for tok in tokens:
            if tok == 'pre:':
                cur = pre
            elif tok == 'post:':
                cur = post
            elif cur is not None:
                n = norm_name(tok)
                if n and n not in cur:
                    cur.append(n)
    return pre, post


def parse_parmtypes(values):
    """解析 `.modinfo` parmtype 条目为有序列表 [{'name': ..., 'type': ...}]。"""
    out = []
    seen = set()
    for item in values:
        if ':' in item:
            pname, ptype = item.split(':', 1)
        else:
            pname, ptype = item, ''
        if pname not in seen:
            seen.add(pname)
            out.append({'name': pname, 'type': ptype})
    return out


def read_kernel_symvers(path):
    """读取标准 Module.symvers（仅保留 0x<crc>\t<sym>\t... 中的内核导出或全量）。"""
    syms = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            cols = line.rstrip('\n').split('\t')
            if len(cols) < 2 or not cols[0].startswith('0x'):
                continue
            crc = int(cols[0], 16)
            sym = cols[1]
            owner = cols[2].strip() if len(cols) >= 3 else 'vmlinux'
            if owner == 'vmlinux' or sym not in syms:
                syms[sym] = '0x%08x' % crc
    return syms


def tree_rank(label, order_idx):
    """同一模块在多分区同时存在时的优先级排序键（vendor_boot 优先于 *_dlkm）。"""
    if label in TREE_PRIORITY_ORDER:
        return (TREE_PRIORITY_ORDER.index(label), order_idx, label)
    return (len(TREE_PRIORITY_ORDER), order_idx, label)


def scan_trees(tree_specs):
    """扫描 --tree <label>:<dir>，解析每个 .ko 的 ELF64 与 .modinfo 元数据。"""
    mods = {}
    by_norm = {}
    for order_idx, spec in enumerate(tree_specs):
        if ':' not in spec:
            raise SystemExit('--tree 参数格式必须为 <label>:<dir>: %s' % spec)
        label, root = spec.split(':', 1)
        if not os.path.isdir(root):
            raise SystemExit('--tree 目录不存在: %s' % root)
        found = 0
        for r, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if not fn.endswith('.ko'):
                    continue
                path = os.path.join(r, fn)
                rel = os.path.relpath(path, root).replace(os.sep, '/')
                key = '%s/%s' % (label, rel)
                elf = KoElf(path)
                mi = elf.modinfo()
                mod_name_raw = (mi.get('name') or [fn[:-3]])[0]
                nname = norm_name(mod_name_raw)
                deps = [norm_name(d) for d in (mi.get('depends') or [''])[0].split(',') if d.strip()]
                soft_pre, soft_post = parse_softdeps(mi.get('softdep') or [])
                parmtypes = parse_parmtypes(mi.get('parmtype') or [])
                parm_desc = {}
                for p in mi.get('parm') or []:
                    if ':' in p:
                        pn, pd = p.split(':', 1)
                        parm_desc[pn] = pd.strip()
                for pt in parmtypes:
                    if pt['name'] in parm_desc:
                        pt['desc'] = parm_desc[pt['name']]
                vers = {sym: '0x%08x' % crc for sym, crc in elf.versions().items()}
                info = {
                    'name': fn[:-3],
                    'modname': mod_name_raw,
                    'norm': nname,
                    'key': key,
                    'source': label,
                    'relpath': rel,
                    'path': path,
                    'rank': tree_rank(label, order_idx),
                    'size': os.path.getsize(path),
                    'imports': elf.imports(),
                    'exports': sorted(elf.exports()),
                    'versions': vers,
                    'modinfo': {
                        'vermagic': (mi.get('vermagic') or [''])[0],
                        'license': ','.join(mi.get('license') or []),
                        'depends': ','.join(mi.get('depends') or []),
                        'srcversion': (mi.get('srcversion') or [''])[0],
                    },
                    'depends_list': deps,
                    'softdep_pre': soft_pre,
                    'softdep_post': soft_post,
                    'parmtypes': parmtypes,
                    'firmware': sorted(set(mi.get('firmware') or [])),
                }
                mods[key] = info
                by_norm.setdefault(nname, []).append(key)
                found += 1
        if not found:
            raise SystemExit('--tree 目录内未找到 .ko 文件: %s' % root)

    for nname, keys in by_norm.items():
        keys.sort(key=lambda k: (mods[k]['rank'], k))
    return mods, by_norm


def resolve_target_key(spec, mods, by_norm):
    """解析 --closure 目标参数为具体模块 key（支持 key、norm_name 或路径）。"""
    s = spec.strip()
    if s in mods:
        return s
    n = norm_name(s)
    cands = by_norm.get(n)
    if not cands:
        raise SystemExit('未在 --tree 中找到目标模块: %s (norm=%s)' % (spec, n))
    return cands[0]


def pick_preferred_provider(keys, requester_source, mods):
    """在多个导出同一符号的候选模块中，优先选择同分区且树优先级最高者。"""
    return min(
        keys,
        key=lambda k: (
            0 if mods[k]['source'] == requester_source else 1,
            mods[k]['rank'],
            k,
        ),
    )


def build_closure(targets, mods, by_norm):
    """计算目标模块集合的硬依赖 ∪ 符号导出 ∪ softdep pre: 闭包及拓扑加载序。"""
    target_keys = []
    duplicate_notes = {}
    for spec in targets:
        k = resolve_target_key(spec, mods, by_norm)
        if k not in target_keys:
            target_keys.append(k)
        cands = by_norm.get(mods[k]['norm'], [])
        if len(cands) > 1:
            duplicate_notes[k] = cands

    sym_providers = {}
    for key, info in mods.items():
        for sym in info['exports']:
            sym_providers.setdefault(sym, []).append(key)

    visited = set()
    stack = list(target_keys)
    edges = {}            # parent_key -> set(child_key)  意味着 parent 必须先于 child 加载
    edge_reasons = {}     # (parent_key, child_key) -> list[str]
    missing_deps = []
    missing_softdeps = []

    def add_edge(parent, child, reason):
        if parent == child:
            return
        edges.setdefault(parent, set()).add(child)
        edge_reasons.setdefault((parent, child), set()).add(reason)

    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        info = mods[cur]

        # 1) 硬依赖 depends（按同分区优先、全局树优先级次之选取）
        for dep in info['depends_list']:
            cands = by_norm.get(dep)
            if not cands:
                missing_deps.append((cur, dep, 'depends'))
                continue
            pk = pick_preferred_provider(cands, info['source'], mods)
            if len(cands) > 1:
                duplicate_notes.setdefault(pk, cands)
            add_edge(pk, cur, 'depends')
            if pk not in visited:
                stack.append(pk)

        # 2) 前置软依赖 softdep pre:
        for sdep in info['softdep_pre']:
            cands = by_norm.get(sdep)
            if not cands:
                missing_softdeps.append((cur, sdep))
                continue
            pk = pick_preferred_provider(cands, info['source'], mods)
            if len(cands) > 1:
                duplicate_notes.setdefault(pk, cands)
            add_edge(pk, cur, 'softdep:pre')
            if pk not in visited:
                stack.append(pk)

        # 3) 模块间导出符号跨模块边
        for sym in info['imports']:
            cands = sym_providers.get(sym)
            if not cands:
                continue
            pk = pick_preferred_provider(cands, info['source'], mods)
            if pk != cur:
                add_edge(pk, cur, 'symbol')
                if pk not in visited:
                    stack.append(pk)

    # Kahn 拓扑排序（带软依赖环路破环保护）
    indeg = {k: 0 for k in visited}
    adj = {k: set() for k in visited}
    for p, children in edges.items():
        if p not in visited:
            continue
        for c in children:
            if c in visited and c not in adj[p]:
                adj[p].add(c)
                indeg[c] += 1

    ordered = []
    cycle_breaks = []
    heap = [(mods[k]['rank'], k) for k, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    remaining = set(visited)

    while remaining:
        if not heap:
            # 遇环：优先剔除仅 softdep:pre 引入的边；若仍无法推进，选入度最低节点确定性破环
            soft_edges = [
                (p, c) for p in remaining for c in adj[p]
                if c in remaining and edge_reasons.get((p, c)) == {'softdep:pre'}
            ]
            if soft_edges:
                p, c = min(soft_edges)
                adj[p].remove(c)
                indeg[c] -= 1
                cycle_breaks.append((p, c, 'dropped softdep:pre edge'))
                if indeg[c] == 0:
                    heapq.heappush(heap, (mods[c]['rank'], c))
                continue
            pick = min(remaining, key=lambda k: (indeg[k], mods[k]['rank'], k))
            cycle_breaks.append((pick, pick, 'forced break indeg=%d' % indeg[pick]))
            heapq.heappush(heap, (mods[pick]['rank'], pick))

        _r, u = heapq.heappop(heap)
        if u not in remaining:
            continue
        remaining.remove(u)
        ordered.append(u)
        for v in adj[u]:
            if v in remaining:
                indeg[v] -= 1
                if indeg[v] == 0:
                    heapq.heappush(heap, (mods[v]['rank'], v))

    return {
        'targets': target_keys,
        'ordered_keys': ordered,
        'missing_deps': sorted(set(missing_deps)),
        'missing_softdeps': sorted(set(missing_softdeps)),
        'duplicate_notes': {k: duplicate_notes[k] for k in sorted(duplicate_notes)},
        'cycle_breaks': cycle_breaks,
    }


def format_closure_markdown(closure, mods):
    lines = []
    lines.append('# 子系统模块依赖闭包与 `.modinfo` 参数表\n')
    lines.append('- 目标模块：`%s`' % '`, `'.join(closure['targets']))
    lines.append('- 闭包总数（按 `depends ∪ 导出符号 ∪ softdep pre:` 拓扑加载序）：**%d**\n' % len(closure['ordered_keys']))

    lines.append('| 序 | 模块 (`source/relpath`) | 大小 (B) | `depends` | `softdep` | 参数 (`.modinfo parmtype`) | 固件 (`firmware`) |')
    lines.append('| --- | --- | ---: | --- | --- | --- | --- |')
    for idx, key in enumerate(closure['ordered_keys'], 1):
        info = mods[key]
        deps = ', '.join(info['depends_list']) if info['depends_list'] else '—'
        sd_parts = []
        if info['softdep_pre']:
            sd_parts.append('pre: ' + ' '.join(info['softdep_pre']))
        if info['softdep_post']:
            sd_parts.append('post: ' + ' '.join(info['softdep_post']))
        sd = '; '.join(sd_parts) if sd_parts else '—'
        parms = ', '.join('`%s:%s`' % (p['name'], p['type']) for p in info['parmtypes']) if info['parmtypes'] else '—'
        fws = ', '.join('`%s`' % fw for fw in info['firmware']) if info['firmware'] else '—'
        lines.append('| %d | `%s` | %d | %s | %s | %s | %s |' % (
            idx, key, info['size'], deps, sd, parms, fws
        ))

    if closure['missing_softdeps']:
        lines.append('\n## 未在模块目录出现的前置 `softdep`（通常为内建驱动或平台可选项）\n')
        for owner, dep in closure['missing_softdeps']:
            lines.append('- `%s` → `softdep pre: %s`' % (owner, dep))

    if closure['missing_deps']:
        lines.append('\n## 缺失的硬依赖\n')
        for owner, dep, kind in closure['missing_deps']:
            lines.append('- `%s` → `%s` (%s)' % (owner, dep, kind))

    if closure['duplicate_notes']:
        lines.append('\n## 多分区同名模块消歧记录\n')
        for chosen, cands in closure['duplicate_notes'].items():
            lines.append('- 选用 `%s`（同池候选：%s）' % (chosen, ', '.join('`%s`' % c for c in cands)))

    if closure['cycle_breaks']:
        lines.append('\n## 拓扑破环记录\n')
        for p, c, msg in closure['cycle_breaks']:
            lines.append('- `%s` -> `%s` (%s)' % (p, c, msg))

    return '\n'.join(lines) + '\n'


def run_full_inventory(kernel_symvers_path, mods, out_path):
    kernel = read_kernel_symvers(kernel_symvers_path)
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
    md.append('- 模块 `__versions` / `__version_ext_*` 与内核符号表 CRC 不一致的条目：%d' % len(vers_mismatch))
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

    text = '\n'.join(md) + '\n'
    print(text)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
    json_payload = {
        'modules': {
            k: {kk: vv for kk, vv in v.items() if kk not in ('path', 'rank')}
            for k, v in mods.items()
        },
        'mod_exports': mod_exports,
        'unresolved': unresolved,
        'vers_mismatch_count': len(vers_mismatch),
        'dep_edges': dep_edges,
    }
    with open(out_path + '.json', 'w', encoding='utf-8') as f:
        json.dump(json_payload, f, ensure_ascii=False, indent=2)
    print('写出 %s 与 .json' % out_path)


def main(argv):
    ap = argparse.ArgumentParser(description='纯 Python ELF64 模块清点与依赖闭包工具')
    ap.add_argument('--kernel-symvers', help='内核 Module.symvers 路径（生成全量 --out 报告时必传）')
    ap.add_argument('--tree', action='append', default=[], help='模块目录 <label>:<dir>')
    ap.add_argument('--out', help='输出全量清点 Markdown 报告路径（同步产出 <out>.json）')
    ap.add_argument('--closure', action='append', default=[], help='导出指定模块依赖闭包（可多次或逗号分隔）')
    ap.add_argument('--closure-out', help='闭包报告 Markdown 输出路径（未传则输出到 stdout）')
    ap.add_argument('--closure-json', help='闭包报告 JSON 输出路径')
    a = ap.parse_args(argv[1:])

    if not a.tree:
        ap.error('至少需要传入一个 --tree <label>:<dir>')
    if not a.out and not a.closure:
        ap.error('必须指定 --out 或 --closure')
    if a.out and not a.kernel_symvers:
        ap.error('使用 --out 时必须指定 --kernel-symvers')

    mods, by_norm = scan_trees(a.tree)

    if a.out:
        run_full_inventory(a.kernel_symvers, mods, a.out)

    if a.closure:
        targets = []
        for item in a.closure:
            for part in item.split(','):
                if part.strip():
                    targets.append(part.strip())
        closure = build_closure(targets, mods, by_norm)
        md_text = format_closure_markdown(closure, mods)
        if a.closure_out:
            cdir = os.path.dirname(os.path.abspath(a.closure_out))
            if cdir:
                os.makedirs(cdir, exist_ok=True)
            with open(a.closure_out, 'w', encoding='utf-8') as f:
                f.write(md_text)
            print('写出闭包报告 %s' % a.closure_out)
        else:
            sys.stdout.write(md_text)

        if a.closure_json:
            jdir = os.path.dirname(os.path.abspath(a.closure_json))
            if jdir:
                os.makedirs(jdir, exist_ok=True)
            payload = {
                'targets': closure['targets'],
                'count': len(closure['ordered_keys']),
                'ordered': [
                    {
                        'order': i,
                        'key': k,
                        'source': mods[k]['source'],
                        'relpath': mods[k]['relpath'],
                        'modname': mods[k]['modname'],
                        'size': mods[k]['size'],
                        'depends': mods[k]['depends_list'],
                        'softdep_pre': mods[k]['softdep_pre'],
                        'softdep_post': mods[k]['softdep_post'],
                        'parmtypes': mods[k]['parmtypes'],
                        'firmware': mods[k]['firmware'],
                        'vermagic': mods[k]['modinfo']['vermagic'],
                    }
                    for i, k in enumerate(closure['ordered_keys'], 1)
                ],
                'missing_deps': closure['missing_deps'],
                'missing_softdeps': closure['missing_softdeps'],
                'duplicate_notes': closure['duplicate_notes'],
                'cycle_breaks': closure['cycle_breaks'],
            }
            with open(a.closure_json, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print('写出闭包 JSON %s' % a.closure_json)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
