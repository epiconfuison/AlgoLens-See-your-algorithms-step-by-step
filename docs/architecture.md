# 架构

数据流：编辑源码 → compiler → GDB/MI → models 快照 → visualization → ui。

- compiler：包装语句片段、独立运行目录、异步调用编译器。
- debugger：MI 协议、进程生命周期、变量对象与停止事件。
- models：变量身份、类型、维度、值、可读状态和最多 500 条历史。
- visualization：OpenCV 画布，Qt 中文文字，分页、变化高亮和索引绑定。
- ui：编辑器、调试控制、历史、输入输出和图像导出。

界面仅在暂停状态读取变量；当前行是下一行待执行语句。历史回看不改变进程。
编译和调试在工作线程执行，Qt 控件只在主线程更新。程序输出重定向到运行目录文件，不混入 MI 协议。

## 实现接口

- `Compiler.build(text, stdin) -> Build`：实际源码、运行路径、可执行文件、诊断和成功状态；60 秒编译超时，可取消。
- `Engine.initialize(breakpoints)`、`execute(action)`：串行 MI 命令；执行返回 `Snapshot` 或退出事件。
- `Engine.snapshot(advance=False)`：刷新分页、观察项和断点后的状态，不推进快照序号。
- `Variable` 包含作用域身份、名称、类型、值、形状、最多 200 个单元格、页偏移和状态；`Snapshot` 包含源码位置、调用栈、停止原因和信号详情。
- `SessionWorker`：一个 QThread 与有序命令队列负责整个会话；独立取消线程终止本会话进程树，Qt 主线程不等待执行完成。
- `render(snapshot, selected, previous, bindings, mode) -> QImage`：OpenCV 绘制几何与颜色，Qt 在图像中绘制 Unicode 标签。

数组页面通过 MI `-var-list-children` 批量读取。libstdc++ pretty-printer 不可用时，使用已验证 GCC 布局适配器尝试读取普通 vector / array；读取失败给出状态，不猜测数据。观察项仅允许变量或限定名，避免通过观察触发函数调用。

## 提交节点

1. 工程框架与约定。
2. 环境检查、隔离依赖与启动入口。
3. 源码包装与编译。
4. GDB 调试与变量读取。
5. OpenCV 绘制与变量绑定。
6. 桌面调试交互。
7. 示例、集成测试与使用文档。
