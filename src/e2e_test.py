#!/usr/bin/env python3
"""E2E Real Test - Uses actual fsq-mac CLI."""
import subprocess
import time
from pathlib import Path
from datetime import datetime


class RealE2ETest:
    def __init__(self, mac_cli: str = "mac"):
        self.mac_cli = mac_cli
    
    def run_command(self, cmd: str, timeout: int = 30) -> dict:
        print(f"  > {cmd}")
        start = time.time()
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            duration = int((time.time() - start) * 1000)
            success = result.returncode == 0
            print(f"    {'✓' if success else '✗'} ({duration}ms)")
            if result.stderr and not success:
                print(f"    Error: {result.stderr[:100]}")
            return {"command": cmd, "success": success, "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr, "duration_ms": duration}
        except subprocess.TimeoutExpired:
            print(f"    ✗ Timeout")
            return {"command": cmd, "success": False, "error": "timeout"}
        except Exception as e:
            print(f"    ✗ Error: {e}")
            return {"command": cmd, "success": False, "error": str(e)}
    
    def test_finder_new_folder(self):
        """场景1: Finder 创建新文件夹"""
        print("\n" + "="*60)
        print("场景1: Finder 创建新文件夹")
        print("="*60)
        
        test_folder = f"TestFolder_{datetime.now().strftime('%H%M%S')}"
        steps = []
        
        print("\n[Step 1] 启动 Finder...")
        result = self.run_command(f"{self.mac_cli} app launch com.apple.finder")
        steps.append(result)
        time.sleep(1.5)
        
        print("\n[Step 2] 切换到桌面 (Cmd+Shift+D)...")
        result = self.run_command(f"{self.mac_cli} input hotkey command+shift+d")
        steps.append(result)
        time.sleep(0.5)
        
        print("\n[Step 3] 创建新文件夹 (Cmd+Shift+N)...")
        result = self.run_command(f"{self.mac_cli} input hotkey command+shift+n")
        steps.append(result)
        time.sleep(0.5)
        
        print(f"\n[Step 4] 输入文件夹名: {test_folder}...")
        result = self.run_command(f'{self.mac_cli} input text "{test_folder}"')
        steps.append(result)
        time.sleep(0.3)
        
        print("\n[Step 5] 按 Enter 确认...")
        result = self.run_command(f"{self.mac_cli} input key return")
        steps.append(result)
        time.sleep(0.5)
        
        print("\n[Step 6] 验证文件夹存在...")
        desktop = Path.home() / "Desktop" / test_folder
        if desktop.exists():
            print(f"    ✓ 文件夹存在: {desktop}")
            steps.append({"command": "verify", "success": True, "path": str(desktop)})
            desktop.rmdir()
            print(f"    ✓ 已清理测试文件夹")
        else:
            print(f"    ✗ 文件夹不存在: {desktop}")
            steps.append({"command": "verify", "success": False, "path": str(desktop)})
        
        passed = sum(1 for s in steps if s.get("success"))
        total = len(steps)
        success = passed == total
        
        print("\n" + "-"*60)
        print(f"结果: {'✓ 通过' if success else '✗ 失败'} ({passed}/{total} 步骤)")
        print("-"*60)
        
        return {"scenario": "finder_new_folder", "success": success, "steps": steps}


def main():
    print("\n" + "="*60)
    print("GOAL-DRIVEN AUTOMATION - 真实 E2E 测试")
    print("="*60)
    
    tester = RealE2ETest()
    result1 = tester.test_finder_new_folder()
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)


if __name__ == "__main__":
    main()
