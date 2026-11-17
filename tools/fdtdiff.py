#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FDT/DTBO 结构比较工具（dijun 设备树工程自用）。

用途：
  1. 解析 .dtb/.dtbo，输出节点路径 -> {属性: 原始字节}；
  2. 读取提供方节点的 #*-cells，把 phandle 引用元组归一化成 REF(路径) + RAW 参数单元，
     避免把 clock ID / gpio flag / 电压数值误判为 phandle；
  3. 比较两份 FDT：默认忽略节点自身 phandle 编号变化，报告缺失/新增节点与属性差异；
  4. overlay 模式利用 /__fixups__ 还原每个 fragment 的真实外部 target 符号名，
     并对同目标多 fragment 追加序号消歧，同时支持外部符号占位值 (0xffffffff) 归一化。

用法：
  fdtdiff.py tree-a.dtb tree-b.dtb [--overlay] [--show-phandle-id] [--json out.json] [--max-diff N]
  fdtdiff.py --dump x.dtb

注意：这是研究用工具，不是 libfdt 的完整替代；不校验 rsvmap、不处理 NOP 之外的特殊 token。
"""
import json
import re
import struct
import sys

FDT_MAGIC = 0xD00DFEED
TOK_BEGIN_NODE, TOK_END_NODE, TOK_PROP, TOK_NOP, TOK_END = 1, 2, 3, 4, 9

# 节点自身标识类或明确纯标量属性，绝不按 phandle 解析
SCALAR_PROPS = {
    '#address-cells', '#size-cells', '#clock-cells', '#gpio-cells', '#interrupt-cells',
    '#dma-cells', '#power-domain-cells', '#pwm-cells', '#thermal-sensor-cells',
    '#iommu-cells', '#phy-cells', '#mbox-cells', '#reset-cells', '#sound-dai-cells',
    '#cooling-cells', '#io-channel-cells', '#hwlock-cells', '#msi-cells',
    'phandle', 'linux,phandle', 'reg', 'interrupts', 'clock-frequency', 'status',
    'board_id', 'board_rev', 'custom0', 'cell-index', 'opp-hz', 'opp-microvolt',
    'opp-millivolt', 'opp-level', 'opp-peak-kBps', 'opp-avg-kBps',
}

# 纯 phandle 数组属性（每个 u32 cell 都是 phandle，不带 specifier 参数）
PURE_PHANDLE_PROPS = {
    'operating-points-v2', 'memory-region', 'interrupt-parent', 'cpus', 'cpu',
    'leds', 'mcu-heap', 'xring,gpufreq', 'asoc-codec', 'asoc-cpu', 'asoc-platform',
    'remote-endpoint', 'msi-parent', 'iommu-map', 'panel', 'dsi-panel',
}

PURE_PHANDLE_RE = re.compile(r'^(?:pinctrl-[0-9]+|.*-supply)$')

# (属性名或后缀) -> (provider 上的 #*-cells 属性名, 缺省 specifier cell 数)
SPECIFIER_PROPS = {
    'clocks': ('#clock-cells', 1),
    'assigned-clocks': ('#clock-cells', 1),
    'assigned-clock-parents': ('#clock-cells', 1),
    'resets': ('#reset-cells', 1),
    'iommus': ('#iommu-cells', 2),
    'power-domains': ('#power-domain-cells', 0),
    'phys': ('#phy-cells', 1),
    'mboxes': ('#mbox-cells', 3),
    'dmas': ('#dma-cells', 1),
    'thermal-sensors': ('#thermal-sensor-cells', 1),
    'cooling-device': ('#cooling-cells', 2),
    'nvmem-cells': ('#nvmem-cell-cells', 0),
    'io-channels': ('#io-channel-cells', 1),
    'sound-dai': ('#sound-dai-cells', 0),
    'hwlocks': ('#hwlock-cells', 1),
    'pwms': ('#pwm-cells', 2),
    'interrupts-extended': ('#interrupt-cells', 3),
    'vote-mngs': ('#vote-mng-cells', 1),
    'gpios': ('#gpio-cells', 2),
}


def parse_fdt(blob):
    if len(blob) < 40:
        raise ValueError('文件太短，不是 FDT')
    (magic, _totalsize, off_struct, off_strings, _off_rsvmap, _version,
     _last_comp, _boot_cpuid, size_strings, size_struct) = struct.unpack('>10I', blob[:40])
    if magic != FDT_MAGIC:
        raise ValueError('FDT magic 不符: %#x' % magic)
    strings = blob[off_strings:off_strings + size_strings]
    struct_blk = blob[off_struct:off_struct + size_struct]

    nodes = {}
    path = []
    i = 0
    while i < len(struct_blk):
        tok = struct.unpack('>I', struct_blk[i:i + 4])[0]
        i += 4
        if tok == TOK_BEGIN_NODE:
            end = struct_blk.index(b'\0', i)
            name = struct_blk[i:end].decode('utf-8', 'replace')
            i = (end + 4) & ~3
            if name:
                path.append(name)
            nodes['/' + '/'.join(path)] = {}
        elif tok == TOK_END_NODE:
            if path:
                path.pop()
        elif tok == TOK_PROP:
            length, nameoff = struct.unpack('>II', struct_blk[i:i + 8])
            i += 8
            value = struct_blk[i:i + length]
            i = (i + length + 3) & ~3
            end = strings.index(b'\0', nameoff)
            prop = strings[nameoff:end].decode('utf-8', 'replace')
            nodes.setdefault('/' + '/'.join(path), {})[prop] = value
        elif tok == TOK_NOP:
            continue
        elif tok == TOK_END:
            break
        else:
            raise ValueError('未知 FDT token %d @%d' % (tok, i - 4))
    return nodes


def build_phandle_map(nodes):
    """phandle 数值 -> 节点路径。"""
    m = {}
    for path, props in nodes.items():
        for key in ('phandle', 'linux,phandle'):
            raw = props.get(key)
            if raw and len(raw) == 4:
                m[struct.unpack('>I', raw)[0]] = path
    return m


def build_cell_counts(nodes):
    """节点路径 -> { '#*-cells': int }。"""
    out = {}
    for path, props in nodes.items():
        d = {}
        for k, raw in props.items():
            if k.startswith('#') and k.endswith('-cells') and len(raw) == 4:
                d[k] = struct.unpack('>I', raw)[0]
        if d:
            out[path] = d
    return out


def build_overlay_fixups(nodes):
    """解析 /__fixups__ -> {(node_path, prop_name): {byte_offset: symbol_name}}。"""
    fixups = {}
    raw_map = nodes.get('/__fixups__', {})
    for label, raw in raw_map.items():
        parts = [s for s in raw.decode('utf-8', 'replace').split('\0') if s]
        for entry in parts:
            fields = entry.rsplit(':', 2)
            if len(fields) != 3:
                continue
            npath, prop, off_str = fields
            try:
                off = int(off_str)
            except ValueError:
                continue
            fixups.setdefault((npath, prop), {})[off] = label
    return fixups


def _specifier_info(prop):
    if prop in SPECIFIER_PROPS:
        return SPECIFIER_PROPS[prop]
    if prop.endswith('-gpios') or prop.endswith('-gpio'):
        return ('#gpio-cells', 2)
    return None


def _is_pure_phandle_prop(prop):
    return prop in PURE_PHANDLE_PROPS or bool(PURE_PHANDLE_RE.match(prop))


def normalize_value(raw, phandles, cell_counts=None, prop='', path='', fixups=None):
    """把 phandle / 外部 fixup 引用解析为 REF(路径) 或 EXT(符号) + RAW 参数。"""
    cell_counts = cell_counts or {}
    prop_fixups = (fixups or {}).get((path, prop), {})

    if prop in SCALAR_PROPS and not prop_fixups:
        return raw
    if len(raw) == 0 or len(raw) % 4:
        return raw

    spec = _specifier_info(prop)
    pure = _is_pure_phandle_prop(prop)
    if not pure and spec is None and not prop_fixups:
        return raw

    cells = struct.unpack('>%dI' % (len(raw) // 4), raw)
    out = []

    if spec is not None:
        cells_prop, default_ncells = spec
        i = 0
        matched_any = False
        while i < len(cells):
            byte_off = i * 4
            val = cells[i]
            if byte_off in prop_fixups:
                matched_any = True
                out.append(('EXT', prop_fixups[byte_off]))
                ncells = default_ncells
                i += 1
                for _ in range(ncells):
                    if i < len(cells):
                        out.append(('RAW', cells[i]))
                        i += 1
            elif val in phandles:
                matched_any = True
                target_path = phandles[val]
                out.append(('REF', target_path))
                ncells = cell_counts.get(target_path, {}).get(cells_prop, default_ncells)
                i += 1
                for _ in range(ncells):
                    if i < len(cells):
                        out.append(('RAW', cells[i]))
                        i += 1
            else:
                out.append(('RAW', val))
                i += 1
        return ('<mixed>', tuple(out)) if matched_any else raw

    # 纯 phandle 数组或仅依赖 fixups 的引用属性
    matched_any = False
    for idx, val in enumerate(cells):
        byte_off = idx * 4
        if byte_off in prop_fixups:
            matched_any = True
            out.append(('EXT', prop_fixups[byte_off]))
        elif pure and val in phandles:
            matched_any = True
            out.append(('REF', phandles[val]))
        else:
            out.append(('RAW', val))
    return ('<mixed>', tuple(out)) if matched_any else raw


def node_view(path, props, phandles, cell_counts, fixups=None, ignore_phandle_id=True):
    view = {}
    for k, v in sorted(props.items()):
        if ignore_phandle_id and k in ('phandle', 'linux,phandle'):
            continue
        view[k] = normalize_value(v, phandles, cell_counts, prop=k, path=path, fixups=fixups)
    return view


def show(value):
    if isinstance(value, bytes):
        if value.endswith(b'\0'):
            try:
                s = value.rstrip(b'\0').decode('utf-8')
                if all(31 < ord(c) for c in s):
                    return 'str(%r)' % s
            except UnicodeDecodeError:
                pass
        if len(value) % 4 == 0 and value:
            cells = struct.unpack('>%dI' % (len(value) // 4), value)
            if len(cells) == 1:
                return '0x%08x' % cells[0]
            return '[' + ', '.join('0x%x' % c for c in cells) + ']'
        return value.hex()
    if isinstance(value, tuple) and value and value[0] == '<mixed>':
        items = []
        for kind, item in value[1]:
            if kind == 'REF':
                items.append('REF(%s)' % item)
            elif kind == 'EXT':
                items.append('EXT(&%s)' % item)
            else:
                items.append('0x%x' % item)
        return '[' + ', '.join(items) + ']'
    return repr(value)


def compare(a_nodes, b_nodes, a_name='A', b_name='B', ignore_phandle_id=True):
    a_ph = build_phandle_map(a_nodes)
    b_ph = build_phandle_map(b_nodes)
    a_cc = build_cell_counts(a_nodes)
    b_cc = build_cell_counts(b_nodes)
    report = {'only_in_a': [], 'only_in_b': [], 'prop_diffs': []}
    for k in sorted(set(a_nodes) - set(b_nodes)):
        report['only_in_a'].append((k, k))
    for k in sorted(set(b_nodes) - set(a_nodes)):
        report['only_in_b'].append((k, k))
    for k in sorted(set(a_nodes) & set(b_nodes)):
        va = node_view(k, a_nodes[k], a_ph, a_cc, ignore_phandle_id=ignore_phandle_id)
        vb = node_view(k, b_nodes[k], b_ph, b_cc, ignore_phandle_id=ignore_phandle_id)
        for prop in sorted(set(va) | set(vb)):
            if prop not in va:
                report['prop_diffs'].append((k, prop, '<缺失>', show(vb[prop])))
            elif prop not in vb:
                report['prop_diffs'].append((k, prop, show(va[prop]), '<缺失>'))
            elif va[prop] != vb[prop]:
                report['prop_diffs'].append((k, prop, show(va[prop]), show(vb[prop])))
    return report


def _fragment_targets(nodes, ph, fixups):
    """fragment 节点路径 -> 带消歧序号的规范目标描述。"""
    raw_targets = []
    for p in sorted(nodes):
        if not p.startswith('/fragment@') or '/' in p[1:]:
            continue
        props = nodes[p]
        tgt = props.get('target-path')
        if tgt is not None:
            desc = tgt.rstrip(b'\0').decode('utf-8', 'replace')
        elif (p, 'target') in fixups and 0 in fixups[(p, 'target')]:
            desc = '&' + fixups[(p, 'target')][0]
        elif 'target' in props and len(props['target']) == 4:
            val = struct.unpack('>I', props['target'])[0]
            desc = ph.get(val, 'phandle#%d' % val)
        else:
            desc = p
        raw_targets.append((p, desc))

    counts = {}
    for _, desc in raw_targets:
        counts[desc] = counts.get(desc, 0) + 1
    seen = {}
    out = {}
    for p, desc in raw_targets:
        if counts[desc] > 1:
            idx = seen.get(desc, 0)
            seen[desc] = idx + 1
            out[p] = '%s#%d' % (desc, idx)
        else:
            out[p] = desc
    return out


def compare_overlay(a_nodes, b_nodes, a_name, b_name, ignore_phandle_id=True):
    """overlay 比较：基于 /__fixups__ 对齐 fragment 目标并保留内部节点上下文。"""
    a_ph, b_ph = build_phandle_map(a_nodes), build_phandle_map(b_nodes)
    a_cc, b_cc = build_cell_counts(a_nodes), build_cell_counts(b_nodes)
    a_fix, b_fix = build_overlay_fixups(a_nodes), build_overlay_fixups(b_nodes)

    def remap(nodes, ph, fixups):
        frags = _fragment_targets(nodes, ph, fixups)
        # fragment 路径 -> 规范 key，用于重写局部 <&{/fragment@N/...}> 引用中的路径
        sorted_frags = sorted(frags.items(), key=lambda kv: len(kv[0]), reverse=True)
        norm_ph = {}
        for num, npath in ph.items():
            mapped = npath
            for f, tgt in sorted_frags:
                if npath == f:
                    mapped = 'fragment->' + tgt
                    break
                if npath.startswith(f + '/'):
                    mapped = 'fragment->' + tgt + npath[len(f):]
                    break
            norm_ph[num] = mapped

        out = {}
        for p, props in nodes.items():
            if p.startswith('/__'):
                continue
            key = p
            for f, tgt in sorted_frags:
                if p == f:
                    key = 'fragment->' + tgt
                    break
                if p.startswith(f + '/'):
                    key = 'fragment->' + tgt + p[len(f):]
                    break
            out[key] = (p, props)
        return out, norm_ph

    a_keys, a_nph = remap(a_nodes, a_ph, a_fix)
    b_keys, b_nph = remap(b_nodes, b_ph, b_fix)
    report = {'only_in_a': [], 'only_in_b': [], 'prop_diffs': []}
    for k in sorted(set(a_keys) - set(b_keys)):
        report['only_in_a'].append((k, k))
    for k in sorted(set(b_keys) - set(a_keys)):
        report['only_in_b'].append((k, k))
    for k in sorted(set(a_keys) & set(b_keys)):
        orig_pa, props_a = a_keys[k]
        orig_pb, props_b = b_keys[k]
        va = node_view(orig_pa, props_a, a_nph, a_cc, fixups=a_fix, ignore_phandle_id=ignore_phandle_id)
        vb = node_view(orig_pb, props_b, b_nph, b_cc, fixups=b_fix, ignore_phandle_id=ignore_phandle_id)
        for prop in sorted(set(va) | set(vb)):
            if prop not in va:
                report['prop_diffs'].append((k, prop, '<缺失>', show(vb[prop])))
            elif prop not in vb:
                report['prop_diffs'].append((k, prop, show(va[prop]), '<缺失>'))
            elif va[prop] != vb[prop]:
                report['prop_diffs'].append((k, prop, show(va[prop]), show(vb[prop])))
    report['fixups'] = {
        a_name: sorted(a_nodes.get('/__fixups__', {})),
        b_name: sorted(b_nodes.get('/__fixups__', {})),
    }
    return report


def summarize(report, max_diff, a_name, b_name):
    lines = []
    lines.append('only in %s: %d' % (a_name, len(report['only_in_a'])))
    for k, _p in report['only_in_a'][:max_diff]:
        lines.append('  - %s' % k)
    if len(report['only_in_a']) > max_diff:
        lines.append('  ... 另有 %d 项' % (len(report['only_in_a']) - max_diff))
    lines.append('only in %s: %d' % (b_name, len(report['only_in_b'])))
    for k, _p in report['only_in_b'][:max_diff]:
        lines.append('  + %s' % k)
    if len(report['only_in_b']) > max_diff:
        lines.append('  ... 另有 %d 项' % (len(report['only_in_b']) - max_diff))
    lines.append('属性差异: %d' % len(report['prop_diffs']))
    for k, prop, va, vb in report['prop_diffs'][:max_diff]:
        lines.append('  ~ %s : %s\n      %s: %s\n      %s: %s' % (k, prop, a_name, va, b_name, vb))
    if len(report['prop_diffs']) > max_diff:
        lines.append('  ... 另有 %d 项' % (len(report['prop_diffs']) - max_diff))
    if 'fixups' in report:
        fa, fb = set(report['fixups'][a_name]), set(report['fixups'][b_name])
        lines.append('__fixups__ 标签: 仅 %s %d 个，仅 %s %d 个' %
                     (a_name, len(fa - fb), b_name, len(fb - fa)))
        if fa - fb:
            lines.append('  仅 %s: %s' % (a_name, sorted(fa - fb)[:20]))
        if fb - fa:
            lines.append('  仅 %s: %s' % (b_name, sorted(fb - fa)[:20]))
    return '\n'.join(lines)


def main(argv):
    if len(argv) >= 3 and argv[1] == '--dump':
        nodes = parse_fdt(open(argv[2], 'rb').read())
        ph = build_phandle_map(nodes)
        cc = build_cell_counts(nodes)
        fix = build_overlay_fixups(nodes)
        for p in sorted(nodes):
            print(p)
            for k, v in sorted(nodes[p].items()):
                print('    %-32s %s' % (k, show(normalize_value(v, ph, cc, prop=k, path=p, fixups=fix))))
        return 0
    if len(argv) < 3:
        print(__doc__)
        return 2
    a_path, b_path = argv[1], argv[2]
    json_out = None
    max_diff = 40
    overlay_mode = '--overlay' in argv
    ignore_ph = '--show-phandle-id' not in argv
    if '--json' in argv:
        json_out = argv[argv.index('--json') + 1]
    if '--max-diff' in argv:
        max_diff = int(argv[argv.index('--max-diff') + 1])
    a_nodes = parse_fdt(open(a_path, 'rb').read())
    b_nodes = parse_fdt(open(b_path, 'rb').read())
    if overlay_mode:
        report = compare_overlay(a_nodes, b_nodes, a_path, b_path, ignore_phandle_id=ignore_ph)
    else:
        report = compare(a_nodes, b_nodes, a_path, b_path, ignore_phandle_id=ignore_ph)
    print('=== %s' % a_path)
    print('=== %s' % b_path)
    print(summarize(report, max_diff, a_path, b_path))
    if json_out:
        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print('JSON -> %s' % json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
