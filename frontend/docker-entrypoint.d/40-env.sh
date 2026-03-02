#!/bin/sh
set -eu

escape_js() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

SUPABASE_URL_ESCAPED="$(escape_js "${VITE_SUPABASE_URL:-}")"
SUPABASE_ANON_KEY_ESCAPED="$(escape_js "${VITE_SUPABASE_ANON_KEY:-}")"
SUPABASE_REDIRECT_URL_ESCAPED="$(escape_js "${VITE_SUPABASE_REDIRECT_URL:-}")"

sed \
  -e "s|__VITE_SUPABASE_URL__|${SUPABASE_URL_ESCAPED}|g" \
  -e "s|__VITE_SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY_ESCAPED}|g" \
  -e "s|__VITE_SUPABASE_REDIRECT_URL__|${SUPABASE_REDIRECT_URL_ESCAPED}|g" \
  /usr/share/nginx/html/env.js.template \
  > /usr/share/nginx/html/env.js
