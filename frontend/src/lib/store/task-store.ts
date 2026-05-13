import { create } from "zustand";

interface QuickAddState {
  isOpen: boolean;
  initialStatus: string;
  open: (initialStatus?: string) => void;
  close: () => void;
}

export const useQuickAddTask = create<QuickAddState>((set) => ({
  isOpen: false,
  initialStatus: "pending",
  open: (initialStatus = "pending") =>
    set({ isOpen: true, initialStatus }),
  close: () => set({ isOpen: false }),
}));