from met_qc.filenames import parse_raw_filename, parse_header_filename


def test_parse_raw_and_header():
    raw = parse_raw_filename("GL-ZaF_BM_20250103_L05_F02.dat")
    assert raw and raw.site == "GL-ZaF" and raw.level == "L05" and raw.file == "F02"
    hdr = parse_header_filename("GL-ZaF_BMHEADER_202501011200_L05_F02.csv")
    assert hdr and hdr.site == "GL-ZaF" and hdr.level == "L05" and hdr.file == "F02"
    # Misspelling should also parse
    hdr2 = parse_header_filename("GL-ZaF_BMHEARDER_202501011200_L05_F02.csv")
    assert hdr2 and hdr2.valid_from.year == 2025
