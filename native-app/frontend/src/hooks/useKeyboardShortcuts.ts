import { useEffect } from 'react';
import { useStore } from '../store/useStore';
import { v4 as uuidv4 } from 'uuid';

export const useKeyboardShortcuts = () => {
  const { 
    undo, redo, elements, selectedId, 
    removeElement, addElement, updateElement, zoom 
  } = useStore();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Undo / Redo
      if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        undo();
      }
      if (e.ctrlKey && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) {
        e.preventDefault();
        redo();
      }

      // Delete
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedId && (e.target as HTMLElement).tagName !== 'INPUT' && (e.target as HTMLElement).tagName !== 'TEXTAREA') {
          removeElement(selectedId);
        }
      }

      // Copy / Paste (Basic implementation)
      if (e.ctrlKey && e.key === 'c') {
        // Handle copy logic if needed (elements are already in store)
      }

      // Arrows for movement
      if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
        if (selectedId && (e.target as HTMLElement).tagName !== 'INPUT') {
          e.preventDefault();
          const step = e.shiftKey ? 10 : 1;
          const el = elements.find(item => item.id === selectedId);
          if (el) {
            let dx = 0, dy = 0;
            if (e.key === 'ArrowLeft') dx = -step;
            if (e.key === 'ArrowRight') dx = step;
            if (e.key === 'ArrowUp') dy = -step;
            if (e.key === 'ArrowDown') dy = step;
            updateElement(selectedId, { x: el.x + dx, y: el.y + dy });
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, selectedId, elements, removeElement, updateElement]);
};
