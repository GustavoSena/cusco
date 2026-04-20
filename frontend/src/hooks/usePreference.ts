import { useCallback, useEffect, useState } from "react";

/**
 * Persist a boolean UI preference in `localStorage` and keep it in sync
 * with React state. Falls back to `defaultValue` when the storage entry
 * is absent, corrupt, or unavailable (private mode / quota errors).
 *
 * Also listens to the `storage` event, so a preference toggled in one
 * tab propagates to every other open tab without needing a reload —
 * a detail users notice the first time they open the app in two tabs.
 */
export function usePreference(
  key: string,
  defaultValue: boolean,
): [boolean, (next: boolean) => void] {
  const storageKey = `cusco.pref.${key}`;

  const read = useCallback((): boolean => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw === null) return defaultValue;
      return raw === "1" || raw === "true";
    } catch {
      return defaultValue;
    }
  }, [storageKey, defaultValue]);

  const [value, setValueState] = useState<boolean>(read);

  // Cross-tab sync: the `storage` event fires in every OTHER tab when one
  // of them writes. Without this, a user toggling the switch in tab A
  // would see tab B still reflect the old state until a reload.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== storageKey) return;
      setValueState(read());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [storageKey, read]);

  const setValue = useCallback(
    (next: boolean) => {
      setValueState(next);
      try {
        localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        // Private mode / quota — best effort, state still updates in-memory.
      }
    },
    [storageKey],
  );

  return [value, setValue];
}
