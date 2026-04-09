# POC Scenarios

This directory contains pre-defined scenarios for validating the automation pipeline.

## Running Scenarios

```bash
# Run a single scenario
python -m src.cli run "Open Edge and create new tab"

# Dry run (no execution)
python -m src.cli run "Open Edge" --dry-run

# Run all POC scenarios
./scripts/run_poc.sh
```

## Scenario Categories

### 1. Tab Management
- Create new tab
- Switch between tabs
- Close tab

### 2. Bookmarks
- Add bookmark
- Open bookmark

### 3. History
- View history
- Clear history

### 4. Downloads
- View downloads
- Clear downloads

## Validation Criteria

1. **3+ goals complete full pipeline** ✓
2. **1+ failure auto-repaired** ✓
3. **Evidence artifacts generated** ✓
4. **Human only at goal/review** ✓
