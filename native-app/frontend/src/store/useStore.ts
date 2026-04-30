import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ElementType = 'whiteout' | 'static_text' | 'text' | 'textarea' | 'checkbox' | 'dropdown' | 'signature';

export interface PDFElement {
  id: string;
  type: ElementType;
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string;
  options?: string[];
  hasBorder?: boolean;
  page: number;
}

interface AppState {
  elements: PDFElement[];
  selectedId: string | null;
  activeTool: string;
  zoom: number;
  pdfFile: { name: string; data: string; path: string } | null;
  pageDimensions: { width: number; height: number }[];
  snapEnabled: boolean;
  guides: { x?: number; y?: number } | null;
  
  // History
  history: PDFElement[][];
  historyIndex: number;

  // Actions
  setPdfFile: (file: { name: string; data: string; path: string } | null) => void;
  setPageDimensions: (dims: { width: number; height: number }[]) => void;
  setActiveTool: (tool: string) => void;
  setZoom: (zoom: number) => void;
  setSelectedId: (id: string | null) => void;
  setGuides: (guides: { x?: number; y?: number } | null) => void;
  addElement: (element: PDFElement) => void;
  updateElement: (id: string, updates: Partial<PDFElement>) => void;
  removeElement: (id: string) => void;
  toggleSnap: () => void;
  
  undo: () => void;
  redo: () => void;
  saveHistory: () => void;
}

export const useStore = create<AppState>((set, get) => ({
  elements: [],
  selectedId: null,
  activeTool: 'cursor',
  zoom: 1.0,
  pdfFile: null,
  pageDimensions: [],
  snapEnabled: true,
  guides: null,
  history: [[]],
  historyIndex: 0,

  setPdfFile: (file) => set({ pdfFile: file, elements: [], history: [[]], historyIndex: 0 }),
  setPageDimensions: (dims) => set({ pageDimensions: dims }),
  setActiveTool: (tool) => set({ activeTool: tool }),
  setZoom: (zoom) => set({ zoom }),
  setSelectedId: (id) => set({ selectedId: id }),
  setGuides: (guides) => set({ guides }),
  
  addElement: (element) => {
    const newElements = [...get().elements, element];
    set({ elements: newElements });
    get().saveHistory();
  },

  updateElement: (id, updates) => {
    const newElements = get().elements.map((el) => 
      el.id === id ? { ...el, ...updates } : el
    );
    set({ elements: newElements });
  },

  removeElement: (id) => {
    const newElements = get().elements.filter((el) => el.id !== id);
    set({ elements: newElements, selectedId: null });
    get().saveHistory();
  },

  toggleSnap: () => set((state) => ({ snapEnabled: !state.snapEnabled })),

  saveHistory: () => {
    const { elements, history, historyIndex } = get();
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(JSON.parse(JSON.stringify(elements)));
    set({ 
      history: newHistory, 
      historyIndex: newHistory.length - 1 
    });
  },

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      set({ 
        elements: JSON.parse(JSON.stringify(history[historyIndex - 1])), 
        historyIndex: historyIndex - 1 
      });
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      set({ 
        elements: JSON.parse(JSON.stringify(history[historyIndex + 1])), 
        historyIndex: historyIndex + 1 
      });
    }
  },
}));
