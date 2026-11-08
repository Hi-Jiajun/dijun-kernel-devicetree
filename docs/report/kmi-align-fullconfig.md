# GKI/KMI 对齐判定

原厂导出符号 9090，自编内核导出 9090，交集 9090。

## 1. KMI 契约
- KMI 符号表合计 2833 个；自编内核导出 2819 个（缺 14）
- 缺失示例：arc4_crypt, arc4_setkey, hci_alloc_dev_priv, hci_free_dev, hci_recv_frame, hci_register_dev, hci_unregister_dev, rfkill_alloc, rfkill_blocked, rfkill_destroy, rfkill_register, rfkill_resume_polling, rfkill_set_hw_state_reason, rfkill_unregister
- KMI 符号中 CRC 相同 2819，不同 0

## 2. CRC（MODVERSIONS）
- 交集 9090 个：相同 9090（100.0%），不同 0
- 原厂有、自编没有的导出符号 0 个

## 3. 原厂模块的符号需求
- 原厂模块互相导出的符号 2176 个
- 检查 .ko 201 个；有缺符号的 63 个
  - lib/modules/xr_isp.ko: 缺 24，例 get_hw_id_value, mdr_map, mdr_register_exception, mdr_register_module_ops, mdr_system_error, mdr_unregister_exception
  - lib/modules/xrse.ko: 缺 20，例 cdev_tevent_add_int, cdev_tevent_add_str, cdev_tevent_alloc, cdev_tevent_destroy, cdev_tevent_write, mdr_register_exception
  - lib/modules/xring_audio.ko: 缺 19，例 ap_ipc_send_sync, cdev_tevent_add_int, cdev_tevent_add_str, cdev_tevent_alloc, cdev_tevent_destroy, cdev_tevent_write
  - lib/modules/xring-hpc.ko: 缺 17，例 is_switch_on, mdr_map, mdr_register_exception, mdr_register_module_ops, mdr_system_error, mdr_unmap
  - lib/modules/shub_dfx.ko: 缺 15，例 ap_ipc_send_sync, dmd_client_record, dmd_register_client, dmd_unregister_client, mdr_register_exception, mdr_register_module_ops
  - lib/modules/xring-ade.ko: 缺 15，例 dpu_hw_dvfs_vote, dpu_wfd_event_register, dpu_wfd_event_unregister, dpu_wfd_sink_deinit, dpu_wfd_sink_get_cmdlist_addr, dpu_wfd_sink_get_cmdlist_config
  - lib/modules/mali_kbase.ko: 缺 12，例 mdr_register_exception, mdr_register_module_ops, mdr_system_error, mdr_unregister_exception, mdr_unregister_module_ops, noc_register_exception
  - lib/modules/hpc_xrp_task.ko: 缺 10，例 is_switch_on, mdr_map, mdr_register_exception, mdr_register_module_ops, mdr_system_error, mdr_unmap
  - lib/modules/wlan_drv_gen4m_eap_6639.ko: 缺 10，例 get_hw_id_value, mdr_register_exception, mdr_register_module_ops, mdr_system_error, mdr_unregister_exception, mdr_unregister_module_ops
  - lib/modules/xring_vdec.ko: 缺 10，例 mdr_register_exception, mdr_register_module_ops, mdr_system_error, mdr_unregister_exception, mdr_unregister_module_ops, media_dvs_is_low_temperature

## 4. KCFI 类型 id
- 模块与内核共有的 __kcfi_typeid_ 符号 65 个；值不同 0 个
