import React from 'react';
import { 
  FileUp, Save, Undo2, Redo2, Copy, ClipboardPaste, Trash2, 
  PlusCircle, FileType, ZoomIn, ZoomOut, Maximize 
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { OpenFile, SaveFile, SaveFileDirect } from '../../wailsjs/go/main/App';
import { processPDF } from '../lib/pdfProcessor';

export const Header: React.FC = () => {
  const { 
    pdfFile, elements, setPdfFile, undo, redo, 
    zoom, setZoom, removeElement, selectedId, pageDimensions 
  } = useStore();

  const handleOpen = async () => {
    console.log('Botón abrir clicado');
    try {
      const file = await OpenFile();
      console.log('Respuesta de OpenFile:', file ? 'Archivo recibido' : 'Cancelado');
      if (file) {
        setPdfFile(file);
      }
    } catch (err) {
      console.error('Error al abrir archivo:', err);
    }
  };

  const handleSave = async () => {
    if (!pdfFile || pageDimensions.length === 0) return;
    try {
      const processedBase64 = await processPDF(pdfFile.data, elements, pageDimensions);
      if (pdfFile.path) {
        await SaveFileDirect(pdfFile.path, processedBase64);
        alert('Archivo guardado correctamente');
      } else {
        handleSaveAs();
      }
    } catch (err) {
      console.error('Error saving:', err);
      alert('Error al guardar: ' + err);
    }
  };

  const handleSaveAs = async () => {
    if (!pdfFile || pageDimensions.length === 0) return;
    try {
      const processedBase64 = await processPDF(pdfFile.data, elements, pageDimensions);
      const newPath = await SaveFile(pdfFile.name.replace('.pdf', '_edited.pdf'), processedBase64);
      if (newPath) {
        setPdfFile({ ...pdfFile, path: newPath });
        alert('Archivo guardado como: ' + newPath);
      }
    } catch (err) {
      console.error('Error saving as:', err);
      alert('Error al guardar como: ' + err);
    }
  };

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-4 z-50">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className="bg-blue-600 p-1.5 rounded-lg">
            <FileType className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg text-slate-800">PDFormer</span>
        </div>

        <nav className="flex items-center gap-1">
          <button onClick={handleOpen} className="px-3 py-1.5 rounded-md hover:bg-slate-100 text-sm font-medium transition-colors flex items-center gap-2" title="Abrir PDF (Ctrl+O)">
            <FileUp className="w-4 h-4" /> Archivo
          </button>
          <button onClick={handleSave} className="px-3 py-1.5 rounded-md hover:bg-slate-100 text-sm font-medium transition-colors flex items-center gap-2" title="Guardar cambios (Ctrl+S)">
            <Save className="w-4 h-4" /> Guardar
          </button>
          <button onClick={handleSaveAs} className="px-3 py-1.5 rounded-md hover:bg-slate-100 text-sm font-medium transition-colors flex items-center gap-2" title="Guardar como... (Ctrl+Shift+S)">
            <Maximize className="w-4 h-4" /> Guardar como
          </button>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <div className="bg-slate-100 p-1 rounded-lg flex items-center gap-1">
          <button onClick={undo} className="p-1.5 hover:bg-white rounded-md transition-shadow">
            <Undo2 className="w-4 h-4 text-slate-600" />
          </button>
          <button onClick={redo} className="p-1.5 hover:bg-white rounded-md transition-shadow">
            <Redo2 className="w-4 h-4 text-slate-600" />
          </button>
        </div>

        <div className="h-6 w-[1px] bg-slate-200" />

        <div className="flex items-center gap-1">
          <button className="p-1.5 hover:bg-slate-100 rounded-md transition-colors">
            <Copy className="w-4 h-4 text-slate-600" />
          </button>
          <button className="p-1.5 hover:bg-slate-100 rounded-md transition-colors">
            <ClipboardPaste className="w-4 h-4 text-slate-600" />
          </button>
          <button 
            onClick={() => selectedId && removeElement(selectedId)}
            className="p-1.5 hover:bg-red-50 rounded-md transition-colors"
          >
            <Trash2 className="w-4 h-4 text-red-500" />
          </button>
        </div>

        <div className="h-6 w-[1px] bg-slate-200" />

        <button className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-blue-700 transition-colors shadow-sm">
          <PlusCircle className="w-4 h-4" /> Añadir Página
        </button>
      </div>
    </header>
  );
};
