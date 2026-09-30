const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Header,
  HeadingLevel,
  ImageRun,
  LevelFormat,
  PageBreak,
  PageNumber,
  Paragraph,
  Packer,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} = require("docx");

const OUTPUT = path.resolve("analysis_output/AR5手机主板装配六维导纳控制算法说明.docx");
const FLOWCHART_PART1 = path.resolve("analysis_output/ar5_admittance_algorithm_flowchart_part1.png");
const FLOWCHART_PART2 = path.resolve("analysis_output/ar5_admittance_algorithm_flowchart_part2.png");
const FONT = "Noto Sans CJK SC";
const MONO = "DejaVu Sans Mono";
const BLUE = "1976D2";
const DARK = "173247";
const MUTED = "526675";
const LIGHT_BLUE = "EAF3FA";
const LIGHT_ORANGE = "FFF2E5";
const LIGHT_GREEN = "EAF6EE";
const CONTENT_WIDTH = 9900;

const borders = {
  top: { style: BorderStyle.SINGLE, size: 4, color: "CCD8E0" },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: "CCD8E0" },
  left: { style: BorderStyle.SINGLE, size: 4, color: "CCD8E0" },
  right: { style: BorderStyle.SINGLE, size: 4, color: "CCD8E0" },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 3, color: "DCE5EB" },
  insideVertical: { style: BorderStyle.SINGLE, size: 3, color: "DCE5EB" },
};

const cellMargins = { top: 110, bottom: 110, left: 140, right: 140 };

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function p(text, options = {}) {
  return new Paragraph({
    alignment: options.alignment || AlignmentType.JUSTIFIED,
    spacing: { after: options.after ?? 140, line: options.line ?? 360 },
    children: [
      new TextRun({
        text,
        font: options.font || FONT,
        size: options.size || 23,
        bold: options.bold || false,
        color: options.color || "263746",
      }),
    ],
  });
}

function richParagraph(runs, options = {}) {
  return new Paragraph({
    alignment: options.alignment || AlignmentType.JUSTIFIED,
    spacing: { after: options.after ?? 140, line: options.line ?? 360 },
    children: runs.map((run) => new TextRun({ font: FONT, size: 23, color: "263746", ...run })),
  });
}

function heading(text, level = 1) {
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    children: [new TextRun(text)],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullet-list", level },
    spacing: { after: 90, line: 330 },
    children: [new TextRun({ text, font: FONT, size: 22, color: "263746" })],
  });
}

function numbered(text) {
  return new Paragraph({
    numbering: { reference: "numbered-list", level: 0 },
    spacing: { after: 100, line: 340 },
    children: [new TextRun({ text, font: FONT, size: 22, color: "263746" })],
  });
}

function formula(text) {
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: [CONTENT_WIDTH],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_WIDTH, type: WidthType.DXA },
            borders,
            shading: { fill: "F2F7FA", type: ShadingType.CLEAR },
            margins: { top: 180, bottom: 180, left: 220, right: 220 },
            verticalAlign: VerticalAlign.CENTER,
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text, font: "Cambria Math", size: 30, color: DARK })],
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

function infoBox(title, body, fill = LIGHT_BLUE) {
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: [CONTENT_WIDTH],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_WIDTH, type: WidthType.DXA },
            borders,
            shading: { fill, type: ShadingType.CLEAR },
            margins: { top: 160, bottom: 160, left: 200, right: 200 },
            children: [
              new Paragraph({
                spacing: { after: 80 },
                children: [new TextRun({ text: title, font: FONT, size: 24, bold: true, color: DARK })],
              }),
              new Paragraph({
                spacing: { after: 0, line: 340 },
                children: [new TextRun({ text: body, font: FONT, size: 21, color: "344B5A" })],
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

function makeTable(headers, rows, widths) {
  const makeCell = (text, width, header = false) => new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    margins: cellMargins,
    shading: { fill: header ? "DCEAF5" : "FFFFFF", type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER,
    children: [
      new Paragraph({
        alignment: header ? AlignmentType.CENTER : AlignmentType.LEFT,
        spacing: { after: 0, line: 300 },
        children: [new TextRun({ text, font: FONT, size: header ? 21 : 20, bold: header, color: DARK })],
      }),
    ],
  });
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ children: headers.map((value, i) => makeCell(value, widths[i], true)) }),
      ...rows.map((row) => new TableRow({ children: row.map((value, i) => makeCell(value, widths[i], false)) })),
    ],
  });
}

const children = [];

children.push(
  new Paragraph({ spacing: { before: 900, after: 260 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "AR5手机主板装配", font: FONT, size: 42, bold: true, color: DARK })] }),
  new Paragraph({ spacing: { after: 260 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "阶段感知六维导纳控制算法说明", font: FONT, size: 52, bold: true, color: BLUE })] }),
  new Paragraph({ spacing: { after: 520 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "数学模型 · 工程控制流程 · 安全机制 · 技术改进", font: FONT, size: 25, color: MUTED })] }),
  infoBox(
    "核心结论",
    "当前控制器是一套位置型六维笛卡尔外环导纳系统：以成功示教轨迹为移动中心，只将超出阶段正常力包络的异常六维扳手转换为有限位姿修正；严重接触时暂停名义轨迹，但保持导纳卸力与回中。",
    LIGHT_BLUE,
  ),
  p("控制平台：AR5机器人、ROS 2、xCoreSDK实时笛卡尔位置接口、M3815六维力传感器。控制循环周期为1 ms，力传感器记录频率约500 Hz。", { alignment: AlignmentType.CENTER, after: 400, color: MUTED }),
  p("2026年9月", { alignment: AlignmentType.CENTER, color: MUTED }),
  pageBreak(),
);

children.push(
  heading("一、当前使用的六维导纳模型", 1),
  p("当前采用位置型外环导纳控制。机器人底层控制器继续执行笛卡尔位置跟踪，上层导纳控制器根据异常接触力计算附加的六维位姿偏移。该方法适用于底层不开放关节力矩控制、但能够高频接收笛卡尔位置指令的工业机器人。"),
  formula("M ẍ + D ẋ + K x = S W_excess"),
  p("状态向量为 x = [Δx, Δy, Δz, Δrx, Δry, Δrz]ᵀ，前三项表示平移修正，后三项表示旋转向量修正。输入W_excess不是传感器测得的全部力，而是超出正常装配力包络的异常部分。"),
  makeTable(
    ["参数", "当前对角参数", "物理作用"],
    [
      ["虚拟质量 M", "[5, 5, 5, 0.05, 0.05, 0.05]", "限制响应加速度，决定外力变化后的瞬态响应速度"],
      ["虚拟阻尼 D", "[150, 150, 140, 2, 2, 1.5]", "耗散振荡能量，控制卸力和回中过程的平稳性"],
      ["虚拟刚度 K", "[800, 5000, 3000, 15, 15, 10]", "定义稳态柔顺量，并将偏移持续拉回示教中心"],
    ],
    [1900, 3900, 4100],
  ),
  heading("1.1 模型的基本物理逻辑", 2),
  bullet("异常接触力推动虚拟质量产生位姿偏移，机器人因此沿卸力方向移动。"),
  bullet("虚拟阻尼抑制来回振荡，避免末端在接触面附近反复摆动。"),
  bullet("虚拟弹簧始终连接到成功示教轨迹；异常力消失后，修正量自动衰减并回到零。"),
  bullet("所有方向共用同一套六维求解器，通过参数、符号和限幅进行工程约束。"),
  infoBox(
    "一句话理解",
    "导纳控制不是让机器人随外力自由漂移，而是让机器人围绕成功示教轨迹，在受限范围内进行可恢复的柔顺偏移。",
    LIGHT_GREEN,
  ),
  pageBreak(),
);

children.push(
  heading("二、正常装配力与异常接触力的区分", 1),
  p("主板装配在压平和最终就位阶段本来就会产生较大的正常接触力。如果直接把全部六维力输入导纳控制器，正常压合力也会推动机器人偏离轨迹。因此当前算法先根据工艺阶段剥离正常载荷，再对剩余异常部分进行响应。"),
  p("算法利用三次成功装配数据，在归一化轨迹进度s上建立每个力/力矩分量的中心cᵢ(s)和半宽hᵢ(s)。"),
  formula("lᵢ(s) = min(cᵢ(s) − hᵢ(s), 0)    uᵢ(s) = max(cᵢ(s) + hᵢ(s), 0)"),
  formula("eᵢ = wᵢ − lᵢ  (wᵢ < lᵢ)；0  (lᵢ ≤ wᵢ ≤ uᵢ)；wᵢ − uᵢ  (wᵢ > uᵢ)"),
  bullet("包络内的力属于正常工艺载荷，不驱动导纳修正。"),
  bullet("包络外的残差组成W_excess，代表需要处理的异常接触。"),
  bullet("包络向零扩展，保证尚未接触时的零力不会被误判为反向异常力。"),
  makeTable(
    ["信号处理", "当前设置", "目的"],
    [
      ["低通滤波", "10 Hz", "抑制传感器高频噪声"],
      ["力死区", "0.5 N", "忽略小幅随机波动"],
      ["力矩死区", "0.03 N·m", "忽略小幅力矩噪声"],
      ["异常持续判定", "0.10 s", "避免单点尖峰立即改变控制状态"],
    ],
    [2400, 2200, 5300],
  ),
  pageBreak(),
);

children.push(
  heading("三、1 kHz离散求解与位姿输出", 1),
  p("控制循环周期Δt为1 ms。每个周期执行固定顺序的向量运算，避免在实时回调中进行复杂规划或阻塞操作。"),
  numbered("读取最新六维力和机器人状态，检查数据新鲜度与有限性。"),
  numbered("将传感器坐标下的力和力矩变换到当前工件/Base参考方向。"),
  numbered("插值当前阶段正常力包络，计算W_excess。"),
  numbered("执行10 Hz低通、死区和异常持续判定。"),
  numbered("根据M、D、K计算加速度，并依次进行加速度、速度和位姿积分。"),
  numbered("应用非对称位姿限幅，防止修正继续推向危险方向。"),
  formula("aₖ = sat[M⁻¹(Wₖ − Dvₖ − Kxₖ)]"),
  formula("vₖ₊₁ = sat(vₖ + aₖΔt)    xₖ₊₁ = sat(xₖ + vₖ₊₁Δt)"),
  heading("3.1 最终位姿合成", 2),
  formula("p_cmd = p_nominal + Δp"),
  formula("R_cmd = Exp([Δr]×) R_nominal"),
  p("姿态修正使用旋转向量指数映射左乘名义姿态，而不是直接相加欧拉角。这样能够保持旋转组合的几何含义，减少欧拉角顺序和奇异性带来的问题。当前g_wobj_0与Base重合，因此六维修正方向实际等同机器人基座轴。"),
  pageBreak(),
);

children.push(
  heading("四、当前算法完整流程", 1),
  p("下图给出从启动检查、六维力处理、导纳求解、轨迹调节到安全退出的完整闭环。严重接触时暂停的是名义轨迹时间，导纳控制仍继续运行，以寻找卸力方向并回到示教中心。"),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 80 },
    children: [
      new ImageRun({
        type: "png",
        data: fs.readFileSync(FLOWCHART_PART1),
        transformation: { width: 610, height: 716 },
        altText: {
          title: "AR5阶段感知六维导纳控制流程上半部分",
          description: "从启动参数校验到阶段正常力包络和导纳分支的流程图",
          name: "admittance-flowchart-part1",
        },
      }),
    ],
  }),
  pageBreak(),
  heading("流程图（下）：导纳求解、轨迹恢复与安全退出", 2),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 80 },
    children: [
      new ImageRun({
        type: "png",
        data: fs.readFileSync(FLOWCHART_PART2),
        transformation: { width: 610, height: 664 },
        altText: {
          title: "AR5阶段感知六维导纳控制流程下半部分",
          description: "从扰动预置和导纳求解到轨迹恢复、位姿输出、成功就位及安全退出的流程图",
          name: "admittance-flowchart-part2",
        },
      }),
    ],
  }),
  pageBreak(),
);

children.push(
  heading("五、轨迹调节器与安全保护", 1),
  heading("5.1 异常接触轨迹调节", 2),
  p("小幅异常力只通过导纳修正，不停止名义轨迹。当任一开放平移轴异常力大于2 N，或异常力矩大于0.10 N·m，并持续0.10 s时，轨迹速率以4 s⁻¹的斜率降至零。此时导纳仍继续计算和输出，使机械臂能够卸力。"),
  p("只有所有异常分量降到1 N和0.05 N·m以内、六维修正进入恢复邻域并持续0.20 s，轨迹才恢复到正常速率。单次恢复超过8 s则判定无法自行恢复并退出。"),
  heading("5.2 多层看门狗", 2),
  makeTable(
    ["保护层", "当前规则"],
    [
      ["传感器", "数据年龄不超过50 ms；拒绝非有限值和明显异常原始量级"],
      ["硬载荷", "合力达到35 N或合力矩达到1.50 N·m立即停止"],
      ["路径与初态", "要求位于P_SAFE附近、关节软限位有效，并检查中心轨迹和最大扰动轨迹"],
      ["TCP跟踪", "预置阶段0.75 mm/0.25°；运行阶段5 mm/3°"],
      ["命令接受", "期望位姿与tcpPose_c偏差超限并持续50周期时停止"],
      ["修正饱和", "某轴到达限位且异常力仍向限位外推动，持续0.80 s时停止"],
      ["任务完成", "进度达到85%后，Z向力达到24 N并持续0.05 s，判定seat=REACHED"],
    ],
    [2500, 7400],
  ),
  infoBox("统一退出动作", "任何不可恢复异常最终执行：停止运动 → 断开实时网络 → 机器人下电 → 切回manual模式。", LIGHT_ORANGE),
  pageBreak(),
);

children.push(
  heading("六、已实现的主要技术改进", 1),
  heading("6.1 从全量力输入改为异常残差输入", 2),
  p("早期方案会把正常压合力也输入导纳。当前方案通过阶段正常力包络提取W_excess，使控制器只对异常接触做修正。"),
  heading("6.2 从单轴控制扩展为统一六维控制", 2),
  p("X、Y、Z、Rx、Ry、Rz使用同一套导纳状态、滤波、限幅和日志结构。单轴与复合误差测试只修改trajectory_error，不针对某次测试切换控制算法。"),
  heading("6.3 从直接停机改为可恢复轨迹调节", 2),
  p("严重接触先平滑暂停轨迹，导纳继续卸力；异常清除且修正回到中心附近后自动恢复，从“只能停止”扩展为“能够卸力和继续”。"),
  heading("6.4 增加双阈值和时间滞回", 2),
  p("触发与清除采用不同阈值，并分别要求持续0.10 s和0.20 s，降低临界状态下的频繁启停。"),
  heading("6.5 增加执行链诊断", 2),
  p("同时比较期望位姿、控制器接收位姿tcpPose_c和实测位姿tcpPose_m，从而区分算法输出异常、控制器未接受命令和机器人实际跟踪失败。"),
  heading("6.6 采用非对称限幅", 2),
  p("不同方向根据装配风险设置不同边界。例如Z方向负向继续顶入的风险更高，因此负向仅允许0.2 mm，而正向卸力允许1.5 mm。"),
  pageBreak(),
);

children.push(
  heading("七、当前局限与后续工作", 1),
  bullet("Sensor到Tool的旋转和平移外参目前仍为零假设，需要通过专用标定完成真实外参辨识。"),
  bullet("当前工件坐标系与Base重合；现有轨迹和力包络均以该方向为基础。"),
  bullet("正常力包络目前基于三次成功装配，样本量不足以代表量产波动。"),
  bullet("当前CSV主要记录原始六维力，尚未同步保存phase、progress、trajectory_rate、W_excess、六维修正和seat状态。"),
  heading("7.1 节拍优化", 2),
  p("后续提速不能只提高统一速度参数。应采用阶段化速度规划：自由空间快速运动，接触、插入和压合阶段保持较低速度；同时使用jerk受限轨迹、段间平滑融合以及根据异常力和力增长率连续调整的速度系数。"),
  heading("7.2 速度相关接触模型", 2),
  p("速度提高后惯性力、摩擦力和冲击峰值都会改变。正常力模型需要从W(s)扩展为W(s,v,a)，并重新评估导纳参数、滤波截止频率、传感器时延和修正速度是否仍能跟上名义轨迹。"),
  heading("7.3 系统化实验验证", 2),
  p("建立X、Rx、Ry正负方向、多档幅值和六轴组合误差矩阵；每组重复多次，统计成功率、峰值合力、峰值力矩、P95载荷、恢复时间、装配节拍及Cp/Cpk等工程指标。"),
  heading("7.4 自动故障恢复与数据闭环", 2),
  p("对卡边、修正饱和、未就位和执行器未接受命令进行分类，并设计有限次数的后退、重新对准和再次插入策略。同时同步保存控制状态和视频时间戳，自动生成关键窗口曲线与实验报告。"),
  infoBox(
    "后续工作的工程目标",
    "在峰值载荷和装配成功率不恶化的前提下缩短节拍，并把控制性能从单次演示提升为可重复、可统计、可追溯的量产能力。",
    LIGHT_GREEN,
  ),
);

const doc = new Document({
  creator: "AstraFlow",
  title: "AR5手机主板装配阶段感知六维导纳控制算法说明",
  description: "六维导纳模型、算法流程、安全保护、技术改进与后续工作",
  styles: {
    default: {
      document: { run: { font: FONT, size: 23, color: "263746" }, paragraph: { spacing: { after: 140, line: 360 } } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 34, bold: true, color: DARK },
        paragraph: { spacing: { before: 300, after: 180 }, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE, space: 8 } } },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 27, bold: true, color: BLUE },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 520, hanging: 260 } } } }],
      },
      {
        reference: "numbered-list",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 300 } } } }],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 900, right: 1000, bottom: 900, left: 1000, header: 420, footer: 420 },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              border: { bottom: { style: BorderStyle.SINGLE, size: 5, color: "B8C8D3", space: 6 } },
              children: [new TextRun({ text: "AR5主板装配六维导纳控制", font: FONT, size: 18, color: MUTED })],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ text: "第 ", font: FONT, size: 18, color: MUTED }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: MUTED }), new TextRun({ text: " 页", font: FONT, size: 18, color: MUTED })],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUTPUT, buffer);
  console.log(OUTPUT);
});
