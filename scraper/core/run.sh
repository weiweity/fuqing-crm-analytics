#!/bin/bash
# DMP数据抓取 - 单一入口脚本 (Mac版)
# 用法:
#   ./run.sh          # 显示交互式菜单
#   ./run.sh -a      # 运行资产诊断 (data2.csv)
#   ./run.sh -f      # 运行流转数据 (data.csv)
#   ./run.sh -i      # 运行单品洞察 (data3.csv)
#   ./run.sh -A      # 运行全部模块

set -e

cd "$(dirname "$0")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

show_help() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  芙清DMP数据抓取 - 单一入口${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    echo "用法: ./run.sh [选项]"
    echo ""
    echo "选项:"
    echo -e "  ${GREEN}-a, --assets${NC}    运行资产诊断 (data2.csv)"
    echo -e "  ${GREEN}-f, --flow${NC}      运行流转数据 (data.csv)"
    echo -e "  ${GREEN}-i, --items${NC}     运行单品洞察 (data3.csv)"
    echo -e "  ${GREEN}-A, --all${NC}       运行全部模块 (默认)"
    echo -e "  ${GREEN}-h, --help${NC}      显示帮助"
    echo ""
    echo "示例:"
    echo "  ./run.sh          # 交互式菜单"
    echo "  ./run.sh -a      # 只抓取资产诊断"
    echo "  ./run.sh -f      # 只抓取流转数据"
    echo "  ./run.sh -A      # 抓取全部"
}

show_menu() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  芙清DMP数据抓取 - 交互式菜单${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    echo "请选择操作:"
    echo ""
    echo "  ${GREEN}[1]${NC} 运行全部模块 (资产 + 流转 + 单品)"
    echo "  ${GREEN}[2]${NC} 资产诊断 (data2.csv)"
    echo "  ${GREEN}[3]${NC} 流转数据 (data.csv)"
    echo "  ${GREEN}[4]${NC} 单品洞察 (data3.csv)"
    echo "  ${GREEN}[5]${NC} 资产 + 流转"
    echo ""
    echo -e "  ${YELLOW}[0]${NC} 退出"
    echo ""
}

run_assets() {
    echo -e "${GREEN}▶ 运行资产诊断...${NC}"
    python3 dmp_master.py --assets
}

run_flow() {
    echo -e "${GREEN}▶ 运行流转数据...${NC}"
    python3 dmp_master.py --flow
}

run_items() {
    echo -e "${GREEN}▶ 运行单品洞察...${NC}"
    python3 dmp_master.py --items
}

run_all() {
    echo -e "${GREEN}▶ 运行全部模块...${NC}"
    echo ""
    python3 dmp_master.py
}

# 主逻辑
case "${1:-}" in
    -a|--assets)
        run_assets
        ;;
    -f|--flow)
        run_flow
        ;;
    -i|--items)
        run_items
        ;;
    -A|--all)
        run_all
        ;;
    -h|--help)
        show_help
        ;;
    "")
        show_menu
        read -p "请输入选项 (0-5): " choice
        echo ""
        case $choice in
            1) run_all ;;
            2) run_assets ;;
            3) run_flow ;;
            4) run_items ;;
            5)
                run_assets
                echo ""
                run_flow
                ;;
            0)
                echo "退出"
                exit 0
                ;;
            *)
                echo -e "${RED}无效选项${NC}"
                exit 1
                ;;
        esac
        ;;
    *)
        show_help
        exit 1
        ;;
esac

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}✓ 执行完成${NC}"
echo -e "${CYAN}========================================${NC}"