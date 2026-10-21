# -*- coding: utf-8 -*-
import io

# 1) 后端：地图默认主题改为"plain"（无瓦片制图底图）
p = r"D:\AAA-Study\work\github\carto-agent\backend\app\services\map_service.py"
src = io.open(p, encoding="utf-8").read()
old = '''                "theme": "standard",'''
new = '''                "theme": "plain",   # 默认无瓦片制图底图（矢量制图）'''
assert old in src
src = src.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(src)
print("map_service.py default theme = plain")

# 2) 前端：初始主题改为 plain
p = r"D:\AAA-Study\work\github\carto-agent\frontend\src\js\map.js"
src = io.open(p, encoding="utf-8").read()
old2 = '''        this.currentTheme = "standard";     // 当前底图主题'''
new2 = '''        this.currentTheme = "plain";        // 当前底图主题（默认无瓦片制图底图）'''
assert old2 in src
src = src.replace(old2, new2, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(src)
print("map.js default theme = plain")

# 3) index.html：底图下拉默认选中"无底图（矢量）"
p = r"D:\AAA-Study\work\github\carto-agent\frontend\src\index.html"
src = io.open(p, encoding="utf-8").read()
old3 = '''                    <option value="standard">标准</option>'''
new3 = '''                    <option value="plain" selected>无底图（矢量）</option>
                    <option value="standard">标准</option>'''
assert old3 in src
src = src.replace(old3, new3, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(src)
print("index.html default select = plain")
