import React from 'react';
import { 
  MousePointer2, Magnet, Type, Eraser, 
  TextCursorInput, AlignLeft, CheckSquare, 
  ChevronDownSquare, PenLine 
} from 'lucide-react';
import { useStore, ElementType } from '../store/useStore';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const Sidebar: React.FC = () => {
  const { snapEnabled, toggleSnap, activeTool, setActiveTool } = useStore();

  const tools = [
    { id: 'cursor', icon: MousePointer2, label: 'Cursor' },
    { id: 'snap', icon: Magnet, label: 'Guías Magnéticas', isToggle: true, active: snapEnabled, action: toggleSnap },
  ];

  const annotations = [
    { id: 'static_text', icon: Type, label: 'Texto Libre' },
    { id: 'whiteout', icon: Eraser, label: 'Típex' },
  ];

  const forms = [
    { id: 'text', icon: TextCursorInput, label: 'Texto' },
    { id: 'textarea', icon: AlignLeft, label: 'Texto Multilínea' },
    { id: 'checkbox', icon: CheckSquare, label: 'Checkbox' },
    { id: 'dropdown', icon: ChevronDownSquare, label: 'Desplegable' },
    { id: 'signature', icon: PenLine, label: 'Firma' },
  ];

  const ToolButton = ({ id, icon: Icon, label, isToggle, active, action }: any) => (
    <button
      onClick={() => isToggle ? action() : setActiveTool(id)}
      className={cn(
        "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all group",
        (isToggle ? active : activeTool === id)
          ? "bg-blue-50 text-blue-600"
          : "text-slate-600 hover:bg-slate-100"
      )}
      title={label}
    >
      <Icon className={cn(
        "w-5 h-5",
        (isToggle ? active : activeTool === id) ? "text-blue-600" : "text-slate-400 group-hover:text-slate-600"
      )} />
      <span>{label}</span>
    </button>
  );

  return (
    <aside className="w-64 bg-[#f8f9fc] border-r border-slate-200 flex flex-col p-4 gap-6 select-none">
      <section>
        <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Herramientas de Edición</h3>
        <div className="space-y-1">
          {tools.map(tool => <ToolButton key={tool.id} {...tool} />)}
        </div>
      </section>

      <div className="h-[1px] bg-slate-200" />

      <section>
        <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Anotación</h3>
        <div className="space-y-1">
          {annotations.map(tool => <ToolButton key={tool.id} {...tool} />)}
        </div>
      </section>

      <div className="h-[1px] bg-slate-200" />

      <section>
        <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Elementos de Formulario</h3>
        <div className="space-y-1">
          {forms.map(tool => <ToolButton key={tool.id} {...tool} />)}
        </div>
      </section>
      
      <div className="mt-auto">
        <div className="bg-blue-600/5 rounded-xl p-4 border border-blue-600/10">
          <p className="text-[11px] text-blue-700/70 font-medium leading-relaxed">
            Selecciona una herramienta y arrastra en el canvas para añadir elementos.
          </p>
        </div>
      </div>
    </aside>
  );
};
