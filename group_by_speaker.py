
"""按 speaker 分组对话文件。

遍历 `dialogue/` 目录下的所有 `.json` 文件，根据条目中的 `speaker` 字段将条目分到 `speaker/` 下的子目录
每个源文件会在对应分组目录下生成同名的 JSON 文件。
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_GROUPS = {  "旅行者",   "派蒙",     "纳西妲",   "安柏",     "砂糖", 
                    "芭芭拉",   "凯亚",     "丽莎",     "罗莎莉亚", "诺艾尔", 
                    "菲谢尔",   "班尼特",   "迪卢克",   "琴",       "温迪", 
                    "可莉",     "钟离",     "刻晴",     "凝光",     "七七", 
                    "迪奥娜",   "莫娜",     "行秋",     "重云",     "雷泽",
                    "早柚",     "八重神子", "神里绫华", "神里绫人", "久岐忍", 
                    "鹿野院平藏","宵宫",    "烟绯",     "云堇",     "夜兰", 
                    "荒泷一斗", "五郎",     "珊瑚宫心海","多莉",    "提纳里", 
                    "柯莱",     "赛诺",     "坎蒂丝",   "莱依拉",   "辛焱", 
                    "托马",     "米卡",     "卡维",     "绮良良",   "瑶瑶", 
                    "阿贝多",   "菲米尼",   "夏洛蒂",   "优菈",     "林尼", 
                    "枫原万叶", "卡齐娜",   "胡桃",     "那维莱特", "迪希雅", 
                    "艾尔海森", "达达利亚", "魈",       "甘雨",     "白术",
                    "克洛琳德", "阿蕾奇诺", "梦见月瑞希", "蓝砚",   "莱欧斯利", 
                    "希格雯",   "嘉明",     "夏沃蕾",   "瓦雷莎",   "北斗", 
                    "闲云",     "妮露",     "希诺宁",   "奈芙尔",   "娜维娅", 
                    "爱诺",     "爱可菲",   "九条裟罗", "琳妮特",   "千织", 
                    "珐露珊",   "雷电将军", "基尼奇",   "菲林斯",   "芙宁娜", 
                    "塔利雅",   "申鹤",     "丝柯克",   "香菱",     "伊安珊", 
                    "艾梅莉埃", "玛薇卡",   "赛索斯",   "茜特菈莉", "伊涅芙", 
                    "伊法",     "欧洛伦",   "菈乌玛",   "玛拉妮",   "恰斯卡", 
                    "流浪者",   "埃洛伊"
                  }
DEFAULT_TOP_N = 5


def normalize_speaker_name(speaker: Any) -> str | None:
    if speaker is None:
        return None
    s = str(speaker).strip()
    if not s:
        return None
    # 去掉左右引号、括号等
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    if s.startswith("《") and s.endswith("》"):
        s = s[1:-1].strip()
    return s


def sanitize_filename(name: str) -> str:
    # 移除或替换文件系统不安全字符
    bad = '/\\:*?"<>|'
    out = ''.join(c for c in name if c not in bad).strip()
    # 防止过长或空名
    if not out:
        return "unknown"
    return out[:200]


def find_entries(data: Any) -> List[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
        return [data]
    return []


def get_speaker(item: Any) -> Any:
    if not isinstance(item, dict):
        return None
    for key in ("speaker", "角色", "actor", "speaker_id", "sid", "role", "speakerId"):
        if key in item:
            return item[key]
    for v in item.values():
        if isinstance(v, dict):
            for key in ("speaker", "actor"):
                if key in v:
                    return v[key]
    return None


def normalize_group(speaker: Any, groups: set) -> str:
    if speaker is None:
        return "other"
    s = str(speaker).strip()
    if s in groups:
        return s
    if s.isdigit():
        return s if s in groups else "other"
    return "other"


def merge_write_json(out_file: Path, items: List[Any]) -> None:
    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = [existing]
        except Exception:
            existing = []
        merged = existing + items
    else:
        merged = items
    out_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="按 speaker 分组 dialogue JSON 文件")
    parser.add_argument("--dialogue-dir", type=Path, default=Path(__file__).parent / "dialogue")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent / "speaker")
    parser.add_argument("--groups", type=str, default=",".join(sorted(DEFAULT_GROUPS)),
                        help="以逗号分隔的分组名，默认: 仓库内 DEFAULT_GROUPS 的值")
    args = parser.parse_args()

    groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    # 生成安全化后的 groups 名称集合用于目录判断
    sanitized_groups = {sanitize_filename(g) for g in groups}
    dialogue_dir = args.dialogue_dir
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = defaultdict(int)

    if not dialogue_dir.exists() or not dialogue_dir.is_dir():
        print(f"dialogue 目录不存在: {dialogue_dir}")
        return

    files = sorted(dialogue_dir.glob("*.json"))
    if not files:
        print(f"在 {dialogue_dir} 中未找到任何 .json 文件")
        return

    # 缓冲所有要写入的输出文件内容，避免对同一文件多次打开并追加，防止重复
    out_buffers: Dict[Path, List[Any]] = defaultdict(list)

    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"跳过文件 {f.name}，读取失败: {e}")
            continue

        entries = find_entries(raw)

        # 直接按说话人导出：若说话人（经 sanitize 后）在 sanitized_groups 中则生成该人名文件夹，
        # 否则统一归入 other
        for item in entries:
            sp_raw = get_speaker(item)
            sp = normalize_speaker_name(sp_raw)
            san_sp = sanitize_filename(sp) if sp is not None else None
            if san_sp and san_sp in sanitized_groups:
                grp = san_sp
            else:
                grp = "other"
            grp_dir = out_dir / grp
            grp_dir.mkdir(parents=True, exist_ok=True)
            out_file = grp_dir / f.name
            out_buffers[out_file].append(item)
            summary[grp] += 1

    # 将缓冲区的内容一次性写入对应文件（覆盖现有文件），避免重复追加
    for out_file, items in out_buffers.items():
        try:
            out_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"写入文件 {out_file} 失败: {e}")

    print("分组完成，统计如下:")
    total = 0
    for k, v in sorted(summary.items(), key=lambda x: x[0]):
        print(f"  {k}: {v}")
        total += v
    print(f"  total: {total}")


if __name__ == "__main__":
    main()
