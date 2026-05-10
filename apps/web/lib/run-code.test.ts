import { describe, it, expect } from "vitest";
import { decodeRunCode, DAY_TUE, DAY_THU, DAY_FRI } from "./run-code";

describe("decodeRunCode", () => {
  it("decodes 'WP0' as White Tue, Pink Thu, no Fri", () => {
    const d = decodeRunCode("'WP0'");
    expect(d.unparseable).toBe(false);
    expect(d.isMailOrder).toBe(false);
    expect(d.byDay[DAY_TUE]).toBe("White");
    expect(d.byDay[DAY_THU]).toBe("Pink");
    expect(d.byDay[DAY_FRI]).toBeNull();
  });

  it("treats 'O' and '0' identically (no van)", () => {
    expect(decodeRunCode("'GOG'").byDay[DAY_THU]).toBeNull();
    expect(decodeRunCode("'GO0'").byDay[DAY_THU]).toBeNull();
    expect(decodeRunCode("'GO0'").byDay[DAY_FRI]).toBeNull();
  });

  it("flags ~NR as mail order, not a van assignment", () => {
    const d = decodeRunCode("'~NR'");
    expect(d.isMailOrder).toBe(true);
    expect(d.unparseable).toBe(false);
    expect(d.byDay[DAY_TUE]).toBeNull();
  });

  it("flags unparseable codes with non-colour letters ('5ME', 'MMR')", () => {
    expect(decodeRunCode("'5ME'").unparseable).toBe(true);
    expect(decodeRunCode("'MMR'").unparseable).toBe(true);
  });

  it("flags wrong-length codes unparseable", () => {
    expect(decodeRunCode("'W'").unparseable).toBe(true);
    expect(decodeRunCode("'WPRR'").unparseable).toBe(true);
    expect(decodeRunCode("").unparseable).toBe(true);
  });
});
