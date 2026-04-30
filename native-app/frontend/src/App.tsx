import React from 'react';
import { Sidebar } from './components/Sidebar';
import { Canvas } from './components/Canvas';
import { Header } from './components/Header';
import { useStore } from './store/useStore';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

function App() {
  const { zoom, setZoom } = useStore();
  
  useKeyboardShortcuts();

  // Zoom controls (Ctrl + MouseWheel handled in Canvas or here)
  React.useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        setZoom(Math.min(Math.max(0.1, zoom + delta), 3));
      }
    };
    window.addEventListener('wheel', handleWheel, { passive: false });
    return () => window.removeEventListener('wheel', handleWheel);
  }, [zoom, setZoom]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#f8f9fc]">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <Canvas />
      </div>
      
      {/* Zoom / Status Bar */}
      <footer className="h-8 bg-white border-t border-slate-200 flex items-center justify-between px-4 text-[11px] text-slate-500 z-50">
        <div className="flex items-center gap-4">
          <span>Listo</span>
          <div className="w-[1px] h-3 bg-slate-200" />
          <span>Zoom: {Math.round(zoom * 100)}%</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom(zoom - 0.1)} className="hover:text-blue-600 transition-colors">Zoom Out</button>
          <input 
            type="range" 
            min="0.1" max="3" step="0.1" 
            value={zoom} 
            onChange={(e) => setZoom(parseFloat(e.target.value))}
            className="w-24 accent-blue-600"
          />
          <button onClick={() => setZoom(zoom + 0.1)} className="hover:text-blue-600 transition-colors">Zoom In</button>
        </div>
      </footer>
    </div>
  );
}

export default App;
