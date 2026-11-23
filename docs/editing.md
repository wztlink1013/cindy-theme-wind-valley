# 微调与发布

这套主题是纯数据：`themes/*.json`（颜色与排版）+ `assets/`（图片与字体）。
改完用仓库自带的 `tools/build.py` 打包即可，不需要 Cindy 的源码。

## 0. 准备

```bash
git clone https://github.com/wztlink1013/cindy-theme-wind-valley.git
cd cindy-theme-wind-valley
```

只需要 Python 3（Windows 用 `py -3` 代替 `python3`）。

## 1. 改颜色

编辑 `themes/light.json` 或 `themes/dark.json` 的 `colors`。**只改值，别删 key**：缺的 key 会回退 Cindy 默认色。

两条硬规则（都踩过）：

| token 类型 | 怎么查 | 该填什么 |
| --- | --- | --- |
| 名字以 `-hsl` 结尾，或 `tools/token-formats.json` 里标为 `hsl` | `tools/token-formats.json` | HSL 分量 `45 40% 92%`，或 `var(--别的-hsl)` |
| 其余 token | 同上标为 `color` | 完整颜色 `#F6F0DD` / `rgba(…)` / `var(--别的token)` |

把 hex 塞进 `hsl(var(--titlebar-border))` 这类位置，声明会整条失效，边框回退成 `currentColor`
——就是之前标题栏那条黑线。`tools/build.py` 会对这种写法报警告。

改色时建议顺手确认对比度：正文对背景 ≥ 4.5:1，次要文字 ≥ 4.5:1（这套现在是亮 10.6 / 暗 12.5）。

## 2. 换墙纸 / 图标 / 字体

| 想换什么 | 做法 | 约束 |
| --- | --- | --- |
| 墙纸 | 覆盖 `assets/wallpaper-light.png` / `wallpaper-dark.png`（文件名不变） | PNG/JPEG/WebP，≤20 MB，≤40 MP |
| 品牌图标 | 覆盖 `assets/icon.png` | 显示区 50×50，透明边会被裁掉 |
| 品牌字标 | 覆盖 `assets/logo.png`（亮）/ `logo-dark.png`（暗） | 显示区 110×37.5 |
| 字体 | 覆盖 `assets/serif-lora.ttf` / `mono-jetbrains.ttf`，或把 `appearance.*Font.resource` 换成 `family` | TTF/OTF，≤10 MB；换字体请带许可文件 |

新增资源（比如再加一张墙纸）时：放好文件，并在 `cindy.json` 的 `resources` 里加一条
`{ "id": "bg-alt", "kind": "image", "path": "assets/xxx.png" }`，再在 `appearance.wallpaper.resource`
里引用 `asset:bg-alt`。

## 3. 改排版 / 密度

在 `themes/*.json` 的 `appearance` 里：

- `wallpaper.visibility` 0–1、`blur` 0–20px、`motion` `static`/`dynamic`
- `reading.bodyLineHeight` 1.2–2.4、`maxWidth` 320–1400
- `contentStyle.messageGap` 0–48、`messagePadding`/`messageRadius` 0–32
- `density` 0.75–1.25、`motion` 0–2（系统“减少动效”优先级更高）

## 4. 打包

```bash
python3 tools/build.py           # 校验 + 产出 dist/wind-valley.cindy
python3 tools/build.py --check   # 只校验
```

脚本会检查：清单结构、主题文档字段、每个颜色 token 的格式、`asset:` 引用是否指向已声明且类型正确的资源、
图片尺寸/体积上限、品牌图是否存在。有 error 就不产出包。

## 5. 本机试用

双击 `dist/wind-valley.cindy` → Cindy 弹出导入 → 设置 → 外观 → 主题 → 选「風之谷」。

ID 没变的话是**原地更新**，已选中的主题会继续生效；想同时保留旧版，就把 `id` 和 `family` 都改成新的 UUID，
这样会变成并存的两套。

## 6. 发布新版本

```bash
# 1) 更新版本说明（可选：把 preview/*.png 截图也换掉）
git add -A
git commit -m "feat(theme): warm the light surface"

# 2) 打 tag 并发 Release（install 脚本永远指向 latest）
git tag v1.1.0 && git push && git push --tags
gh release create v1.1.0 dist/wind-valley.cindy \
  --title "v1.1.0 — 風之谷 · Wind Valley" \
  --notes "亮色纸面更暖一点；墙纸对比度略降。"
```

## 7. 其它设备更新

每台设备重跑一次安装命令即可（`releases/latest` 会自动指向新版本）：

```powershell
irm https://raw.githubusercontent.com/wztlink1013/cindy-theme-wind-valley/main/install.ps1 | iex
```

同 ID 覆盖，不会出现重复条目，选中状态保持。

## 8. 常见坑

- **别改 `id`/`family`**：改了就不是更新，而是另起一套。
- **`*-hsl` 不能填 hex**：会静默失效（黑线/颜色发黑）。
- **显式设置优先**：你在 Cindy 里手动选过墙纸或字体，主题同名字段就不生效；到 设置 → 外观 里
  「恢复默认」才会跟随主题。
- **字体许可**：换字体时把对应的 OFL 文本放进 `licenses/`，README 的许可段也要跟着改。
- **图片体积**：墙纸 PNG 很容易 >20 MB，转 8-bit RGB、适度压缩，或改存 JPEG/WebP。
