import { useEffect, useState } from "react";
import { readStored, writeStored } from "./storage";
export function useStoredState<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => readStored(key, fallback));
  useEffect(() => writeStored(key, value), [key, value]);
  return [value, setValue] as const;
}
