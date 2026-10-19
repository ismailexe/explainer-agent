// Exponential backoff with full jitter: a random wait of up to 0.5s, 1s, 2s, 4s
// between at most 5 attempts, so retries from many relays do not line up (D-07).
export async function withRetry<T>(work: () => Promise<T>, attempts = 5): Promise<T> {
  let ceiling = 500;
  for (let attempt = 1; ; attempt++) {
    try {
      return await work();
    } catch (error) {
      if (attempt >= attempts) throw error;
      await new Promise((resolve) => setTimeout(resolve, Math.random() * ceiling));
      ceiling *= 2;
    }
  }
}
