#!/usr/bin/env python3
"""
自定义选股脚本 — 建仓选股策略
================================
逻辑：
1. 获取今日各行业板块涨跌幅排名
2. 对比昨日排名，找到"新晋热门板块"（昨日不在前列、今日新晋）
3. 从热点板块中筛选个股：
   - 当日涨幅 3% ~ 5%
   - 量比 > 1.5
   - 总市值 50亿 ~ 300亿
4. 输出结果供 AI 进一步分析可持续性

用法：python3 stock_picker.py [--top-n 10] [--save-daily]
"""

import akshare as ak
import pandas as pd
import json
import os
import sys
import argparse
from datetime import datetime, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "../data/stock_picker")
os.makedirs(CACHE_DIR, exist_ok=True)

TODAY = date.today().strftime("%Y-%m-%d")
YESTERDAY_CACHE_FILE = os.path.join(CACHE_DIR, "last_boards.json")
TODAY_CACHE_FILE = os.path.join(CACHE_DIR, f"boards_{TODAY}.json")

# ============================================================
# PART 1: 获取行业板块今日行情
# ============================================================

def get_industry_boards():
    """获取全部行业板块行情（东方财富分类）"""
    print("[1/4] 获取行业板块数据...", file=sys.stderr)
    df = ak.stock_board_industry_name_em()
    # 重命名列方便处理
    df = df.rename(columns={
        "板块名称": "name",
        "板块代码": "code",
        "涨跌幅": "pct_chg",       # 涨跌幅(%)
        "涨跌股数": "up_count",
        "跌股数": "down_count",
        "上涨家数": "up_count2",
        "下跌家数": "down_count2",
        "领涨股": "leader",
        "领涨股涨跌幅": "leader_pct",
    })
    # 确保关键列存在
    cols = [c for c in ["name", "code", "pct_chg", "leader"] if c not in df.columns]
    # 如果没有标准列名，尝试按顺序索引
    if cols:
        print(f"⚠️ 列名不匹配，可用列: {list(df.columns)}", file=sys.stderr)
    return df


def get_concept_boards():
    """获取概念板块行情"""
    print("   获取概念板块数据...", file=sys.stderr)
    df = ak.stock_board_concept_name_em()
    return df.rename(columns={
        "板块名称": "name",
        "板块代码": "code",
        "涨跌幅": "pct_chg",
    })


# ============================================================
# PART 2: 识别新晋热门板块
# ============================================================

def identify_new_hot_boards(today_df, top_n=15):
    """
    识别新晋热门板块：
    1. 今天涨幅前top_n的板块
    2. 对比昨日缓存，找出今天新出现的
    """
    # 按涨跌幅排序取前top_n
    today_top = today_df.sort_values("pct_chg", ascending=False).head(top_n).copy()
    today_top["rank_today"] = range(1, len(today_top) + 1)

    # 读取昨日缓存
    hot_today_names = set(today_top["name"].tolist())
    yesterday_hot = set()
    yesterday_raw = {}

    if os.path.exists(YESTERDAY_CACHE_FILE):
        with open(YESTERDAY_CACHE_FILE, "r") as f:
            yesterday_raw = json.load(f)
        yesterday_hot = set(yesterday_raw.get("hot_names", []))

    # 新晋热门 = 今天在top_n，昨天不在
    new_hot_names = hot_today_names - yesterday_hot
    new_hot = today_top[today_top["name"].isin(new_hot_names)]

    # 连续热门 = 两天都在前列
    sustained_hot = today_top[today_top["name"].isin(yesterday_hot)]

    # 排名上升的板块
    rising = []
    if yesterday_raw.get("rankings"):
        yesterday_ranks = yesterday_raw["rankings"]
        for _, row in today_top.iterrows():
            name = row["name"]
            if name in yesterday_ranks:
                old_rank = yesterday_ranks[name]
                new_rank = row["rank_today"]
                if new_rank < old_rank:
                    rising.append({
                        "name": name,
                        "old_rank": old_rank,
                        "new_rank": new_rank,
                        "rank_up": old_rank - new_rank
                    })

    return {
        "today_top": today_top.to_dict("records"),
        "new_hot": new_hot.to_dict("records"),
        "sustained_hot": sustained_hot.to_dict("records"),
        "rising": rising,
    }


# ============================================================
# PART 3: 缓存今日数据供明日对比
# ============================================================

def save_today_cache(today_df, top_n=15):
    """保存今日排名供明日识别新晋热门"""
    top = today_df.sort_values("pct_chg", ascending=False).head(top_n)
    rankings = {}
    for i, (_, row) in enumerate(top.iterrows(), 1):
        rankings[row["name"]] = i

    cache = {
        "date": TODAY,
        "hot_names": top["name"].tolist(),
        "rankings": rankings,
    }
    with open(YESTERDAY_CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"   已保存缓存 → {YESTERDAY_CACHE_FILE}", file=sys.stderr)


# ============================================================
# PART 4: 从特定板块中筛选优质个股
# ============================================================

def screen_stocks_in_board(board_name, min_pct=3.0, max_pct=5.0, min_vol_ratio=1.5, min_mcap=50e8, max_mcap=300e8):
    """
    筛选板块内符合条件的个股
    - 涨幅 3% ~ 5%
    - 量比 > 1.5
    - 总市值 50亿 ~ 300亿
    """
    try:
        print(f"   筛选板块: {board_name}", file=sys.stderr)
        df = ak.stock_board_industry_cons_em(symbol=board_name)
    except Exception as e:
        print(f"   ⚠️  获取板块'{board_name}'成分股失败: {e}", file=sys.stderr)
        return []

    # 尝试识别列
    print(f"     原始列: {list(df.columns)}", file=sys.stderr)

    # 建立列名映射（东方财富接口列名可能变化）
    col_map = {}
    for col in df.columns:
        col_lower = col.strip().lower()
        if "代码" in col or "code" in col_lower:
            col_map["code"] = col
        elif "名称" in col or "name" in col_lower:
            col_map["name"] = col
        elif "涨跌幅" in col or "涨幅" in col or "pct" in col_lower:
            col_map["pct_chg"] = col
        elif "量比" in col or "volume" in col_lower and "ratio" in col_lower:
            col_map["vol_ratio"] = col
        elif "总市值" in col or "mcap" in col_lower or "market" in col_lower:
            col_map["mcap"] = col
        elif "现价" in col or "price" in col_lower:
            col_map["price"] = col

    print(f"     列映射: {col_map}", file=sys.stderr)

    required = ["code", "name", "pct_chg"]
    missing = [r for r in required if r not in col_map]
    if missing:
        print(f"   ⚠️  缺少必要列 {missing}，跳过板块 '{board_name}'", file=sys.stderr)
        print(f"     可用列: {list(df.columns)}", file=sys.stderr)
        # 尝试按位置索引
        if len(df.columns) >= 4:
            # 常见东方财富顺序：代码,名称,现价,涨跌幅,...
            print(f"     尝试按位置索引（前5列）", file=sys.stderr)
            for i, col in enumerate(df.columns[:5]):
                print(f"       列{i}: {col} → sample: {df[col].iloc[0] if len(df) > 0 else 'N/A'}", file=sys.stderr)
        return []

    # 筛选
    try:
        df_screened = df.copy()

        # 转换数值列
        if col_map.get("pct_chg"):
            df_screened["pct_chg_num"] = pd.to_numeric(df_screened[col_map["pct_chg"]], errors="coerce")
        if col_map.get("vol_ratio"):
            df_screened["vol_ratio_num"] = pd.to_numeric(df_screened[col_map["vol_ratio"]], errors="coerce")
        if col_map.get("mcap"):
            df_screened["mcap_num"] = pd.to_numeric(df_screened[col_map["mcap"]], errors="coerce")

        cond = True
        cond_str_parts = []

        if "pct_chg_num" in df_screened.columns:
            cond &= (df_screened["pct_chg_num"] >= min_pct) & (df_screened["pct_chg_num"] <= max_pct)
            cond_str_parts.append(f"涨幅 {min_pct}%~{max_pct}%")

        if "vol_ratio_num" in df_screened.columns:
            cond &= (df_screened["vol_ratio_num"] > min_vol_ratio)
            cond_str_parts.append(f"量比 > {min_vol_ratio}")

        if "mcap_num" in df_screened.columns:
             mcap_min_yi = min_mcap / 1e8
             mcap_max_yi = max_mcap / 1e8
             cond &= (df_screened["mcap_num"] >= min_mcap) & (df_screened["mcap_num"] <= max_mcap)
             cond_str_parts.append(f"市值 {mcap_min_yi:.0f}亿~{mcap_max_yi:.0f}亿")

        result_df = df_screened[cond].copy()
        print(f"     筛选条件: {' | '.join(cond_str_parts)}", file=sys.stderr)
        print(f"     筛选结果: {len(result_df)} 只", file=sys.stderr)

        results = []
        for _, row in result_df.iterrows():
            item = {
                "股票代码": row[col_map["code"]],
                "股票名称": row[col_map["name"]],
                "现价": row[col_map.get("price", "")] if col_map.get("price") and pd.notna(row.get(col_map.get("price", ""))) else "",
                "涨幅%": round(row.get("pct_chg_num", 0), 2) if pd.notna(row.get("pct_chg_num")) else "",
                "量比": round(row.get("vol_ratio_num", 0), 2) if col_map.get("vol_ratio") and pd.notna(row.get("vol_ratio_num")) else "",
                "总市值(亿)": round(row.get("mcap_num", 0) / 1e8, 2) if col_map.get("mcap") and pd.notna(row.get("mcap_num")) else "",
            }
            results.append(item)

        return results

    except Exception as e:
        print(f"   ⚠️  筛选出错: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return []


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="建仓选股策略工具")
    parser.add_argument("--top-n", type=int, default=10, help="取今日涨幅前N个板块（默认10）")
    parser.add_argument("--save", action="store_true", help="保存今日数据到缓存（供明日对比新晋板块）")
    parser.add_argument("--board", type=str, default=None, help="指定板块名称直接筛选，跳过新晋识别")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    # ---------- 获取板块数据 ----------
    try:
        industry_df = get_industry_boards()
    except Exception as e:
        print(json.dumps({"error": f"获取板块数据失败: {e}"}, ensure_ascii=False))
        sys.exit(1)

    if args.board:
        # 指定板块模式
        stocks = screen_stocks_in_board(args.board)
        if args.json:
            print(json.dumps({"board": args.board, "stocks": stocks}, ensure_ascii=False, indent=2))
        else:
            print(f"\n📍 板块: {args.board}")
            if stocks:
                print(f"{'代码':<10} {'名称':<10} {'现价':<8} {'涨幅%':<8} {'量比':<8} {'市值(亿)':<10}")
                print("-" * 55)
                for s in stocks:
                    vals = [str(s.get(k, "")) for k in ["股票代码", "股票名称", "现价", "涨幅%", "量比", "总市值(亿)"]]
                    print(f"{vals[0]:<10} {vals[1]:<10} {vals[2]:<8} {vals[3]:<8} {vals[4]:<8} {vals[5]:<10}")
            else:
                print("  无符合条件的个股")
        return

    # ---------- 识别新晋热门板块 ----------
    hot_info = identify_new_hot_boards(industry_df, top_n=args.top_n)

    # 保存今日数据
    if args.save:
        save_today_cache(industry_df, top_n=args.top_n)

    # ---------- 输出 ----------
    output = {
        "date": TODAY,
        "today_top": [],
        "new_hot": [],
        "rising": [],
        "stocks_by_board": {},
    }

    if not args.json:
        print(f"\n{'='*60}")
        print(f"📊 建仓选股报告 — {TODAY}")
        print(f"{'='*60}")
        print(f"\n【今日涨幅TOP{args.top_n}板块】")
        print(f"{'排名':<6} {'板块名称':<16} {'涨幅%':<8} {'领涨股':<12}")
        print("-" * 50)
        for i, b in enumerate(hot_info["today_top"], 1):
            name = b.get("name", "")
            pct = round(b.get("pct_chg", 0), 2) if b.get("pct_chg") else 0
            leader = b.get("leader", "")
            marker = ""
            if b["name"] in [h["name"] for h in hot_info["new_hot"]]:
                marker = "🆕"
            elif b["name"] in [h["name"] for h in hot_info["sustained_hot"]]:
                marker = "🔥"
            print(f"{i:<6} {name:<16} {pct:<8.2f} {leader:<12} {marker}")
        output["today_top"] = hot_info["today_top"]

        if hot_info["new_hot"]:
            print(f"\n【🆕 新晋热门板块（昨日不在前列）】")
            print(f"{'排名':<6} {'板块名称':<16} {'涨幅%':<8}")
            print("-" * 35)
            for b in hot_info["new_hot"]:
                rank = b.get("rank_today", "?")
                name = b.get("name", "")
                pct = round(b.get("pct_chg", 0), 2) if b.get("pct_chg") else 0
                print(f"{rank:<6} {name:<16} {pct:<8.2f}")
            output["new_hot"] = hot_info["new_hot"]

        if hot_info["rising"]:
            print(f"\n【⬆️ 排名上升板块】")
            for r in hot_info["rising"]:
                print(f"  {r['name']}: 第{r['old_rank']}→第{r['new_rank']} (+{r['rank_up']}位)")
            output["rising"] = hot_info["rising"]

        if hot_info["sustained_hot"]:
            print(f"\n【🔥 连续热门板块（两天前列）】")
            for b in hot_info["sustained_hot"]:
                rank = b.get("rank_today", "?")
                name = b.get("name", "")
                pct = round(b.get("pct_chg", 0), 2) if b.get("pct_chg") else 0
                print(f"  #{rank} {name} ({pct:+.2f}%)")

    # ---------- 找候选板块进行个股筛选 ----------
    candidate_boards = []

    # 优先：新晋热门板块 + 排名上升板块
    candidate_names = set()
    for b in hot_info["new_hot"]:
        candidate_names.add(b["name"])
    for r in hot_info["rising"]:
        candidate_names.add(r["name"])

    # 如果没有新晋/上升的，就用TOP3
    if not candidate_names:
        for b in hot_info["today_top"][:3]:
            candidate_names.add(b["name"])

    # 最多处理5个板块（避免耗时过长）
    candidate_names = list(candidate_names)[:5]

    if candidate_names:
        if not args.json:
            print(f"\n{'='*60}")
            print(f"【个股筛选】候选板块: {', '.join(candidate_names)}")
            print(f"条件: 涨幅3%~5% | 量比>1.5 | 市值50亿~300亿")
            print(f"{'='*60}")

        for board_name in candidate_names:
            stocks = screen_stocks_in_board(board_name)
            output["stocks_by_board"][board_name] = stocks

            if not args.json:
                if stocks:
                    print(f"\n📍 {board_name} — {len(stocks)} 只符合条件:")
                    print(f"{'代码':<10} {'名称':<10} {'现价':<8} {'涨幅%':<8} {'量比':<8} {'市值(亿)':<10}")
                    print("-" * 55)
                    for s in stocks:
                        vals = [str(s.get(k, "")) for k in ["股票代码", "股票名称", "现价", "涨幅%", "量比", "总市值(亿)"]]
                        print(f"{vals[0]:<10} {vals[1]:<10} {vals[2]:<8} {vals[3]:<8} {vals[4]:<8} {vals[5]:<10}")
                else:
                    print(f"\n📍 {board_name} — 无符合条件的个股")

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()