import { createContext, useContext } from 'react';

const TooltipContext = createContext({});

export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return (
    <TooltipContext.Provider value={{}}>
      {children}
    </TooltipContext.Provider>
  );
}