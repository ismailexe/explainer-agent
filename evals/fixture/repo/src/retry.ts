// Exponential backoff: 0.5s, 1s, 2s, 4s between at most 5 attempts (D-06).
export async function withRetry<T>(work: () => Promise<T>, attempts = 5): Promise<T> {
  let delay = 500;
  for (let attempt = 1; ; attempt++) {
    try {
      return await work();
    } catch (error) {
      if (attempt >= attempts) throw error;
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay *= 2;
    }
  }
}
