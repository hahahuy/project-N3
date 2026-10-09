import { describe, expect, it } from "vitest";
import { apiUrl } from "./api";

describe("API boundary", () => {
  it("keeps browser requests under the local API prefix", () => {
    expect(apiUrl("/scenarios")).toMatch(/\/api\/scenarios$/);
  });
});
