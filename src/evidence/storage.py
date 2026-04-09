"""
Evidence Storage - Persists run evidence to disk.
"""
import json
import platform
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .types import Environment, RunEvidence


class EvidenceStorage:
    """Stores and retrieves run evidence."""
    
    def __init__(self, runs_dir: Optional[Path] = None):
        """Initialize storage with runs directory."""
        if runs_dir is None:
            runs_dir = Path(__file__).parent.parent.parent / "runs"
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)
    
    def create_run(self, plan_id: str) -> RunEvidence:
        """
        Create a new run and its directory structure.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            RunEvidence with initialized paths
        """
        evidence = RunEvidence(plan_id=plan_id)
        run_dir = self.runs_dir / evidence.run_id
        
        # Create directory structure
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "screenshots").mkdir(exist_ok=True)
        (run_dir / "ui_trees").mkdir(exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)
        
        # Capture environment
        evidence.environment = self._capture_environment()
        evidence.artifacts_dir = f"runs/{evidence.run_id}"
        
        return evidence
    
    def _capture_environment(self) -> Environment:
        """Capture current environment details."""
        return Environment(
            os=platform.system(),
            os_version=platform.release(),
            hostname=socket.gethostname(),
            executor_version="1.0.0",
        )
    
    def save_evidence(self, evidence: RunEvidence) -> Path:
        """
        Save run evidence to disk.
        
        Args:
            evidence: RunEvidence to save
            
        Returns:
            Path to saved evidence.json
        """
        run_dir = self.runs_dir / evidence.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save evidence.json
        evidence_path = run_dir / "evidence.json"
        with open(evidence_path, "w") as f:
            json.dump(evidence.to_dict(), f, indent=2)
        
        return evidence_path
    
    def save_input_plan(self, run_id: str, plan: Dict[str, Any]) -> Path:
        """
        Save the input plan for a run.
        
        Args:
            run_id: Run identifier
            plan: Plan dictionary
            
        Returns:
            Path to saved input_plan.json
        """
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        plan_path = run_dir / "input_plan.json"
        with open(plan_path, "w") as f:
            json.dump(plan, f, indent=2)
        
        return plan_path
    
    def load_evidence(self, run_id: str) -> Optional[RunEvidence]:
        """
        Load evidence for a run.
        
        Args:
            run_id: Run identifier
            
        Returns:
            RunEvidence or None if not found
        """
        evidence_path = self.runs_dir / run_id / "evidence.json"
        if not evidence_path.exists():
            return None
        
        with open(evidence_path, "r") as f:
            data = json.load(f)
        
        # Convert back to RunEvidence (simplified)
        evidence = RunEvidence(
            evidence_id=data.get("evidence_id", ""),
            plan_id=data.get("plan_id", ""),
            run_id=data.get("run_id", run_id),
        )
        return evidence
    
    def list_runs(self, limit: int = 50) -> list:
        """
        List recent runs.
        
        Args:
            limit: Maximum runs to return
            
        Returns:
            List of run summaries
        """
        runs = []
        for run_dir in sorted(self.runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            if run_dir.name.startswith("."):
                continue
            
            evidence_path = run_dir / "evidence.json"
            if evidence_path.exists():
                with open(evidence_path, "r") as f:
                    data = json.load(f)
                runs.append({
                    "run_id": data.get("run_id"),
                    "plan_id": data.get("plan_id"),
                    "status": data.get("status"),
                    "started_at": data.get("started_at"),
                    "duration_ms": data.get("duration_ms"),
                })
            
            if len(runs) >= limit:
                break
        
        return runs
    
    def get_run_dir(self, run_id: str) -> Path:
        """Get the directory path for a run."""
        return self.runs_dir / run_id
    
    def cleanup_old_runs(self, keep_days: int = 30) -> int:
        """
        Clean up runs older than specified days.
        
        Args:
            keep_days: Number of days to keep
            
        Returns:
            Number of runs deleted
        """
        import shutil
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        deleted = 0
        
        for run_dir in self.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            
            evidence_path = run_dir / "evidence.json"
            if evidence_path.exists():
                with open(evidence_path, "r") as f:
                    data = json.load(f)
                started_at = data.get("started_at")
                if started_at:
                    run_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    if run_time < cutoff:
                        shutil.rmtree(run_dir)
                        deleted += 1
        
        return deleted
