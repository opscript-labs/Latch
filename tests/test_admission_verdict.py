from latch.domain.admission import AdmissionVerdict


def test_admission_verdict_defines_exact_stable_members() -> None:
    assert list(AdmissionVerdict) == [
        AdmissionVerdict.SAFE,
        AdmissionVerdict.UNSAFE,
        AdmissionVerdict.INSUFFICIENT,
    ]


def test_admission_verdict_serializes_to_lowercase_strings() -> None:
    assert AdmissionVerdict.SAFE.value == "safe"
    assert AdmissionVerdict.UNSAFE.value == "unsafe"
    assert AdmissionVerdict.INSUFFICIENT.value == "insufficient"
