#!/usr/bin/env python3
import os
import sys
import pytest
import datetime
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DIR = PROJECT_ROOT / "tests"
REPORT_DIR = PROJECT_ROOT / "documentations" / "test-reports"
VERSION = os.getenv("PROJECT_VERSION", "v0.0.1")  # Default version

def setup_directories():
    """Ensure report directories exist."""
    version_dir = REPORT_DIR / VERSION
    version_dir.mkdir(parents=True, exist_ok=True)
    return version_dir

def generate_report_header(file_handle):
    """Write the standard report header."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_handle.write(f"# Test Report: {VERSION}\n\n")
    file_handle.write(f"- **Date**: {now}\n")
    file_handle.write(f"- **Environment**: {sys.platform}\n")
    file_handle.write(f"- **Tester**: Automated Test Runner\n\n")
    file_handle.write("---\n\n")

class ReportPlugin:
    """Pytest plugin to capture results and write to Markdown."""
    def __init__(self, file_handle):
        self.file_handle = file_handle
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            status = "PASS"
            if report.failed:
                status = "FAIL"
                self.failed += 1
            elif report.skipped:
                status = "SKIP"
                self.skipped += 1
            else:
                self.passed += 1
            
            self.results.append((report.nodeid, status, report.longrepr))

    def write_summary(self):
        self.file_handle.write("## Summary\n\n")
        self.file_handle.write(f"| Total | Pass | Fail | Skip |\n")
        self.file_handle.write(f"| :---: | :--: | :--: | :--: |\n")
        self.file_handle.write(f"| {len(self.results)} | {self.passed} | {self.failed} | {self.skipped} |\n\n")

    def write_details(self):
        self.file_handle.write("## Test Details\n\n")
        for nodeid, status, error in self.results:
            icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
            self.file_handle.write(f"### {icon} {nodeid}\n")
            self.file_handle.write(f"- **Result**: {status}\n")
            if error:
                self.file_handle.write(f"- **Error**:\n```\n{error}\n```\n")
            self.file_handle.write("\n")

def main():
    print(f"🚀 Starting Test Runner for {VERSION}...")
    
    # 1. Setup
    report_dir = setup_directories()
    report_file_name = f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = report_dir / report_file_name
    
    print(f"📄 Report will be saved to: {report_path}")

    # 2. Run Tests & Generate Report
    with open(report_path, "w", encoding="utf-8") as f:
        generate_report_header(f)
        
        plugin = ReportPlugin(f)
        
        # Run pytest (suppress default output to keep console clean, or remove -q to see it)
        exit_code = pytest.main([str(TEST_DIR), "-q"], plugins=[plugin])
        
        plugin.write_summary()
        plugin.write_details()

    # 3. Console Summary
    print("\n" + "="*30)
    if plugin.failed > 0:
        print(f"❌ FAILED: {plugin.failed} tests failed.")
    else:
        print(f"✅ SUCCESS: All {plugin.passed} tests passed!")
    print(f"📊 Detailed Report: {report_path}")
    print("="*30 + "\n")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
