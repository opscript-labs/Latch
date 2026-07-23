import logging
from collections.abc import Callable
from typing import Any

from latch.application.retirement_admission_adapter import RetirementAdmissionAdapter

logger = logging.getLogger("latch.retirement_admission_lambda")


def create_lambda_handler(
    adapter: RetirementAdmissionAdapter,
    default_producer_authority: str | None = None,
) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    """Creates a Lambda handler that delegates to the RetirementAdmissionAdapter."""
    if not isinstance(adapter, RetirementAdmissionAdapter):
        raise TypeError("adapter must be a RetirementAdmissionAdapter")

    def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        if not isinstance(event, dict):
            logger.error("Event must be a dictionary")
            return {"error": "Malformed transport payload"}

        try:
            return adapter.handle(event, producer_authority=default_producer_authority)
        except ValueError as error:
            logger.error(f"Transport validation error: {error}")
            return {"error": "Malformed transport payload"}
        except Exception as error:
            logger.error(f"Unexpected internal failure: {error}")
            return {"error": "Internal error"}

    return handler
