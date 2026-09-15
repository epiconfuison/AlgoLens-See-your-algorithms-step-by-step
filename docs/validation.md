# 验证记录

验证环境：Windows、Python 3.9.13、PySide6 6.8.3、OpenCV 4.11.0、MinGW GCC 14.2.0、GDB 16.2。

## 自动化覆盖

| 子系统 | 已覆盖场景 |
| --- | --- |
| 编译 | 完整程序、片段包装、真实 g++ 编译、错误行号 |
| MI 协议 | 嵌套元组、重复结果、转义、UTF-8 八进制字符串、停止事件 |
| 调试器 | 真实断点、逐过程、函数进入 / 跳出、递归、同名变量作用域退出 |
| 数据 | 原生一维 / 二维数组、vector、二维 vector、std::array、vector<bool>、空容器、负数、字符串、字符、布尔、中文变量名 |
| 分页 | 450 元素容器、200 元素上限、尾页、批量读取命令数量上限、不等长矩阵 |
| 输入与异常 | 文件标准输入、独立输出、全局观察、不存在变量、真实 SIGSEGV |
| 快照 | 按变量身份与元素索引比较、保留最近 500 条 |
| 桌面流程 | 包装源码行号、断点、索引绑定、历史回看、导出、自动播放停在断点、分页不新增历史、重启清空历史 |
| 清理 | 编译失败恢复、死循环停止、GDB 进程退出 |

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试使用真实编译器 / 调试器；Qt 交互测试使用离屏窗口，不替换调试状态为模拟数据。

本次完整验证结果：**19 项测试通过**。除图形检查外，环境自检也验证了 Qt 控件创建、OpenCV 绘图和 GDB/MI 通信。

## 图形检查

运行 `.\.venv\Scripts\python.exe -m tests.capture_demo`，使用真实冒泡排序和二维动态规划代码，在断点处单步后抓取桌面布局及完整画布：

- `artifacts/bubble_sort-window.png`、`artifacts/bubble_sort-canvas.png`
- `artifacts/matrix_dp-window.png`、`artifacts/matrix_dp-canvas.png`

人工检查截图中的中文字体、代码行号、变量标签、索引位置、变化高亮和矩阵排列。离屏环境需要显式加载系统字体，已加入微软雅黑与 Consolas 的加载处理。截图和运行产物不纳入 Git。

本次验证以此机器的工具链为准；不同 Windows DPI、不同 MinGW 版本及其他 Python 版本未作全面兼容性测试。当前运行步骤和功能边界见 `usage.md`。
