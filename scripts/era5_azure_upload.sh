#!/usr/bin/env bash
#
# era5_azure_upload.sh
#
# Upload ERA5 monthly NetCDF files (era5_YYYY_MM.nc) to the Azure Blob container
# using a SAS URL, following the layout   <prefix>/<YYYY>/era5_YYYY_MM.nc
# (default prefix: "hourly", e.g. hourly/1955/era5_1955_01.nc).
#
# Safe by design:
#   * The SAS URL is typed into a hidden prompt. It is never stored on disk, never
#     written to the log, and never appears in the process list (it is handed to
#     curl through stdin, not on the command line).
#   * Uploads are create-only (If-None-Match: *). An existing blob is never
#     overwritten unless you pass --overwrite.
#   * Files that are still being downloaded (modified within the last --min-age
#     minutes) are skipped, so half-written files are never uploaded.
#   * Files that are not real NetCDF (e.g. a zip or an HTML error page saved as .nc)
#     are rejected.
#   * Every upload is sent with an MD5 so Azure rejects corrupted transfers, and is
#     re-checked afterwards (size + MD5 when Azure returns one). A final pass
#     re-lists the container and confirms every file.
#   * Nothing local is ever deleted or modified.
#   * Safe to re-run: files already in Azure with the same size/MD5 are skipped,
#     so a re-run after an interruption simply resumes.
#
# Usage:  ./era5_azure_upload.sh [options] SOURCE_DIR
#
# Options:
#   -n, --dry-run       List what would be uploaded; upload nothing.
#       --prefix P      Remote folder prefix (default: hourly).
#       --min-age N     Skip files modified less than N minutes ago (default: 15).
#       --overwrite     Allow replacing blobs that exist with different content.
#       --log FILE      Log file (default: ./era5_azure_upload.log).
#   -h, --help          Show this help.
#
# Requires: bash, curl, perl, openssl, od, head, awk (all standard on macOS/Linux).

set -u
set -o pipefail

SCRIPT_NAME=$(basename "$0")
PREFIX="hourly"
DRY_RUN=0
OVERWRITE=0
MIN_AGE_MIN=15
LOG_FILE="./era5_azure_upload.log"
SRC_DIR=""
NAME_RE='^era5_([0-9]{4})_([0-9]{2})\.nc$'

usage() { sed -n '2,/^# Requires/p' "$0" | sed 's/^# \{0,1\}//'; }
die()   { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

# ---------------------------------------------------------------- arguments
while [ $# -gt 0 ]; do
  case "$1" in
    -n|--dry-run)  DRY_RUN=1 ;;
    --overwrite)   OVERWRITE=1 ;;
    --prefix)      [ $# -ge 2 ] || die "--prefix needs a value";  PREFIX=$2;      shift ;;
    --min-age)     [ $# -ge 2 ] || die "--min-age needs a value"; MIN_AGE_MIN=$2; shift ;;
    --log)         [ $# -ge 2 ] || die "--log needs a value";     LOG_FILE=$2;    shift ;;
    -h|--help)     usage; exit 0 ;;
    -*)            die "unknown option: $1 (try --help)" ;;
    *)             [ -z "$SRC_DIR" ] || die "only one SOURCE_DIR may be given"; SRC_DIR=$1 ;;
  esac
  shift
done

[ -n "$SRC_DIR" ] || { usage >&2; exit 2; }
[ -d "$SRC_DIR" ] || die "not a directory: $SRC_DIR"
case "$MIN_AGE_MIN" in ''|*[!0-9]*) die "--min-age must be a whole number of minutes" ;; esac
PREFIX=${PREFIX#/}; PREFIX=${PREFIX%/}
[ -n "$PREFIX" ] || die "--prefix must not be empty"
case "$PREFIX" in *[!A-Za-z0-9._/-]*) die "--prefix may only contain letters, digits, . _ - /" ;; esac

for tool in curl perl openssl od head awk; do
  command -v "$tool" >/dev/null 2>&1 || die "required tool not found: $tool"
done

# ---------------------------------------------------------------- cleanup
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/era5up.XXXXXX") || die "cannot create temp dir"
chmod 700 "$TMP_DIR"
cleanup() {
  rm -rf "$TMP_DIR"
  unset SAS_URL SAS_TOKEN CONTAINER_URL ERA5_SAS_URL
}
trap cleanup EXIT
trap 'echo; echo "Interrupted. Nothing partial is committed in Azure; re-run to resume." >&2; exit 130' INT TERM

# ---------------------------------------------------------------- SAS URL
if [ -n "${ERA5_SAS_URL:-}" ]; then            # non-interactive use / testing only
  SAS_URL=$ERA5_SAS_URL
else
  [ -t 0 ] || die "no terminal for the SAS prompt (run this script from an interactive shell)"
  read -rsp "Paste Blob SAS URL: " SAS_URL
  echo
fi
# Tidy the paste: drop CR/LF, surrounding spaces and surrounding quotes (a stray trailing
# character silently invalidates the signature).
SAS_URL=$(printf '%s' "$SAS_URL" | tr -d '\r\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e "s/^[\"']//" -e "s/[\"']\$//" -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
case "$SAS_URL" in
  *[[:space:]]*) die "the pasted URL contains spaces inside it; paste only the 'Blob Container SAS URL' line" ;;
esac
case "$SAS_URL" in
  https://*\?*) ;;
  http://*\?*)  [ "${ERA5_ALLOW_HTTP:-0}" = 1 ] || die "SAS URL must start with https://" ;;
  *)            die "that does not look like a Blob SAS URL (expected https://<account>.blob.core.windows.net/<container>?<token>)" ;;
esac
CONTAINER_URL="${SAS_URL%%\?*}"
CONTAINER_URL="${CONTAINER_URL%/}"
SAS_TOKEN="${SAS_URL#*\?}"
unset SAS_URL

sas_param() { printf '%s' "$SAS_TOKEN" | tr '&' '\n' | sed -n "s/^$1=//p" | head -1; }
PERMS=$(sas_param sp)
case "$PERMS" in *r*) ;; *) echo "WARNING: SAS token has no read (r) permission; verification will fail." >&2 ;; esac
case "$PERMS" in *l*) ;; *) echo "WARNING: SAS token has no list (l) permission; listing will fail." >&2 ;; esac
case "$PERMS" in *w*|*c*) ;; *) [ "$DRY_RUN" = 1 ] || die "SAS token has no write/create permission (sp=$PERMS)" ;; esac

# ---------------------------------------------------------------- helpers
# curl wrapper: the URL (which contains the token) goes via stdin, not argv.
az_curl() {
  local url=$1; shift
  printf 'url = "%s"\n' "$url" | curl -sS -K - "$@"
}

if stat --version >/dev/null 2>&1; then STAT=gnu; else STAT=bsd; fi
file_size()  { if [ "$STAT" = gnu ]; then stat -c %s "$1"; else stat -f %z "$1"; fi; }
file_mtime() { if [ "$STAT" = gnu ]; then stat -c %Y "$1"; else stat -f %m "$1"; fi; }
local_md5()  { openssl dgst -md5 -binary "$1" | openssl base64; }   # base64 of raw MD5 (Azure format)
human()      { awk -v b="$1" 'BEGIN{split("B KB MB GB TB",u," ");i=1;while(b>=1024&&i<5){b/=1024;i++}printf "%.1f %s",b,u[i]}'; }
log()        { printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$3" "$4" >> "$LOG_FILE"; }

# Azure error body -> "Code: Message [AuthenticationErrorDetail]"  (never contains the token)
azure_error() {
  local f=$1 code msg detail
  code=$(perl -0777 -ne 'print $1 if /<Code>([^<]*)<\/Code>/' "$f" 2>/dev/null)
  msg=$(perl -0777 -ne 'print $1 if /<Message>([^<]*)<\/Message>/' "$f" 2>/dev/null | tr '\r\n' '  ')
  detail=$(perl -0777 -ne 'print $1 if /<AuthenticationErrorDetail>([^<]*)</' "$f" 2>/dev/null | tr '\r\n' '  ')
  printf '%s: %s' "${code:-?}" "$msg" | cut -c1-300
  [ -z "$detail" ] || printf '\n         Azure detail: %s' "$(printf '%s' "$detail" | cut -c1-400)"
}

# Print the non-secret parts of the SAS token and flag obvious problems.
describe_sas() {
  local sp st se sv sr sigraw sig now
  sp=$(sas_param sp); st=$(sas_param st); se=$(sas_param se); sv=$(sas_param sv); sr=$(sas_param sr)
  sigraw=$(sas_param sig)
  sig=$(printf '%s' "$sigraw" | perl -pe 's/%([0-9A-Fa-f]{2})/chr(hex($1))/ge')
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "SAS token:   permissions=${sp:-?}  valid ${st:-?} -> ${se:-?}  version=${sv:-?}  scope=${sr:-?}  signature=${#sig} chars"
  [ -n "$sigraw" ] || echo "  WARNING: no sig= parameter found; the URL is incomplete." >&2
  if [ -n "$sigraw" ] && [ "${#sig}" -ne 44 ]; then
    echo "  WARNING: a normal signature is 44 characters; this one is ${#sig}. The URL was probably cut off or altered when pasted." >&2
  fi
  [ -z "$se" ] || [[ ! "$se" < "$now" ]] || echo "  WARNING: token expiry ($se) is in the past (now: $now)." >&2
  [ -z "$st" ] || [[ ! "$st" > "$now" ]] || echo "  WARNING: token is not valid until $st (now: $now)." >&2
}

# List every blob under "<prefix>/" into file $1 as lines:  <name> <size> <md5-or-dash>
list_remote() {
  local out=$1 marker="" url code next
  : > "$out"
  while :; do
    url="${CONTAINER_URL}?${SAS_TOKEN}&restype=container&comp=list&prefix=${PREFIX}/"
    [ -z "$marker" ] || url="${url}&marker=$(printf '%s' "$marker" | perl -pe 's/([^A-Za-z0-9_.~-])/sprintf("%%%02X",ord($1))/ge')"
    code=$(az_curl "$url" -o "$TMP_DIR/list.xml" -w '%{http_code}') || code=000
    if [ "$code" != 200 ]; then
      LIST_CODE=$code
      echo "ERROR: listing the container failed (HTTP $code)" >&2
      echo "         $(azure_error "$TMP_DIR/list.xml")" >&2
      return 1
    fi
    perl -0777 -ne '
      while (/<Blob>(.*?)<\/Blob>/sg) {
        my $b = $1;
        my ($n) = $b =~ /<Name>([^<]*)<\/Name>/;
        my ($l) = $b =~ /<Content-Length>(\d+)</;
        my ($m) = $b =~ /<Content-MD5>([^<]+)</;
        print "$n $l ", (defined $m ? $m : "-"), "\n" if defined $n && defined $l;
      }' "$TMP_DIR/list.xml" >> "$out"
    next=$(perl -0777 -ne 'print $1 if /<NextMarker>([^<]+)<\/NextMarker>/' "$TMP_DIR/list.xml")
    [ -n "$next" ] || break
    marker=$next
  done
}

# HEAD one blob -> prints "<size> <md5-or-dash>"
remote_head() {
  local code
  code=$(az_curl "${CONTAINER_URL}/$1?${SAS_TOKEN}" -I -o "$TMP_DIR/head.txt" -w '%{http_code}') || return 1
  [ "$code" = 200 ] || return 1
  tr -d '\r' < "$TMP_DIR/head.txt" | awk -F': ' '
    tolower($1)=="content-length" {l=$2}
    tolower($1)=="content-md5"    {m=$2}
    END {print l, (m==""?"-":m)}'
}

# Upload one file. $1=local file  $2=remote path  $3=base64 md5.  Sets UP_ERR on failure.
upload_one() {
  local f=$1 remote=$2 md5=$3 attempt=1 code cond
  if [ "$OVERWRITE" = 1 ]; then cond="x-ms-meta-uploader: era5_azure_upload"; else cond="If-None-Match: *"; fi
  UP_ERR=""
  while [ "$attempt" -le 3 ]; do
    code=$(az_curl "${CONTAINER_URL}/${remote}?${SAS_TOKEN}" \
             -T "$f" \
             -H "x-ms-blob-type: BlockBlob" \
             -H "Content-Type: application/x-netcdf" \
             -H "Content-MD5: ${md5}" \
             -H "x-ms-blob-content-md5: ${md5}" \
             -H "$cond" \
             -o "$TMP_DIR/resp.txt" -w '%{http_code}') || code=000
    case "$code" in
      201) return 0 ;;
      409|412)
        if [ "$attempt" -gt 1 ]; then return 0; fi        # an earlier attempt may have landed; HEAD check decides
        UP_ERR="already exists in Azure (HTTP $code)"; return 3 ;;
      000|408|429|5??)
        UP_ERR="HTTP $code $(azure_error "$TMP_DIR/resp.txt" 2>/dev/null)"
        sleep $((attempt * 5)) ;;
      *)
        UP_ERR="HTTP $code $(azure_error "$TMP_DIR/resp.txt" 2>/dev/null)"; return 1 ;;
    esac
    attempt=$((attempt + 1))
  done
  return 1
}

# ---------------------------------------------------------------- collect local files
shopt -s nullglob
files=("$SRC_DIR"/*.nc)
shopt -u nullglob
total=${#files[@]}
[ "$total" -gt 0 ] || die "no .nc files found in $SRC_DIR"

echo "Source:      $SRC_DIR  ($total .nc files)"
echo "Destination: ${CONTAINER_URL}/${PREFIX}/<YYYY>/"
[ "$DRY_RUN"   = 1 ] && echo "Mode:        DRY RUN (nothing will be uploaded)"
[ "$OVERWRITE" = 1 ] && echo "Mode:        --overwrite enabled"
echo "Log:         $LOG_FILE"
describe_sas
echo

INDEX="$TMP_DIR/remote_index.txt"
echo "Listing existing blobs under ${PREFIX}/ ..."
if ! list_remote "$INDEX"; then
  case "${LIST_CODE:-}" in
    401|403)
      cat >&2 <<'EOF'

Azure rejected the token itself, before looking at any of your files. The usual causes are:
  1. The URL was altered when pasted (cut off, extra character). Paste the line that starts
     with https:// and is labelled "Blob Container SAS URL", not the shorter "SAS Token" line.
  2. The token was revoked, regenerated or has expired. Ask whoever issued it for a new one.
  3. The URL belongs to a different container/account than the one you intend to use.
The "Azure detail" line above says which one applies.
EOF
      ;;
  esac
  exit 1
fi
echo "  $(wc -l < "$INDEX" | tr -d ' ') blobs already there."
echo

# ---------------------------------------------------------------- main loop
DONE="$TMP_DIR/done.txt"; : > "$DONE"
n_up=0; b_up=0; n_have=0; n_recent=0; n_conflict=0; n_fail=0; n_bad=0; n_would=0; b_would=0
now=$(date +%s)
i=0
for f in "${files[@]}"; do
  i=$((i + 1))
  base=$(basename "$f")
  tag="[$i/$total]"

  if [[ $base =~ $NAME_RE ]]; then
    remote="${PREFIX}/${BASH_REMATCH[1]}/${base}"
  else
    printf '%s SKIP     %s  (name is not era5_YYYY_MM.nc)\n' "$tag" "$base"
    log SKIP_NAME "$base" "-" 0; n_bad=$((n_bad + 1)); continue
  fi

  size=$(file_size "$f"); mtime=$(file_mtime "$f"); age=$((now - mtime))
  if [ "$age" -lt $((MIN_AGE_MIN * 60)) ]; then
    printf '%s SKIP     %s  (modified %d min ago, may still be downloading)\n' "$tag" "$base" $((age / 60))
    log SKIP_RECENT "$base" "$remote" "$size"; n_recent=$((n_recent + 1)); continue
  fi
  if [ "$size" -le 0 ]; then
    printf '%s SKIP     %s  (empty file)\n' "$tag" "$base"
    log SKIP_EMPTY "$base" "$remote" 0; n_bad=$((n_bad + 1)); continue
  fi
  magic=$(head -c4 "$f" | od -An -tx1 | tr -d ' \n')
  case "$magic" in
    89484446|4344460[125]) ;;                              # HDF5 (NetCDF-4) or classic NetCDF
    *) printf '%s SKIP     %s  (not a NetCDF file: starts with 0x%s)\n' "$tag" "$base" "$magic"
       log SKIP_NOT_NETCDF "$base" "$remote" "$size"; n_bad=$((n_bad + 1)); continue ;;
  esac

  # already in Azure?
  rinfo=$(awk -v n="$remote" '$1 == n {print $2, $3; exit}' "$INDEX")
  lmd5=""
  if [ -n "$rinfo" ]; then
    rsize=${rinfo% *}; rmd5=${rinfo#* }
    same=0
    if [ "$rsize" = "$size" ]; then
      if [ "$rmd5" = "-" ]; then same=1
      else lmd5=$(local_md5 "$f"); [ "$lmd5" = "$rmd5" ] && same=1
      fi
    fi
    if [ "$same" = 1 ]; then
      printf '%s EXISTS   %s  (already in Azure, identical)\n' "$tag" "$base"
      log EXISTS "$base" "$remote" "$size"; echo "$remote $size" >> "$DONE"; n_have=$((n_have + 1)); continue
    fi
    if [ "$OVERWRITE" != 1 ]; then
      printf '%s CONFLICT %s  (Azure has a different version: local %s bytes, remote %s bytes; not touched)\n' "$tag" "$base" "$size" "$rsize"
      log CONFLICT "$base" "$remote" "$size"; n_conflict=$((n_conflict + 1)); continue
    fi
  fi

  if [ "$DRY_RUN" = 1 ]; then
    printf '%s WOULD UPLOAD %s -> %s (%s)\n' "$tag" "$base" "$remote" "$(human "$size")"
    n_would=$((n_would + 1)); b_would=$((b_would + size)); continue
  fi

  [ -n "$lmd5" ] || lmd5=$(local_md5 "$f")
  printf '%s UPLOAD   %s -> %s (%s) ... ' "$tag" "$base" "$remote" "$(human "$size")"
  t0=$SECONDS
  upload_one "$f" "$remote" "$lmd5"; rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FAILED: $UP_ERR"
    log FAILED "$base" "$remote" "$size"; n_fail=$((n_fail + 1)); continue
  fi
  hv=$(remote_head "$remote") || hv=""
  hsize=${hv% *}; hmd5=${hv#* }
  if [ -n "$hv" ] && [ "$hsize" = "$size" ] && { [ "$hmd5" = "-" ] || [ "$hmd5" = "$lmd5" ]; }; then
    echo "ok, verified ($((SECONDS - t0))s)"
    log UPLOADED "$base" "$remote" "$size"; echo "$remote $size" >> "$DONE"
    n_up=$((n_up + 1)); b_up=$((b_up + size))
  else
    echo "FAILED verification (Azure reports size=${hsize:-?}, md5=${hmd5:-?}; local size=$size)"
    log VERIFY_FAILED "$base" "$remote" "$size"; n_fail=$((n_fail + 1))
  fi
done

# ---------------------------------------------------------------- final verification pass
n_vfail=0
if [ "$DRY_RUN" != 1 ] && [ -s "$DONE" ]; then
  echo
  echo "Final check: re-listing the container ..."
  INDEX2="$TMP_DIR/remote_index2.txt"
  if list_remote "$INDEX2"; then
    while read -r rpath rsz; do
      got=$(awk -v n="$rpath" '$1 == n {print $2; exit}' "$INDEX2")
      if [ "$got" != "$rsz" ]; then
        echo "  MISMATCH: $rpath (local $rsz bytes, Azure ${got:-missing})"
        log FINAL_MISMATCH "$rpath" "$rpath" "$rsz"; n_vfail=$((n_vfail + 1))
      fi
    done < "$DONE"
    [ "$n_vfail" -eq 0 ] && echo "  All $(wc -l < "$DONE" | tr -d ' ') files confirmed in Azure with matching sizes."
  else
    echo "  Could not re-list the container; per-file checks above still apply." >&2
  fi
fi

# ---------------------------------------------------------------- summary
echo
echo "================ Summary ($((SECONDS))s) ================"
if [ "$DRY_RUN" = 1 ]; then
  printf 'Would upload:            %d files (%s)\n' "$n_would" "$(human "$b_would")"
else
  printf 'Uploaded + verified:     %d files (%s)\n' "$n_up" "$(human "$b_up")"
fi
printf 'Already in Azure (same): %d\n' "$n_have"
printf 'Skipped, still new:      %d  (re-run later once downloads finish)\n' "$n_recent"
printf 'Skipped, bad file/name:  %d\n' "$n_bad"
printf 'Conflicts (not touched): %d\n' "$n_conflict"
printf 'Failed:                  %d\n' "$((n_fail + n_vfail))"
echo "Your local files were not modified or deleted. Keep them until you are happy with the Azure copy."

if [ $((n_fail + n_conflict + n_vfail)) -gt 0 ]; then exit 1; fi
exit 0
