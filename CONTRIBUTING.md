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
