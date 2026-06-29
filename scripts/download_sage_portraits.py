#!/usr/bin/env python3
"""下载圣贤堂 16 张卡通头像到本地缓存。

从 demos/saints_hall.html 解析每位圣人的 name + portraitPrompt，
调用文生图 API 下载图片，保存为 demos/images/{no}_{pinyin}.jpg。
下载后同步复制到 site/demos/images/ 供部署使用。
"""
import re
import json
import time
import hashlib
import urllib.request
import urllib.parse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "demos" / "saints_hall.html"
IMG_DIR = ROOT / "demos" / "images"
SITE_IMG_DIR = ROOT / "site" / "demos" / "images"
API = "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image"

# 简易拼音映射（避免引入 pypinyin 依赖）
PINYIN = {
    "孔子": "kongzi", "颜回": "yanhui", "曾参": "zengshen", "孔伋": "kongji",
    "孟子": "mengzi", "伯夷": "boyi", "伊尹": "yiyin", "柳下惠": "liuxiahui",
    "孙武": "sunwu", "王羲之": "wangxizhi", "张仲景": "zhangzhongjing",
    "吴道子": "wudaozi", "杜甫": "dufu", "陆羽": "luyu", "司马迁": "simaqian",
    "赵公明": "zhaogongming", "比干": "bigan", "范蠡": "fanli", "关羽": "guanyu",
    "李诡祖": "liguizu", "姚少司": "yaoshaosi", "沈万三": "shenwansan",
    "刘海蟾": "liuhai", "张福德": "fudezhengshen", "端木赐": "duamugong",
}


def extract_sages():
    """从 HTML 提取 SAGES 数组里的 name + no + portraitPrompt。"""
    text = HTML_PATH.read_text(encoding="utf-8")
    # 匹配每个对象块：从 { name: 开始到下一个 { name: 之前的 }
    pattern = re.compile(
        r"name:\s*'([^']+)',\s*courtesyName:[^,]+,\s*title:[^,]+,\s*"
        r"faction:[^,]+,\s*subFaction:[^,]+,\s*"
        r"dynasty:[^,]+,\s*state:[^,]+,\s*lifespan:[^,]+,\s*no:\s*'([^']+)',\s*"
        r"portraitPrompt:\s*'([^']+)'",
        re.DOTALL
    )
    results = []
    for m in pattern.finditer(text):
        name, no, prompt = m.group(1), m.group(2), m.group(3)
        results.append({"name": name, "no": no, "prompt": prompt})
    return results


def download_one(sage):
    """下载单张图片，返回 (sage, success, msg)。"""
    no = sage["no"]
    pinyin = PINYIN.get(sage["name"], sage["name"])
    filename = f"{no}_{pinyin}.jpg"
    dest = IMG_DIR / filename
    if dest.exists() and dest.stat().st_size > 10000:
        return sage, True, f"已存在跳过 ({dest.stat().st_size} bytes)"

    url = API + "?prompt=" + urllib.parse.quote(sage["prompt"]) + "&image_size=portrait_4_3"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return sage, True, f"下载成功 ({len(data)} bytes)"
    except Exception as e:
        return sage, False, f"下载失败: {e}"


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    SITE_IMG_DIR.mkdir(parents=True, exist_ok=True)

    sages = extract_sages()
    print(f"提取到 {len(sages)} 位圣人头像待下载")
    for s in sages:
        print(f"  - {s['no']} {s['name']}")

    print("\n开始串行下载（每张间隔 2 秒，避免 API 限流返回相同图）...")
    success, fail = 0, 0
    seen_md5 = {}  # md5 -> filename，检测重复
    for i, sage in enumerate(sages):
        if i > 0:
            time.sleep(2)
        sage_data, ok, msg = download_one(sage)
        status = "✓" if ok else "✗"
        if ok:
            no = sage["no"]
            pinyin = PINYIN.get(sage["name"], sage["name"])
            filename = f"{no}_{pinyin}.jpg"
            dest = IMG_DIR / filename
            md5 = hashlib.md5(dest.read_bytes()).hexdigest()
            if md5 in seen_md5:
                print(f"  ✗ {no} {sage['name']}: 与 {seen_md5[md5]} 重复（md5={md5[:8]}），API 限流")
                dest.unlink()
                fail += 1
                # 重试一次
                time.sleep(5)
                sage_data, ok, msg = download_one(sage)
                if ok:
                    md5 = hashlib.md5(dest.read_bytes()).hexdigest()
                    if md5 in seen_md5:
                        print(f"    重试仍重复，跳过")
                        dest.unlink()
                        fail += 1
                        continue
                    seen_md5[md5] = filename
                    print(f"  ✓ {no} {sage['name']}: 重试成功 ({dest.stat().st_size} bytes, md5={md5[:8]})")
                    success += 1
                else:
                    print(f"    重试失败: {msg}")
                    fail += 1
                continue
            seen_md5[md5] = filename
            print(f"  {status} {no} {sage['name']}: {msg} (md5={md5[:8]})")
            success += 1
        else:
            print(f"  {status} {sage['no']} {sage['name']}: {msg}")
            fail += 1

    print(f"\n下载完成: 成功 {success}，失败 {fail}")

    # 同步复制到 site/demos/images/
    print("\n同步到 site/demos/images/...")
    for img in IMG_DIR.glob("*.jpg"):
        shutil.copy2(img, SITE_IMG_DIR / img.name)
    print(f"已复制 {len(list(IMG_DIR.glob('*.jpg')))} 张到 site/")

    # 生成 manifest 供 HTML 引用
    manifest = {}
    for s in sages:
        pinyin = PINYIN.get(s["name"], s["name"])
        manifest[s["name"] + "|" + s["no"]] = f"images/{s['no']}_{pinyin}.jpg"
    manifest_path = IMG_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(manifest_path, SITE_IMG_DIR / "manifest.json")
    print(f"\nmanifest 已生成: {manifest_path}")
    print("HTML 可改用本地路径 images/{no}_{pinyin}.jpg 引用，不再远程加载")


if __name__ == "__main__":
    main()
