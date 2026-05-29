'use client';

import { useState } from 'react';
import { Moon, Palette, Sun } from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';

const tabs = [{ key: 'appearance', label: 'Appearance', icon: Palette }];

export function SettingsTab() {
  const { theme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState('appearance');

  return (
    <div className="grid grid-cols-4 gap-6">
      <div className="col-span-1">
        <div className="rounded-lg bg-card border border-border overflow-hidden sticky top-4">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`w-full flex items-center gap-3 px-4 py-3.5 text-sm font-medium transition-all border-l-2 ${
                activeTab === key
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`}
            >
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
      </div>

      <div className="col-span-3 space-y-5">
        {activeTab === 'appearance' && (
          <div className="rounded-lg bg-card border border-border p-6 space-y-4">
            <h3 className="text-sm font-semibold text-foreground">
              Appearance
            </h3>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-foreground">Theme</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Switch between light and dark appearance
                </div>
              </div>
              <div className="flex rounded-md border border-border overflow-hidden">
                <button
                  onClick={() => setTheme('light')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all ${
                    theme === 'light'
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                  }`}
                >
                  <Sun size={13} /> Light
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border-l border-border transition-all ${
                    theme === 'dark'
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                  }`}
                >
                  <Moon size={13} /> Dark
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
