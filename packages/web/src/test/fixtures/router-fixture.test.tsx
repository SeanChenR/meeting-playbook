import { describe, expect, test } from "bun:test";
import { renderWithRouter } from "./router";

describe("renderWithRouter fixture", () => {
  test("renders the supplied element inside a router context", async () => {
    const { getByTestId } = await renderWithRouter(<div data-testid="probe">hi</div>);
    expect(getByTestId("probe").textContent).toBe("hi");
  });

  test("respects initialEntries — router lands on the requested path", async () => {
    const { router } = await renderWithRouter(<div />, {
      initialEntries: ["/some-path"],
      path: "/some-path",
    });
    expect(router.state.location.pathname).toBe("/some-path");
  });
});
