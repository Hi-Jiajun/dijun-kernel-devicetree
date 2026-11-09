# dijun kernel device tree

小米 15S Pro（`dijun`，XRING O1，25042PN24C）的**内核设备树**工程，以及配套的 GKI/KMI 兼容性验证工具链。

本仓库关注的是内核侧的 DTS/DTB/DTBO 与内核 ABI，不是 Android 的 `device/xiaomi/dijun` 设备树仓库。

## 当前状态（2026-11-09）

- **三代 DTS 基线**：`dts/` 是官方开源 DTS（Android V / 6.6.30）；`dts-reconstructed/6.6.118-os3/` 与 `dts-reconstructed/6.18.21-os4/` 是从设备分区二进制无损还原的两代基线（回编与设备二进制逐字节一致）。
- **两种打包链可复现**：`dtbo.img` 用设备 8 个 entry 重打、`vendor_boot` 用原厂件重打，均与设备镜像逐字节一致。
- **ABI 对齐**：6.6.118 保持原厂 config 重编，导出符号 9,090/9,090、CRC 全等；6.18.21 用 AOSP 公开源 + 厂商同款工具链，404 个原厂模块 CRC 全等。
- **当前内核基线**：AOSP `android17-6.18-2026-09`（6.18.32），已在 OS4 真机验证；更新流程见 [kernel-update-process](docs/kernel-compat/2026-11-09-kernel-update-process.md)。
- **真机验证**：自编 6.18.21 / 6.18.32 内核在 OS4 上均正常启动、功能基本可用；`CONFIG_PID_NS=y` 变体验证通过（PID namespace 可用）。`android17-6.18` 分支头 6.18.33 因 ABI 类型变化暂不兼容 OS4 原厂模块。
- **已知缺口**：`xr_pmonitor` 是死模块（依赖的 `lp_mnt` 在内核与分区中都不存在）；原厂 `rust_binder.ko` 与自编内核 crate 哈希不匹配，需用本仓库自编并签名的模块替代。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `dts/` | 官方开源 DTS（Android V / 6.6.30），cpp + dtc 可编 |
| `dts-reconstructed/6.6.118-os3/` | OS3 分区二进制还原的 6.6.118 基线 |
| `dts-reconstructed/6.18.21-os4/` | OS4 分区二进制还原的 6.18.21 基线 |
| `include/` | 补齐的 xring dt-bindings（`platform-specific` 映射） |
| `baseline/6.6.118-os3/`、`baseline/6.18.21-os4/` | 两代原厂 `base.dtb` 与 8 个 dtbo entry（二进制，回归基线） |
| `configs/6.18/` | 内核 config、模块符号白名单、内核基线版本（`baseline.env`） |
| `tools/` | Python 工具：结构 diff、dtbo 提取/打包、ABI 门、模块盘点、BTF 对比、CRC 改写 |
| `scripts/` | Shell 入口：`verify.sh`、`build-kernel.sh`、`pack-vendor_boot.sh`、`demo-patch.sh` |
| `docs/device-tree/` | 设备树调研与构建/验收记录 |
| `docs/kernel-compat/` | GKI/KMI、工具链、OS4 6.18 自编内核与功能开关文档 |
| `docs/runbooks/` | 真机自编内核的首测失败与成功记录（含回滚方式） |
| `docs/reports/` | 各阶段 gate/结构 diff 的原始输出 |
| `Makefile` | V/B 两套 DTS 产物构建入口 |

## 快速开始

```bash
unset PYTHONHOME PYTHONPATH      # DSH/AppImage 注入坑
make all                         # 编 V 与 B 两套 base dtb + O2S overlay
make verify                      # 离线验收：回编哈希、结构 diff、容器同构
make dtboimg                     # 用 8 个 entry 重打 dtbo.img
make vendor_boot                 # 用 B 基线 dtb 重打 vendor_boot
```

`KERNEL` 默认指向本地 ACK 6.6.118 源码树，仅用于取通用 `include/dt-bindings`。

ABI 门（需要原厂 `Module.symvers` 与完整模块集合，按需自备）：

```bash
python3 tools/abi-gate.py --stock-symvers <原厂 symvers> \
  --our-symvers <自编 Module.symvers> \
  --modules <vendor_boot 模块目录> --modules <vendor_dlkm 目录> --modules <system_dlkm 目录> \
  --allow-unresolved-prefix mtk_pwrctl_slt_gpio_ \
  --out docs/reports/abi-gate.md
```

## 内核构建（可复现）

```bash
export CLANG_BIN=<clang-r584948c>/bin
export RUSTC=<rust-1.91.1.p3>/bin/rustc
export RUST_LIB_SRC=<rust-1.91.1.p3>/lib/rustlib/src/rust/library
export BINDGEN=$(command -v bindgen)
scripts/build-kernel.sh --source <AOSP android17-6.18 树> --out <构建目录> \
  --sign <构建目录>/drivers/android/binder/rust_binder.ko \
  --gate-modules <vendor_boot 模块目录> --gate-modules <vendor_dlkm 目录> --gate-modules <system_dlkm 目录>
```

配置与符号白名单在 `configs/6.18/`；脚本会补 `protected_module_names_list`、强制 `KBUILD_GENDWARFKSYMS_STABLE=1`、构建模块、签名指定模块并运行 ABI 门。构建出的 Image 与 `Module.symvers` 用于后续刷机与校验。

## 方法学

- 判据优先看**模块 `__versions` 期望 CRC 与实际内核导出的差异条数**（基线 0），全量 CRC 百分比只作诊断。
- 不要关"看似无关"的配置：`DEBUG_INFO_BTF` 会改变 `__user` 是否展开为 `btf_type_tag` 注解，genksyms 把属性算进类型字符串，一关就会造成大面积 CRC 漂移。
- 6.18 的 CRC 由 `gendwarfksyms` 从 DWARF 计算，必须带 `KBUILD_GENDWARFKSYMS_STABLE=1`，工具链需与厂商一致（clang `r584948c`、Rust `1.91.1.p3`）。
- 模块集合必须完整（`vendor_boot` + `vendor_dlkm` + `system_dlkm`），否则会把"没找到提供方"误判成"驱动缺失"。

## 文档

从 [`docs/README.md`](docs/README.md) 开始，按设备树、内核兼容、真机运行记录、原始报告四类索引。

## 边界

- 仅用于**自有设备**的授权研究，不适用于他人设备，不提供任何明示或暗示的担保。
- 仓库内不含设备分区镜像与厂商闭源二进制；文档中的路径与序列号已做占位符脱敏。
- 真机刷写属于高风险操作，请先阅读 `docs/runbooks/` 中的回滚方式；本仓库不对刷写后果负责。
- 与小米公司无隶属关系。

## 许可与归属

- `dts/` 与 `include/` 来自小米开源 `dijun-v-oss` 树（GPL-2.0 / MIT，见文件 SPDX）。
- `dts-reconstructed/` 与 `baseline/` 由自有设备分区二进制反编译/提取得到，属于 GPL-2.0 内核衍生物；整体按 GPL-2.0（`LICENSE`）。
- `tools/`、`scripts/` 为本仓库自写，MIT（`LICENSE-MIT`）。
- 社区参考：`lolipuru/android_device_xiaomi_dijun`、`android_device_xiaomi_O1_asic-common`、`android_device_xiaomi_dijun-kernel`（非本仓库内容）。
