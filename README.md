# 宣讲会日历

一个完全离线的 Windows 桌面小软件，用于把群聊中的宣讲会消息解析成滚动日历备忘。

## 下载

从 [Releases](https://github.com/zxlpdr/seminar-calendar/releases/latest) 下载最新的 `宣讲会日历.exe`，双击即可运行，无需安装 Python。

## 主要功能

- 从今天开始自动显示连续 15 天，日期变化后自动向前滚动。
- 每次粘贴一场宣讲会消息，本地提取企业、日期、时间、地点、腾讯会议号和投递方式。
- “今晚”“明天”等相对日期按照点击“解析消息”当天计算。
- 解析结果先进入可编辑预览；企业、日期、开始时间或地点缺失时提示手工补充。
- 相同“企业 + 日期 + 开始时间”的记录会提示重复，可取消或仍然导入。
- 日历内的网页链接可直接点击，邮箱可打开默认邮件客户端。
- 支持编辑、删除、手工录入、全部记录和历史记录。
- 超出 15 天的未来记录仍会保存，进入日期范围后自动显示；过期记录永久保留在历史记录中。

## 使用方法

1. 双击下载的 `宣讲会日历.exe`。
2. 点击右上角“＋ 导入宣讲会”。
3. 在上方文本框粘贴一场宣讲会消息，点击“解析消息”。
4. 检查并按需修改识别结果，然后点击“确认导入”。
5. 在日历中点击企业名称可编辑该记录，点击蓝色下划线链接可打开网页。

软件数据保存在：

```text
%LOCALAPPDATA%\SeminarCalendar\seminars.db
```

因此移动或替换 EXE 不会丢失已经录入的数据。

## 从源码运行

本项目运行时只使用 Python 标准库，Python 3.10 或更高版本即可：

```powershell
python app.py
```

运行测试：

```powershell
python -m unittest discover -v
```

## 重新打包

先安装 PyInstaller，再执行：

```powershell
python -m pip install pyinstaller
.\build.ps1
```

## 许可证

[MIT License](LICENSE)

