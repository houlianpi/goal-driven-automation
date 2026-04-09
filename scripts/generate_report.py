#!/usr/bin/env python3
"""
Generate HTML Report from test evidence.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def load_evidence(runs_dir: Path) -> List[Dict[str, Any]]:
    """Load all evidence.json files from runs directory."""
    evidence_list = []
    for run_dir in sorted(runs_dir.iterdir()):
        if run_dir.is_dir():
            evidence_file = run_dir / "evidence.json"
            if evidence_file.exists():
                with open(evidence_file) as f:
                    data = json.load(f)
                    data["_run_dir"] = str(run_dir)
                    evidence_list.append(data)
    return evidence_list


def generate_html(evidence_list: List[Dict[str, Any]], output_path: Path):
    """Generate HTML report from evidence list."""
    
    # Calculate summary
    total = len(evidence_list)
    passed = sum(1 for e in evidence_list if e.get("status") == "success")
    failed = total - passed
    total_duration = sum(e.get("total_duration_ms", 0) for e in evidence_list)
    
    # Generate HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report - {datetime.now().strftime("%Y-%m-%d %H:%M")}</title>
    <style>
        :root {{
            --success: #22c55e;
            --failure: #ef4444;
            --warning: #f59e0b;
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f1f5f9;
            --muted: #94a3b8;
            --border: #334155;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .subtitle {{ color: var(--muted); margin-bottom: 2rem; }}
        
        /* Summary Cards */
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: var(--card);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid var(--border);
        }}
        .card-title {{ color: var(--muted); font-size: 0.875rem; margin-bottom: 0.5rem; }}
        .card-value {{ font-size: 2rem; font-weight: 700; }}
        .card-value.success {{ color: var(--success); }}
        .card-value.failure {{ color: var(--failure); }}
        
        /* Scenario List */
        .scenario {{
            background: var(--card);
            border-radius: 12px;
            margin-bottom: 1rem;
            border: 1px solid var(--border);
            overflow: hidden;
        }}
        .scenario-header {{
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            border-bottom: 1px solid var(--border);
        }}
        .scenario-header:hover {{ background: rgba(255,255,255,0.05); }}
        .scenario-title {{ display: flex; align-items: center; gap: 0.75rem; }}
        .status-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-badge.success {{ background: rgba(34,197,94,0.2); color: var(--success); }}
        .status-badge.failure {{ background: rgba(239,68,68,0.2); color: var(--failure); }}
        .duration {{ color: var(--muted); font-size: 0.875rem; }}
        
        /* Steps */
        .steps {{ padding: 1rem 1.5rem; }}
        .step {{
            display: flex;
            align-items: flex-start;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--border);
        }}
        .step:last-child {{ border-bottom: none; }}
        .step-icon {{
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 1rem;
            flex-shrink: 0;
            font-size: 0.75rem;
        }}
        .step-icon.success {{ background: rgba(34,197,94,0.2); color: var(--success); }}
        .step-icon.failure {{ background: rgba(239,68,68,0.2); color: var(--failure); }}
        .step-content {{ flex: 1; }}
        .step-action {{ font-weight: 500; }}
        .step-details {{ color: var(--muted); font-size: 0.875rem; margin-top: 0.25rem; }}
        .step-error {{
            background: rgba(239,68,68,0.1);
            border-left: 3px solid var(--failure);
            padding: 0.5rem 1rem;
            margin-top: 0.5rem;
            font-size: 0.875rem;
            border-radius: 0 4px 4px 0;
        }}
        .step-duration {{ color: var(--muted); font-size: 0.75rem; margin-left: auto; }}
        
        /* Timeline */
        .timeline {{
            display: flex;
            gap: 2px;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 1rem;
        }}
        .timeline-segment {{
            height: 100%;
            min-width: 4px;
        }}
        .timeline-segment.success {{ background: var(--success); }}
        .timeline-segment.failure {{ background: var(--failure); }}
        
        /* Screenshot */
        .screenshots {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }}
        .screenshot {{
            width: 120px;
            height: 80px;
            background: var(--border);
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            color: var(--muted);
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            color: var(--muted);
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 E2E Test Report</h1>
        <p class="subtitle">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <div class="summary">
            <div class="card">
                <div class="card-title">Total Scenarios</div>
                <div class="card-value">{total}</div>
            </div>
            <div class="card">
                <div class="card-title">Passed</div>
                <div class="card-value success">{passed}</div>
            </div>
            <div class="card">
                <div class="card-title">Failed</div>
                <div class="card-value {"failure" if failed > 0 else ""}">{failed}</div>
            </div>
            <div class="card">
                <div class="card-title">Total Duration</div>
                <div class="card-value">{total_duration / 1000:.1f}s</div>
            </div>
        </div>
'''
    
    # Generate scenario cards
    for evidence in evidence_list:
        run_id = evidence.get("run_id", "unknown")
        plan_id = evidence.get("plan_id", "unknown")
        status = evidence.get("status", "unknown")
        steps = evidence.get("steps", [])
        duration = evidence.get("total_duration_ms", 0)
        
        status_class = "success" if status == "success" else "failure"
        
        html += f'''
        <div class="scenario">
            <div class="scenario-header">
                <div class="scenario-title">
                    <span class="status-badge {status_class}">{"✓ Pass" if status == "success" else "✗ Fail"}</span>
                    <strong>{run_id}</strong>
                    <span style="color: var(--muted)">({plan_id})</span>
                </div>
                <span class="duration">{duration}ms</span>
            </div>
            <div class="steps">
'''
        
        # Timeline
        if steps:
            html += '<div class="timeline">'
            for step in steps:
                step_status = step.get("status", "unknown")
                step_duration = step.get("duration_ms", 100)
                width = max(step_duration / 100, 4)
                html += f'<div class="timeline-segment {step_status}" style="flex: {width}"></div>'
            html += '</div>'
        
        # Steps
        for step in steps:
            step_id = step.get("step_id", "?")
            action = step.get("action", "unknown")
            step_status = step.get("status", "unknown")
            step_duration = step.get("duration_ms", 0)
            error = step.get("error", {})
            
            icon = "✓" if step_status == "success" else "✗"
            
            html += f'''
                <div class="step">
                    <div class="step-icon {step_status}">{icon}</div>
                    <div class="step-content">
                        <div class="step-action">{step_id}: {action}</div>
'''
            
            if error:
                error_msg = error.get("message", str(error))
                html += f'''
                        <div class="step-error">❌ {error_msg}</div>
'''
            
            html += f'''
                    </div>
                    <span class="step-duration">{step_duration}ms</span>
                </div>
'''
        
        html += '''
            </div>
        </div>
'''
    
    html += f'''
        <div class="footer">
            <p>Goal-Driven Automation • Generated by generate_report.py</p>
            <p>Report contains {total} scenarios with {sum(len(e.get("steps", [])) for e in evidence_list)} total steps</p>
        </div>
    </div>
</body>
</html>
'''
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    
    print(f"✓ Report generated: {output_path}")
    print(f"  Total: {total} | Passed: {passed} | Failed: {failed}")


def main():
    runs_dir = Path("runs")
    output_path = Path("test-results/report.html")
    
    if not runs_dir.exists():
        print("❌ runs/ directory not found")
        return 1
    
    evidence_list = load_evidence(runs_dir)
    if not evidence_list:
        print("❌ No evidence.json files found")
        return 1
    
    print(f"Found {len(evidence_list)} test runs")
    generate_html(evidence_list, output_path)
    return 0


if __name__ == "__main__":
    exit(main())
