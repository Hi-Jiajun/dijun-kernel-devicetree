#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FDT/DTBO 结构比较工具（dijun 设备树工程自用）。

用途：
  1. 解析 .dtb/.dtbo，输出节点路径 -> {属性: 原始字节}；
  2. 把 phandle 引用归一化成被引用节点的路径，消除编号差异；
  3. 比较两份 FDT：报告缺失/新增节点、缺失/新增属性、值不同的属性；
  4. 对 overlay 按 fragment 的目标路径对齐比较，而不是按 fragment 序号。

用法：
  fdtdiff.py tree-a.dtb tree-b.dtb [--json out.json] [--max-diff N]
  fdtdiff.py --dump x.dtb

注意：这是研究用工具，不是 libfdt 的完整替代；不校验 rsvmap、不处理 NOP 之外的特殊 token。
"""
import json
import struct
import sys

FDT_MAGIC = 0xD00DFEED
TOK_BEGIN_NODE, TOK_END_NODE, TOK_PROP, TOK_NOP, TOK_END = 1, 2, 3, 4, 9


def parse_fdt(blob):
    if len(blob) < 40:
        raise ValueError('文件太短，不是 FDT')
    (magic, totalsize, off_struct, off_strings, off_rsvmap, version,
     last_comp, boot_cpuid, size_strings, size_struct) = struct.unpack('>10I', blob[:40])
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


def label_map(nodes):
    """label -> 路径（来自 /__symbols__）。"""
    out = {}
    for key, raw in nodes.get('/__symbols__', {}).items():
        out[key] = raw.rstrip(b'\0').decode('utf-8', 'replace')
    return out


SCALAR_PROPS = {
    '#address-cells', '#size-cells', '#clock-cells', '#gpio-cells', '#interrupt-cells',
    '#dma-cells', '#power-domain-cells', '#pwm-cells', '#thermal-sensor-cells',
    '#iommu-cells', '#phy-cells', '#mbox-cells', '#reset-cells', '#sound-dai-cells',
    'phandle', 'linux,phandle', 'reg', 'interrupts', 'interrupts-extended',
    'clock-frequency', 'status', 'board_id', 'board_rev', 'custom0', 'cell-index',
}

# 允许按 phandle 归一化的属性（混合列表里只替换命中的单元）
PHANDLE_HINTS = (
    'clocks', 'resets', 'interrupt-parent', 'interrupts-extended', 'memory-region',
    'power-domains', 'iommus', 'dmas', 'dma-names', 'mboxes', 'mbox-names', 'phys',
    'phy-names', 'pinctrl-', 'gpios', 'gpio', '*-supply', 'clocks-', 'assigned-clocks',
    'assigned-clock-parents', 'operating-points-v2', 'opp-', 'cpus', 'cpu', 'cooling-device',
    'thermal-sensors', 'nvmem-cells', 'io-channels', 'sound-dai', 'dai-link', 'remote-endpoint',
)


def _is_phandle_prop(prop):
    if prop in SCALAR_PROPS:
        return False
    for h in PHANDLE_HINTS:
        if h.startswith('*') and prop.endswith(h[1:]):
            return True
        if prop.startswith(h) or prop.endswith(h):
            return True
    return False


def normalize_value(raw, phandles, prop=''):
    """把 phandle 引用单元替换成 REF(路径)，消除编号差异。

    只有属性名命中 PHANDLE_HINTS 才解释；混合列表逐单元替换，标量保持原样。
    """
    if not _is_phandle_prop(prop) or len(raw) == 0 or len(raw) % 4:
        return raw
    cells = struct.unpack('>%dI' % (len(raw) // 4), raw)
    if not any(c in phandles for c in cells):
        return raw
    out = []
    for c in cells:
        out.append(('REF', phandles[c]) if c in phandles else ('RAW', c))
    return ('<mixed>', tuple(out))



def values_equal(raw_a, raw_b, ph_a, ph_b, prop):
    """先比原始字节；不同时再按 phandle 归一化比较，消除编号差异。"""
    if raw_a == raw_b:
        return True
    na = normalize_value(raw_a, ph_a, prop)
    nb = normalize_value(raw_b, ph_b, prop)
    if isinstance(na, bytes) or isinstance(nb, bytes):
        return False
    # 归一化后只比较 RAW 单元序列；REF 目标路径要求两侧一致
    return tuple(na[1]) == tuple(nb[1])


def node_view(path, props, phandles):
    view = {}
    for k, v in sorted(props.items()):
        view[k] = normalize_value(v, phandles, k)
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
            items.append('REF(%s)' % item if kind == 'REF' else '0x%x' % item)
        return '[' + ', '.join(items) + ']'
    return repr(value)


def compare(a_nodes, b_nodes, a_name='A', b_name='B', key_norm=None):
    """比较两份节点表；key_norm(path)->对齐 key（overlay 用目标路径）。"""
    a_ph = build_phandle_map(a_nodes)
    b_ph = build_phandle_map(b_nodes)
    a_keys = {key_norm(p) if key_norm else p: p for p in a_nodes}
    b_keys = {key_norm(p) if key_norm else p: p for p in b_nodes}
    report = {'only_in_a': [], 'only_in_b': [], 'prop_diffs': []}
    for k in sorted(set(a_keys) - set(b_keys)):
        report['only_in_a'].append((k, a_keys[k]))
    for k in sorted(set(b_keys) - set(a_keys)):
        report['only_in_b'].append((k, b_keys[k]))
    for k in sorted(set(a_keys) & set(b_keys)):
        pa, pb = a_nodes[a_keys[k]], b_nodes[b_keys[k]]
        va, vb = node_view(a_keys[k], pa, a_ph), node_view(b_keys[k], pb, b_ph)
        for prop in sorted(set(va) | set(vb)):
            if prop not in va:
                report['prop_diffs'].append((k, prop, '<缺失>', show(vb[prop])))
            elif prop not in vb:
                report['prop_diffs'].append((k, prop, show(va[prop]), '<缺失>'))
            elif va[prop] != vb[prop]:
                if isinstance(va[prop], bytes) and isinstance(vb[prop], bytes) and va[prop] == vb[prop]:
                    continue
                report['prop_diffs'].append((k, prop, show(va[prop]), show(vb[prop])))
    return report


def overlay_key(nodes, path):
    """overlay 的 fragment 用 target-path 对齐；非 fragment 节点保持原路径。"""
    props = nodes[path]
    tgt = props.get('target-path')
    if tgt is not None:
        return 'fragment->' + tgt.rstrip(b'\0').decode('utf-8', 'replace')
    raw = props.get('target')
    if raw is not None and len(raw) == 4:
        return 'fragment->phandle:%d' % struct.unpack('>I', raw)[0]
    return path


def _fragment_targets(nodes, ph):
    """fragment 节点路径 -> 目标描述（target-path 优先，其次 target phandle）。"""
    m = {}
    for p, props in nodes.items():
        tgt = props.get('target-path')
        if tgt is not None:
            m[p] = tgt.rstrip(b'\0').decode('utf-8', 'replace')
        elif 'target' in props and len(props['target']) == 4:
            val = struct.unpack('>I', props['target'])[0]
            m[p] = ph.get(val, 'phandle#%d' % val)
    return m


def compare_overlay(a_nodes, b_nodes, a_name, b_name):
    """overlay 比较：按 fragment 的 target 路径对齐整棵子树，而不是按 fragment 序号。"""
    a_ph = build_phandle_map(a_nodes)
    b_ph = build_phandle_map(b_nodes)
    def remap(nodes, ph):
        frags = _fragment_targets(nodes, ph)
        out = {}
        for p, props in nodes.items():
            if p.startswith('/__'):
                continue
            key = p
            for f, tgt in frags.items():
                if p == f:
                    key = 'fragment->' + tgt
                    break
                if p.startswith(f + '/'):
                    key = 'fragment->' + tgt + p[len(f):]
                    break
            out[key] = props
        return out, ph
    a_keys, _ = remap(a_nodes, a_ph)
    b_keys, _ = remap(b_nodes, b_ph)
    report = {'only_in_a': [], 'only_in_b': [], 'prop_diffs': []}
    for k in sorted(set(a_keys) - set(b_keys)):
        report['only_in_a'].append((k, k))
    for k in sorted(set(b_keys) - set(a_keys)):
        report['only_in_b'].append((k, k))
    for k in sorted(set(a_keys) & set(b_keys)):
        va = {p: normalize_value(v, a_ph, p) for p, v in a_keys[k].items()}
        vb = {p: normalize_value(v, b_ph, p) for p, v in b_keys[k].items()}
        for prop in sorted(set(va) | set(vb)):
            if prop not in va:
                report['prop_diffs'].append((k, prop, '<缺失>', show(vb[prop])))
            elif prop not in vb:
                report['prop_diffs'].append((k, prop, show(va[prop]), '<缺失>'))
            elif not values_equal(a_keys[k].get(prop, b''), b_keys[k].get(prop, b''), a_ph, b_ph, prop):
                report['prop_diffs'].append((k, prop, show(va[prop]), show(vb[prop])))
    report['fixups'] = {
        a_name: sorted(a_nodes.get('/__fixups__', {})),
        b_name: sorted(b_nodes.get('/__fixups__', {})),
    }
    return report


def summarize(report, max_diff, a_name, b_name):
    lines = []
    lines.append('only in %s: %d' % (a_name, len(report['only_in_a'])))
    for k, p in report['only_in_a'][:max_diff]:
        lines.append('  - %s' % k)
    if len(report['only_in_a']) > max_diff:
        lines.append('  ... 另有 %d 项' % (len(report['only_in_a']) - max_diff))
    lines.append('only in %s: %d' % (b_name, len(report['only_in_b'])))
    for k, p in report['only_in_b'][:max_diff]:
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
        for p in sorted(nodes):
            print(p)
            for k, v in sorted(nodes[p].items()):
                print('    %-32s %s' % (k, show(normalize_value(v, ph, k))))
        return 0
    if len(argv) < 3:
        print(__doc__)
        return 2
    a_path, b_path = argv[1], argv[2]
    json_out = None
    max_diff = 40
    overlay_mode = '--overlay' in argv
    if '--json' in argv:
        json_out = argv[argv.index('--json') + 1]
    if '--max-diff' in argv:
        max_diff = int(argv[argv.index('--max-diff') + 1])
    a_nodes = parse_fdt(open(a_path, 'rb').read())
    b_nodes = parse_fdt(open(b_path, 'rb').read())
    if overlay_mode:
        report = compare_overlay(a_nodes, b_nodes, a_path, b_path)
    else:
        report = compare(a_nodes, b_nodes, a_path, b_path)
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
