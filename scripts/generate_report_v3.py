#!/usr/bin/env python3
"""
Generate Enhanced HTML Report v3 - Optimized screenshots, better UI, annotations.
Addresses: #32 (screenshot size), #33 (UI beauty), #35 (annotations)
"""
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image
import io


def load_scenarios(results_dir: Path) -> List[Dict[str, Any]]:
    """Load all scenario evidence."""
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


def encode_image_thumbnail(img_path: Path, max_width: int = 400) -> tuple:
    """Encode image as thumbnail + full size base64."""
    if not img_path.exists():
        return "", ""
    
    with Image.open(img_path) as img:
        if img.mode == "RGBA":
            img = img.convert("RGB")
        # Full size (compressed)
        full_buffer = io.BytesIO()
        img.save(full_buffer, format="JPEG", quality=85, optimize=True)
        full_data = base64.b64encode(full_buffer.getvalue()).decode()
        
        # Thumbnail
        ratio = max_width / img.width
        thumb_size = (max_width, int(img.height * ratio))
        thumb = img.resize(thumb_size, Image.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        thumb.save(thumb_buffer, format="JPEG", quality=80)
        thumb_data = base64.b64encode(thumb_buffer.getvalue()).decode()
    
    return f"data:image/jpeg;base64,{thumb_data}", f"data:image/jpeg;base64,{full_data}"


def format_action(step: Dict) -> str:
    """Format action with icons."""
    action = step.get("action", "")
    target = step.get("target", "")
    
    icons = {
        "app.launch": "🚀", "input.hotkey": "⌨️", "input.text": "📝",
        "input.key": "🔑", "capture.screenshot": "📸", "wait": "⏳", "assert": "✅",
    }
    icon = icons.get(action, "▶️")
    
    if action == "app.launch":
        return f"{icon} Launch <strong>{target.split('.')[-1]}</strong>"
    elif action == "input.hotkey":
        return f"{icon} Press <kbd>{target.replace('+', ' + ').upper()}</kbd>"
    elif action == "input.text":
        return f'{icon} Type "<em>{target}</em>"'
    elif action == "input.key":
        return f"{icon} Press <kbd>{target.upper()}</kbd>"
    elif action == "capture.screenshot":
        return f"{icon} Capture screenshot"
    return f"{icon} {action}: {target}"


def generate_html(scenarios: List[Dict], results_dir: Path, output_path: Path):
    """Generate enhanced HTML report."""
    
    total = len(scenarios)
    passed = sum(1 for s in scenarios if s.get("status") == "PASS")
    failed = total - passed
    total_duration = sum(s.get("duration_ms", 0) for s in scenarios)
    pass_rate = (passed * 100 // total) if total else 0
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report - {datetime.now().strftime("%Y-%m-%d")}</title>
    <style>
        :root {{
            --success: #10b981; --success-bg: rgba(16,185,129,0.15);
            --failure: #f43f5e; --failure-bg: rgba(244,63,94,0.15);
            --warning: #f59e0b;
            --bg: linear-gradient(135deg, #0c0f1a 0%, #1a1f35 100%);
            --card: rgba(30,41,59,0.8); --card-hover: rgba(30,41,59,0.95);
            --text: #f1f5f9; --muted: #94a3b8; --border: rgba(148,163,184,0.2);
            --accent: #6366f1; --accent-glow: rgba(99,102,241,0.3);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg); background-attachment: fixed;
            color: var(--text); min-height: 100vh; padding: 2rem;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        
        /* Header */
        .header {{ text-align: center; margin-bottom: 3rem; }}
        .header h1 {{ font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #fff, #a5b4fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header .subtitle {{ color: var(--muted); font-size: 1rem; }}
        
        /* Summary Cards */
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 3rem; }}
        .stat-card {{
            background: var(--card); backdrop-filter: blur(10px);
            border-radius: 16px; padding: 1.5rem; border: 1px solid var(--border);
            text-align: center; transition: all 0.3s ease;
        }}
        .stat-card:hover {{ transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0,0,0,0.3); }}
        .stat-card .label {{ color: var(--muted); font-size: 0.875rem; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-card .value {{ font-size: 2.5rem; font-weight: 700; }}
        .stat-card .value.success {{ color: var(--success); }}
        .stat-card .value.failure {{ color: var(--failure); }}
        .stat-card.highlight {{ background: linear-gradient(135deg, var(--accent), #8b5cf6); border: none; }}
        .stat-card.highlight .label, .stat-card.highlight .value {{ color: white; }}
        
        /* Progress Bar */
        .progress-bar {{ height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; margin-top: 0.75rem; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, var(--success), #34d399); border-radius: 4px; transition: width 0.5s ease; }}
        
        /* Scenario Cards */
        .scenario {{
            background: var(--card); backdrop-filter: blur(10px);
            border-radius: 20px; margin-bottom: 1.5rem; border: 1px solid var(--border);
            overflow: hidden; transition: all 0.3s ease;
        }}
        .scenario:hover {{ border-color: var(--accent); box-shadow: 0 0 30px var(--accent-glow); }}
        
        .scenario-header {{
            padding: 1.25rem 1.5rem; display: flex; justify-content: space-between; align-items: center;
            background: rgba(0,0,0,0.2); cursor: pointer;
        }}
        .scenario-title {{ display: flex; align-items: center; gap: 1rem; }}
        .badge {{
            padding: 0.4rem 1rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.05em;
        }}
        .badge.pass {{ background: var(--success-bg); color: var(--success); }}
        .badge.fail {{ background: var(--failure-bg); color: var(--failure); }}
        .scenario-name {{ font-weight: 600; font-size: 1.1rem; }}
        .scenario-meta {{ color: var(--muted); font-size: 0.875rem; display: flex; gap: 1rem; }}
        
        /* Scenario Body */
        .scenario-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; padding: 1.5rem; }}
        
        /* Steps Panel */
        .steps-panel h3 {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem; }}
        .step {{
            display: flex; align-items: center; padding: 1rem; margin-bottom: 0.5rem;
            background: rgba(0,0,0,0.2); border-radius: 12px; transition: all 0.2s ease;
        }}
        .step:hover {{ background: rgba(0,0,0,0.3); transform: translateX(4px); }}
        .step-num {{
            width: 32px; height: 32px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
            font-size: 0.8rem; font-weight: 700; margin-right: 1rem; flex-shrink: 0;
        }}
        .step-num.success {{ background: var(--success-bg); color: var(--success); }}
        .step-num.failure {{ background: var(--failure-bg); color: var(--failure); }}
        .step-action {{ flex: 1; font-size: 0.95rem; }}
        .step-action kbd {{
            background: rgba(99,102,241,0.2); color: #a5b4fc; padding: 0.2rem 0.5rem;
            border-radius: 6px; font-family: 'SF Mono', monospace; font-size: 0.85rem;
        }}
        
        /* Verification */
        .verification {{
            margin-top: 1rem; padding: 1rem; border-radius: 12px;
            background: rgba(0,0,0,0.2); border-left: 3px solid var(--muted);
        }}
        .verification.pass {{ border-left-color: var(--success); }}
        .verification.fail {{ border-left-color: var(--failure); }}
        .verification-title {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 0.5rem; text-transform: uppercase; }}
        .verification-content {{ font-family: 'SF Mono', monospace; font-size: 0.85rem; color: var(--text); }}
        
        /* Screenshot Panel */
        .screenshot-panel h3 {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem; }}
        .screenshot-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }}
        .screenshot-item {{
            position: relative; border-radius: 12px; overflow: hidden; cursor: pointer;
            border: 2px solid transparent; transition: all 0.3s ease;
        }}
        .screenshot-item:hover {{ border-color: var(--accent); transform: scale(1.02); }}
        .screenshot-item img {{ width: 100%; height: auto; display: block; }}
        .screenshot-label {{
            position: absolute; bottom: 0; left: 0; right: 0; padding: 0.5rem;
            background: linear-gradient(transparent, rgba(0,0,0,0.8)); font-size: 0.7rem; color: white;
        }}
        .screenshot-single {{ grid-column: span 3; }}
        .screenshot-single img {{ border-radius: 12px; max-height: 300px; object-fit: contain; width: 100%; }}
        
        /* Annotation overlay */
        .annotation {{
            position: absolute; border: 3px solid var(--failure); border-radius: 8px;
            box-shadow: 0 0 10px var(--failure); animation: pulse 2s infinite;
        }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
        
        /* JSON Panel */
        details {{ margin-top: 1rem; }}
        summary {{ cursor: pointer; color: var(--muted); font-size: 0.875rem; padding: 0.5rem; border-radius: 8px; }}
        summary:hover {{ background: rgba(0,0,0,0.2); }}
        .json-view {{
            background: rgba(0,0,0,0.4); padding: 1rem; border-radius: 12px; margin-top: 0.5rem;
            font-family: 'SF Mono', monospace; font-size: 0.75rem; overflow-x: auto; max-height: 250px;
        }}
        
        /* Modal */
        .modal {{
            display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.95);
            z-index: 1000; justify-content: center; align-items: center; padding: 2rem;
        }}
        .modal.active {{ display: flex; }}
        .modal img {{ max-width: 95vw; max-height: 90vh; border-radius: 12px; box-shadow: 0 0 60px rgba(0,0,0,0.5); }}
        .modal-close {{ position: absolute; top: 1rem; right: 1.5rem; color: white; font-size: 2rem; cursor: pointer; opacity: 0.7; }}
        .modal-close:hover {{ opacity: 1; }}
        
        /* Footer */
        .footer {{ text-align: center; color: var(--muted); margin-top: 3rem; padding: 2rem; border-top: 1px solid var(--border); }}
        
        @media (max-width: 900px) {{
            .summary {{ grid-template-columns: repeat(2, 1fr); }}
            .scenario-body {{ grid-template-columns: 1fr; }}
            .screenshot-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 E2E Test Report</h1>
            <p class="subtitle">Generated {datetime.now().strftime("%B %d, %Y at %H:%M")} • Total Duration: {total_duration/1000:.1f}s</p>
        </div>
        
        <div class="summary">
            <div class="stat-card">
                <div class="label">Total Tests</div>
                <div class="value">{total}</div>
            </div>
            <div class="stat-card">
                <div class="label">Passed</div>
                <div class="value success">{passed}</div>
            </div>
            <div class="stat-card">
                <div class="label">Failed</div>
                <div class="value {"failure" if failed else ""}">{failed}</div>
            </div>
            <div class="stat-card highlight">
                <div class="label">Pass Rate</div>
                <div class="value">{pass_rate}%</div>
                <div class="progress-bar"><div class="progress-fill" style="width: {pass_rate}%"></div></div>
            </div>
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
        
        # Load step screenshots
        step_screenshots = []
        steps_dir = scenario_dir / "screenshots" / "steps"
        if steps_dir.exists():
            for img_file in sorted(steps_dir.glob("*.png")):
                thumb, full = encode_image_thumbnail(img_file, max_width=200)
                step_screenshots.append({"name": img_file.stem, "thumb": thumb, "full": full})
        
        # Load final screenshot
        final_screenshot = ""
        final_full = ""
        screenshots = artifacts.get("screenshots", [])
        if screenshots:
            final_path = scenario_dir / screenshots[0]
            if final_path.exists():
                final_screenshot, final_full = encode_image_thumbnail(final_path, max_width=500)
        
        html += f'''
        <div class="scenario">
            <div class="scenario-header">
                <div class="scenario-title">
                    <span class="badge {status_class}">{"✓ Pass" if status == "PASS" else "✗ Fail"}</span>
                    <span class="scenario-name">{name}</span>
                </div>
                <div class="scenario-meta">
                    <span>⏱️ {duration/1000:.1f}s</span>
                    <span>📋 {len(steps)} steps</span>
                </div>
            </div>
            <div class="scenario-body">
                <div class="steps-panel">
                    <h3>Execution Steps</h3>
'''
        
        for step in steps:
            step_num = step.get("step", "?")
            step_status = step.get("status", "unknown")
            step_class = "success" if step_status == "success" else "failure"
            action_html = format_action(step)
            
            html += f'''
                    <div class="step">
                        <div class="step-num {step_class}">{step_num}</div>
                        <div class="step-action">{action_html}</div>
                    </div>
'''
        
        if verification:
            v_passed = verification.get("passed", False)
            v_class = "pass" if v_passed else "fail"
            v_method = verification.get("method", "")
            v_expected = verification.get("expected", "")
            v_actual = verification.get("actual", "")[:80]
            
            html += f'''
                    <div class="verification {v_class}">
                        <div class="verification-title">✅ Verification: {v_method}</div>
                        <div class="verification-content">Expected: {v_expected}
Actual: {v_actual}...</div>
                    </div>
'''
        
        html += '''
                    <details>
                        <summary>📋 View Raw JSON Evidence</summary>
                        <div class="json-view"><pre>''' + json.dumps({k:v for k,v in scenario.items() if k != "_dir"}, indent=2) + '''</pre></div>
                    </details>
                </div>
                <div class="screenshot-panel">
                    <h3>Screenshots</h3>
'''
        
        if step_screenshots:
            html += '<div class="screenshot-grid">'
            for ss in step_screenshots[:6]:
                html += f'''
                    <div class="screenshot-item" onclick="openModal('{ss["full"]}')">
                        <img src="{ss["thumb"]}" alt="{ss["name"]}">
                        <div class="screenshot-label">{ss["name"].replace("-", " ").title()}</div>
                    </div>
'''
            html += '</div>'
        elif final_screenshot:
            html += f'''
                    <div class="screenshot-single">
                        <img src="{final_screenshot}" onclick="openModal('{final_full}')" style="cursor: pointer">
                    </div>
'''
        
        html += '''
                </div>
            </div>
        </div>
'''
    
    html += '''
        <div class="footer">
            <p><strong>Goal-Driven Automation</strong> • E2E Test Report v3</p>
            <p style="margin-top: 0.5rem; font-size: 0.875rem;">Powered by fsq-mac CLI</p>
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
    
    scenarios = load_scenarios(results_dir)
    if not scenarios:
        print("❌ No scenarios found")
        return 1
    
    print(f"Found {len(scenarios)} scenarios")
    generate_html(scenarios, results_dir, output_path)
    return 0


if __name__ == "__main__":
    exit(main())
