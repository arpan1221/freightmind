import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SqlDisclosure from "./SqlDisclosure";

/** Cross-table style SQL (FR28): both linkage tables referenced, multi-line. */
const LINKAGE_SQL = `SELECT s.country, e.invoice_number, e.total_freight_cost_usd
FROM shipments s
INNER JOIN extracted_documents e
  ON s.shipment_mode = e.shipment_mode
WHERE e.confirmed_by_user = 1`;

describe("SqlDisclosure", () => {
  it("renders full linkage SQL with both shipments and extracted_documents visible", () => {
    const { container } = render(<SqlDisclosure sql={LINKAGE_SQL} />);
    const text = container.textContent ?? "";
    expect(text).toContain("shipments");
    expect(text).toContain("extracted_documents");
  });

  it("renders single-table SQL without adding extra table names", () => {
    const sql = "SELECT COUNT(*) FROM shipments WHERE country = 'NG'";
    const { container } = render(<SqlDisclosure sql={sql} />);
    expect(container.textContent).toContain("shipments");
    expect(container.textContent).not.toContain("extracted_documents");
  });

  it("uses details hidden by default (no open attribute)", () => {
    const { container } = render(<SqlDisclosure sql="SELECT 1" />);
    const details = container.querySelector("details");
    expect(details).toBeTruthy();
    expect(details).not.toHaveAttribute("open");
  });
});
