## 番茄钟对我的意义：

比起专注，番茄钟对于我来说更重要的是打断我。打断我无意义的浪费时间。

经常会因为一个bug卡一天，正常番茄钟那个温柔的声音我根本就没听到，或者听到了也装作没听到。

碰到那种bug卡住，往往会在即将打算停下时得到解法，或者在停下后突如想到一个似乎可行的解法。与其一直想一直想，有时候一个break可能就能解决困扰的问题。虽然但是，能够不碰到这种bug就尽量不碰到。

## 正常的番茄钟太温柔了对我：

我上面提到我经常听到番茄钟结束当作没听到，然后一坐一个早上。可能都在做一件事情，或者什么都没做，我并不是很喜欢那样子。



## V1.0 - released:

[https://github.com/MrXnneHang/Yasumi-Clock/releases/tag/Yasumi-v1.0](https://github.com/MrXnneHang/Yasumi-Clock/releases/tag/Yasumi-v1.0)

![v1.0](https://fastly.jsdelivr.net/gh/MrXnneHang/blog_img/BlogHosting/img/24/07/202407150648261.jpeg)

![v1.0yasumi](https://fastly.jsdelivr.net/gh/MrXnneHang/blog_img/BlogHosting/img/24/07/202407150648226.jpeg)



## V1.1 - 更新介绍:

### 添加功能:

- 切换状态时在两种动画间切换（休息和工作）。

### bug-fix:

- 倒计时结束时窗口置顶
- Loading Window置顶

### 效果预览：

休息动画:

![休息动画](https://fastly.jsdelivr.net/gh/MrXnneHang/blog_img/BlogHosting/img/24/07/202407151537830.jpeg)

工作动画:

![工作动画](https://fastly.jsdelivr.net/gh/MrXnneHang/blog_img/BlogHosting/img/24/07/202407151538988.jpeg)


## V1.2 - linux-release. 2025.1.27

- [x] linux 环境下的 pyqt5 和 opencv-python 的兼容性问题,改用 opencv-headless
- [x] 将涉及 win32 api 的部分代码改用通用性代码写。
- [x] 指定了 requirements 的版本。
- [x] 删除了 v1.3 中一些花里胡哨的功能，keep it simple.
- [x] 修复 desktop 工作目录和程序目录不一致时无法正常运行的问题。

时隔大半年，我对麻衣桑依然抱持着相同的热情，所以这里麻衣依然是我的 yasumi 图。<br>

## v1.2.2 - 2025.1.28 - bug-fix

在尝试用可执行程序运行时，当时间结束后，程序会闪退。<br>

原因是程序实际上有三个 window:<br>

- Loading window: 加载时你看到的窗口，加载完成后会关闭。
- Main window: 主窗口，用户操作的窗口。
- Yasumi Window: 时间结束后弹出的麻衣桑本质上也是一个窗口。ESC可以退出。

其中每个都需要用到src下的资源文件,也就都需要更改资源文件的路径。需要absolute path。但是我并未修改。已修复。<br>

**值得注意的是：在util.py中引入了一个get_absolute_path函数，用于获取资源文件的绝对路径。这是因为运行源码和运行可执行程序时，工作目录不同，执行目录也不同。**

## v1.2.3 - 2025.1.29 - bug-find

- 以前做了一个布局按键，之前是为了确定方框的位置。但是这次似乎在点击后会发生闪退，原因未确定。
- 布局需要重新排布。 

## v1.4 - 强制休息模式与UI优化

- https://github.com/MrXnneHang/Yasumi-Clock/pull/1
- feat: 添加强制休息模式和UI优化
- feat: 恢复原先没有缩放版本的样式
- fix: 启用无控制台模式确保强制休息功能正常工作

## 感谢所有贡献者

<a href="https://github.com/GreenHatHG">
 <img src="./fig/conrtibuters/GreenHatHG.png" width="100" height="100" alt="GreenHatHG">
</a>