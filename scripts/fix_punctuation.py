#!/usr/bin/env python3
"""将食养根本组4章的半角标点转为全角（仅正文，不动frontmatter和代码）。"""
import re

FILES = [
    '/workspace/output/饮食养生课/食养根本_一口饭的体内旅程.md',
    '/workspace/output/饮食养生课/食养根本_人为什么会吃错.md',
    '/workspace/output/饮食养生课/食养根本_你被这些常识骗了多少.md',
    '/workspace/output/饮食养生课/食养根本_养生变瘦长寿的饮食公约数.md',
]

# 半角→全角映射（仅中文语境标点）
# , → ，  : → ：  ; → ；  ! → ！  ? → ？
# 注意：不动英文引号、不动数字间冒号(时间)、不动frontmatter
def convert(text):
    # 拆出 frontmatter（--- ... ---）不动
    parts = text.split('---', 2)
    if len(parts) >= 3:
        # parts[0] 空, parts[1] frontmatter, parts[2] 正文
        head = '---' + parts[1] + '---'
        body = parts[2]
    else:
        head = ''
        body = text

    # 正文标点转换
    # 逗号：, → ，（但不动数字如 1,000）
    body = re.sub(r',(?!\d)', '，', body)
    body = re.sub(r'(?<=\d),', ',', body)  # 数字后逗号保留（保险）
    # 冒号：: → ：（但不动 URL、时间 12:30、frontmatter 已拆出）
    # 只转中文语境的冒号：前面是中文字或中文标点
    body = re.sub(r'(?<=[\u4e00-\u9fff）」』】])\s*:', '：', body)
    # 小标题行 传言一: → 传言一：
    body = re.sub(r'^(第[一二三四五六七八九十]+站|传言[一二三四五六]|公约数[一二三四五六]|[一二三四五六七八九十]+[、.])\s*:', r'\1：', body, flags=re.MULTILINE)
    # 分号 ; → ；
    body = re.sub(r';', '；', body)
    # 感叹号 ! → ！（不动英文!）
    body = re.sub(r'(?<=[\u4e00-\u9fff])!', '！', body)
    # 问号 ? → ？
    body = re.sub(r'(?<=[\u4e00-\u9fff])\?', '？', body)

    return head + body

for path in FILES:
    with open(path, 'r', encoding='utf-8') as f:
        original = f.read()
    new = convert(original)
    if new != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)
        # 统计变化
        old_comma = original.count(',')
        new_comma = new.count(',')
        old_colon = original.count(':')
        new_colon = new.count(':')
        print(f'{path.split("/")[-1]}: 逗号 {old_comma}→{new_comma}, 冒号 {old_colon}→{new_colon}')
    else:
        print(f'{path.split("/")[-1]}: 无变化')
