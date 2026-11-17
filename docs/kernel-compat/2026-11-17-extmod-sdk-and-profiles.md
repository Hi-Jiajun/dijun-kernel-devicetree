# 6.18.32-4k 双契约、外部模块构建 SDK 与多线 Profile（2026-11-17）

## 1. 外部内核模块加载的硬性双契约

对已烧录到设备的 `6.18.32-4k` 内核，任何独立编译的 `.ko` 必须同时满足两项常量，否则加载直接失败：

1. **`vermagic` 逐字一致**（否则 `insmod` 报 `Exec format error` / `ENOEXEC`）：
   ```text
   6.18.32-4k SMP preempt mod_unload modversions aarch64
   ```
   - 必须同时设置 `CONFIG_LOCALVERSION="-4k"`、`CONFIG_LOCALVERSION_AUTO=n`，**并在 `make` 命令行显式传入 `LOCALVERSION=""`**（查看 `scripts/setlocalversion` 可知：即使禁用 `LOCALVERSION_AUTO`，只要未传 `LOCALVERSION=""`，非干净 tag 的 Git 树仍会追加 `+`）。
2. **`module_layout` CRC 一致**（否则报 `disagrees about version of symbol module_layout`）：
   ```text
   0x60801db3
   ```
   - 由精确对齐 `OS4.0.4.0` 的 `dijun-os4.0.4.0.config` + `clang r584948c` + `KBUILD_GENDWARFKSYMS_STABLE=1` 在完整内核链接后锁定。

## 2. 只读符号表 SDK (`symvers/6.18.32-os4.0.4.0/`) 与 `build-extmod.sh`

直接在其它实验目录 `cp -a` 已有 `out/` 构造模块环境时，若遗漏重写 `out/Makefile` 中的 `export KBUILD_OUTPUT`，`make` 会写回原目录并触发重算，导致数千个内核导出符号 CRC 漂移。

因此本仓库在 [`symvers/6.18.32-os4.0.4.0/`](../../symvers/6.18.32-os4.0.4.0/) 固化三份只读符号表：
- `vmlinux-pure.symvers`（3,642 条，纯净 ABI 基线）；
- `vmlinux-hmos.symvers`（3,646 条，含 `dijun_hmos_ipc_api_v2` `0xcf4c0200`）；
- `vendor-modules.symvers`（2,518 条，由 `tools/export-mod-symvers.py` 从 OS4.0.4.0 332 个原厂模块提取，供依赖 `xr_dfx`/`securelib`/`xr_isp` 等平台符号的模块作 `KBUILD_EXTRA_SYMBOLS`）。

使用 [`scripts/build-extmod.sh`](../../scripts/build-extmod.sh) 编译外部模块：
- 对 `--kernel-src` 与 `--mod-src` 全程只读，模块源码过滤已有构建残留后复制到临时目录编；
- 用冻结 `vmlinux-*.symvers` 锁定隔离 `$O/Module.symvers`；
- 编译完成后自动核验 `.ko` 数量、`vermagic`、`module_layout` CRC 以及调用 `tools/abi-gate.py` 校验全部导入（0 未解析、0 CRC 冲突），最后生成 `build-manifest.json`。
- 纯 C 外部模块在未提供 Android Rust 工具链时会自动在隔离配置中禁用 `CONFIG_RUST` 完成 `modules_prepare`（不影响 `struct module` 与预置 `Module.symvers`）；若同时提供了 `RUSTC` / `RUST_LIB_SRC` / `BINDGEN`，则以完整原厂配置构建。

## 3. 多线内核 Profile (`scripts/build-kernel.sh --profile`)

| Profile | 配置叠加 | 源码补丁 | 白名单 | 用途与边界 |
| --- | --- | --- | --- | --- |
| `stock-abi` | 无 | 无 | `ksym-whitelist-os4.0.4.0.txt` (4,951) | 纯净复现 OS4.0.4.0 兼容内核 |
| `pidns` | `fragments/pidns.config` | 无 | 同上 | 开启 `CONFIG_PID_NS=y`，实测不破坏模块 CRC |
| `hmos` | `fragments/hmos-ipc.config` | `patches/6.18/hmos/` | `ksym-whitelist-hmos.txt` (4,955) | 导出 `dijun_hmos_ipc_api_v2`（`0xcf4c0200`），供 HarmonyOS 外部 IPC 模块使用 |
| `panthor` | `fragments/panthor-builtin.config` | `patches/6.18/panthor/`（规划中） | 视内核内建导出扩展 | [实验候选] 内建 DRM Panthor，需配套 GPU DT overlay、CSF 固件与 clk 桥接 |

## 4. `abi-gate.py` 升级要点

合并原离线核对脚本 `modabi.py` 的核心能力并保持向后兼容：
- 自动按 `Module.symvers` 第 3 列严格过滤 `vmlinux` 导出（避免同树模块导出污染内核表）；
- 支持 `--moddir <分区>=<目录>`，以 `<分区>:<相对路径>` 唯一建键，避免跨分区 69 个同名 `.ko` 相互覆盖；
- 新增模块间导出 CRC 校验、`--replace` 内存模块替换、`--allow-dead-module xr_pmonitor.ko` 死模块豁免、`--expect-vermagic`、`--protected-list` 未签名命中检查与 `--json` 输出；
- `scripts/build-kernel.sh` 不再使用 `|| true` 吞掉门禁错误。
