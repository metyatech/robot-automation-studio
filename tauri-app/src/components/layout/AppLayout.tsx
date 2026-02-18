import type { ReactNode } from "react";

interface AppLayoutProps {
  menuBar: ReactNode;
  toolBar: ReactNode;
  leftPanel: ReactNode;
  rightPanel: ReactNode;
  logPanel: ReactNode;
  statusBar: ReactNode;
}

export function AppLayout({
  menuBar,
  toolBar,
  leftPanel,
  rightPanel,
  logPanel,
  statusBar,
}: AppLayoutProps) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      {/* Menu bar */}
      {menuBar}

      {/* Toolbar */}
      {toolBar}

      {/* Main content: left panel + right panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel (step list) */}
        <div className="w-[300px] min-w-[200px] shrink-0 border-r border-border overflow-hidden">
          {leftPanel}
        </div>

        {/* Right panel (editor tabs) */}
        <div className="flex-1 overflow-hidden">{rightPanel}</div>
      </div>

      {/* Log panel (collapsible) */}
      {logPanel}

      {/* Status bar */}
      {statusBar}
    </div>
  );
}
