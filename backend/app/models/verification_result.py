from sqlalchemy import Column, Float, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import relationship

from app.core.database import Base


class VerificationResult(Base):
    """One row per SU document verification run.

    Minimum schema from assignment spec — extended with error_message for
    failed-pipeline storage and customer_name for display convenience.
    """

    __tablename__ = "verification_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Text, nullable=False)
    received_at = Column(Text, nullable=False)
    customer_id = Column(Text, nullable=False)
    customer_name = Column(Text)
    overall_status = Column(
        Text, nullable=False
    )  # approved | amendment_required | uncertain | failed
    draft_reply = Column(Text)
    error_message = Column(Text)  # populated only on status=failed
    created_at = Column(Text, server_default=text("(datetime('now'))"))

    fields = relationship(
        "VerificationField",
        back_populates="result",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_verif_customer", "customer_id"),
        Index("idx_verif_status", "overall_status"),
        Index("idx_verif_received", "received_at"),
    )


class VerificationField(Base):
    """One row per field checked in a verification run.

    Stores what was extracted, what was expected, and the comparison outcome.
    The analytics layer queries this table for patterns like
    "which fields failed most often this week?".
    """

    __tablename__ = "verification_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    verification_id = Column(
        Integer,
        ForeignKey("verification_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    extracted = Column(Text)
    expected = Column(Text)
    status = Column(Text, nullable=False)  # match | mismatch | uncertain | no_rule
    confidence = Column(Float, nullable=False)
    rule_description = Column(Text)
    source_document = Column(Text)  # e.g. "Commercial Invoice", "Bill of Lading", "Packing List"

    result = relationship("VerificationResult", back_populates="fields")

    __table_args__ = (
        Index("idx_vfield_verification", "verification_id"),
        Index("idx_vfield_status", "status"),
        Index("idx_vfield_name", "name"),
    )
