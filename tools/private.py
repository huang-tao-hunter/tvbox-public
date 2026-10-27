#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成私有自用 TVBox 配置（以 js.json 为底）

做四件事：
1. 剔除黑名单 / 本地资源缺失的站点（本地文件缺失会导致客户端整站加载异常）
2. 重新计算 spider 的 md5，避免换了 jar 忘改 md5
3. 可选探测远程接口存活（默认仅报告，加 --drop-dead 才剔除）
4. 输出紧凑格式的 my.json，可直接托管到 GitHub Pages / raw

用法：
  python tools/private.py
  python tools/private.py --drop Youtube,TGYunPanLocal
  python tools/private.py --check-http
  python tools/private.py --check-http --drop-dead
"""

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Windows 控制台默认 GBK，先切到 UTF-8 再输出 ✓/✗
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

根目录 = Path(__file__).resolve().parent.parent
默认输入 = 根目录 / "js.json"
默认输出 = 根目录 / "my.json"

# 永久剔除的站点 key，按需增删（也可以命令行 --drop 传入）
剔除列表 = {
    # "Youtube",          # 需要本地 socks5 代理
    # "TGYunPanLocal",    # 需要本地 token / 代理
}


class CompactJSONEncoder(json.JSONEncoder):
    """与仓库其它 tools 脚本一致的紧凑输出：站点对象一行一个"""

    def iterencode(self, o, _one_shot=False):
        def _compact_list(lst, indent_level):
            pad = "  " * indent_level
            if not lst or all(isinstance(i, (str, int, float, bool, type(None))) for i in lst):
                return json.dumps(lst, ensure_ascii=False)
            if all(isinstance(i, dict) for i in lst):
                return "[\n" + ",\n".join(
                    [pad + "  " + json.dumps(i, ensure_ascii=False, separators=(",", ": ")) for i in lst]
                ) + "\n" + pad + "]"
            return json.dumps(lst, ensure_ascii=False, indent=2)

        def _encode(obj, indent_level=0):
            pad = "  " * indent_level
            if isinstance(obj, dict):
                lines = [f'"{k}": {_encode(v, indent_level + 1)}' for k, v in obj.items()]
                return "{\n" + pad + "  " + (",\n" + pad + "  ").join(lines) + "\n" + pad + "}"
            if isinstance(obj, list):
                return _compact_list(obj, indent_level)
            return json.dumps(obj, ensure_ascii=False)

        return iter([_encode(o)])


def 计算md5(路径):
    md5 = hashlib.md5()
    with open(路径, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
    return md5.hexdigest()


def 解析相对路径(路径文本):
    if 路径文本.startswith("./"):
        return 根目录 / 路径文本[2:]
    return 根目录 / 路径文本


def 收集本地路径(值):
    """递归收集字符串里的 ./ 或 ../ 开头的本地路径（按 $ & ? 空格切分）"""
    found = []
    if isinstance(值, str):
        for token in 值.replace("$", " ").replace("&", " ").replace("?", " ").split():
            token = token.strip()
            if token.startswith("./") or token.startswith("../"):
                found.append(token)
    elif isinstance(值, dict):
        for v in 值.values():
            found.extend(收集本地路径(v))
    elif isinstance(值, list):
        for v in 值:
            found.extend(收集本地路径(v))
    return found


def 站点本地资源(站点):
    return (
        收集本地路径(站点.get("api"))
        + 收集本地路径(站点.get("ext"))
        + 收集本地路径(站点.get("jar"))
    )


def 检查站点(站点):
    """返回站点不可用的原因列表，空列表代表通过"""
    原因 = []
    if not 站点.get("api"):
        原因.append("缺少 api")
    for 路径文本 in 站点本地资源(站点):
        if not 解析相对路径(路径文本).exists():
            原因.append(f"本地文件缺失 {路径文本}")
    return 原因


def 探测(url, 超时=8):
    try:
        import requests

        resp = requests.get(
            url,
            headers={"User-Agent": "okhttp/3.12.0"},
            timeout=超时,
            stream=True,
        )
        code = resp.status_code
        resp.close()
        # CMS 接口不带参数常返回 400/404，只要不是 5xx / 连不上就认为存活
        return code < 500
    except Exception:
        return False


def 处理spider(spider):
    """把 spider 的 md5 更新为本地文件的实际值"""
    if not spider:
        return spider, ["配置缺少 spider 字段"]
    parts = spider.split(";")
    路径文本 = parts[0]
    if 路径文本.startswith("http://") or 路径文本.startswith("https://"):
        return spider, []
    文件 = 解析相对路径(路径文本)
    if not 文件.exists():
        return spider, [f"spider 文件不存在: {路径文本}"]
    return f"{路径文本};md5;{计算md5(文件)}", []


def main():
    parser = argparse.ArgumentParser(description="生成私有自用 TVBox 配置")
    parser.add_argument("--src", default=str(默认输入), help="输入配置，默认 js.json")
    parser.add_argument("--out", default=str(默认输出), help="输出配置，默认 my.json")
    parser.add_argument("--drop", default="", help="额外剔除的站点 key，逗号分隔")
    parser.add_argument("--check-http", action="store_true", help="探测远程 api/live 是否存活（仅报告）")
    parser.add_argument("--drop-dead", action="store_true", help="探测失败的远程源直接剔除")
    parser.add_argument("--workers", type=int, default=12, help="探测并发数")
    args = parser.parse_args()

    with open(args.src, "r", encoding="utf-8") as f:
        配置 = json.load(f)

    剔除 = set(剔除列表)
    剔除.update(k.strip() for k in args.drop.split(",") if k.strip())

    spider, spider问题 = 处理spider(配置.get("spider"))
    for 问题 in spider问题:
        print(f"✗ {问题}")

    保留, 丢弃 = [], []
    for 站点 in 配置.get("sites", []):
        key = 站点.get("key", "?")
        if key in 剔除:
            丢弃.append((key, "黑名单"))
            continue
        原因 = 检查站点(站点)
        if 原因:
            丢弃.append((key, "; ".join(原因)))
            continue
        保留.append(站点)

    # 远程接口探测
    if args.check_http:
        远程 = [s for s in 保留 if str(s.get("api", "")).startswith("http")]
        print(f"探测 {len(远程)} 个远程 api ...")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            结果 = list(pool.map(lambda s: (s, 探测(s["api"])), 远程))
        存活 = {id(s) for s, ok in 结果 if ok}
        if args.drop_dead:
            新保留 = []
            for 站点 in 保留:
                if str(站点.get("api", "")).startswith("http") and id(站点) not in 存活:
                    丢弃.append((站点.get("key", "?"), "远程接口无响应"))
                else:
                    新保留.append(站点)
            保留 = 新保留
        else:
            失效 = [s.get("key", "?") for s, ok in 结果 if not ok]
            if 失效:
                print(f"⚠ 远程接口无响应（未剔除，加 --drop-dead 可剔除）: {', '.join(失效)}")

    # 直播源本地文件校验
    直播 = []
    for live in 配置.get("lives", []):
        url = str(live.get("url", ""))
        if (url.startswith("./") or url.startswith("../")) and not 解析相对路径(url).exists():
            丢弃.append((f"live:{live.get('name', '?')}", f"本地文件缺失 {url}"))
            continue
        直播.append(live)

    # 去掉重复站点：完全相同直接丢弃，key 冲突则改名，避免客户端加载异常
    去重后, 已用key, 已见, 改名 = [], set(), set(), []
    for 站点 in 保留:
        指纹 = json.dumps(站点, ensure_ascii=False, sort_keys=True)
        if 指纹 in 已见:
            丢弃.append((站点.get("key", "?"), "重复站点"))
            continue
        已见.add(指纹)
        key = 站点.get("key", "?")
        if key in 已用key:
            序号 = 2
            while f"{key}__{序号}" in 已用key:
                序号 += 1
            站点 = dict(站点, key=f"{key}__{序号}")
            改名.append((key, 站点["key"]))
        已用key.add(站点["key"])
        去重后.append(站点)
    保留 = 去重后

    if not 保留:
        print("✗ 没有可用站点，检查输入配置")
        return 1

    输出 = dict(配置)
    输出["spider"] = spider
    输出["sites"] = 保留
    输出["lives"] = 直播

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(CompactJSONEncoder(ensure_ascii=False).encode(输出))
        f.write("\n")

    print(f"✓ 输出 {args.out}")
    print(f"  站点 {len(保留)}/{len(配置.get('sites', []))}，直播 {len(直播)}/{len(配置.get('lives', []))}")
    print(f"  spider {spider}")
    for key, 新key in 改名:
        print(f"  ⚠ key 冲突，{key} 已改名为 {新key}")
    if 丢弃:
        print(f"  剔除 {len(丢弃)} 项：")
        for key, 原因 in 丢弃:
            print(f"    - {key}: {原因}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
