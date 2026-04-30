import React, { useState, useRef } from 'react';
import { useStore, PDFElement } from '../store/useStore';
import { Element } from './Element';
import { v4 as uuidv4 } from 'uuid';

interface DrawingLayerProps {
  pageIndex: number;
  width: number;
  height: number;
}

export const DrawingLayer: React.FC<DrawingLayerProps> = ({ pageIndex, width, height }) => {
  const { elements, addElement, zoom, snapEnabled, activeTool, guides } = useStore();
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  
  const containerRef = useRef<HTMLDivElement>(null);

  const getMousePos = (e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: (e.clientX - rect.left) / zoom,
      y: (e.clientY - rect.top) / zoom
    };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click
    // If clicking on an element, don't start drawing (this is handled by element event propagation)
    if ((e.target as HTMLElement).closest('.pdf-element')) return;

    const pos = getMousePos(e);
    setIsDrawing(true);
    setStartPos(pos);
    setCurrentRect({ x: pos.x, y: pos.y, w: 0, h: 0 });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDrawing) return;
    const pos = getMousePos(e);
    
    setCurrentRect({
      x: Math.min(startPos.x, pos.x),
      y: Math.min(startPos.y, pos.y),
      w: Math.abs(pos.x - startPos.x),
      h: Math.abs(pos.y - startPos.y)
    });
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);

    if (currentRect && currentRect.w > 5 && currentRect.h > 5) {
      const newElement: PDFElement = {
        id: uuidv4(),
        type: activeTool as any,
        x: currentRect.x,
        y: currentRect.y,
        width: currentRect.w,
        height: currentRect.h,
        page: pageIndex,
        hasBorder: true
      };
      addElement(newElement);
    }
    setCurrentRect(null);
  };

  return (
    <div 
      ref={containerRef}
      className={`absolute inset-0 z-10 overflow-hidden ${activeTool === 'cursor' ? 'cursor-default' : 'cursor-crosshair'}`}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {elements.filter(el => el.page === pageIndex).map(el => (
        <Element key={el.id} element={el} containerWidth={width} containerHeight={height} />
      ))}

      {isDrawing && currentRect && (
        <div 
          className="absolute border-2 border-blue-500 bg-blue-500/20 pointer-events-none"
          style={{
            left: currentRect.x * zoom,
            top: currentRect.y * zoom,
            width: currentRect.w * zoom,
            height: currentRect.h * zoom
          }}
        />
      )}

      {/* Snapping Guides */}
      {guides?.x !== undefined && (
        <div 
          className="absolute border-l border-dashed border-blue-500 z-40 pointer-events-none"
          style={{ left: guides.x * zoom, top: 0, bottom: 0 }}
        />
      )}
      {guides?.y !== undefined && (
        <div 
          className="absolute border-t border-dashed border-blue-500 z-40 pointer-events-none"
          style={{ top: guides.y * zoom, left: 0, right: 0 }}
        />
      )}
    </div>
  );
};
