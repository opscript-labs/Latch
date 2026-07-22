from latch.domain.evidence import Evidence


def test_evidence_is_importable_from_latch_evidence_domain_namespace() -> None:
    assert Evidence.__name__ == "Evidence"


def test_evidence_is_defined_in_latch_domain_not_provider_package() -> None:
    assert Evidence.__module__ == "latch.domain.evidence.evidence"
