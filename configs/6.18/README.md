# 6.18 构建配置（dijun / OS4.0.0.19）

- `dijun-os4.config`：设备运行中的 `/proc/config.gz` 原样导出（Android 17 / 6.18.21 基线）。构建时不要手改；`olddefconfig` 会自动丢弃本树不存在的厂商私有选项。
- `ksym-whitelist.txt`：OS4 全部模块（`vendor_boot` + `vendor_dlkm` + `system_dlkm`）未定义符号的并集，用作 `UNUSED_KSYMS_WHITELIST`，让 `TRIM_UNUSED_KSYMS=y` 下仍导出模块需要的符号。

## 已知被丢弃的厂商私有选项

`F2FS_VIP_FILE`、`F2FS_INLINE_EXTENT`、`SCSI_DISCARD`、`SCSI_FASTDISCARD`、`XIAOMI_ENHANCED_IOSTAT`、`XIAOMI_EROFS_IOSTAT` 等在本 AOSP 树里没有对应 Kconfig，构建后不存在。

## 构建要点

- 工具链必须与厂商一致：clang `r584948c`（22.0.1）、Rust `1.91.1.p3`（build 15551131）、bindgen 0.72.x/0.73.x。
- 必须传 `KBUILD_GENDWARFKSYMS_STABLE=1`，否则 CRC 全部漂移。
- 源码目录需要存在 `protected_module_names_list`（`CONFIG_MODULE_SIG_PROTECT_LIST` 指向它），本仓库的构建脚本会自动创建空文件。
- 构建出的模块默认未签名；需要加载的模块（如自编 `rust_binder.ko`）用构建产出的 `scripts/sign-file` + `certs/signing_key.*` 签名。
