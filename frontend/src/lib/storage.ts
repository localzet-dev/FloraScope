// В браузере храним только выбор пользователя. Результаты и прогресс берём из API.
export function readStored<T>(key: string, fallback: T): T {
  try {
    const value = JSON.parse(
      localStorage.getItem(`florascope:${key}`) ?? "null",
    );
    return value !== null &&
      typeof value === typeof fallback &&
      Array.isArray(value) === Array.isArray(fallback)
      ? value
      : fallback;
  } catch {
    return fallback;
  }
}
export function writeStored<T>(key: string, value: T) {
  try {
    localStorage.setItem(`florascope:${key}`, JSON.stringify(value));
  } catch {
    // Запрет storage не должен мешать запускать анализ.
  }
}
