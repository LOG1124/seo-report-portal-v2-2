#!/usr/bin/env bash
# 发布已审核的 SEO 报告：先归档到 SMB 公盘，再从公盘上传三个公开报告文件。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${OSS_ENV_FILE:-$ROOT_DIR/private/oss.env}"

usage() {
  echo "用法：$0 --local-report-dir <本地报告目录> --client-slug <客户标识> --type <monthly|quarterly|yearly> --period <周期> [--replace-archive] [--dry-run]" >&2
  exit 2
}

[[ -f "$ENV_FILE" ]] || { echo "缺少私密配置：$ENV_FILE；请复制 assets/oss.env.example 并填写本机配置。" >&2; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"

LOCAL_REPORT_DIR=""
CLIENT_SLUG=""
REPORT_TYPE=""
PERIOD=""
REPLACE_ARCHIVE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local-report-dir) LOCAL_REPORT_DIR="${2:-}"; shift 2 ;;
    --client-slug) CLIENT_SLUG="${2:-}"; shift 2 ;;
    --type) REPORT_TYPE="${2:-}"; shift 2 ;;
    --period) PERIOD="${2:-}"; shift 2 ;;
    --replace-archive) REPLACE_ARCHIVE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) usage ;;
  esac
done

[[ -n "$LOCAL_REPORT_DIR" && -n "$CLIENT_SLUG" && -n "$REPORT_TYPE" && -n "$PERIOD" ]] || usage
[[ -d "$LOCAL_REPORT_DIR" ]] || { echo "本地报告目录不存在：$LOCAL_REPORT_DIR" >&2; exit 1; }
[[ "$CLIENT_SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "客户标识只能使用小写字母、数字和连字符。" >&2; exit 1; }
[[ "$REPORT_TYPE" == monthly || "$REPORT_TYPE" == quarterly || "$REPORT_TYPE" == yearly ]] || { echo "报告类型必须是 monthly、quarterly 或 yearly。" >&2; exit 1; }
[[ "$PERIOD" =~ ^[0-9]{4}(-[0-9]{2}|-[0-9]{2}_to_[0-9]{4}-[0-9]{2})$ || "$PERIOD" =~ ^[0-9]{4}$ ]] || { echo "周期格式不符合约定：$PERIOD" >&2; exit 1; }

OSSUTIL_BIN="${OSSUTIL_BIN:-ossutil}"
OSSUTIL_CONFIG_FILE="${OSSUTIL_CONFIG_FILE:-$ROOT_DIR/private/ossutilconfig}"
OSS_BUCKET="${OSS_BUCKET:-jzyseo-reports}"
OSS_PUBLIC_BASE_URL="${OSS_PUBLIC_BASE_URL:-https://reports.jzyseo.com}"
OSS_REPORT_PREFIX="${OSS_REPORT_PREFIX:-reports}"
OSS_ARCHIVE_ROOT="${OSS_ARCHIVE_ROOT:-/Volumes/共享盘/seo-report-portal}"
ARCHIVE_DIR="$OSS_ARCHIVE_ROOT/$CLIENT_SLUG/$REPORT_TYPE/$PERIOD"

if [[ "$DRY_RUN" -eq 0 ]]; then
  command -v "$OSSUTIL_BIN" >/dev/null 2>&1 || { echo "未找到 ossutil：$OSSUTIL_BIN" >&2; exit 1; }
  [[ -f "$OSSUTIL_CONFIG_FILE" ]] || { echo "缺少 ossutil 私密配置：$OSSUTIL_CONFIG_FILE" >&2; exit 1; }
fi

FILES=(index.html dashboard-data.json summary.md)
REMOTE_PREFIX="oss://$OSS_BUCKET/$OSS_REPORT_PREFIX/$CLIENT_SLUG/$REPORT_TYPE/$PERIOD"
PUBLIC_URL="$OSS_PUBLIC_BASE_URL/$OSS_REPORT_PREFIX/$CLIENT_SLUG/$REPORT_TYPE/$PERIOD/"

for file in "${FILES[@]}"; do
  [[ -f "$LOCAL_REPORT_DIR/$file" ]] || { echo "本地报告产物不完整，缺少：$LOCAL_REPORT_DIR/$file" >&2; exit 1; }
done

if [[ "$DRY_RUN" -eq 0 ]]; then
  mount | grep -Fq "on /Volumes/共享盘 " || { echo "公盘未挂载：/Volumes/共享盘；已停止，未归档、未上传。" >&2; exit 1; }
fi

echo "发布目标：$REMOTE_PREFIX/"
echo "公开链接：$PUBLIC_URL"
echo "公盘归档：$ARCHIVE_DIR"
for file in "${FILES[@]}"; do
  printf '%-22s %s bytes  %s\n' "$file" "$(wc -c < "$LOCAL_REPORT_DIR/$file" | tr -d ' ')" "$(shasum -a 256 "$LOCAL_REPORT_DIR/$file" | awk '{print $1}')"
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY_RUN：未上传。"
  exit 0
fi

mkdir -p "$ARCHIVE_DIR"
for file in "${FILES[@]}"; do
  if [[ -f "$ARCHIVE_DIR/$file" && "$REPLACE_ARCHIVE" -ne 1 ]]; then
    LOCAL_SHA="$(shasum -a 256 "$LOCAL_REPORT_DIR/$file" | awk '{print $1}')"
    ARCHIVE_SHA="$(shasum -a 256 "$ARCHIVE_DIR/$file" | awk '{print $1}')"
    [[ "$LOCAL_SHA" == "$ARCHIVE_SHA" ]] || { echo "公盘已有不同版本：$ARCHIVE_DIR/$file；如确认替换，请增加 --replace-archive。" >&2; exit 1; }
  fi
  cp "$LOCAL_REPORT_DIR/$file" "$ARCHIVE_DIR/$file"
done

for file in "${FILES[@]}"; do
  LOCAL_SHA="$(shasum -a 256 "$LOCAL_REPORT_DIR/$file" | awk '{print $1}')"
  ARCHIVE_SHA="$(shasum -a 256 "$ARCHIVE_DIR/$file" | awk '{print $1}')"
  [[ "$LOCAL_SHA" == "$ARCHIVE_SHA" ]] || { echo "公盘归档校验失败：$file SHA-256 不一致。" >&2; exit 1; }
done
echo "公盘归档完成，三份文件与本地版 SHA-256 一致。"

for file in "${FILES[@]}"; do
  "$OSSUTIL_BIN" cp -c "$OSSUTIL_CONFIG_FILE" "$ARCHIVE_DIR/$file" "$REMOTE_PREFIX/$file" --force
done

CHECK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/oss-report-check.XXXXXX")"
trap 'rm -rf "$CHECK_DIR"' EXIT
curl -fsSL "$PUBLIC_URL" -o "$CHECK_DIR/index.html"
LOCAL_SHA="$(shasum -a 256 "$ARCHIVE_DIR/index.html" | awk '{print $1}')"
REMOTE_SHA="$(shasum -a 256 "$CHECK_DIR/index.html" | awk '{print $1}')"
[[ "$LOCAL_SHA" == "$REMOTE_SHA" ]] || { echo "线上 index.html 校验失败：SHA-256 不一致。" >&2; exit 1; }

echo "上传成功，线上 index.html SHA-256 校验一致：$REMOTE_SHA"
echo "客户交付链接：$PUBLIC_URL"
