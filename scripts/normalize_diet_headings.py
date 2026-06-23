#!/usr/bin/env python3
"""统一饮食养生课章节的七段标题编号格式。"""
import glob, re, os

# 目标格式：## 一、讲清楚 ... ## 七、结语
ORDER = ["讲清楚", "讲原理", "讲实验/案例", "讲核心方法", "讲权威依据", "讲实操落地", "结语"]
NUMS = ["一", "二", "三", "四", "五", "六", "七"]

def normalize(text):
    # 先把所有可能的现有编号格式剥掉，统一成裸标题，再重新编号
    # 匹配 ## 后面可选的「序号、」前缀，再接标题名
    for i, name in enumerate(ORDER):
        # 匹配 ## (任意序号、)? name  -> ## 序号、name
        # 序号可能是 一二三...或 1. 2. 等
        pattern = re.compile(r'^(## )+(?:[一二三四五六七八九0-9]+[、.．]? ?)?' + re.escape(name) + r'(?:[：:].*)?$', re.MULTILINE)
        replacement = f'## {NUMS[i]}、{name}'
        text = pattern.sub(lambda m: replacement, text)
    return text

changed = 0
for path in sorted(glob.glob('/workspace/output/饮食养生课/饮食课*.md')):
    with open(path, 'r', encoding='utf-8') as f:
        original = f.read()
    new = normalize(original)
    if new != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)
        changed += 1
        print(f'normalized: {os.path.basename(path)}')

print(f'\n共规范化 {changed} 个文件')
