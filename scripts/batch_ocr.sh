#!/usr/bin/env bash
# 批量 OCR — 用 mimo-omni 识别 PDF 扫描页
# 用法: bash scripts/batch_ocr.sh [起始页] [结束页]
# 默认: 处理所有缺失页面 (4-667)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PDF="$PROJECT_DIR/pdf-books/争夺欧洲霸权的斗争（1848-1918年）.pdf"
OCR_DIR="$PROJECT_DIR/output/ocr_text"
PNG_DIR="$PROJECT_DIR/.openclaw/tmp/pdf_pages"
MIMO_API="$HOME/.openclaw/skills/mimo-omni/mimo_api.sh"

START_PAGE="${1:-4}"
END_PAGE="${2:-667}"

mkdir -p "$OCR_DIR" "$PNG_DIR"

echo "📖 PDF OCR 批量处理"
echo "   范围: 第${START_PAGE}页 - 第${END_PAGE}页"
echo "   OCR输出: $OCR_DIR"
echo ""

# 计数器
total=0
cached=0
success=0
fail=0

for ((pn=START_PAGE; pn<=END_PAGE; pn++)); do
    fpath=$(printf "$OCR_DIR/page_%04d.txt" $pn)

    # 跳过已有且有效的文件
    if [[ -f "$fpath" ]]; then
        content=$(cat "$fpath")
        if [[ -n "$content" ]] && [[ "$content" != "ERROR" ]]; then
            ((cached++))
            continue
        fi
    fi

    ((total++))

    # 1) PDF → PNG (用 Python PyMuPDF)
    png_path=$(printf "$PNG_DIR/page_%04d.png" $pn)
    if [[ ! -f "$png_path" ]]; then
        python3 -c "
import fitz
doc = fitz.open('$PDF')
page = doc[$pn - 1]
pix = page.get_pixmap(dpi=150)
pix.save('$png_path')
doc.close()
" 2>/dev/null
    fi

    # 2) OCR 识别
    result=$(bash "$MIMO_API" image "$png_path" \
        "这是扫描版书籍的内页。请完整提取所有文字，保持段落结构。只输出文字，不要说明。" \
        --max-tokens 131072 2>/dev/null) || true

    if [[ -n "$result" ]]; then
        echo "$result" > "$fpath"
        chars=${#result}
        printf "  ✓ Page %d: %d chars\n" $pn $chars
        ((success++))
    else
        echo "ERROR" > "$fpath"
        printf "  ✗ Page %d: FAILED\n" $pn
        ((fail++))
    fi

    # 每处理10页清理一次PNG缓存
    if (( total % 10 == 0 )); then
        rm -f "$PNG_DIR"/page_*.png 2>/dev/null
        echo "  --- 已处理 ${total} 页 (成功${success} 失败${fail}) ---"
    fi
done

# 清理PNG缓存
rm -rf "$PNG_DIR" 2>/dev/null

echo ""
echo "========================================="
echo "✅ OCR 完成"
echo "   缓存跳过: ${cached} 页"
echo "   本次处理: ${total} 页"
echo "   成功: ${success}"
echo "   失败: ${fail}"
echo "========================================="

# 合并全文
merged="$OCR_DIR/full_text.txt"
echo "📝 合并全文..."
> "$merged"
for f in $(ls "$OCR_DIR"/page_*.txt 2>/dev/null | sort); do
    content=$(cat "$f")
    if [[ -n "$content" ]] && [[ "$content" != "ERROR" ]]; then
        echo "$content" >> "$merged"
        echo "" >> "$merged"
    fi
done
final_size=$(wc -c < "$merged")
echo "✅ 全文合并完成: ${merged} (${final_size} bytes)"
