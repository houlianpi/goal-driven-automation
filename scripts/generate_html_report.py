#!/usr/bin/env python3
"""
Generate HTML Report from E2E Test Results
"""
import json
import os
from pathlib import Path
from datetime import datetime

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report - {date}</title>
    <style>
        :root {{
            --success: #22c55e;
            --failure: #ef4444;
            --warning: #f59e0b;
            --bg: #0f172a;
            --card: #1e293b;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
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
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border-radius: 1rem;
        }}
        .header h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .header .date {{ color: var(--text-muted); }}
        
        /* Summary Cards */
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            background: var(--card);
            padding: 1.5rem;
            border-radius: 0.75rem;
            text-align: center;
            border: 1px solid var(--border);
        }}
        .summary-card .value {{
            font-size: 2.5rem;
            font-weight: bold;
        }}
        .summary-card .label {{ color: var(--text-muted); font-size: 0.875rem; }}
        .summary-card.success .value {{ color: var(--success); }}
        .summary-card.failure .value {{ color: var(--failure); }}
        
        /* Scenario Cards */
        .scenario {{
            background: var(--card);
            border-radius: 0.75rem;
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
            background: rgba(255,255,255,0.02);
        }}
        .scenario-header:hover {{ background: rgba(255,255,255,0.05); }}
        .scenario-title {{ font-weight: 600; }}
        .scenario-meta {{ display: flex; gap: 1rem; align-items: center; }}
        
        .status {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status.pass {{ background: rgba(34, 197, 94, 0.2); color: var(--success); }}
        .status.fail {{ background: rgba(239, 68, 68, 0.2); color: var(--failure); }}
        
        .duration {{ color: var(--text-muted); font-size: 0.875rem; }}
        
        /* Steps */
        .scenario-body {{ padding: 1.5rem; display: none; }}
        .scenario.expanded .scenario-body {{ display: block; }}
        
        .steps {{ margin-top: 1rem; }}
        .step {{
            display: flex;
            align-items: flex-start;
            padding: 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        .step-num {{
            width: 1.5rem;
            height: 1.5rem;
            background: var(--border);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            margin-right: 0.75rem;
            flex-shrink: 0;
        }}
        .step.success .step-num {{ background: var(--success); }}
        .step.failure .step-num {{ background: var(--failure); }}
        
        .step-content {{ flex: 1; }}
        .step-action {{ font-weight: 500; }}
        .step-target {{ color: var(--text-muted); font-size: 0.875rem; }}
        .step-command {{
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.75rem;
            background: rgba(0,0,0,0.3);
            padding: 0.5rem;
            border-radius: 0.25rem;
            margin-top: 0.5rem;
            overflow-x: auto;
        }}
        
        /* Verification */
        .verification {{
            margin-top: 1rem;
            padding: 1rem;
            background: rgba(34, 197, 94, 0.1);
            border-radius: 0.5rem;
            border-left: 3px solid var(--success);
        }}
        .verification.failed {{
            background: rgba(239, 68, 68, 0.1);
            border-left-color: var(--failure);
        }}
        .verification-title {{ font-weight: 600; margin-bottom: 0.5rem; }}
        .verification-detail {{ font-size: 0.875rem; color: var(--text-muted); }}
        
        /* Screenshot */
        .screenshot {{
            margin-top: 1rem;
        }}
        .screenshot img {{
            max-width: 100%;
            border-radius: 0.5rem;
            border: 1px solid var(--border);
        }}
        .screenshot-link {{
            color: #60a5fa;
            text-decoration: none;
            font-size: 0.875rem;
        }}
        .screenshot-link:hover {{ text-decoration: underline; }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
        
        /* Expand icon */
        .expand-icon {{
            transition: transform 0.2s;
        }}
        .scenario.expanded .expand-icon {{
            transform: rotate(180deg);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 E2E Test Report</h1>
            <div class="date">{date} | Platform: {platform}</div>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <div class="value">{total}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card success">
                <div class="value">{passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card failure">
                <div class="value">{failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card">
                <div class="value">{pass_rate}</div>
                <div class="label">Pass Rate</div>
            </div>
            <div class="summary-card">
                <div class="value">{duration}</div>
                <div class="label">Total Duration</div>
            </div>
        </div>
        
        <h2 style="margin-bottom: 1rem;">📋 Test Scenarios</h2>
        
        {scenarios_html}
        
        <div class="footer">
            Generated by Goal-Driven Automation Framework<br>
            {timestamp}
        </div>
    </div>
    
    <script>
        document.querySelectorAll('.scenario-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('expanded');
            }});
        }});
    </script>
</body>
</html>
"""

SCENARIO_TEMPLATE = """
<div class="scenario {expanded}">
    <div class="scenario-header">
        <div class="scenario-title">{icon} {name}</div>
        <div class="scenario-meta">
            <span class="duration">{duration}</span>
            <span class="status {status_class}">{status}</span>
            <span class="expand-icon">▼</span>
        </div>
    </div>
    <div class="scenario-body">
        <div class="steps">
            <h4>Steps</h4>
            {steps_html}
        </div>
        
        <div class="verification {verification_class}">
            <div class="verification-title">✓ Verification</div>
            <div class="verification-detail">
                <strong>Method:</strong> {verification_method}<br>
                <strong>Expected:</strong> {verification_expected}<br>
                <strong>Actual:</strong> {verification_actual}
            </div>
        </div>
        
        {screenshot_html}
    </div>
</div>
"""

STEP_TEMPLATE = """
<div class="step {status_class}">
    <div class="step-num">{num}</div>
    <div class="step-content">
        <div class="step-action">{action}</div>
        <div class="step-target">{target}</div>
    </div>
</div>
"""


def format_duration(ms):
    """Format milliseconds to human readable."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms/1000:.1f}s"
    else:
        return f"{ms/60000:.1f}m"


def generate_report(results_dir: Path, output_path: Path):
    """Generate HTML report from test results."""
    
    # Find all evidence.json files
    scenarios = []
    total_duration = 0
    
    for evidence_file in sorted(results_dir.glob("*/evidence.json")):
        with open(evidence_file) as f:
            data = json.load(f)
        scenarios.append(data)
        total_duration += data.get("duration_ms", 0)
    
    # Load summary if exists
    summary_file = results_dir / "summary.json"
    if summary_file.exists():
        with open(summary_file) as f:
            summary = json.load(f)
    else:
        summary = {
            "date": results_dir.name,
            "platform": {"os": "macOS", "cli": "fsq-mac"}
        }
    
    # Count pass/fail
    passed = sum(1 for s in scenarios if s.get("status") == "PASS")
    failed = len(scenarios) - passed
    
    # Generate scenarios HTML
    scenarios_html = []
    for i, scenario in enumerate(scenarios):
        # Steps HTML
        steps_html = []
        for j, step in enumerate(scenario.get("steps", []), 1):
            steps_html.append(STEP_TEMPLATE.format(
                num=j,
                action=step.get("action", "unknown"),
                target=step.get("target", ""),
                status_class="success" if step.get("status") == "success" else "failure"
            ))
        
        # Verification
        verification = scenario.get("verification", {})
        
        # Screenshot
        screenshots = scenario.get("artifacts", {}).get("screenshots", [])
        screenshot_html = ""
        if screenshots:
            screenshot_path = screenshots[0]
            screenshot_html = f'''
            <div class="screenshot">
                <h4>📸 Screenshot</h4>
                <a href="{scenario['scenario_id']}/{screenshot_path}" class="screenshot-link" target="_blank">
                    View Screenshot →
                </a>
            </div>
            '''
        
        status = scenario.get("status", "UNKNOWN")
        scenarios_html.append(SCENARIO_TEMPLATE.format(
            expanded="expanded" if i == 0 else "",
            icon="✅" if status == "PASS" else "❌",
            name=scenario.get("name", scenario.get("scenario_id", "Unknown")),
            duration=format_duration(scenario.get("duration_ms", 0)),
            status=status,
            status_class="pass" if status == "PASS" else "fail",
            steps_html="\n".join(steps_html),
            verification_class="" if verification.get("passed", True) else "failed",
            verification_method=verification.get("method", "N/A"),
            verification_expected=verification.get("expected", "N/A"),
            verification_actual=verification.get("actual", "N/A"),
            screenshot_html=screenshot_html
        ))
    
    # Generate final HTML
    platform_info = summary.get("platform", {})
    platform_str = f"{platform_info.get('os', 'macOS')} | {platform_info.get('cli', 'fsq-mac')}"
    
    html = HTML_TEMPLATE.format(
        date=summary.get("date", datetime.now().strftime("%Y-%m-%d")),
        platform=platform_str,
        total=len(scenarios),
        passed=passed,
        failed=failed,
        pass_rate=f"{passed/len(scenarios)*100:.0f}%" if scenarios else "N/A",
        duration=format_duration(total_duration),
        scenarios_html="\n".join(scenarios_html),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    
    print(f"✅ Report generated: {output_path}")
    print(f"   Total: {len(scenarios)} | Passed: {passed} | Failed: {failed}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        # Default paths
        results_dir = Path("test-results/2026-04-09")
        output_path = Path("test-results/2026-04-09/report.html")
    else:
        results_dir = Path(sys.argv[1])
        output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else results_dir / "report.html"
    
    generate_report(results_dir, output_path)
