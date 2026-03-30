from sqlalchemy import Column, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ExtractedLineItem(Base):
    __tablename__ = "extracted_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("extracted_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    description = Column(Text)
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_price = Column(Float)
    confidence = Column(Float)

    document = relationship("ExtractedDocument", back_populates="line_items")
