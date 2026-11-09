# 跟进 AOSP 6.18 内核的更新流程

## 当前基线

| 项 | 值 |
| --- | --- |
| AOSP 分支 | `android17-6.18-2026-09` |
| 内核版本 | 6.18.32 |
| 源码提交 | `ecdaacc9a0ee87eaf9544e1836d86bd9d590312e` |
| clang | `r584948c`（22.0.1 / build 15323222） |
| Rust | `1.91.1.p3`（build 15551131） |
| config | `configs/6.18/dijun-os4.config`（设备 `/proc/config.gz` 原样） |
| 符号白名单 | `configs/6.18/ksym-whitelist.txt` |
| Image sha256 | `34aead8c…` |
| 真机验证 | 2026-11-09 / OS4.0.0.19 / slot a |

机器可读版本在 `configs/6.18/baseline.env`。

## 更新步骤

1. 选目标：优先 AOSP 的季度分支 `android17-6.18-YYYY-MM` 或 `_rNN` 发布标签；不要直接跟 kernel.org stable（需要自己合 Android 补丁）。
2. 拉源码（浅克隆即可）：
   ```bash
   git clone --depth 1 --branch android17-6.18-2026-09 \
     https://android.googlesource.com/kernel/common aosp-6.18
   ```
3. 用构建脚本编内核 + 模块，并顺手签名 `rust_binder.ko`、跑 ABI 门：
   ```bash
   CLANG_BIN=<clang-r584948c>/bin \
   RUSTC=<rust-1.91.1.p3>/bin/rustc \
   RUST_LIB_SRC=<rust-1.91.1.p3>/lib/rustlib/src/rust/library \
   BINDGEN=$(command -v bindgen) \
   scripts/build-kernel.sh --source aosp-6.18 --out out-<版本> \
     --sign out-<版本>/drivers/android/binder/rust_binder.ko \
     --gate-modules <vendor_boot 模块目录> --gate-modules <vendor_dlkm 目录> --gate-modules <system_dlkm 目录>
   ```
4. **门禁判定**：ABI 门必须“CRC 不符 0 条”，唯一允许项是死模块 `xr_pmonitor`（缺 `lp_mnt`/`next_op_mode`）。出现其他不符就停——说明 ABI/KMI 变了（6.18.33 分支头就是这种情况，13,370 条不符），不能刷。
5. 真机验证：`mkbootimg` 生成 boot → `fastboot flash boot_a` → 检查 `sys.boot_completed=1`、模块数、无新 tombstone、关键功能；失败用原厂 `boot_a` 镜像回滚。
6. 记录与发布：更新 `configs/6.18/baseline.env`、本文档与 `CHANGELOG.md`，打标签 `vYYYY.MM-<内核版本>`。

## 注意

- 配置必须用设备原始 `/proc/config.gz`，不要手工归一化；`olddefconfig` 丢掉的厂商私有选项在 `configs/6.18/README.md` 有清单。
- 必须 `KBUILD_GENDWARFKSYMS_STABLE=1`，否则 CRC 全量漂移。
- 源码树需要 `protected_module_names_list`（脚本会自动补空文件）。
- 构建出的模块默认未签名，要加载的模块用 `scripts/sign-file` + `certs/signing_key.*` 签名。
- 回滚镜像常备：原厂 `boot_a`（与 OS4 包 `images/boot.img` 一致）。
