from app.agents.pii_scrub import scrub


def test_scrubs_afm_amka_amounts_dates_names():
    text = ("Ο Ιωάννης Παπαδόπουλος με ΑΦΜ 123456789 και ΑΜΚΑ 12345678901 "
            "οφείλει 14.500,00 € από 01/06/2026, υπόθεση 123/2026.")
    out, reps = scrub(text)
    for bad in ["123456789", "12345678901", "14.500,00", "01/06/2026",
                "Παπαδόπουλος", "123/2026"]:
        assert bad not in out
    assert "⟨ΑΦΜ⟩" in out and "⟨ΟΝΟΜΑ⟩" in out and "⟨ΠΟΣΟ⟩" in out
    assert len(reps) >= 5


def test_keeps_legal_caps():
    out, _ = scrub("ΕΝΩΠΙΟΝ ΤΟΥ ΜΟΝΟΜΕΛΟΥΣ ΠΡΩΤΟΔΙΚΕΙΟΥ")
    assert "ΕΝΩΠΙΟΝ" in out
