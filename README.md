# 算法可视化调试器

Windows 桌面应用：Python / PySide6 界面、OpenCV 绘图、g++ 编译、GDB/MI 真实调试 C++17。

## 启动

当前机器的依赖已经安装，双击 **`run.bat`** 即可打开桌面程序。

首次安装或重新创建环境时，在项目目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\run.bat
```

已验证环境为 Windows、Python 3.9.13，以及带 Python 支持的 MinGW g++ / GDB。默认查找 `C:\mingw64\bin`，再查找 PATH。

## 使用

1. 载入示例，或粘贴代码并选择“完整程序 / 语句片段”。
2. 点击开始；在“实际编译源码”中按 F10 单步，或点击行号左侧设置断点。
3. 右侧选择数组 / 矩阵，再选择索引变量并绑定。图形中显示变量名、下标和值。
4. 使用历史条回看，或导出 PNG。F5 继续执行到断点；停止会结束当前程序。

支持数值与字符串、原生数组、`std::array`、`std::vector` 和二维矩阵。高亮行是**下一条待执行语句**，图形来自当前真实调试状态。

详细操作与限制见 [使用说明](docs/usage.md)，架构见 [架构说明](docs/architecture.md)，验证记录见 [验收记录](docs/validation.md)。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m tests.capture_demo
```

第二条命令运行真实示例并生成 `artifacts/` 下的窗口截图与完整图形，截图不纳入 Git。
