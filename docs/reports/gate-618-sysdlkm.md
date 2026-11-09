# ABI 回归门

- 模块 210 个；内核导出 2823；模块间导出 482
- 内核符号 CRC 不符：**5362** 条
  - 6lowpan.ko:register_netdevice 期望 0xf6011eda 实际 0xfc9303ca
  - 6lowpan.ko:unregister_netdevice_queue 期望 0x15fc0dc5 实际 0xdf9f1bfe
  - 6lowpan.ko:addrconf_add_linklocal 期望 0xeb08e084 实际 0x8de0d9e6
  - 6lowpan.ko:skb_pull 期望 0x0efe08e4 实际 0xc6d89a82
  - 6lowpan.ko:pskb_expand_head 期望 0x2772acda 实际 0xf89bd468
  - 6lowpan.ko:skb_push 期望 0x0efe08e4 实际 0xc6d89a82
  - 6lowpan.ko:__pskb_pull_tail 期望 0x439f7f0a 实际 0x70638484
  - 6lowpan.ko:netdev_warn 期望 0xe492b2d4 实际 0xd764a590
  - 6lowpan.ko:__ndisc_fill_addr_option 期望 0x91348d22 实际 0xec40268d
  - 6lowpan.ko:addrconf_prefix_rcv_add_addr 期望 0x5b5d8b38 实际 0x8143bf3d
- 无法解析导入的模块：**1**
  - rust_binder.ko 缺 60：RUST_BINDER_LAYOUT, _RINvNtCs3o2tGsuHyou_4core9panicking13assert_failedjjEB4_, _RNvMNtCsdfZWD8DztAw_6kernel5errorNtB2_5Error10from_errno, _RNvMNtCsdfZWD8DztAw_6kernel7id_poolNtB2_14ReallocRequest7realloc, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff11genlmsg_put, _RNvMNtNtCsdfZWD8DztAw_6kernel3net7netlinkNtB2_13NetlinkSkBuff3new

**判定：FAIL**
