# 6.18 构建配置（dijun / OS4.0.0.19, OS4.0.4.0 & OS4.0.5.0）

- `dijun-os4.config`：OS4.0.0.19 设备运行中 `/proc/config.gz` 原样导出（6.18.21 基线）。
- `dijun-os4.0.4.0.config`：OS4.0.4.0 设备运行中 `/proc/config.gz` 原样导出（新增 `CONFIG_DPM_WATCHDOG=y` 等）。
- `dijun-os4.0.5.0.config`：OS4.0.5.0 `boot.img` 内核 `extract-ikconfig` 原样导出（与 `dijun-os4.0.4.0.config` 逐字节完全一致，`08d01cd15a30e805…`）。构建时不要手工归一化；`olddefconfig` 会自动丢弃本树不存在的厂商私有选项。
- 白名单系列（用作 `UNUSED_KSYMS_WHITELIST`，让 `TRIM_UNUSED_KSYMS=y` 下仍导出必需符号）：
  - `ksym-whitelist-os4.0.0.19.txt`（4,945 条）
  - `ksym-whitelist-os4.0.4.0.txt`（4,951 条）
  - `ksym-whitelist-os4.0.5.0.txt`（4,951 条；`ksym-whitelist.txt` 默认软链至此）
  - `ksym-whitelist-hmos.txt`（4,955 条；补齐 `dijun_hmos_ipc_api_v2`、`get_task_pid`、`pid_nr_ns`、`task_active_pid_ns`）
  - `ksym-whitelist-hmos-opt2.txt`（4,964 条；在 `hmos` 基础上补齐 `LZ4_*HC` 4 项与 `USER_NS` 的 `make_kuid`/`from_kuid*`/`make_kgid`/`from_kgid` 5 项，消除未签名外部模块命中 `KSYM_FLAG_PROTECTED` 的风险）
- `fragments/`：可叠加配置片段（`pidns.config`、`hmos-ipc.config`、`hmos-opt2.config`、`panthor-builtin.config`）。
- `baselines/`：分场景环境契约（`os4.0.0.19.env`、`os4.0.4.0-pure.env`、`os4.0.4.0-hmos.env`、`os4.0.5.0-pure.env`、`os4.0.5.0-hmos-opt2.env`）；`baseline.env` 对齐当前现役 `OS4.0.5.0 / 6.18.32-hmos-opt2` 契约（含 `VERMAGIC` 与 `MODULE_LAYOUT_CRC=0x60801db3`）。

## 已知被丢弃的厂商私有选项

`F2FS_VIP_FILE`、`F2FS_INLINE_EXTENT`、`SCSI_DISCARD`、`SCSI_FASTDISCARD`、`XIAOMI_ENHANCED_IOSTAT`、`XIAOMI_EROFS_IOSTAT`、`UAPI_HEADER_TEST`、`CC_CAN_LINK` 等在本 AOSP 树里没有对应 Kconfig，构建后不存在。

## 构建要点

- 工具链必须与厂商一致：clang `r584948c`（22.0.1，需导出 `LIBCLANG_PATH`）、Rust `1.91.1.p3`（build 15551131）、bindgen 0.72.x/0.73.x。
- 必须传 `KBUILD_GENDWARFKSYMS_STABLE=1`，且命令行显式传入 `LOCALVERSION=""` 配合 `.config` 中的 `CONFIG_LOCALVERSION="-4k"` 与 `CONFIG_LOCALVERSION_AUTO=n`，防止 `setlocalversion` 追加 `+` 或 `-dirty`。
- 源码目录需要存在 `protected_module_names_list`（`CONFIG_MODULE_SIG_PROTECT_LIST` 指向它），`scripts/build-kernel.sh` 会自动创建空文件。
- 构建出的模块默认未签名；需要加载到开启 `MODULE_SIG_PROTECT` 内核上的模块用 `scripts/sign-file` + `certs/signing_key.*` 签名，或通过白名单导出非 protected 符号。
