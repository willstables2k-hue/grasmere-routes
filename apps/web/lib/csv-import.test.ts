import { describe, it, expect } from "vitest";
import {
  parseCustomerCsv,
  parseDayGroup,
  parseUkDate,
  extractSoftWindow,
} from "./csv-import";

const HEADER = [
  "customer_name (do not edit)",
  "legal_entity_name (do not edit)",
  "business_tax_number (do not edit)",
  "delivery_address (do not edit)",
  "billing_address (do not edit)",
  "latest_delivery_date (do not edit)",
  "customer_code",
  "outbound_integration_customer_code",
  "active (Yes or No)",
  "pricing_level",
  "negotiated_prices_group",
  "show_only_negotiated_pricing (Yes or No)",
  "auto_assign_last_price_as_negotiated_price (Yes or No)",
  "show_rrp (Yes or No)",
  "require_external_reference (Yes or No)",
  "minimum_order_amounts_enabled (Yes or No)",
  "preserve_original_line_item_sequence_in_invoice_documents (Yes or No)",
  "discount",
  "rebate",
  "invoice_notes",
  "standing_picking_instructions",
  "delivery_date_message",
  "standing_delivery_instructions",
  "delivery_run_code",
  "delivery_run_position",
  "freight_rule",
  "delivery_fee_percentage",
  "minimum_order_amount_for_freight",
  "delivery_days_and_cut_off_times_group",
  "payment_term_days",
  "payment_term_option",
  "sales_rep",
  "internal_notes",
  "internal_customer_contact_notes",
  "automatically_charge_fuel_levy (Yes or No)",
  "charge_card (Yes or No)",
  "charge_customer_card_fee (Yes or No)",
  "visibility_groups (separated by '|')",
  "tags (separated by '|')",
  "agreement_id (do not edit)",
].join(",");

function row(values: Record<string, string>) {
  const cols = HEADER.split(",");
  return cols
    .map((c) => {
      const v = values[c] ?? "";
      // crude quoting: wrap if value contains a comma
      return v.includes(",") ? `"${v}"` : v;
    })
    .join(",");
}

describe("parseUkDate", () => {
  it("parses DD/MM/YYYY → ISO", () => {
    expect(parseUkDate("21/08/2025")).toBe("2025-08-21");
    expect(parseUkDate("1/5/2026")).toBe("2026-05-01");
  });
  it("returns null for blank or junk", () => {
    expect(parseUkDate("")).toBeNull();
    expect(parseUkDate("   ")).toBeNull();
    expect(parseUkDate("21-08-2025")).toBeNull();
  });
});

describe("parseDayGroup", () => {
  const cases: [string, number[] | null][] = [
    ["TUES THURS", [1, 3]],
    ["TUES FRI", [1, 4]],
    ["THURS", [3]],
    ["Default", [1, 3]],
    ["MON FRI", [0, 4]],
    ["MON TUES THURS FRI", [0, 1, 3, 4]],
    ["SAT", [5]],
    ["Cromer", null],
    ["", null],
    ["Vine house farm grasmere", null],
  ];
  for (const [input, expected] of cases) {
    it(`${JSON.stringify(input)} → ${JSON.stringify(expected)}`, () => {
      expect(parseDayGroup(input)).toEqual(expected);
    });
  }
});

describe("extractSoftWindow", () => {
  it("BETWEEN 7AM AND 9AM", () => {
    expect(extractSoftWindow("delivery BETWEEN 7AM AND 9AM please")).toEqual({
      start: "07:00",
      end: "09:00",
    });
  });
  it("before 1pm", () => {
    expect(extractSoftWindow("delivery before 1pm")).toEqual({ start: null, end: "13:00" });
  });
  it("9 and 10", () => {
    expect(extractSoftWindow("Delivery between 9 and 10 if poss")).toEqual({
      start: "09:00",
      end: "10:00",
    });
  });
  it("opening times 06:45 - 17:30", () => {
    expect(extractSoftWindow("Opening times: 06:45 - 17:30")).toEqual({
      start: "06:45",
      end: "17:30",
    });
  });
  it("returns nulls when nothing matches", () => {
    expect(extractSoftWindow("just leave it round the back")).toEqual({
      start: null,
      end: null,
    });
  });
});

describe("parseCustomerCsv — round trip", () => {
  it("parses one full row from the supplied CSV format", () => {
    const csv = [
      HEADER,
      row({
        "customer_name (do not edit)": "Abbots Ripton Village Stores",
        "legal_entity_name (do not edit)": "Abbots Ripton Village Stores",
        "delivery_address (do not edit)": "Station Road, Abbots Ripton, Huntingdon PE28 2PA",
        "billing_address (do not edit)": "Station Road, Abbots Ripton, Huntingdon PE28 2PA",
        "latest_delivery_date (do not edit)": "01/05/2026",
        customer_code: "'ABOTTRIP'",
        "active (Yes or No)": "Yes",
        pricing_level: "Level 1",
        invoice_notes: "Cheque/COD. Opening times: 06:45 - 17:30",
        standing_picking_instructions: "TUE: GREEN FRI: GREEN",
        standing_delivery_instructions: "Cheque/COD. Opening times: 06:45 - 17:30",
        delivery_run_code: "'GOG'",
        delivery_run_position: "28",
        delivery_days_and_cut_off_times_group: "TUES THURS",
        payment_term_days: "0",
        sales_rep: "James (Grasmere Farm)",
      }),
    ].join("\n");

    const { rows, errors } = parseCustomerCsv(csv);
    expect(errors).toEqual([]);
    expect(rows).toHaveLength(1);
    const r = rows[0]!;
    expect(r.customerCode).toBe("ABOTTRIP");
    expect(r.legacyRunCode).toBe("GOG");
    expect(r.legacyRunPosition).toBe(28);
    expect(r.preferredDays).toEqual([1, 3]);
    expect(r.isCod).toBe(true);
    expect(r.lastDeliveryDate).toBe("2026-05-01");
    expect(r.softWindowStart).toBe("06:45");
    expect(r.softWindowEnd).toBe("17:30");
    expect(r.active).toBe(true);
    expect(r.rawCsvRow["customer_code"]).toBe("'ABOTTRIP'");
  });

  it("flags rows whose day-group is freeform", () => {
    const csv = [
      HEADER,
      row({
        "customer_name (do not edit)": "Cromer Crab Co",
        customer_code: "'CROMER1'",
        "active (Yes or No)": "Yes",
        delivery_run_code: "'~NR'",
        delivery_days_and_cut_off_times_group: "Cromer",
      }),
    ].join("\n");
    const { rows } = parseCustomerCsv(csv);
    expect(rows[0]!.flaggedForReview).toBe(true);
    expect(rows[0]!.preferredDays).toBeNull();
  });

  it("emits an error for rows missing customer_code", () => {
    const csv = [
      HEADER,
      row({ "customer_name (do not edit)": "X" }),
    ].join("\n");
    const { rows, errors } = parseCustomerCsv(csv);
    expect(rows).toHaveLength(0);
    expect(errors[0]!.message).toMatch(/customer_code/);
  });
});
