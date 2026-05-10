import { describe, it, expect } from "vitest";
import { classifyConfidence } from "./geocode";

describe("classifyConfidence", () => {
  it("rooftop when relevance ≥ 0.9 and address type", () => {
    expect(
      classifyConfidence({ relevance: 0.95, place_type: ["address"] }),
    ).toBe("rooftop");
  });
  it("rooftop when match_code.exact_match", () => {
    expect(
      classifyConfidence({
        relevance: 0.92,
        place_type: ["place"],
        properties: { match_code: { exact_match: true } },
      }),
    ).toBe("rooftop");
  });
  it("street for mid-relevance addresses", () => {
    expect(classifyConfidence({ relevance: 0.8, place_type: ["address"] })).toBe(
      "street",
    );
  });
  it("postcode for low-relevance / postcode-type", () => {
    expect(classifyConfidence({ relevance: 0.55, place_type: ["postcode"] })).toBe(
      "postcode",
    );
  });
  it("failed when relevance very low and no useful type", () => {
    expect(classifyConfidence({ relevance: 0.2, place_type: ["region"] })).toBe(
      "failed",
    );
  });
});
