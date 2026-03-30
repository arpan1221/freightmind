from sqlalchemy import Column, Integer, Text, Float, Index

from app.core.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)  # CSV id — NOT autoincrement
    project_code = Column(Text, nullable=False)
    pq_number = Column(Text)
    po_so_number = Column(Text)
    asn_dn_number = Column(Text)
    country = Column(Text, nullable=False)
    managed_by = Column(Text, nullable=False)
    fulfill_via = Column(Text, nullable=False)
    vendor_inco_term = Column(Text)
    shipment_mode = Column(Text)  # nullable: real CSV has 360 rows with no shipment mode
    pq_first_sent_to_client_date = Column(Text)
    po_sent_to_vendor_date = Column(Text)
    scheduled_delivery_date = Column(Text)
    delivered_to_client_date = Column(Text)
    delivery_recorded_date = Column(Text)
    product_group = Column(Text, nullable=False)
    sub_classification = Column(Text)
    vendor = Column(Text, nullable=False)
    item_description = Column(Text)
    molecule_test_type = Column(Text)
    brand = Column(Text)
    dosage = Column(Text)
    dosage_form = Column(Text)
    unit_of_measure_per_pack = Column(Integer)
    line_item_quantity = Column(Integer, nullable=False)
    line_item_value = Column(Float, nullable=False)
    pack_price = Column(Float)
    unit_price = Column(Float)
    manufacturing_site = Column(Text)
    first_line_designation = Column(Text)
    weight_kg = Column(Float)         # NULL after cleaning non-numeric CSV values
    freight_cost_usd = Column(Float)  # NULL after cleaning non-numeric CSV values
    line_item_insurance_usd = Column(Float)

    __table_args__ = (
        Index("idx_shipments_country", "country"),
        Index("idx_shipments_shipment_mode", "shipment_mode"),
        Index("idx_shipments_vendor", "vendor"),
        Index("idx_shipments_product_group", "product_group"),
        Index("idx_shipments_scheduled_delivery", "scheduled_delivery_date"),
    )
