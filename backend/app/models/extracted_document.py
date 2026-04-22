from sqlalchemy import Column, Integer, Text, Float, Index, text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ExtractedDocument(Base):
    __tablename__ = "extracted_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_filename = Column(Text, nullable=False)
    invoice_number = Column(Text)
    invoice_date = Column(Text)
    shipper_name = Column(Text)
    consignee_name = Column(Text)
    origin_country = Column(Text)
    destination_country = Column(Text)
    shipment_mode = Column(Text)
    carrier_vendor = Column(Text)
    total_weight_kg = Column(Float)
    total_freight_cost_usd = Column(Float)
    total_insurance_usd = Column(Float)
    payment_terms = Column(Text)
    delivery_date = Column(Text)
    hs_code = Column(Text)
    port_of_loading = Column(Text)
    port_of_discharge = Column(Text)
    incoterms = Column(Text)
    description_of_goods = Column(Text)
    extraction_confidence = Column(Float)
    extracted_at = Column(Text, server_default=text("(datetime('now'))"))
    confirmed_by_user = Column(Integer, default=0, server_default="0")
    # Multi-document support: commercial_invoice | bill_of_lading | packing_list
    document_type = Column(Text, nullable=False, server_default="commercial_invoice")
    # Bill of Lading specific fields
    bl_number = Column(Text)
    vessel_name = Column(Text)
    container_numbers = Column(Text)
    # Packing List specific fields
    package_count = Column(Integer)

    line_items = relationship(
        "ExtractedLineItem",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_extracted_destination", "destination_country"),
        Index("idx_extracted_shipment_mode", "shipment_mode"),
    )
