#!/bin/bash
# 一键启动脚本 - 芙清DMP数据抓取
# 用法: ./START.sh [选项]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/core"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${GREEN}芙清DMP数据抓取 - 一键启动${NC}"
    echo ""
    echo "用法: ./START.sh [选项]"
    echo ""
    echo "选项:"
    echo "  -a, --assets    运行资产诊断抓取 (data2.csv)"
    echo "  -f, --flow      运行流转数据抓取 (data.csv)"
    echo "  -i, --item      运行单品洞察抓取 (data3.csv)"
    echo "  -A, --all       运行全部抓取（默认）"
    echo "  -h, --help      显示帮助"
    echo ""
    echo "示例:"
    echo "  ./START.sh         # 运行全部抓取（默认）"
    echo "  ./START.sh -a      # 只抓取资产诊断"
    echo "  ./START.sh -f      # 只抓取流转数据"
    echo "  ./START.sh -A      # 抓取全部数据"
}

# 确保脚本可执行
chmod +x *.sh 2>/dev/null || true

case "${1:-}" in
    -a|--assets)
        echo -e "${GREEN}运行资产诊断抓取...${NC}"
        ./run.sh -a
        ;;
    -f|--flow)
        echo -e "${GREEN}运行流转数据抓取...${NC}"
        ./run.sh -f
        ;;
    -i|--item)
        echo -e "${GREEN}运行单品洞察抓取...${NC}"
        ./run.sh -i
        ;;
    -A|--all|"")
        echo -e "${GREEN}运行全部抓取...${NC}"
        ./run.sh -a
        ./run.sh -f
        ./run.sh -i
        echo -e "${GREEN}全部抓取完成!${NC}"
        ;;
    -h|--help)
        show_help
        ;;
    *)
        show_help
        ;;
esac