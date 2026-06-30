import React, { useState } from 'react';
import { Rnd } from 'react-rnd';
import { X, Maximize2, Minus } from 'lucide-react';

const FloatingWindow = ({ id, title, children, onClose, defaultSize = { width: 800, height: 600 }, zIndex, bringToFront }) => {
  const [isMaximized, setIsMaximized] = useState(false);
  const [position, setPosition] = useState({ x: window.innerWidth / 2 - defaultSize.width / 2, y: 50 });
  const [size, setSize] = useState(defaultSize);

  const toggleMaximize = () => {
    setIsMaximized(!isMaximized);
  };

  return (
    <Rnd
      size={isMaximized ? { width: '100vw', height: '100vh' } : size}
      position={isMaximized ? { x: 0, y: 0 } : position}
      onDragStop={(e, d) => !isMaximized && setPosition({ x: d.x, y: d.y })}
      onResizeStop={(e, direction, ref, delta, position) => {
        if (!isMaximized) {
          setSize({ width: ref.style.width, height: ref.style.height });
          setPosition(position);
        }
      }}
      disableDragging={isMaximized}
      enableResizing={!isMaximized}
      minWidth={400}
      minHeight={300}
      bounds="window"
      dragHandleClassName="window-header"
      style={{ zIndex, display: 'flex', flexDirection: 'column' }}
      className="bg-white dark:bg-[#131722] rounded-xl shadow-2xl border border-gray-200 dark:border-gray-800 overflow-hidden flex flex-col transition-shadow duration-200"
      onMouseDownCapture={bringToFront}
    >
      {/* Window Header */}
      <div 
        className="window-header h-12 flex-none bg-gray-50 dark:bg-[#1e293b] border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-4 cursor-grab active:cursor-grabbing"
      >
        <div className="font-bold text-gray-800 dark:text-gray-200 flex items-center space-x-2">
          {title}
        </div>
        <div className="flex items-center space-x-2">
          <button 
            onClick={toggleMaximize}
            className="p-1.5 rounded text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <Maximize2 size={14} />
          </button>
          <button 
            onClick={onClose}
            className="p-1.5 rounded text-gray-500 hover:bg-red-500 hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Window Body */}
      <div className="flex-1 overflow-auto bg-white dark:bg-[#131722]">
        {children}
      </div>
    </Rnd>
  );
};

export default FloatingWindow;
