import sys
from pathlib import Path
import types
from datetime import datetime

# Ensure repository root is on path for importing test_suite
sys.path.append(str(Path(__file__).resolve().parent.parent))
import test_suite


def test_pdf_report_generation(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "report.html").write_text("<html><body>Test</body></html>")

    monkeypatch.chdir(tmp_path)

    # Stub out run_command to avoid external dependencies
    def fake_run_command(cmd, description):
        return 0
    monkeypatch.setattr(test_suite, "run_command", fake_run_command)

    # Stub pdfkit with a simple implementation
    def fake_from_file(input_path, output_path):
        Path(output_path).write_text("PDF")
    fake_pdfkit = types.SimpleNamespace(from_file=fake_from_file)
    monkeypatch.setitem(sys.modules, "pdfkit", fake_pdfkit)

    # Deterministic timestamps for unique filenames
    class DummyDateTime:
        def __init__(self):
            self.count = 0
        def now(self):
            dt = datetime(2024, 1, 1, 0, 0, self.count)
            self.count += 1
            return dt
    monkeypatch.setattr(test_suite, "datetime", DummyDateTime())

    def run_once():
        monkeypatch.setattr(sys, "argv", ["test_suite.py", "--report", "--pdf"])
        test_suite.main()

    run_once()
    run_once()

    pdf_files = list(data_dir.glob("report_*.pdf"))
    assert len(pdf_files) == 2
    names = {p.name for p in pdf_files}
    assert len(names) == 2
    for p in pdf_files:
        assert p.read_text() == "PDF"
