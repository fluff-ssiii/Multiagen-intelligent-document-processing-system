from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.exceptions import ExtractionError
from app.schemas.document_schema import PageImage


class FieldSpec(BaseModel):
    name: str
    description: str
    dtype: Literal["string", "integer", "amount", "date", "json"] = "string"
    required: bool = True

class DateOrderRule(BaseModel):
    earlier: str
    later: str


class AmountSumRule(BaseModel):
    """sum(add) - sum(subtract) must equal `equals`. e.g. subtotal + tax == total."""
    rule_id: str = "TOTALS_CONSISTENCY"
    add: list[str]
    subtract: list[str] = Field(default_factory=list)
    equals: str


class LineItemsRule(BaseModel):
    """`field` holds a JSON list of items; each item: quantity * unit_price == amount."""
    rule_id: str = "LINE_ITEMS_CONSISTENCY"
    field: str = "line_items"
    quantity_key: str = "quantity"
    unit_price_key: str = "unit_price"
    amount_key: str = "amount"
    sum_equals: Optional[str] = None   # e.g. "subtotal": sum of item amounts must match it

class DocumentTypeSpec(BaseModel):
    name: str
    description: str
    fields: list[FieldSpec]

    date_order_rules: list[DateOrderRule] = Field(default_factory=list)
    amount_sum_rules: list[AmountSumRule] = Field(default_factory=list)
    line_items_rule: Optional[LineItemsRule] = None
    duplicate_key_field: Optional[str] = None

    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]


# Field set mirrors the columns of processvenue/INVOICE_ANNOTATION_V2.
INVOICE_SPEC = DocumentTypeSpec(
    name="invoice",
    description="invoice",
    date_order_rules=[DateOrderRule(earlier="date_of_issue", later="date_due")],
    duplicate_key_field="invoice_number",
    fields=[
        FieldSpec(name="invoice_number", dtype="string",
                  description="The invoice or purchase-order number. Keep any prefix (e.g. PO-629227)."),
        FieldSpec(name="date_of_issue", dtype="date",
                  description="Date the invoice was issued, copied exactly as printed."),
        FieldSpec(name="date_due", dtype="date",
                  description="Payment due date, copied exactly as printed."),
        FieldSpec(name="client_name", dtype="string",
                  description="Name of the client/customer being billed (Bill To / Client), not the issuing company."),
        FieldSpec(name="client_address", dtype="string", required=False,
                  description="Address of the client as printed, on a single line. null if not shown."),
        FieldSpec(name="total_items", dtype="integer",
                  description="Total number of products/items on the invoice."),
        FieldSpec(name="total_amount", dtype="amount",
                  description="Final total amount payable, as printed."),
    ],
)

DOCUMENT_TYPES: dict[str, DocumentTypeSpec] = {"invoice": INVOICE_SPEC}


def get_document_type(name: str) -> DocumentTypeSpec:
    spec = DOCUMENT_TYPES.get(name)
    if spec is None:
        raise ExtractionError(
            f"Unknown document type '{name}'. Available: {', '.join(DOCUMENT_TYPES)}",
            code="UNKNOWN_DOCUMENT_TYPE", status_code=400,
        )
    return spec


class ExtractionInput(BaseModel):
    document_id: str
    document_type: str = "invoice"
    pages: list[PageImage]


class ExtractionOutput(BaseModel):
    document_id: str
    document_type: str
    extractor_name: str
    fields: dict[str, Optional[str]]
    missing_fields: list[str] = Field(default_factory=list)
    parse_ok: bool = True
    attempts: int = 1
    generation_ms: int = 0
    # Sequence-level signals from the model's token probabilities (not calibrated, not per-field).
    confidence: Optional[dict[str, Optional[float]]] = None
    raw_output: str = ""
    warnings: list[str] = Field(default_factory=list)