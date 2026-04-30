import React, { useState, useCallback } from 'react';
import { useStore, PDFElement } from '../store/useStore';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ElementProps {
  element: PDFElement;
  containerWidth: number;
  containerHeight: number;
}

export const Element: React.FC<ElementProps> = ({ element, containerWidth, containerHeight }) => {
  const { selectedId, setSelectedId, updateElement, zoom, snapEnabled, elements } = useStore();
  const isSelected = selectedId === element.id;

  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState<string | null>(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (e.shiftKey) {
      // Clone element
      const id = uuidv4();
      const clone: PDFElement = { ...element, id };
      useStore.getState().addElement(clone);
      setSelectedId(id);
    } else {
      setSelectedId(element.id);
    }
    
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleResizeStart = (e: React.MouseEvent, handle: string) => {
    e.stopPropagation();
    setIsResizing(handle);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging && !isResizing) return;

    const dx = (e.clientX - dragStart.x) / zoom;
    const dy = (e.clientY - dragStart.y) / zoom;

    if (isDragging) {
      if (e.shiftKey && !isDragging) {
        // Simple cloning logic: if shift is held at the START of drag
        // However, it's better handled in MouseDown for cleaner logic
      }

      let newX = element.x + dx;
      let newY = element.y + dy;

      // Snapping logic
      if (snapEnabled) {
        const threshold = 5;
        let guideX: number | undefined;
        let guideY: number | undefined;

        for (const el of elements) {
          if (el.id === element.id || el.page !== element.page) continue;
          
          // Snap edges (left, right, center X)
          const myCenterX = newX + element.width / 2;
          const elCenterX = el.x + el.width / 2;

          if (Math.abs(newX - el.x) < threshold) { newX = el.x; guideX = el.x; }
          else if (Math.abs((newX + element.width) - (el.x + el.width)) < threshold) { newX = el.x + el.width - element.width; guideX = el.x + el.width; }
          else if (Math.abs(myCenterX - elCenterX) < threshold) { newX = elCenterX - element.width / 2; guideX = elCenterX; }

          // Snap edges (top, bottom, center Y)
          const myCenterY = newY + element.height / 2;
          const elCenterY = el.y + el.height / 2;

          if (Math.abs(newY - el.y) < threshold) { newY = el.y; guideY = el.y; }
          else if (Math.abs((newY + element.height) - (el.y + el.height)) < threshold) { newY = el.y + el.height - element.height; guideY = el.y + el.height; }
          else if (Math.abs(myCenterY - elCenterY) < threshold) { newY = elCenterY - element.height / 2; guideY = elCenterY; }
        }
        
        useStore.getState().setGuides(guideX || guideY ? { x: guideX, y: guideY } : null);
      }

      updateElement(element.id, { x: newX, y: newY });
      setDragStart({ x: e.clientX, y: e.clientY });
    }

    if (isResizing) {
      let { x, y, width, height } = element;
      
      if (isResizing.includes('r')) width += dx;
      if (isResizing.includes('l')) { x += dx; width -= dx; }
      if (isResizing.includes('b')) height += dy;
      if (isResizing.includes('t')) { y += dy; height -= dy; }

      updateElement(element.id, { x, y, width, height });
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  }, [isDragging, isResizing, dragStart, element, zoom, snapEnabled, elements, updateElement]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setIsResizing(null);
    useStore.getState().setGuides(null);
  }, []);

  React.useEffect(() => {
    if (isDragging || isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, isResizing, handleMouseMove, handleMouseUp]);

  const renderHandles = () => {
    if (!isSelected) return null;
    const handles = ['tl', 'tc', 'tr', 'lc', 'rc', 'bl', 'bc', 'br'];
    return handles.map(h => (
      <div
        key={h}
        className={cn(
          "absolute w-2.5 h-2.5 bg-blue-600 border border-white rounded-sm z-20 cursor-pointer",
          h === 'tl' && "-top-1.5 -left-1.5 cursor-nwse-resize",
          h === 'tc' && "-top-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize",
          h === 'tr' && "-top-1.5 -right-1.5 cursor-nesw-resize",
          h === 'lc' && "top-1/2 -left-1.5 -translate-y-1/2 cursor-ew-resize",
          h === 'rc' && "top-1/2 -right-1.5 -translate-y-1/2 cursor-ew-resize",
          h === 'bl' && "-bottom-1.5 -left-1.5 cursor-nesw-resize",
          h === 'bc' && "-bottom-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize",
          h === 'br' && "-bottom-1.5 -right-1.5 cursor-nwse-resize",
        )}
        onMouseDown={(e) => handleResizeStart(e, h)}
      />
    ));
  };

  const getStyle = () => {
    const baseStyle = {
      left: element.x * zoom,
      top: element.y * zoom,
      width: element.width * zoom,
      height: element.height * zoom,
    };

    switch (element.type) {
      case 'whiteout': return { ...baseStyle, backgroundColor: '#ffffff' };
      case 'signature': return { ...baseStyle, backgroundColor: 'rgba(255, 235, 156, 0.6)' };
      default: return { ...baseStyle, backgroundColor: 'rgba(219, 234, 254, 0.6)' };
    }
  };

  return (
    <div
      className={cn(
        "absolute pdf-element group select-none",
        isSelected ? "ring-2 ring-blue-500 z-30" : "hover:ring-1 hover:ring-blue-300 z-20",
        element.hasBorder && "border border-blue-600"
      )}
      style={getStyle()}
      onMouseDown={handleMouseDown}
    >
      {renderHandles()}
      {element.type === 'static_text' && (
        <div className="p-1 text-[11px] overflow-hidden break-words text-slate-800">
          {element.text || 'Texto libre...'}
        </div>
      )}
      {element.type === 'signature' && (
        <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
          <PenLine className="w-1/2 h-1/2" />
        </div>
      )}
    </div>
  );
};

import { PenLine } from 'lucide-react';
