# +0.1 mm 工件X误差与单轴X导纳实验

本实验保持原P_SAFE不变。从P_SAFE下降到后退低点时，平滑加入工件坐标系
`+0.1 mm` X误差，并把该误差保持到P_EDGE_IN和P8。实时控制器只允许工件
X方向产生导纳修正，另外五个方向不开放。

默认限制：X修正最大 `±0.3 mm`、速度最大 `0.5 mm/s`；27 N持续30 ms停止、
30 N或1.25 Nm立即停止、六维力话题超过50 ms未更新立即停止。修正到边界且
横向力仍大于2 N持续0.5 s也会停止。

## 运行顺序

1. 一个终端运行 `~/assembly.sh force-driver`。
2. 可选：另一个终端运行 `~/assembly.sh plot`。
3. 先运行 `~/assembly.sh x-admit-shadow`，沿工件X轻推，确认日志中的
   `F_workobject X` 正负方向。SHADOW不运动。
4. 用 `~/assembly.sh guard-safe` 回到同一CSV中的P_SAFE。
5. 清空工作区、握住急停，然后运行 `~/assembly.sh x-admit-run`。
6. 完整输入 `ARM_X_ERROR_ADMIT` 才会进入实时控制。

如果SHADOW发现外力方向与机械臂应顺从的方向相反，只修改
`force_to_motion_sign` 为 `-1.0`，不要同时修改传感器六轴符号。每次只改一个
符号，并重新做SHADOW。

本程序不是随机实验。误差固定为+0.1 mm，便于无导纳/有导纳重复对照。首次
实机必须使用假件或允许损坏的样件；软件停止不是安全认证功能。
