#!/usr/bin/env bash
# docs/dev-plan/_verify-links.sh
# 校验本目录下所有 markdown 的引用：
#   1) 文档之间的相对 link（必须 resolve 到存在的文件）
#   2) markdown link 形式 [text](https://...) 的外部 URL（必须 2xx / 3xx / 4xx 中已知豁免）
#
# 不校验：
#   - script/testnet/* 路径（规划中将由实施者 / AI 产出，预期不存在）
#   - 模板文件 `_template-*.md` 内的示例 link
#   - inline text 字符串中的 URL（仅用于代码示例，不渲染）
#   - 占位符 / 自己内部域名 / localhost
#   - 规划中的 GitHub 仓库（部署时由甲方创建，加入 PLANNED_URLS 列表）
#
# 用法：
#   bash docs/dev-plan/_verify-links.sh
#   bash docs/dev-plan/_verify-links.sh --skip-external    # 离线模式
#
# 退出码：
#   0 全绿；1 存在 broken
set -u
SKIP_EXT=0
[[ "${1:-}" == "--skip-external" ]] && SKIP_EXT=1

DEV_PLAN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEV_PLAN_DIR/../.." && pwd)"
cd "$REPO_ROOT"
FAIL=0

echo "=== [1/2] 文档间相对 link 校验 ==="
python3 - <<'PY'
import os, re, sys, pathlib
root = pathlib.Path('docs/dev-plan')
link_re = re.compile(r'(?<!`)\[([^\]]+)\]\(([^)]+)\)')
broken = []
for md in sorted(root.rglob('*.md')):
    if md.name.startswith('_template'):
        continue
    text = md.read_text(errors='ignore').splitlines()
    in_code = False
    for i, line in enumerate(text, 1):
        if line.lstrip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in link_re.finditer(line):
            target = m.group(2).strip()
            if target.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            if '://' in target:
                continue
            path_only = target.split('#')[0]
            if not path_only:
                continue
            target_path = os.path.normpath(os.path.join(md.parent, path_only))
            if 'script/testnet' in target_path:
                continue
            if not os.path.exists(target_path):
                broken.append((md, i, target, target_path))

if broken:
    print(f"FAIL: {len(broken)} broken link(s)")
    for md, line, target, resolved in broken:
        print(f"  {md}:{line}  -> {target}  (resolved: {resolved})")
    sys.exit(1)
print("OK: 所有文档间相对 link 全绿")
PY
[[ $? -ne 0 ]] && FAIL=1

if [[ $SKIP_EXT -eq 1 ]]; then
    echo ""
    echo "=== [2/2] 外部 URL 校验（--skip-external，跳过） ==="
else
    echo ""
    echo "=== [2/2] 外部 URL 校验（markdown link 中的 https://，HTTP 2xx/3xx 或已知豁免）==="
    # 抽 markdown link 中的 URL，去模板，去自己域名 / localhost / 占位
    TMPLIST=$(mktemp)
    python3 - >"$TMPLIST" <<'PY'
import re, pathlib
root = pathlib.Path('docs/dev-plan')
link_re = re.compile(r'(?<!`)\[([^\]]+)\]\((https?://[^)\s]+)\)')
seen = set()
# 规划中的仓库 / 部署时才存在的 URL（豁免）
PLANNED = {
    'https://github.com/superaichain/examples',
}
for md in sorted(root.rglob('*.md')):
    if md.name.startswith('_template'):
        continue
    text = md.read_text(errors='ignore').splitlines()
    in_code = False
    for line in text:
        if line.lstrip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in link_re.finditer(line):
            url = m.group(2).strip().rstrip(",.;:'\")]")
            if any(p in url for p in ('${', '{DOMAIN', '{TESTNET', '{ROOT', '{name', '{port', '{host', '{module', '{any', '{bridge', '{GITHUB')):
                continue
            if any(d in url for d in ('localhost', '127.0.0.1', 'testnet.superai.chain', 'superaichain.ai')):
                continue
            if url in PLANNED:
                continue
            seen.add(url)
for u in sorted(seen):
    print(u)
PY
    TOTAL=$(wc -l < "$TMPLIST" | tr -d ' ')
    BAD=0
    RESULTS=$(mktemp)
    while IFS= read -r url; do
      [[ -z "$url" ]] && continue
      ( c=$(curl -sS -o /dev/null -w "%{http_code}" -L --max-time 10 -A "Mozilla/5.0" "$url" 2>/dev/null); echo "$c $url" >> "$RESULTS" ) &
    done < "$TMPLIST"
    wait
    while IFS= read -r line; do
      code="${line%% *}"
      url="${line#* }"
      # 豁免：2xx/3xx 正常；403 反爬；405 POST endpoint；429 限流
      if [[ "$code" =~ ^(200|201|301|302|303|307|308|403|405|429)$ ]]; then
          continue
      fi
      echo "  $code  $url"
      BAD=$((BAD+1))
    done < "$RESULTS"
    rm -f "$TMPLIST" "$RESULTS"
    if [[ $BAD -gt 0 ]]; then
      echo "FAIL: $BAD / $TOTAL external URL(s) broken"
      FAIL=1
    else
      echo "OK: $TOTAL external URLs 全绿"
    fi
fi

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "✅ 全部校验通过"
  exit 0
else
  echo "❌ 校验失败：见上述 broken 列表"
  exit 1
fi
