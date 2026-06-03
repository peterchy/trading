#!/usr/bin/env bash
# ========================================
# 交易专家 - 新服务器一键安装脚本
# 用法: bash setup.sh
# ========================================

set -e

echo "=========================================="
echo "  📦 交易专家 · 环境初始化"
echo "=========================================="
echo ""

# 1. Python依赖安装
echo "[1/3] 安装 Python 依赖..."
pip install akshare requests beautifulsoup4 lxml httpx feedparser pandas --break-system-packages -q 2>/dev/null || \
pip install akshare requests beautifulsoup4 lxml httpx feedparser pandas -q
echo "  ✅ Python 依赖安装完成"

# 2. 检查关键技能文件
echo ""
echo "[2/3] 技能文件校验..."
SKILLS=(
  "finance-news-pro"
  "akshare-stock"
  "stock-analyst"
  "a-share-short-decision"
  "a-stock-data"
  "a-stock-fundamental-screening"
  "a-stock-market-sentiment"
  "market-sentiment-radar"
  "stock-board"
  "ticai-lieshou"
  "valuation-analysis"
)
MISSING=0
for s in "${SKILLS[@]}"; do
  if [ -d "skills/$s" ]; then
    echo "  ✅ skills/$s"
  else
    echo "  ❌ skills/$s — 缺失！"
    MISSING=$((MISSING+1))
  fi
done

if [ "$MISSING" -gt 0 ]; then
  echo ""
  echo "  ⚠️  有 $MISSING 个技能缺失，请确认 workspace 已完整克隆"
else
  echo "  ✅ 全部核心技能就绪"
fi

# 3. 检查关键文件
echo ""
echo "[3/3] 关键文件校验..."
for f in "AGENTS.md" "SOUL.md" "选股策略.md"; do
  if [ -f "$f" ]; then
    echo "  ✅ $f"
  else
    echo "  ❌ $f — 缺失"
  fi
done

# 4. 网络连通性测试
echo ""
echo "=========================================="
echo "  🌐 数据源连通性测试"
echo "=========================================="
echo ""

TEST_URLS=(
  "腾讯行情API:https://qt.gtimg.cn/q=sh000001"
  "新浪新闻API:https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=1"
  "东方财富API:https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001"
)

for entry in "${TEST_URLS[@]}"; do
  name="${entry%%:*}"
  url="${entry#*:}"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "超时/失败")
  if [ "$code" = "200" ]; then
    echo "  ✅ $name ($code)"
  else
    echo "  ⚠️  $name ($code) — 可能受网络限制"
  fi
done

# 5. 输出结果
echo ""
echo "=========================================="
echo "  🎯 安装检查完成"
echo "=========================================="
echo ""
echo "快速使用示例："
echo "  财经简报    → 输入「财经新闻」"
echo "  持仓诊断    → 输入「持仓分析」"
echo "  个股分析    → 输入「深度分析XX」"
echo "  建仓选股    → 输入「建仓选股」"
echo ""
echo "如果数据源有问题，请检查："
echo "  1. curl 测试是否通过（上面有结果）"
echo "  2. 服务器时间是否正确（影响API签名）"
echo "  3. 是否需要配置代理"
echo ""
