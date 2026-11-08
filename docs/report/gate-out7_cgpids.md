# ABI 回归门

- 模块 586 个；内核导出 9090；模块间导出 3044
- 内核符号 CRC 不符：**7027** 条
  - ir_spi.ko:__spi_register_driver 期望 0xd4afda11 实际 0x8caa7d97
  - ir_spi.ko:noop_llseek 期望 0x58fb8ca8 实际 0x693d46c2
  - ir_spi.ko:_dev_warn 期望 0xa7b4ce54 实际 0xa96f5ac0
  - ir_spi.ko:_dev_err 期望 0x3b00ee3e 实际 0x35db7aaa
  - ir_spi.ko:spi_sync 期望 0xd637ba6d 实际 0x65605f7c
  - mi_fp.ko:cdev_init 期望 0x9089cd36 实际 0x5c134dbe
  - mi_fp.ko:cdev_add 期望 0xe0da49dc 实际 0xce577834
  - mi_fp.ko:device_create 期望 0xbeca914b 实际 0x3e671641
  - mi_fp.ko:wakeup_source_register 期望 0xed7053fc 实际 0x94e3215f
  - mi_fp.ko:device_destroy 期望 0x26824530 实际 0xe93a839d
- 无法解析导入的模块：**0**

**判定：FAIL**
