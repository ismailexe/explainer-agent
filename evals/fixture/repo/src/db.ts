export interface Database {
  run(sql: string, params: unknown[]): Promise<{ changes: number }>;
}
