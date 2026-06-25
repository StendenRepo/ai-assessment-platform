'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import {
  getTeacherPreferences,
  updateTeacherPreferences,
} from '@/lib/api/teacherPreferences';
import { useTheme } from './ThemeContext';

const TeacherPreferenceContext = createContext(null);

export function TeacherPreferenceProvider({ children }) {
  const { setTheme } = useTheme();
  const [preferences, setPreferences] = useState({
    theme: 'light',
    date_format: 'DD-MM-YYYY',
    language: 'en',
  });
  const [loading, setLoading] = useState(true);

  const loadPreferences = useCallback(async () => {
    try {
      const data = await getTeacherPreferences();
      // Convert snake_case from API to camelCase for frontend
      setPreferences({
        theme: data.theme,
        date_format: data.date_format,
        language: data.language,
      });
      // Apply theme immediately
      setTheme(data.theme);
    } catch (error) {
      // Silently fail - preferences not found or not authenticated
      // Use defaults already set in state
    } finally {
      setLoading(false);
    }
  }, [setTheme]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const updatePreference = useCallback(
    async (updates) => {
      try {
        // Optimistic update
        setPreferences((prev) => ({ ...prev, ...updates }));

        // Apply theme change immediately if updating theme
        if (updates.theme) {
          setTheme(updates.theme);
        }

        // Send to server
        const payload = {};
        if (updates.theme) payload.theme = updates.theme;
        if (updates.date_format) payload.date_format = updates.date_format;
        if (updates.language) payload.language = updates.language;

        const response = await updateTeacherPreferences(payload);

        // Update with server response
        setPreferences({
          theme: response.theme,
          date_format: response.date_format,
          language: response.language,
        });
      } catch (error) {
        // Revert on error
        await loadPreferences();
      }
    },
    [setTheme, loadPreferences]
  );

  const value = {
    preferences,
    loading,
    updatePreference,
  };

  return (
    <TeacherPreferenceContext.Provider value={value}>
      {children}
    </TeacherPreferenceContext.Provider>
  );
}

export function useTeacherPreference() {
  const context = useContext(TeacherPreferenceContext);
  if (!context) {
    throw new Error(
      'useTeacherPreference must be used within TeacherPreferenceProvider'
    );
  }
  return context;
}
