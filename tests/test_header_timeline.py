from datetime import datetime
from met_qc.headers import build_header_timeline
from met_qc.filenames import HeaderFileId
from pathlib import Path


def test_timeline_resolve(tmp_path: Path):
    # create two header csvs with different valid_from
    h1 = tmp_path / "GL-ZaF_BMHEADER_202501010000_L05_F02.csv"
    h2 = tmp_path / "GL-ZaF_BMHEADER_202501030000_L05_F02.csv"
    h1.write_text("index,name\n0,TIMESTAMP\n1,VarA\n")
    h2.write_text("index,name\n0,TIMESTAMP\n1,VarB\n")
    tl = build_header_timeline(str(tmp_path))
    # date Jan 2 -> VarA
    cols = tl.resolve("GL-ZaF", "L05", "F02", datetime(2025,1,2))
    assert cols and cols[1].name == "VarA"
    # date Jan 4 -> VarB
    cols2 = tl.resolve("GL-ZaF", "L05", "F02", datetime(2025,1,4))
    assert cols2 and cols2[1].name == "VarB"
