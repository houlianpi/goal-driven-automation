#!/usr/bin/env python3
"""
Generate Enhanced HTML Report with embedded screenshots and formatted actions.
"""
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def load_scenarios(results_dir: Path) -> List[Dict[str, Any]]:
    """Load all scenario evidence from results directory."""
    scenarios = []
    for scenario_dir in sorted(results_dir.iterdir()):
        if scenario_dir.is_dir() and scenario_dir.name.startswith("scenario-"):
            evidence_file = scenario_dir / "evidence.json"
            if evidence_file.exists():
                with open(evidence_file) as f:
                    data = json.load(f)
                    data["_dir"] = scenario_dir
                    scenarios.append(data)
    return scenarios


def encode_image(img_path: Path) -> str:
    """Encode image to base64 data URI."""
    if not img_path.exists():
        return ""
    with open(img_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    suffix = img_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{data}"


def format_action(step: Dict) -> str:
    """Format action for human-readable display."""
    action = step.get("action", "")
    target = step.get("target", "")
    
    action_icons = {
        "app.launch": "🚀",
        "input.hotkey": "⌨️",
        "input.text": "📝",
        "input.key": "🔑",
        "capture.screenshot": "📸",
        "wait": "⏳",
        "assert": "✅",
    }
    
    icon = action_icons.get(action, "▶️")
    
    if action == "app.launch":
        app_name = target.split(".")[-1] if target else "app"
        return f"{icon} Launch <strong>{app_name}</strong>"
    elif action == "input.hotkey":
        keys = target.replace("+", " + ").upper()
        return f"{icon} Press <kbd>{keys}</kbd>"
    elif action == "input.text":
        return f'{icon} Type "<em>{target}</em>"'
    elif action == "input.key":
        return f"{icon} Press <kbd>{target.upper()}</kbd>"
    elif action == "capture.screenshot":
        return f"{icon} Capture screenshot"
    else:
        return f"{icon} {action}: {target}"


def generate_html(scenarios: List[Dict], results_dir: Path, output_path: Path):
    """Generate enhanced HTML report."""
    
    total = len(scenarios)
    passed = sum(1 for s in scenarios if s.get("status") == "PASS")
    failed = total - passed
    total_duration = sum(s.get("duration_ms", 0) for s in scenarios)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report - {datetime.now().strftime("%Y-%m-%d")}</title>
    <style>
        :root {{
            --success: #22c55e; --failure: #ef4444; --bg: #0f172a;
            --card: #1e293b; --text: #f1f5f9; --muted: #94a3b8; --border: #334155;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 2rem; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .subtitle {{ color: var(--muted); margin-bottom: 2rem; }}
        
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
        .card {{ background: var(--card); border-radius: 12px; padding: 1.5rem; border: 1px solid var(--border); }}
        .card-title {{ color: var(--muted); font-size: 0.875rem; }}
        .card-value {{ font-size: 2rem; font-weight: 700; }}
        .card-value.success {{ color: var(--success); }}
        .card-value.failure {{ color: var(--failure); }}
        
        .scenario {{ background: var(--card); border-radius: 12px; margin-bottom: 1.5rem; border: 1px solid var(--border); overflow: hidden; }}
        .scenario-header {{ padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); }}
        .scenario-title {{ display: flex; align-items: center; gap: 1rem; }}
        .badge {{ padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .badge.pass {{ background: rgba(34,197,94,0.2); color: var(--success); }}
        .badge.fail {{ background: rgba(239,68,68,0.2); color: var(--failure); }}
        
        .scenario-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; padding: 1.5rem; }}
        .steps-panel {{ }}
        .screenshot-panel {{ }}
        
        .step {{ display: flex; align-items: center; padding: 0.75rem 1rem; background: rgba(0,0,0,0.2); border-radius: 8px; margin-bottom: 0.5rem; }}
        .step-num {{ width: 28px; height: 28px; border-radius: 50%; background: var(--border); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600; margin-right: 1rem; flex-shrink: 0; }}
        .step-num.success {{ background: rgba(34,197,94,0.3); color: var(--success); }}
        .step-num.failure {{ background: rgba(239,68,68,0.3); color: var(--failure); }}
        .step-action {{ flex: 1; }}
        .step-action kbd {{ background: var(--border); padding: 0.1rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.85rem; }}
        
        .screenshot {{ width: 100%; border-radius: 8px; border: 1px solid var(--border); cursor: pointer; transition: transform 0.2s; }}
        .screenshot:hover {{ transform: scale(1.02); }}
        .screenshot-label {{ color: var(--muted); font-size: 0.875rem; margin-bottom: 0.5rem; }}
        
        .verification {{ background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 8px; margin-top: 1rem; }}
        .verification-title {{ color: var(--muted); font-size: 0.75rem; margin-bottom: 0.5rem; }}
        .verification-content {{ font-family: monospace; font-size: 0.85rem; white-space: pre-wrap; word-break: break-all; }}
        .verification.pass {{ border-left: 3px solid var(--success); }}
        .verification.fail {{ border-left: 3px solid var(--failure); }}
        
        .json-view {{ background: rgba(0,0,0,0.4); padding: 1rem; border-radius: 8px; margin-top: 1rem; font-family: monospace; font-size: 0.8rem; overflow-x: auto; max-height: 300px; overflow-y: auto; }}
        .json-key {{ color: #93c5fd; }}
        .json-string {{ color: #86efac; }}
        .json-number {{ color: #fcd34d; }}
        .json-bool {{ color: #f472b6; }}
        
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }}
        .modal.active {{ display: flex; }}
        .modal img {{ max-width: 95%; max-height: 95%; border-radius: 8px; }}
        .modal-close {{ position: absolute; top: 20px; right: 30px; color: white; font-size: 2rem; cursor: pointer; }}
        
        @media (max-width: 900px) {{ .scenario-body {{ grid-template-columns: 1fr; }} .summary {{ grid-template-columns: repeat(2, 1fr); }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 E2E Test Report</h1>
        <p class="subtitle">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Duration: {total_duration/1000:.1f}s</p>
        
        <div class="summary">
            <div class="card"><div class="card-title">Total</div><div class="card-value">{total}</div></div>
            <div class="card"><div class="card-title">Passed</div><div class="card-value success">{passed}</div></div>
            <div class="card"><div class="card-title">Failed</div><div class="card-value {"failure" if failed else ""}">{failed}</div></div>
            <div class="card"><div class="card-title">Pass Rate</div><div class="card-value">{passed*100//total if total else 0}%</div></div>
        </div>
'''
    
    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        name = scenario.get("name", scenario_id)
        status = scenario.get("status", "UNKNOWN")
        duration = scenario.get("duration_ms", 0)
        steps = scenario.get("steps", [])
        verification = scenario.get("verification", {})
        artifacts = scenario.get("artifacts", {})
        scenario_dir = scenario.get("_dir", results_dir / scenario_id)
        
        status_class = "pass" if status == "PASS" else "fail"
        
        # Load screenshot
        screenshots = artifacts.get("screenshots", [])
        screenshot_html = ""
        if screenshots:
            screenshot_path = scenario_dir / screenshots[0]
            if screenshot_path.exists():
                img_data = encode_image(screenshot_path)
                screenshot_html = f'''
                <div class="screenshot-panel">
                    <div class="screenshot-label">📸 Final Screenshot</div>
                    <img src="{img_data}" class="screenshot" onclick="openModal(this.src)" alt="Screenshot">
                </div>'''
        
        html += f'''
        <div class="scenario">
            <div class="scenario-header">
                <div class="scenario-title">
                    <span class="badge {status_class}">{"✓ PASS" if status == "PASS" else "✗ FAIL"}</span>
                    <strong>{name}</strong>
                </div>
                <span style="color: var(--muted)">{duration/1000:.1f}s</span>
            </div>
            <div class="scenario-body">
                <div class="steps-panel">
                    <div style="color: var(--muted); font-size: 0.875rem; margin-bottom: 0.75rem;">Execution Steps</div>
'''
        
        for step in steps:
            step_num = step.get("step", "?")
            step_status = step.get("status", "unknown")
            status_class_step = "success" if step_status == "success" else "failure"
            action_html = format_action(step)
            
            html += f'''
                    <div class="step">
                        <div class="step-num {status_class_step}">{step_num}</div>
                        <div class="step-action">{action_html}</div>
                    </div>
'''
        
        # Verification
        if verification:
            v_passed = verification.get("passed", False)
            v_class = "pass" if v_passed else "fail"
            v_method = verification.get("method", "")
            v_expected = verification.get("expected", "")
            v_actual = verification.get("actual", "")[:100]
            
            html += f'''
                    <div class="verification {v_class}">
                        <div class="verification-title">Verification: {v_method}</div>
                        <div class="verification-content">Expected: {v_expected}
Actual: {v_actual}...</div>
                    </div>
'''
        
        # JSON view
        html += f'''
                    <details style="margin-top: 1rem;">
                        <summary style="cursor: pointer; color: var(--muted);">📋 Raw JSON Evidence</summary>
                        <div class="json-view"><pre>{json.dumps({k:v for k,v in scenario.items() if k != "_dir"}, indent=2)}</pre></div>
                    </details>
                </div>
                {screenshot_html}
            </div>
        </div>
'''
    
    html += '''
        <div style="text-align: center; color: var(--muted); margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border);">
            Goal-Driven Automation • E2E Test Report
        </div>
    </div>
    
    <div class="modal" id="imageModal" onclick="closeModal()">
        <span class="modal-close">&times;</span>
        <img id="modalImage" src="">
    </div>
    
    <script>
        function openModal(src) {
            document.getElementById('modalImage').src = src;
            document.getElementById('imageModal').classList.add('active');
        }
        function closeModal() {
            document.getElementById('imageModal').classList.remove('active');
        }
        document.addEventListener('keydown', e => { if(e.key === 'Escape') closeModal(); });
    </script>
</body>
</html>
'''
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    
    print(f"✓ Report generated: {output_path}")
    print(f"  Scenarios: {total} | Passed: {passed} | Failed: {failed}")


def main():
    results_dir = Path("test-results/2026-04-09")
    output_path = results_dir / "report.html"
    
    if not results_dir.exists():
        print(f"❌ Results directory not found: {results_dir}")
        return 1
    
    scenarios = load_scenarios(results_dir)
    if not scenarios:
        print("❌ No scenario evidence found")
        return 1
    
    print(f"Found {len(scenarios)} scenarios")
    generate_html(scenarios, results_dir, output_path)
    return 0


if __name__ == "__main__":
    exit(main())
