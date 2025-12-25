## 执行结果

执行：
```bash
chmod +x check_led.sh
sudo bash ./check_led.sh
```

```bash
=========================================
RK3568 LED 检查工具
=========================================

[1] 可用的 LED 列表：
总用量 0
lrwxrwxrwx 1 root root 0 12月 25 09:41 mmc0:: -> ../../devices/platform/fe310000.sdhci/leds/mmc0::
lrwxrwxrwx 1 root root 0 12月 25 09:41 work -> ../../devices/platform/leds/leds/work

[2] LED 详细信息：

--- mmc0:: ---
  当前亮度: 0
  最大亮度: 255
  触发模式: none rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock mmc1 [mmc0] timer rfkill0 rfkill1 rfkill2
  路径: /sys/class/leds/mmc0::/

--- work ---
  当前亮度: 0
  最大亮度: 255
  触发模式: [none] rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock mmc1 mmc0 timer rfkill0 rfkill1 rfkill2
  路径: /sys/class/leds/work/

[3] 推荐配置：

✓ 推荐使用: work
  配置路径: /sys/class/leds/work/brightness

[4] 是否测试 LED 控制？(y/n)
y

请输入要测试的 LED 名称（如 sys_led）：
work
开始测试 work ...
  原始亮度: 0
  [1/3] 关闭 LED...
  [2/3] 打开 LED...
  [3/3] 闪烁测试（5次）...
  恢复原始状态: 0

✓ 测试完成！

=========================================
检查完成
=========================================
```

**LED 设备ID：LED9:work**
