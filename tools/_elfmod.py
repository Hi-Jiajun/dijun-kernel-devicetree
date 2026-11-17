#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""轻量纯 Python ELF64 内核模块（.ko）解析辅助库。

不依赖外部 readelf / modinfo / nm，可用于跨架构（aarch64）离线校验：
  - `__version_ext_crcs` / `__version_ext_names`（6.18+）与旧式 `__versions`；
  - 强未定义符号（GLOBAL + SHN_UNDEF）；
  - 导出符号、CRC（`__kcrctab` / `__kcrctab_gpl`）及导出标志（`__kflagstab`）；
  - `.modinfo` 键值（`vermagic` / `name` / `license` / `depends` 等）。
"""
import struct

SHT_SYMTAB = 2
SHN_UNDEF = 0
STB_GLOBAL = 1
KSYM_FLAG_GPL_ONLY = 0x01


class KoElf:
    """只读解析单个 ELF64 `.ko` 模块。"""

    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.blob = f.read()
        if len(self.blob) < 64 or self.blob[:4] != b'\x7fELF' or self.blob[4] != 2:
            raise ValueError('不是有效的 ELF64 文件: %s' % path)
        if self.blob[5] != 1:
            raise ValueError('仅支持小端 ELF64: %s' % path)

        (self.e_shoff,) = struct.unpack_from('<Q', self.blob, 0x28)
        (self.e_shentsize, self.e_shnum, self.e_shstrndx) = struct.unpack_from('<HHH', self.blob, 0x3A)
        self.sections = []
        for i in range(self.e_shnum):
            off = self.e_shoff + i * self.e_shentsize
            name_off, typ, _flags, _addr, sh_off, size, link, _info, _align, entsize = (
                struct.unpack_from('<IIQQQQIIQQ', self.blob, off)
            )
            self.sections.append(dict(
                name_off=name_off, type=typ, off=sh_off, size=size,
                link=link, entsize=entsize, idx=i,
            ))

        shstr = self.sections[self.e_shstrndx]
        strtab = self.blob[shstr['off']:shstr['off'] + shstr['size']]
        for s in self.sections:
            end = strtab.find(b'\0', s['name_off'])
            s['name'] = strtab[s['name_off']:end].decode('ascii', 'replace')
        self.by_name = {s['name']: s for s in self.sections}
        self.symbols = self._parse_symbols()

    def _parse_symbols(self):
        for s in self.sections:
            if s['type'] != SHT_SYMTAB:
                continue
            st = self.sections[s['link']]
            strings = self.blob[st['off']:st['off'] + st['size']]
            out = []
            n = s['size'] // 24
            for i in range(n):
                o = s['off'] + i * 24
                name_off, info, _other, shndx, value, _size = struct.unpack_from('<IBBHQQ', self.blob, o)
                end = strings.find(b'\0', name_off) if name_off < len(strings) else -1
                name = strings[name_off:end].decode('ascii', 'replace') if name_off and end >= 0 else ''
                out.append(dict(name=name, bind=info >> 4, shndx=shndx, value=value))
            return out
        return []

    def section_bytes(self, name):
        s = self.by_name.get(name)
        if not s:
            return b''
        return self.blob[s['off']:s['off'] + s['size']]

    def versions(self):
        """返回 {symbol: 期望 CRC(int)}，优先 6.18 的 __version_ext_*。"""
        crcs = self.section_bytes('__version_ext_crcs')
        names = self.section_bytes('__version_ext_names')
        out = {}
        if crcs and names:
            pos = 0
            for i in range(0, len(crcs) - 3, 4):
                (c,) = struct.unpack_from('<I', crcs, i)
                end = names.find(b'\0', pos)
                if end < 0:
                    break
                out[names[pos:end].decode('ascii', 'replace')] = c
                pos = end + 1
            return out

        data = self.section_bytes('__versions')
        for i in range(0, len(data) - 63, 64):
            (crc,) = struct.unpack_from('<Q', data, i)
            name = data[i + 8:i + 64].split(b'\0')[0].decode('ascii', 'replace')
            if name:
                out[name] = crc & 0xFFFFFFFF
        return out

    def imports(self):
        """强未定义符号（GLOBAL + SHN_UNDEF）；weakref 为 STB_WEAK 故自动排除。"""
        return sorted({
            s['name'] for s in self.symbols
            if s['shndx'] == SHN_UNDEF and s['bind'] == STB_GLOBAL and s['name']
        })

    def exports(self):
        """通过 __ksymtab* 符号反推模块声明导出的符号集合。"""
        out = set()
        for s in self.symbols:
            for pre in ('__ksymtab_gpl_', '__ksymtab_'):
                if s['name'].startswith(pre):
                    out.add(s['name'][len(pre):])
                    break
        return out

    def export_details(self):
        """返回 {symbol: (crc_int, export_type_str, namespace_str)}。"""
        kcrctab_map = {}
        for sec_name, default_type in (('__kcrctab', 'EXPORT_SYMBOL'), ('__kcrctab_gpl', 'EXPORT_SYMBOL_GPL')):
            sec = self.by_name.get(sec_name)
            if sec:
                kcrctab_map[sec['idx']] = (self.section_bytes(sec_name), default_type)

        gpl_sym_names = {
            s['name'][len('__ksymtab_gpl_'):]
            for s in self.symbols
            if s['name'].startswith('__ksymtab_gpl_')
        }

        flags_sec = self.by_name.get('__kflagstab')
        flags_bytes = self.section_bytes('__kflagstab') if flags_sec else b''
        sym_flags = {}
        if flags_sec and flags_bytes:
            fidx = flags_sec['idx']
            for s in self.symbols:
                if s['shndx'] == fidx and s['name'].startswith('__flags_'):
                    off = s['value']
                    if off < len(flags_bytes):
                        sym_flags[s['name'][len('__flags_'):]] = flags_bytes[off]

        ns_sec = self.by_name.get('__ksymtab_strings')
        ns_bytes = self.section_bytes('__ksymtab_strings') if ns_sec else b''
        sym_ns = {}
        if ns_sec and ns_bytes:
            nidx = ns_sec['idx']
            for s in self.symbols:
                if s['shndx'] == nidx and s['name'].startswith('__kstrtabns_'):
                    off = s['value']
                    end = ns_bytes.find(b'\0', off) if off < len(ns_bytes) else -1
                    if end >= 0:
                        sym_ns[s['name'][len('__kstrtabns_'):]] = ns_bytes[off:end].decode('ascii', 'replace')

        out = {}
        for s in self.symbols:
            if s['shndx'] in kcrctab_map and s['name'].startswith('__crc_'):
                sym = s['name'][len('__crc_'):]
                data, default_type = kcrctab_map[s['shndx']]
                off = s['value']
                if off + 4 <= len(data):
                    (crc,) = struct.unpack_from('<I', data, off)
                    if sym in gpl_sym_names:
                        exp_type = 'EXPORT_SYMBOL_GPL'
                    elif sym in sym_flags:
                        exp_type = 'EXPORT_SYMBOL_GPL' if (sym_flags[sym] & KSYM_FLAG_GPL_ONLY) else 'EXPORT_SYMBOL'
                    else:
                        exp_type = default_type
                    out[sym] = (crc, exp_type, sym_ns.get(sym, ''))
        return out

    def export_crcs(self):
        return {sym: crc for sym, (crc, _typ, _ns) in self.export_details().items()}

    def modinfo(self):
        """解析 `.modinfo` 节为 {key: [values...]} 以及单值便捷字典。"""
        raw = self.section_bytes('.modinfo')
        multi = {}
        for item in raw.split(b'\0'):
            if not item or b'=' not in item:
                continue
            k, v = item.split(b'=', 1)
            key = k.decode('utf-8', 'replace')
            val = v.decode('utf-8', 'replace')
            multi.setdefault(key, []).append(val)
        return multi

    def modinfo_first(self, key, default=''):
        vals = self.modinfo().get(key)
        return vals[0] if vals else default
