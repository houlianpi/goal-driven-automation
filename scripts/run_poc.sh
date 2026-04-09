#!/bin/bash
# POC Runner
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCENARIOS_FILE="$PROJECT_DIR/data/scenarios/poc_goals.json"
REPORT_DIR="$PROJECT_DIR/data/runs/poc-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$REPORT_DIR"
echo "POC Runner"
echo "Report: $REPORT_DIR"
cd "$PROJECT_DIR"
TOTAL=0; PASSED=0; FAILED=0; REPAIRED=0
while IFS="|" read -r id goal; do
  TOTAL=$((TOTAL+1))
  echo "Running: $id"
  OUTPUT=$(python3 -m src.cli run "$goal" --json 2>&1) || true
  echo "$OUTPUT" > "$REPORT_DIR/$id.log"
  if echo "$OUTPUT" | grep -q '"final_status": "success"'; then
    PASSED=$((PASSED+1)); echo "  PASSED"
  elif echo "$OUTPUT" | grep -q '"final_status": "recovered"'; then
    PASSED=$((PASSED+1)); REPAIRED=$((REPAIRED+1)); echo "  RECOVERED"
  else
    FAILED=$((FAILED+1)); echo "  FAILED"
  fi
done < <(python3 -c "import json; f=open('data/scenarios/poc_goals.json'); d=json.load(f); [print(s['id'],'|',s['goal']) for s in d['scenarios']]")
echo "Summary: TOTAL=$TOTAL PASSED=$PASSED FAILED=$FAILED REPAIRED=$REPAIRED"
echo "Done. Results in $REPORT_DIR"
