import { describe, expect, it } from "vitest";
import { claim, settle } from "../src/ledger";
import { memoryDatabase } from "./memory-database";

describe("ledger", () => {
  it("claims a webhook id once", async () => {
    const db = memoryDatabase();
    expect(await claim(db, "wh-1")).toBe(true);
    expect(await claim(db, "wh-1")).toBe(false);
  });

  it("settles a claimed id", async () => {
    const db = memoryDatabase();
    await claim(db, "wh-2");
    await settle(db, "wh-2");
    expect(db.state("wh-2")).toBe("settled");
  });
});
