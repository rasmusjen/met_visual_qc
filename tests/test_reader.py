from met_visual_qc.reader import read_csv
from pathlib import Path

def test_read_csv(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("a,b\n1,2\n3,4\n")
    df = read_csv(str(p))
    assert df.shape == (2,2)
