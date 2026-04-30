import React, { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
// @ts-ignore
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.mjs?url';
import { useStore } from '../store/useStore';
import { DrawingLayer } from './DrawingLayer';

// Set up pdf.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

export const Canvas: React.FC = () => {
  const { pdfFile, zoom } = useStore();
  const [pages, setPages] = useState<string[]>([]);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!pdfFile) return;

    const loadPdf = async () => {
      const binaryString = atob(pdfFile.data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      
      const loadingTask = pdfjsLib.getDocument({ data: bytes });
      const pdf = await loadingTask.promise;
      const newPages = [];
      const newDims = [];

      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const viewport = page.getViewport({ scale: 2 }); // Render at 2x for quality
        
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d')!;
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        await page.render({ 
          canvasContext: context, 
          viewport,
          canvas: canvas as any
        }).promise;
        newPages.push(canvas.toDataURL());
        newDims.push({ width: viewport.width / 2, height: viewport.height / 2 });
      }

      setPages(newPages);
      setDimensions(newDims);
      useStore.getState().setPageDimensions(newDims);
    };

    loadPdf();
  }, [pdfFile]);

  if (!pdfFile) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-100">
        <div className="text-center">
          <div className="w-16 h-16 bg-white rounded-2xl shadow-sm flex items-center justify-center mx-auto mb-4">
            <Maximize className="w-8 h-8 text-slate-300" />
          </div>
          <h2 className="text-slate-400 font-medium">Suelta un PDF o ábrelo desde el menú</h2>
        </div>
      </div>
    );
  }

  return (
    <main ref={containerRef} className="flex-1 overflow-auto bg-slate-200 p-8 scroll-smooth">
      <div className="flex flex-col gap-8 items-center">
        {pages.map((pageData, index) => (
          <div 
            key={index} 
            className="relative shadow-2xl bg-white"
            style={{ 
              width: dimensions[index].width * zoom, 
              height: dimensions[index].height * zoom 
            }}
          >
            <img 
              src={pageData} 
              alt={`Página ${index + 1}`} 
              className="w-full h-full select-none"
              draggable={false}
            />
            <DrawingLayer pageIndex={index} width={dimensions[index].width} height={dimensions[index].height} />
          </div>
        ))}
      </div>
    </main>
  );
};

import { Maximize } from 'lucide-react';
