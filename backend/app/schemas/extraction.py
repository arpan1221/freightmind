from pydantic import BaseModel


class DeleteExtractionResponse(BaseModel):
    extraction_id: int
    deleted: bool = True
    message: str
