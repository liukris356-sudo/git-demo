# XB7 无力控示教装配轨迹

当前候选采用p6的World/Base Y作为统一通道位置，从斜插终点到最终按压点全部使用：

```text
Y = 1.434873 mm
```

轨迹：

```text
P_SAFE -> P_PRE -> P_EDGE_NEAR -> P_VERY_NEAR
-> P_EDGE_IN_Y_P6 -> P_CLEARANCE_P3_Y_P6 -> P_PRESS_X491648_Y_P6_FINAL
```

完整文件：

```text
xb7_records/xb7_assembly_p6_y_aligned_final_gtool1_20260922.csv
```

关键点：

```text
P_EDGE_IN_Y_P6
  X=490.9754, Y=1.4349, Z=-2.6823 mm, J6=-0.7030 deg

P_CLEARANCE_P3_Y_P6
  X=490.9754, Y=1.4349, Z=-7.2810 mm, J6=-0.7030 deg

P_PRESS_X491648_Y_P6_FINAL
  X=491.6480, Y=1.4349, Z=-9.5555 mm, J6=-0.6547 deg
```

X/Z/Rx/Ry保留当前各阶段目标；Rz和其它关节由XB7运动学微调。完整七点路径已经通过控制器`checkPath`。

## 分阶段命令

```bash
./xb7_assembly.sh go-safe
./xb7_assembly.sh insert-test
./xb7_assembly.sh clearance-test
./xb7_assembly.sh press-test
```

- `insert-test`：到Y对齐后的斜插端点。
- `clearance-test`：保持Y=1.4349 mm到转平点。
- `press-test`：保持Y=1.4349 mm到最终点X=491.648 mm。
- `full-test`暂禁用，必须先逐段验证。

## 反向拔出

反向轨迹严格把当前七个正向点倒序，不生成新中间点：

```text
P_PRESS_X491648_Y_P6_FINAL -> P_CLEARANCE_P3_Y_P6
-> P_EDGE_IN_Y_P6 -> P_VERY_NEAR -> P_EDGE_NEAR -> P_PRE -> P_SAFE
```

```bash
./xb7_assembly.sh reverse-plan
./xb7_assembly.sh reverse-check
./xb7_assembly.sh reverse-release
./xb7_assembly.sh reverse-extract
./xb7_assembly.sh reverse-test
```

- `reverse-release`：从最终点慢速反向释放到斜插点，0.1 mm/s、0.1 deg/s。
- `reverse-extract`：从斜插点继续反向拔出到P_SAFE，0.2 mm/s、0.2 deg/s。
- `reverse-test`：完整七点直接倒序到P_SAFE，首次使用前应先分别验证前两段。
- 所有反向命令仍是位置控制，不是力控拔出；阻力上升或零件卡住时必须立即停止。

此前曾出现35610 Axis 5转矩故障。程序已将NRT加速度/加加速度设为20%/10%；任一阶段出现持续顶压、异响、抖动或故障，必须立即停止，不得反复重试。
