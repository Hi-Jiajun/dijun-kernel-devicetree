# Contributing

## 范围

本仓库只接受以下类型的改动：

- 设备树源码、绑定补齐、构建与校验脚本；
- ABI/KMI 兼容性工具与文档；
- 运行记录与回滚手册。

不接受：设备分区镜像、厂商闭源二进制、未脱敏的序列号/路径/凭据。

## 提交前检查

```bash
unset PYTHONHOME PYTHONPATH
make all
make verify
python3 -m py_compile tools/*.py
```

真机相关改动必须附运行记录（命令、退出码、日志路径、回滚方式）。

## 约定

- 文档使用中文，文件名用 `YYYY-MM-DD-<kebab-case>.md`。
- 脚本需保留真实退出码，不使用 `rm -rf`。
- 第三方代码保留 SPDX 头与来源说明。

## 版本、分支与标签

- `main` 保持工具、脚本、文档与两代 DTS 基线（`dts/` = V 6.6.30，`dts-reconstructed/` = B 6.6.118）。
- 当某代内核的 DTS 需要独立演进（例如 OS4 / 6.18 的 DTS 开始维护），再按内核版本开分支，命名 `dijun-<kernel-version>`，分支内自带 `dts/`、`baseline/` 和该版本的运行记录；工具通过 `git subtree` 从 `main` 同步，避免复制维护。
- 发布快照用标签，不用分支：`v<YYYY.MM>-<kernel-version>`，例如 `v2026.11-6.6.118`、`v2026.11-6.18.21`。
- 跟进 Google 开源内核时，以 AOSP `android17-6.18` 的分支/标签为基线，更新后必须重跑 `tools/abi-gate.py` 和真机启动验证，再打新标签。
