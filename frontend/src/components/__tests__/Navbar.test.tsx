import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import Navbar from "../Navbar";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchGeocode: vi.fn(),
}));

describe("Navbar location autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders search input with current query and placeholder", () => {
    render(<Navbar onSearch={vi.fn()} isLoading={false} currentQuery="Manali" />);
    const input = screen.getByRole("combobox") as HTMLInputElement;
    expect(input.value).toBe("Manali");
    expect(input.placeholder).toContain("Search any destination");
  });

  it("fetches and displays suggestions when typing query", async () => {
    const mockCandidates = [
      {
        display_name: "Paris, Île-de-France, France",
        lat: 48.8566,
        lon: 2.3522,
        bbox: [2.2, 48.8, 2.4, 48.9] as [number, number, number, number],
        type: "city",
        state: "Île-de-France",
        district: "Paris",
        country: "France",
        is_in_india: false,
      },
    ];

    vi.mocked(api.fetchGeocode).mockResolvedValue(mockCandidates);

    render(<Navbar onSearch={vi.fn()} isLoading={false} currentQuery="" />);
    const input = screen.getByRole("combobox");

    await act(async () => {
      fireEvent.change(input, { target: { value: "Pari" } });
      await new Promise((r) => setTimeout(r, 350));
    });

    expect(api.fetchGeocode).toHaveBeenCalledWith("Pari");

    const listbox = screen.getByRole("listbox");
    expect(listbox).toBeDefined();
    expect(screen.getByRole("option")).toBeDefined();
  });

  it("selects suggestion on click and triggers onSearch", async () => {
    const onSearchMock = vi.fn();
    const mockCandidates = [
      {
        display_name: "Kathmandu, Bagmati, Nepal",
        lat: 27.7172,
        lon: 85.324,
        bbox: [85.2, 27.6, 85.4, 27.8] as [number, number, number, number],
        type: "city",
        state: "Bagmati",
        district: "Kathmandu",
        country: "Nepal",
        is_in_india: false,
      },
    ];

    vi.mocked(api.fetchGeocode).mockResolvedValue(mockCandidates);

    render(<Navbar onSearch={onSearchMock} isLoading={false} currentQuery="" />);
    const input = screen.getByRole("combobox");

    await act(async () => {
      fireEvent.change(input, { target: { value: "Kath" } });
      await new Promise((r) => setTimeout(r, 350));
    });

    const option = screen.getByRole("option");
    expect(option).toBeDefined();
    await act(async () => {
      fireEvent.click(option);
    });

    expect(onSearchMock).toHaveBeenCalledWith("Kathmandu, Bagmati, Nepal");
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});
