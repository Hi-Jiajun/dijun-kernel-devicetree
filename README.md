# dijun kernel device tree

小米 15S Pro（`dijun`，XRING O1，25042PN24C）的**内核设备树与 GKI/KMI 构建底座**仓库。

本仓库聚焦内核侧的 DTS/DTB/DTBO、GKI/KMI 兼容性验证工具链、多线内核构建 Profile 以及外部模块（extmod）构建 SDK，不是 Android 用户态的 `device/xiaomi/dijun` 仓库。

## 当前状态（2026-11-17）

- **四套 DTS 基线（严格分层防误判）**：
  - [`dts-oss/6.6.30-android15-v/`](dts-oss/6.6.30-android15-v/)：官方开源 DTS（Android 15 / 6.6.30），仅作宏定义与节点语义参考，**严禁当作现行真机设备树**；
  - [`dts-reconstructed/6.6.118-os3/`](dts-reconstructed/6.6.118-os3/)：OS3（6.6.118）`base.dtb` + 全部 8 个 `dtbo` 无损还原；
  - [`dts-reconstructed/6.18.21-os4.0.0.19/`](dts-reconstructed/6.18.21-os4.0.0.19/)：OS4.0.0.19（6.18.21）`base.dtb` + 全部 8 个 `dtbo` 无损还原；
  - [`dts-reconstructed/6.18.21-os4.0.4.0/`](dts-reconstructed/6.18.21-os4.0.4.0/)（顶层软链 [`dts-current`](dts-current)）：OS4.0.4.0（现行底包）`base.dtb`（221,460 B）+ 全部 8 个 `dtbo` 无损还原，宿主 `dtc 1.8.1` 回编逐字节一致。
- **增量 DT 补丁层**：[`overlays/custom/`](overlays/custom/) 支持以最小 `.dtso` 叠加到现行基线，不直接修改上万行反编译 DTS。
- **当前内核与外部模块双契约**：AOSP `android17-6.18-2026-09`（`6.18.32-4k`），真机验证通过（`boot_b`）：
  - `VERMAGIC` 必须逐字等于 `"6.18.32-4k SMP preempt mod_unload modversions aarch64"`（不得带 `+` 或 `-dirty`）；
  - `module_layout` CRC 必须等于 `0x60801db3`；
  - 内置只读符号 SDK [`symvers/6.18.32-os4.0.4.0/`](symvers/6.18.32-os4.0.4.0/) 与 [`scripts/build-extmod.sh`](scripts/build-extmod.sh)，消除外部 `.ko` 构建的 CRC 漂移与 `ENOEXEC` 事故。
- **多线内核 Profile**：[`scripts/build-kernel.sh`](scripts/build-kernel.sh) 支持 `stock-abi`、`pidns`、`hmos`（补丁 [`patches/6.18/hmos/`](patches/6.18/hmos/)，导出 `dijun_hmos_ipc_api_v2` CRC `0xcf4c0200`）与实验性 `panthor` 内建规划（[`patches/6.18/panthor/`](patches/6.18/panthor/)）。
- **工具链全增强**：[`tools/fdtdiff.py`](tools/fdtdiff.py) 支持 `#*-cells` 规格化与 `/__fixups__` 对齐；[`tools/abi-gate.py`](tools/abi-gate.py) 支持多分区同名消歧、模块间 CRC 校验、`--replace`、`--allow-dead-module`、`--expect-vermagic`；[`scripts/pack-vendor_boot.sh`](scripts/pack-vendor_boot.sh) 动态继承原镜像参数避免跨代 cmdline 污染。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `dts-oss/6.6.30-android15-v/` | 官方开源参考 DTS（Android V / 6.6.30），cpp + dtc 可编 |
| `dts-reconstructed/` | 三代设备分区二进制无损还原的 `base.dts` + 全 8 个 `dtbo/entry*.dts`（含 `dts-current` 指向 OS4.0.4.0） |
| `overlays/custom/` | 最小增量 `.dtso` 补丁层及 `fdtoverlay` 验证示例 |
| `include/` | 补齐的 xring dt-bindings（`platform-specific` 映射） |
| `baseline/` | 三代原厂 `base.dtb` 与各自 8 个 `.dtbo` entry（二进制回归基线） |
| `configs/6.18/` | OS4.0.0.19/OS4.0.4.0 原始 config、多版本符号白名单、配置片段 `fragments/` 与场景基线 `baselines/` |
| `symvers/6.18.32-os4.0.4.0/` | 只读内核符号表 (`vmlinux-pure`/`vmlinux-hmos`) 与原厂 332 模块导出表 (`vendor-modules.symvers`) |
| `patches/6.18/` | 受控内核补丁集（`hmos` IPC 导出表、`panthor` 内建说明） |
| `tools/` | Python 工具：`_elfmod.py`、`fdtdiff.py`、`abi-gate.py`、`export-mod-symvers.py`、`dtbo-extract.py`、`mkdtboimg.py`、`module-inventory.py`、`btf-diff.py`、`kmi-check.py`、`patch-module-crc.py` |
| `scripts/` | 构建与验证脚本：`verify.sh`、`build-kernel.sh`、`build-extmod.sh`、`pack-boot.sh`、`pack-vendor_boot.sh`、`demo-patch.sh` |
| `docs/` | 设备树、内核兼容、外部模块 SDK、真机运行记录与原始 diff 报告 |

## 快速开始

### 1. 设备树构建与离线验收

```bash
unset PYTHONHOME PYTHONPATH      # 避免宿主环境污染 Python encodings
make b overlays                  # 编译全部三代 B 基线 (base.dtb + 24 个 dtbo) 与自定义 overlays
make verify                      # 全量离线验收（回编校验、fdtoverlay、容器重打、demo-patch、脱敏门禁）
make dtboimg-os4                 # 重打 OS4.0.4.0 dtbo.img
```

### 2. 构建外部内核模块（6.18.32-4k，不修改内核树）

```bash
export CLANG_BIN=<clang-r584948c>/bin
# 可选：同时提供 Android RUSTC / RUST_LIB_SRC / BINDGEN 以保持全量 CONFIG_RUST=y 准备环境
scripts/build-extmod.sh \
  --kernel-src <aosp-6.18.32-src> \
  --mod-src <extmod-src-dir> \
  --out <output-dir> \
  --profile hmos \
  --vendor-symvers
```

自动校验产出 `.ko` 的 `vermagic`、`module_layout=0x60801db3` 与全部 `__versions` CRC，并写出 `build-manifest.json`。

### 3. 全量构建 6.18.32 内核（按 Profile）

```bash
export CLANG_BIN=<clang-r584948c>/bin
export RUSTC=<rust-1.91.1.p3>/bin/rustc
export RUST_LIB_SRC=<rust-1.91.1.p3>/lib/rustlib/src/rust/library
export BINDGEN=$(command -v bindgen)
scripts/build-kernel.sh \
  --source <aosp-6.18.32-copy> --out <build-dir> \
  --profile hmos --baseline os4.0.4.0 --apply-patches \
  --sign <build-dir>/drivers/android/binder/rust_binder.ko \
  --gate-modules <vendor_boot-mods> --gate-modules <vendor_dlkm-mods> --gate-modules <system_dlkm-mods>
```

### 4. 重打包 `boot.img` 与 `vendor_boot.img`

```bash
scripts/pack-boot.sh --kernel <build-dir>/arch/arm64/boot/Image --out build/boot.img
scripts/pack-vendor_boot.sh --stock-img <stock_vendor_boot.img> --dtb build/b/6.18.21-os4.0.4.0/base.dtb --out build/vendor_boot.img --pad-to-stock
```

## 文档

从 [`docs/README.md`](docs/README.md) 开始，按设备树、内核兼容、外部模块 SDK、真机运行记录、原始报告分类索引。

## 边界与许可

- 仅用于**自有设备**的授权研究，仓库内不含设备分区镜像、厂商 `.ko`、固件二进制或未脱敏敏感信息。
- `dts-oss/`、`include/` 来自小米开源 `dijun-v-oss`（GPL-2.0 / MIT）；`dts-reconstructed/`、`baseline/`、`patches/` 为 GPL-2.0 内核衍生或补丁（见 [`LICENSE`](LICENSE)）；`tools/`、`scripts/` 为 MIT（见 [`LICENSE-MIT`](LICENSE-MIT)）。
- 社区参考：`lolipuru/android_device_xiaomi_dijun`、`xiatian410/xringo1-twrp`、`Lw5959/dijun_orangefox`、`Lw5959/dijun_skyward`（非本仓库内容）。
