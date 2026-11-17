# Contributing

## 范围

本仓库只接受以下类型的改动：

- 设备树源码（`dts-reconstructed/`、`overlays/custom/`）、绑定补齐与引用参考（`dts-oss/`）；
- ABI/KMI 兼容性工具、符号导出表（纯文本 `symvers/`）、受控内核补丁（`patches/`）与文档；
- 构建、打包与离线验证脚本及真机运行记录。

不接受：设备分区镜像、厂商闭源二进制（`.ko`/固件）、未脱敏的序列号/本机用户名/路径/内网 IP/凭据。

## 提交前检查

```bash
unset PYTHONHOME PYTHONPATH
make verify
python3 -m py_compile tools/*.py
bash -n scripts/*.sh
```

真机相关改动必须附运行记录（命令、退出码、日志路径、回滚方式）。

## 约定

- 文档使用中文，文件名用 `YYYY-MM-DD-<kebab-case>.md`。
- 脚本需保留真实退出码，禁止使用 `rm -rf`，临时目录使用 `TMPDIR` 或 `~/.cache/dsh-tmp`。
- 仓库内软链必须使用相对路径；第三方代码保留 SPDX 头与来源说明。

## 版本、分支与标签

- `main` 保持工具、脚本、文档、多代 DTS 基线（`dts-oss/6.6.30-android15-v/` 参考基线与 `dts-reconstructed/` 三代设备基线）、配置片段与符号 SDK。
- 当某代内核的 DTS 需要独立演进，按内核版本开分支，命名 `dijun-<kernel-version>`；工具通过 `git subtree` 从 `main` 同步，避免复制维护。
- 发布快照用标签，不用分支：`v<YYYY.MM>-<tag-name>`，例如 `v2026.11-6.18.32`、`v2026.11-os4.0.4.0-sdk`。
- 跟进 Google 开源内核时，以 AOSP `android17-6.18` 的分支/标签为基线，更新后必须重跑 `tools/abi-gate.py` 与真机启动验证，再打新标签。
