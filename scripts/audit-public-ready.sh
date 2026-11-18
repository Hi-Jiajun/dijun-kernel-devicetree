#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# 公开前合规与全量脱敏门禁：
#   Gate 1  完整许可证文件体系校验（LICENSE / COPYING / LICENSES / LICENSE-MIT / NOTICE）
#           与 36 对 DTB/DTBO ↔ DTS 1:1 源码配对校验
#   Gate 2  违禁二进制（.ko/.img/.bin/.so/.apk/.ta/.key/压缩包）与私有工具目录拦截
#   Gate 3  工作区受控文件与 Git 历史敏感串/本地路径/占位符扫描
#
# 用法：
#   scripts/audit-public-ready.sh                    # 仅检查当前工作区（及受控清单）
#   scripts/audit-public-ready.sh --check-history    # 同步检查 HEAD --branches --tags 可达历史
#   scripts/audit-public-ready.sh --check-history --all-refs  # 检查 --all 全部引用历史
set -uo pipefail
unset PYTHONHOME PYTHONPATH

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

CHECK_HISTORY=0
ALL_REFS=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --check-history) CHECK_HISTORY=1 ;;
        --all-refs)      ALL_REFS=1; CHECK_HISTORY=1 ;;
        -h|--help)
            sed -n '2,15p' "$0"
            exit 0
            ;;
        *)
            printf '未知参数: %s\n' "$1" >&2
            exit 2
            ;;
    esac
    shift
done

fail=0
ok() { printf 'PASS  %s\n' "$*"; }
ng() { printf 'FAIL  %s\n' "$*" >&2; fail=$((fail + 1)); }

# Gate 1: 许可证文件体系与 GPL 二进制-源码 1:1 配对
req_files=(
    "LICENSE"
    "COPYING"
    "LICENSES/preferred/GPL-2.0"
    "LICENSES/exceptions/Linux-syscall-note"
    "LICENSE-MIT"
    "NOTICE"
)
g1_bad=0
for f in "${req_files[@]}"; do
    if [ ! -s "$f" ]; then
        ng "Gate 1 缺少非空许可/声明文件: $f"
        g1_bad=1
    fi
done
if [ -s LICENSE ] && { ! grep -q "GNU GENERAL PUBLIC LICENSE" LICENSE || ! grep -q "Version 2" LICENSE; }; then
    ng "Gate 1 根目录 LICENSE 未包含标准 GNU GPL Version 2 正文"
    g1_bad=1
fi

dt_pairs=0
dt_missing=0
for b in baseline/*/base.dtb baseline/*/dtbo/*.dtbo; do
    [ -e "$b" ] || continue
    rel=${b#baseline/}
    ver=${rel%%/*}
    [ -L "baseline/$ver" ] && continue
    sub=${rel#*/}
    src="dts-reconstructed/$ver/${sub%.*}.dts"
    if [ ! -s "$src" ]; then
        ng "Gate 1 缺少对应源码: $b -> $src"
        dt_missing=$((dt_missing + 1))
    else
        dt_pairs=$((dt_pairs + 1))
    fi
done
if [ "$g1_bad" -eq 0 ] && [ "$dt_missing" -eq 0 ] && [ "$dt_pairs" -eq 36 ]; then
    ok "Gate 1 许可证体系完整且 $dt_pairs/36 个 DTB/DTBO 具备 1:1 源码配对"
elif [ "$dt_pairs" -ne 36 ]; then
    ng "Gate 1 预期 36 对基线产物，实际检测到 $dt_pairs 对 (缺失 $dt_missing)"
fi

# Gate 2 & 3 通用正则（以字符串分段拼接，避免脚本自身触发自匹配）
p_user="hil""iang"
p_host="arch-""9700x"
p_sn="0285AC""2001A00540"
p_ip1="192\.168""\.1\."
p_ip2="127\.0\.0\.1"":7890"
p_ws1="mib""ugs"
p_ws2="deepseek""-harness"
p_ws3="cpa-""config"
p_sec1="Mi""SRC"
p_sec2="24""182"
p_sec3="64""560"
p_sec4="64""468"
p_sec5="64""469"
p_sec6="98""260"
p_sec7="cred""spray"
p_sec8="ghost""lock"
p_sec9="one""click"
p_sec10="enn""ea"
PAT_SENSITIVE="${p_user}|${p_host}|${p_sn}|${p_ip1}|${p_ip2}|${p_ws1}|${p_ws2}|${p_ws3}|${p_sec1}|${p_sec2}|${p_sec3}|${p_sec4}|${p_sec5}|${p_sec6}|${p_sec7}|${p_sec8}|${p_sec9}|${p_sec10}"
PAT_HOME="<""home>"
PAT_EXT="\.(ko|img|bin|so|apk|ta|key|pem|der|zst|gz|xz|tar|zip|7z|deb|rpm)$"
PAT_PRIV="(\.dsh-project-memory|(^|/)openspec(/|$)|\.codegraph|\.bak)"

# Gate 2: 工作区与历史中的违禁扩展名/私有目录拦截
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git ls-files | grep -E "${PAT_EXT}|${PAT_PRIV}" >/dev/null; then
        git ls-files | grep -E "${PAT_EXT}|${PAT_PRIV}" >&2
        ng "Gate 2 受控文件清单中发现违禁扩展名或私有工具目录"
    else
        ok "Gate 2 工作区受控文件扩展名与目录边界 CLEAN"
    fi

    if [ "$CHECK_HISTORY" -eq 1 ]; then
        if [ "$ALL_REFS" -eq 1 ]; then
            REV_ARGS=(--all)
        else
            REV_ARGS=(HEAD --branches --tags)
        fi
        if git rev-list --objects "${REV_ARGS[@]}" | awk 'NF>=2 {print $2}' | grep -E "${PAT_EXT}|${PAT_PRIV}" >/dev/null; then
            git rev-list --objects "${REV_ARGS[@]}" | awk 'NF>=2 {print $2}' | grep -E "${PAT_EXT}|${PAT_PRIV}" >&2
            ng "Gate 2 Git 可达对象历史中发现违禁二进制或私有工具产物"
        else
            ok "Gate 2 Git 可达对象历史无违禁二进制与私有目录"
        fi
    fi
else
    ok "Gate 2 非 Git 目录，跳过历史对象校验"
fi

# Gate 3: 工作区文件、可执行目录占位符与 Git 历史敏感词扫描
if grep -rnIE "$PAT_SENSITIVE" \
    --exclude-dir=.git --exclude-dir=build --exclude-dir=__pycache__ --exclude-dir=.dsh-project-memory \
    --exclude='*.bak*' . >/dev/null 2>&1; then
    grep -rnIE "$PAT_SENSITIVE" \
        --exclude-dir=.git --exclude-dir=build --exclude-dir=__pycache__ --exclude-dir=.dsh-project-memory \
        --exclude='*.bak*' . >&2
    ng "Gate 3 工作区文件中检测到敏感字符串"
elif grep -rnI "$PAT_HOME" Makefile scripts tools >/dev/null 2>&1; then
    grep -rnI "$PAT_HOME" Makefile scripts tools >&2
    ng "Gate 3 构建/脚本代码中检测到未替换的占位符"
else
    ok "Gate 3 工作区敏感串与构建占位符扫描 CLEAN"
fi

if [ "$CHECK_HISTORY" -eq 1 ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git log "${REV_ARGS[@]}" -p | grep -aIE "$PAT_SENSITIVE" >/dev/null 2>&1; then
        git log "${REV_ARGS[@]}" -p | grep -aIE "$PAT_SENSITIVE" | head -n 20 >&2
        ng "Gate 3 Git 可达提交 diff 历史中检测到敏感字符串"
    elif git log "${REV_ARGS[@]}" --format='%an <%ae> | %cn <%ce> | %B' | grep -aIE "$PAT_SENSITIVE|users\.noreply" >/dev/null 2>&1; then
        git log "${REV_ARGS[@]}" --format='%h %an <%ae> | %cn <%ce> | %s' | grep -aIE "$PAT_SENSITIVE|users\.noreply" >&2
        ng "Gate 3 Git 提交者元数据/日志中检测到未规范化标识"
    else
        ok "Gate 3 Git 可达提交历史与作者邮箱审计 CLEAN"
    fi
fi

if [ "$fail" -eq 0 ]; then
    printf 'PUBLIC-AUDIT PASS\n'
    exit 0
fi
printf 'PUBLIC-AUDIT FAIL (failures=%d)\n' "$fail" >&2
exit 1
