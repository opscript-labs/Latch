from enum import StrEnum


class AdmissionVerdict(StrEnum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    INSUFFICIENT = "insufficient"
