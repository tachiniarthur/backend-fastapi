from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Intercepts Pydantic/FastAPI validation errors and reformats them
    from the default FastAPI format to the Laravel validation error format.

    FastAPI default: {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
    Laravel format:  {"message": "The given data was invalid.", "errors": {"field": ["msg"]}}
    """
    errors: dict[str, list[str]] = {}

    for err in exc.errors():
        # err["loc"] is a tuple like ("body", "field_name") or ("body", "items", 0, "field_name")
        # Skip the "body" prefix and use the last element as the field name
        loc = err.get("loc", ())
        if loc and loc[0] == "body":
            loc = loc[1:]

        field = str(loc[-1]) if loc else "unknown"
        msg = err.get("msg", "")

        if field not in errors:
            errors[field] = []
        errors[field].append(msg)

    return JSONResponse(
        status_code=422,
        content={
            "message": "The given data was invalid.",
            "errors": errors,
        },
    )


def register_exception_handlers(app) -> None:
    """Register custom exception handlers on the FastAPI app instance."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
