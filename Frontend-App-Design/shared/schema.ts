import { pgTable, text, serial, integer, boolean } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

export const songs = pgTable("songs", {
  id: serial("id").primaryKey(),
  title: text("title").notNull(),
  artist: text("artist"),
  language: text("language").notNull(),
  genre: text("genre"),
  coverUrl: text("cover_url"),
  progress: integer("progress").default(0), // 0-100
  isFavorite: boolean("is_favorite").default(false),
});

export const insertSongSchema = createInsertSchema(songs).pick({
  title: true,
  artist: true,
  language: true,
  genre: true,
  coverUrl: true,
  progress: true,
  isFavorite: true,
});

export type Song = typeof songs.$inferSelect;
export type InsertSong = z.infer<typeof insertSongSchema>;
