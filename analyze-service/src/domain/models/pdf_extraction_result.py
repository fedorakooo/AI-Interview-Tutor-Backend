from pydantic import BaseModel, Field


class PDFExtractionResult(BaseModel):
    text: str
    method: str = "docling"
    page_count: int = Field(ge=0)
    char_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
