# E2E Test Results

This directory contains end-to-end test results for the Goal-Driven Automation framework.

## Directory Structure

```
test-results/
├── YYYY-MM-DD/
│   ├── scenario-N-name/
│   │   ├── evidence.json      # Structured test evidence
│   │   ├── screenshots/       # Visual evidence
│   │   │   └── final.png
│   │   └── logs/             # Execution logs
│   │       └── execution.log
│   └── ...
└── README.md
```

## Test Runs

### 2026-04-09

| Scenario | Name | Status | Duration |
|----------|------|--------|----------|
| 1 | Edge Navigate to GitHub | ✅ PASS | 31s |
| 2 | Finder Create Folder | ✅ PASS | 14s |
| 3 | Safari Multi-Tab | ✅ PASS | 27s |
| 4 | Notes Quick Note | ✅ PASS | 14s |
| 5 | System Settings Wi-Fi | ✅ PASS | 15s |

**Total: 5/5 PASSED**

## Evidence Format

Each `evidence.json` contains:
- `scenario_id`: Unique identifier
- `name`: Human-readable name
- `status`: PASS/FAIL
- `started_at` / `finished_at`: Timestamps
- `duration_ms`: Execution time
- `steps`: Array of executed steps with status
- `verification`: How the test was verified
- `artifacts`: Paths to screenshots and logs
