#!/usr/bin/env bash
# Family Health OS Skill — GitHub 发布脚本
# 使用方法：把下面的 YOUR_TOKEN 替换成你的 GitHub Personal Access Token
# 然后 bash publish.sh

set -e
export PATH="/opt/homebrew/bin:$PATH"

REPO_DIR="$HOME/GitHub/family-health-os-skill"
GITHUB_USER="navyxiong"
REPO_NAME="family-health-os-skill"
TOKEN=***   # ← 替换为你的 token (ghp_xxxxxxxx...)

# ---------- 1. 验证 token ----------
echo "=== 验证 token ==="
curl -sf -H "Authorization: Bearer ***" https://api.github.com/user > /tmp/gh_user.json || {
  echo "✗ Token 验证失败"
  exit 1
}
echo "✓ 已登录: $(python3 -c "import json; print(json.load(open('/tmp/gh_user.json'))['login'])")"

# ---------- 2. 创建仓库 ----------
echo ""
echo "=== 创建仓库 $GITHUB_USER/$REPO_NAME ==="
HTTP_CODE=$(curl -s -o /tmp/gh_repo.json -w "%{http_code}" \
  -X POST \
  -H "Authorization: Bearer *** \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d "{
    \"name\": \"$REPO_NAME\",
    \"description\": \"Hermes Agent skill for managing family lifetime medical records\",
    \"private\": false,
    \"has_issues\": true,
    \"has_wiki\": false
  }")

if [ "$HTTP_CODE" = "201" ]; then
  echo "✓ 仓库创建成功"
elif [ "$HTTP_CODE" = "422" ]; then
  echo "! 仓库已存在（HTTP 422），将直接推送"
else
  echo "✗ 创建失败 HTTP $HTTP_CODE"
  cat /tmp/gh_repo.json
  exit 1
fi

# ---------- 3. 配置 git remote + push ----------
echo ""
echo "=== 推送代码 ==="
cd "$REPO_DIR"
git remote remove origin 2>/dev/null || true
git remote add origin "https://***@github.com/$GITHUB_USER/$REPO_NAME.git"
git branch -M main
git push -u origin main 2>&1 | tail -5

# ---------- 4. 创建 v1.3.0 release ----------
echo ""
echo "=== 创建 v1.3.0 release ==="
TAG_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Authorization: Bearer *** \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$GITHUB_USER/$REPO_NAME/releases \
  -d "{
    \"tag_name\": \"v1.3.0\",
    \"name\": \"v1.3.0 — 家庭健康档案 7技能集成版\",
    \"body\": \"## v1.3.0 — 2026-06-14\\n\\n### Added\\n- **7-skill auto-routing** — health-trend-analyzer, family-health-analyzer, medical-entity-extractor, pubmed-search, sleep-analyzer, nutrition-analyzer, fitness-analyzer\\n- **Report analyzer workflow** — 6-step pipeline: OCR → classify → extract → write → aggregate → summarize\\n- **Doctor handoff template** — 8-section structured handover for transfers\\n- **Smoke test** — 6 verification suites for CI\\n- **Reference docs** — report-type-rules, zero-confirmation-workflow, image-cache-handling, vision-report-parsing, field-mapping, data-management\\n- **Timeline support for 29 event types × 9 categories**\\n\\nSee [CHANGELOG.md](https://github.com/$GITHUB_USER/$REPO_NAME/blob/main/CHANGELOG.md) for full details.\",
    \"draft\": false,
    \"prerelease\": false
  }")

echo "$TAG_RESPONSE" | head -1 | python3 -c "import json,sys; d=json.load(sys.stdin); print('✓ Release:', d.get('html_url','创建失败'))" 2>/dev/null || echo "✓ Release 创建完成"

# ---------- 5. 清理 ----------
echo ""
echo "=== 完成 ==="
echo "仓库地址: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "Release:  https://github.com/$GITHUB_USER/$REPO_NAME/releases/tag/v1.3.0"
