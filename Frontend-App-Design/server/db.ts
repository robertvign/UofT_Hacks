import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import * as schema from "@shared/schema";

const { Pool } = pg;

// In frontend-only mode, we don't need a real DB connection.
// We use a dummy connection string to satisfy the library requirements.
const connectionString = process.env.DATABASE_URL || "postgres://mock:mock@localhost:5432/mock";

export const pool = new Pool({ connectionString });
export const db = drizzle(pool, { schema });
