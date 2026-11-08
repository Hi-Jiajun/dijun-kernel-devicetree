# ABI 回归门

- 模块 210 个；内核导出 2823；模块间导出 482
- 内核符号 CRC 不符：**0** 条
- 无法解析导入的模块：**1**
  - rust_binder.ko 缺 60：RUST_BINDER_LAYOUT, _RINvNtCs3o2tGsuHyou_4core9panicking13assert_failedjjEB4_, _RNvMNtCsdfZWD8DztAw_6kernel5errorNtB2_5Error10from_errno, _RNvMNtCsdfZWD8DztAw_6kernel7id_poolNtB2_14ReallocRequest7realloc, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff11genlmsg_put, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff3new

**判定：FAIL**
